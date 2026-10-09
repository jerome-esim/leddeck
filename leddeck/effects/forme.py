"""Forme : une tache deformee qui se promene et reboucle sur les bords.

Porte du shader ISF « Forme qui bouge avec wrapping ». La trajectoire est une
somme de sinus — fluide, contrairement au Blob — et la distance est torique :
ce qui sort d'un cote revient de l'autre.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class Forme(Effect):
    name = "Forme"
    params = {
        "vitesse": (0.1, 3.0, 0.5),
        "taille": (0.05, 0.5, 0.2),
        "déformation": (0.0, 2.0, 1.0),
    }

    def reset(self) -> None:
        x = (np.arange(self.strips, dtype=np.float32) + 0.5) / self.strips
        y = (np.arange(self.leds, dtype=np.float32) + 0.5) / self.leds
        self._x, self._y = x[:, None], y[None, :]
        self._ratio = self.strips / 12.0

    def render(self, t, dt, audio, palette, p):
        local = t * p["vitesse"]
        cx = (0.5 + np.sin(local) * 0.4 + np.cos(local * 0.7) * 0.3) % 1.0
        cy = (0.5 + np.cos(local * 0.8) * 0.4 + np.sin(local * 1.2) * 0.3) % 1.0

        dx = self._x - cx
        dy = self._y - cy
        dx = np.where(dx > 0.5, dx - 1.0, np.where(dx < -0.5, dx + 1.0, dx)) * self._ratio
        dy = np.where(dy > 0.5, dy - 1.0, np.where(dy < -0.5, dy + 1.0, dy))

        distance = np.sqrt(dx * dx + dy * dy)
        angle = np.arctan2(dy, dx)
        deform = (np.sin(angle * 5.0 + t) * 0.05
                  + np.sin(angle * 3.0 - t * 0.7) * 0.03) * p["déformation"]
        radius = p["taille"] + deform

        level = np.where(distance < radius, 1.0 - distance / np.maximum(radius, 1e-5), 0.0)
        color = palette.sample((local * 0.07) % 1.0)
        np.multiply(level.astype(np.float32)[..., None], color, out=self.frame)
        return self.frame
