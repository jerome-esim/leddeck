"""Couleur fixe : l'utilitaire de base, a piocher dans la palette."""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class Fixe(Effect):
    """Couleur fixe prise dans la palette, eventuellement etalee sur la longueur.

    Sert de fond, de base a melanger avec l'autre deck, ou simplement a eclairer.
    """

    name = "Fixe"
    params = {
        "couleur": (0.0, 1.0, 0.0),       # position dans la palette
        "étalement": (0.0, 1.0, 0.0),     # 0 = unie ; 1 = toute la palette sur la longueur
        "décalage": (0.0, 1.0, 0.0),      # decalage d'une ligne a l'autre
        "son": (0.0, 1.0, 1.0, "interrupteur"),   # luminosite pilotee par le niveau
    }

    def reset(self) -> None:
        self._x = (np.arange(self.leds, dtype=np.float32) / max(1, self.leds))[None, :]
        self._rows = (np.arange(self.strips, dtype=np.float32))[:, None]

    def render(self, t, dt, audio, palette, p):
        pos = p["couleur"] + self._x * p["étalement"] + self._rows * p["décalage"]
        react = 0.7 if p["son"] >= 0.5 else 0.0
        intensity = np.float32(self.reactive(audio, "level", react, floor=0.2))
        np.multiply(palette.sample(pos.astype(np.float32) % 1.0), intensity, out=self.frame)
        return self.frame
