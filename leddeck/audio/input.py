"""Entree audio : capture micro (ou ligne) et livraison des blocs a l'analyse.

Le flux audio a son propre thread, fourni par PortAudio. Le callback doit rester
tres court : il ne fait que convertir en mono et passer le bloc a l'analyseur.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from ..i18n import tr
import sounddevice as sd

SAMPLERATE = 44100
BLOCKSIZE = 512           # 11,6 ms a 44,1 kHz : assez fin pour caler un beat


@dataclass
class DeviceInfo:
    index: int
    name: str
    channels: int
    samplerate: float
    latency_ms: float
    default: bool = False

    def __str__(self) -> str:
        mark = " (defaut)" if self.default else ""
        return (tr("[{}] {} — {} canal/aux, {:.0f} Hz, latence {:.0f} ms{}")
                .format(self.index, self.name, self.channels,
                        self.samplerate, self.latency_ms, mark))


def list_devices() -> list[DeviceInfo]:
    """Peripheriques d'entree disponibles."""
    default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            out.append(DeviceInfo(
                index=i,
                name=d["name"],
                channels=d["max_input_channels"],
                samplerate=d["default_samplerate"],
                latency_ms=d["default_low_input_latency"] * 1000.0,
                default=(i == default_in),
            ))
    return out


def find_device(name_or_index: str | int | None) -> int | None:
    """Accepte un index, un fragment de nom, ou None (peripherique par defaut)."""
    if name_or_index is None or name_or_index == "":
        return None
    try:
        return int(name_or_index)
    except (TypeError, ValueError):
        pass
    needle = str(name_or_index).lower()
    for d in list_devices():
        if needle in d.name.lower():
            return d.index
    raise ValueError(tr("peripherique audio introuvable : {!r}").format(name_or_index))


class AudioInput:
    """Capture continue, en mono, avec callback par bloc."""

    def __init__(self, device=None, samplerate: int = SAMPLERATE,
                 blocksize: int = BLOCKSIZE, on_block=None, channels=None) -> None:
        self.device = find_device(device)
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.on_block = on_block
        # Une carte pro a plusieurs entrees : il faut savoir sur laquelle arrive
        # le signal. On les ouvre toutes et on melange celles qu'on a choisies.
        self.wanted = list(channels) if channels else None
        self.channel_levels: np.ndarray | None = None
        # Gain applique avant l'analyse : une sortie REC faible se rattrape ici,
        # sans toucher au materiel.
        self.gain = 1.0
        self.raw_peak = 0.0
        # Une carte son debranchee ne previent pas : le flux se tait, et sans
        # surveillance l'analyse reste figee sur sa derniere valeur.
        self.last_block = 0.0
        self.stream: sd.InputStream | None = None
        # diagnostic
        self.blocks = 0
        self.overflows = 0
        self.rms = 0.0
        self.peak = 0.0
        self.clipped = 0          # blocs satures : le micro est trop pres / trop fort
        self.clipped_recent = 0.0  # instant du dernier ecretage
        self.started_at = 0.0
        self.silent_since = 0.0

    # --- cycle de vie ---------------------------------------------------

    def start(self) -> None:
        if self.stream is not None:
            return
        info = sd.query_devices(self.device, "input") if self.device is not None \
            else sd.query_devices(kind="input")
        available = int(info["max_input_channels"])
        self.available = available
        wanted = self.wanted or []
        self.selected = ([c for c in wanted if 0 <= c < available]
                         or list(range(min(2, available))))
        self.channel_levels = np.zeros(available, dtype=np.float32)
        self.samplerate = int(info["default_samplerate"]) or self.samplerate
        self.stream = sd.InputStream(
            device=self.device,
            channels=available,
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="float32",
            latency="low",
            callback=self._callback,
        )
        self.stream.start()
        self.started_at = self.silent_since = self.last_block = time.monotonic()

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def __enter__(self) -> "AudioInput":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    @property
    def device_name(self) -> str:
        info = sd.query_devices(self.device, "input") if self.device is not None \
            else sd.query_devices(kind="input")
        return info["name"]

    @property
    def alive(self) -> bool:
        """Des blocs arrivent-ils encore ? False si la carte a disparu."""
        return self.stream is not None and (time.monotonic() - self.last_block) < 1.0

    def restart(self) -> bool:
        """Tente de rouvrir l'entree. True si elle refonctionne."""
        try:
            self.stop()
        except Exception:
            pass
        try:
            self.start()
            return True
        except Exception:
            self.stream = None
            return False

    @property
    def clipping(self) -> bool:
        """Ecretage dans la derniere seconde."""
        return time.monotonic() - self.clipped_recent < 1.0

    @property
    def silent_seconds(self) -> float:
        """Duree depuis laquelle on ne capte rien (autorisation micro refusee ?)."""
        return time.monotonic() - self.silent_since

    # --- callback PortAudio ---------------------------------------------

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            self.overflows += 1
        if indata.ndim > 1:
            # Niveau de chaque entree : c'est ce qui permet de trouver la bonne.
            np.sqrt(np.mean(indata * indata, axis=0), out=self.channel_levels)
            mono = indata[:, self.selected].mean(axis=1)
        else:
            mono = indata
        # L'ecretage se juge sur le signal brut : c'est le materiel qui sature,
        # pas notre gain.
        self.raw_peak = float(np.max(np.abs(mono)))
        if self.gain != 1.0:
            mono = mono * np.float32(self.gain)
        self.rms = float(np.sqrt(np.mean(mono * mono)))
        self.peak = float(np.max(np.abs(mono)))
        self.blocks += 1
        self.last_block = time.monotonic()
        if self.raw_peak >= 0.99:
            # Un signal ecrete remplit le spectre de distorsion : le detecteur
            # d'attaques y voit des transitoires qui n'existent pas.
            self.clipped += 1
            self.clipped_recent = time.monotonic()
        if self.peak > 1e-5:
            self.silent_since = time.monotonic()
        if self.on_block is not None:
            self.on_block(mono)
