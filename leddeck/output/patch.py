"""Patch : matrice (N, L, 3) -> buffers par sortie, puis envoi DDP.

C'est ici qu'on remet l'ordre physique : chaque ligne de la matrice est routee
vers une sortie, eventuellement inversee et decalee, puis tronquee / completee
en noir pour coller au nombre de LED reel du bandeau.
"""

from __future__ import annotations

import numpy as np

from ..core.config import Output, Profile
from .ddp import DDPSender


def gamma_lut(gamma: float) -> np.ndarray:
    """Table 0..255 -> 0..255 appliquant la correction gamma."""
    x = np.linspace(0.0, 1.0, 256)
    return np.clip(np.power(x, gamma) * 255.0 + 0.5, 0, 255).astype(np.uint8)


class Patch:
    """Transforme une frame de la matrice en un buffer uint8 par sortie."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.profile.ensure_patch()
        self._lut = gamma_lut(profile.gamma)
        self._gamma = profile.gamma

    def _refresh_lut(self) -> None:
        if self.profile.gamma != self._gamma:
            self._gamma = self.profile.gamma
            self._lut = gamma_lut(self._gamma)

    def row_for_output(self, output_id: int) -> int | None:
        """Ligne de la matrice alimentant cette sortie (None si non patchee)."""
        for i, row in enumerate(self.profile.patch):
            if row.output_id == output_id:
                return i
        return None

    def targets(self) -> list[tuple[int, Output]]:
        """Couples (index de ligne, sortie) effectivement actifs."""
        out = []
        for i, row in enumerate(self.profile.patch):
            o = self.profile.output(row.output_id)
            if o is not None and o.enabled and o.ip:
                out.append((i, o))
        return out

    def map_frame(self, frame: np.ndarray, brightness: float | None = None) -> dict[int, np.ndarray]:
        """frame : (N, L, 3) float 0..1 -> {output_id: (led_count, 3) uint8}."""
        self._refresh_lut()
        prof = self.profile
        b = prof.brightness if brightness is None else brightness
        buffers: dict[int, np.ndarray] = {}
        for i, out in self.targets():
            row_cfg = prof.patch[i]
            line = frame[i] if i < frame.shape[0] else np.zeros((prof.leds, 3), np.float32)
            if row_cfg.offset:
                line = np.roll(line, row_cfg.offset, axis=0)
            if row_cfg.reverse:
                line = line[::-1]
            buffers[out.id] = self.to_bytes(line, out.led_count, b)
        return buffers

    def to_bytes(self, line: np.ndarray, led_count: int, brightness: float = 1.0) -> np.ndarray:
        """(l, 3) float 0..1 -> (led_count, 3) uint8, tronque ou complete en noir."""
        buf = np.zeros((led_count, 3), dtype=np.uint8)
        n = min(led_count, line.shape[0])
        if n > 0:
            v = np.clip(line[:n], 0.0, 1.0) * (255.0 * max(0.0, min(1.0, brightness)))
            buf[:n] = self._lut[v.astype(np.uint8)]
        return buf


class OutputStage:
    """Patch + emetteur DDP : le point de sortie unique du moteur."""

    def __init__(self, profile: Profile, sender: DDPSender | None = None,
                 keep_frame: bool = False, blank_unpatched: bool = True) -> None:
        self.profile = profile
        self.patch = Patch(profile)
        self.sender = sender or DDPSender()
        # Toute sortie active recoit quelque chose, meme sans ligne attribuee :
        # sans flux, WLED sort du mode temps reel au bout de 2,5 s et repart sur
        # son effet interne. Une sortie non patchee doit rester noire, pas vivre
        # sa vie.
        self.blank_unpatched = blank_unpatched
        # Copie de la derniere frame pour l'apercu : les effets reutilisent leur
        # propre tampon, une simple reference se ferait modifier sous les yeux de l'UI.
        self.last_frame = (np.zeros((profile.strips, profile.leds, 3), np.float32)
                           if keep_frame else None)

    def reload(self) -> None:
        """Relit le patch du profil en gardant l'emetteur (et ses sequences)."""
        self.patch = Patch(self.profile)
        if self.last_frame is not None:
            self.last_frame = np.zeros(
                (self.profile.strips, self.profile.leds, 3), np.float32)

    def send_frame(self, frame, brightness: float | None = None) -> None:
        """Envoie une frame de matrice (N, L, 3) float 0..1 via le patch.

        Accepte aussi un dictionnaire {sortie: ligne} : le mode installation
        adresse les bandeaux par numero, avant meme qu'un patch existe.
        """
        if isinstance(frame, dict):
            self.send_direct(frame, brightness)
            return
        if self.last_frame is not None and frame.shape == self.last_frame.shape:
            np.copyto(self.last_frame, frame)
        buffers = self.patch.map_frame(frame, brightness)
        for out_id, buf in buffers.items():
            out = self.profile.output(out_id)
            if out:
                self.sender.send_pixels(out.ip, out.port, buf)
        if self.blank_unpatched:
            for out in self.profile.outputs:
                if out.id not in buffers and out.enabled and out.ip:
                    self.sender.send_pixels(out.ip, out.port,
                                            np.zeros((out.led_count, 3), np.uint8))

    def send_direct(self, buffers: dict[int, np.ndarray], brightness: float | None = None) -> None:
        """Envoie sans passer par le patch : {output_id: (n, 3) float 0..1}.

        Sert au mode installation (identification, clignotement) ou l'on adresse
        les bandeaux par leur numero, avant meme que le patch existe.
        """
        b = self.profile.brightness if brightness is None else brightness
        for out_id, line in buffers.items():
            out = self.profile.output(out_id)
            if out is None or not out.enabled or not out.ip:
                continue
            self.sender.send_pixels(out.ip, out.port, self.patch.to_bytes(line, out.led_count, b))

    def blackout(self) -> None:
        """Eteint toutes les sorties actives (a appeler en quittant)."""
        for out in self.profile.outputs:
            if out.enabled and out.ip:
                self.sender.send_pixels(out.ip, out.port, np.zeros((out.led_count, 3), np.uint8))

    def close(self) -> None:
        self.sender.close()
