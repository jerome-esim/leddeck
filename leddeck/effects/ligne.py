"""Ligne mouvante : une ligne qui balaie la matrice.

Porte du shader ISF « Ligne mouvante ». `direction` a 0 balaie *en travers* des
tubes — un tube apres l'autre ; a 1, le point court *le long* de tous les tubes
en meme temps ; a 2, les deux alternent.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register, smoothstep


@register
class Ligne(Effect):
    name = "Ligne"
    params = {
        "vitesse": (0.1, 4.0, 1.0),
        "épaisseur": (0.01, 0.3, 0.05),
        "direction": (0.0, 2.0, 0.0),     # 0 en travers, 1 le long, 2 alterne
        "rebond": (0.0, 1.0, 0.0, "interrupteur"),
        "bords doux": (0.0, 1.0, 1.0, "interrupteur"),
    }

    def reset(self) -> None:
        self._along = ((np.arange(self.leds, dtype=np.float32) + 0.5) / self.leds)[None, :]
        self._across = ((np.arange(self.strips, dtype=np.float32) + 0.5) / self.strips)[:, None]

    def render(self, t, dt, audio, palette, p):
        phase = t * p["vitesse"]
        if p["rebond"] >= 0.5:
            position = abs((phase * 0.5) % 1.0 * 2.0 - 1.0)
        else:
            position = phase % 1.0

        mode = int(round(p["direction"]))
        if mode == 2:
            mode = 1 if int(phase) % 2 == 0 else 0
        axis = self._along if mode == 1 else self._across

        thickness = p["épaisseur"]
        distance = np.abs(axis - position)
        if p["bords doux"] >= 0.5:
            level = smoothstep(0.0, 1.0, np.clip(1.0 - distance / thickness, 0.0, 1.0))
        else:
            level = (distance < thickness).astype(np.float32)

        color = palette.sample(position)
        np.multiply(np.broadcast_to(level, self.frame.shape[:2])[..., None], color, out=self.frame)
        return self.frame
