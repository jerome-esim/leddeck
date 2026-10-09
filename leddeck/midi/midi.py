"""Liaison MIDI : ports, reception, envoi (retour visuel sur le controleur)."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

import mido

from ..i18n import tr

NOTE, CC = "note", "cc"


@dataclass(frozen=True)
class Control:
    """Un organe du controleur : un pad, un bouton ou un fader."""

    kind: str          # NOTE ou CC
    channel: int
    number: int

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.channel}:{self.number}"

    def __str__(self) -> str:
        label = "note" if self.kind == NOTE else "CC"
        return f"{label} {self.number} (canal {self.channel + 1})"

    @classmethod
    def parse(cls, key: str) -> "Control":
        kind, channel, number = key.split(":")
        return cls(kind, int(channel), int(number))

    @classmethod
    def from_message(cls, msg) -> "Control | None":
        if msg.type in ("note_on", "note_off"):
            return cls(NOTE, msg.channel, msg.note)
        if msg.type == "control_change":
            return cls(CC, msg.channel, msg.control)
        return None


def message_value(msg) -> float:
    """Valeur normalisee 0..1 du message (velocite ou valeur de CC)."""
    if msg.type == "note_off":
        return 0.0
    if msg.type == "note_on":
        return msg.velocity / 127.0
    if msg.type == "control_change":
        return msg.value / 127.0
    return 0.0


def input_ports() -> list[str]:
    return list(mido.get_input_names())


def output_ports() -> list[str]:
    return list(mido.get_output_names())


def find_port(names: list[str], wanted: str | None) -> str | None:
    """Accepte un nom exact, un fragment, ou None (premier port non virtuel)."""
    if not names:
        return None
    if wanted:
        for name in names:
            if wanted.lower() in name.lower():
                return name
        raise ValueError(f"port MIDI introuvable : {wanted!r} (vus : {', '.join(names)})")
    return names[0]


class MidiLink:
    """Entree + sortie MIDI. La sortie sert au retour visuel sur les pads."""

    def __init__(self, port: str | None = None, out_port: str | None = None,
                 on_control: Callable[[Control, float, object], None] | None = None) -> None:
        self.wanted_in = port
        self.wanted_out = out_port if out_port is not None else port
        self.on_control = on_control
        self._in = None
        self._out = None
        self.messages = 0
        self.last: tuple[Control, float] | None = None
        # Echos de nos propres envois : sur un bus en boucle (IAC), le retour
        # visuel revient en entree et redeclencherait les actions a l'infini.
        self._sent: deque[tuple[float, tuple]] = deque(maxlen=256)

    # --- cycle de vie ---------------------------------------------------

    def start(self) -> None:
        name_in = find_port(input_ports(), self.wanted_in)
        if name_in is None:
            raise RuntimeError("aucune entree MIDI disponible")
        self._in = mido.open_input(name_in, callback=self._callback)
        try:
            name_out = find_port(output_ports(), self.wanted_out)
            if name_out is not None:
                self._out = mido.open_output(name_out)
        except Exception:
            self._out = None      # le retour visuel est un bonus, jamais bloquant

    def stop(self) -> None:
        # Detacher le callback AVANT de fermer : fermer un port pendant qu'un
        # callback est en cours fige rtmidi (constate sur un bus en boucle, mais
        # le risque existe aussi a la fermeture de l'application).
        self.on_control = None
        if self._in is not None:
            try:
                self._in.callback = None
            except Exception:
                pass
        time.sleep(0.05)
        for port in (self._in, self._out):
            if port is not None:
                try:
                    port.close()
                except Exception:
                    pass
        self._in = self._out = None

    def __enter__(self) -> "MidiLink":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    @property
    def input_name(self) -> str:
        return self._in.name if self._in else "—"

    @property
    def output_name(self) -> str:
        return self._out.name if self._out else "—"

    # --- reception --------------------------------------------------------

    def _is_echo(self, signature: tuple) -> bool:
        now = time.monotonic()
        while self._sent and now - self._sent[0][0] > 0.25:
            self._sent.popleft()
        for stamp, sent in self._sent:
            if sent == signature:
                return True
        return False

    def _callback(self, msg) -> None:
        control = Control.from_message(msg)
        if control is None:
            return
        value = message_value(msg)
        if self._is_echo((control.key, round(value, 3))):
            return
        self.messages += 1
        self.last = (control, value)
        if self.on_control is not None:
            try:
                self.on_control(control, value, msg)
            except Exception as exc:     # un binding fautif ne doit rien casser
                print(tr("[midi] erreur sur {} : {!r}").format(control, exc))

    # --- retour visuel ----------------------------------------------------

    def send_note(self, note: int, velocity: int, channel: int = 0) -> None:
        if self._out is None:
            return
        velocity = max(0, min(127, int(velocity)))
        channel = max(0, min(15, int(channel)))
        self._sent.append((time.monotonic(),
                           (Control(NOTE, channel, int(note)).key, round(velocity / 127.0, 3))))
        try:
            self._out.send(mido.Message("note_on", note=note, velocity=velocity,
                                        channel=channel))
        except Exception:
            pass

    def send_cc(self, control: int, value: int, channel: int = 0) -> None:
        if self._out is None:
            return
        value = max(0, min(127, int(value)))
        self._sent.append((time.monotonic(),
                           (Control(CC, channel, int(control)).key, round(value / 127.0, 3))))
        try:
            self._out.send(mido.Message("control_change", control=control,
                                        value=value, channel=channel))
        except Exception:
            pass
