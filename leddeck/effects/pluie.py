"""Pluie : gouttes qui tombent le long des tubes.

Porte du shader ISF « Gouttes de pluie » : une colonne du shader = un tube ici.
Chaque tube porte plusieurs gouttes, de vitesses differentes, suivies d'une
trainee degressive.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register, shader_random


@register
class Pluie(Effect):
    name = "Pluie"
    params = {
        "vitesse": (0.1, 5.0, 1.0),
        "taille": (0.01, 0.2, 0.08),
        "densité": (0.1, 3.0, 1.0),
        "traînée": (0.0, 0.5, 0.1),
        "sens": (0.0, 1.0, 0.0, "interrupteur"),   # inverse : les gouttes montent
    }

    def reset(self) -> None:
        self._y = ((np.arange(self.leds, dtype=np.float32) + 0.5) / self.leds)[None, :]
        self._rows = np.arange(self.strips, dtype=np.float32)[:, None]

    def render(self, t, dt, audio, palette, p):
        self.frame.fill(0.0)
        drops = max(1, int(p["densité"] * 3.0))
        size, trail = p["taille"], p["traînée"]
        reverse = p["sens"] >= 0.5

        for index in range(drops):
            seed = self._rows * 100.0 + index * 37.0
            speed = p["vitesse"] * (0.5 + shader_random(seed + 1.0) * 0.5)
            pos = t * speed * 0.2 + shader_random(seed + 2.0)
            drop_y = pos - np.floor(pos)
            if not reverse:
                drop_y = 1.0 - drop_y

            gap = self._y - drop_y
            level = (np.abs(gap) < size).astype(np.float32)
            if trail > 0.0:
                behind = -gap if reverse else gap
                inside = (behind > 0.0) & (behind < trail)
                level = level + np.where(inside, (1.0 - behind / trail) * 0.5, 0.0)

            color = palette.sample((index * 0.17 + t * 0.03) % 1.0)
            self.frame += level[..., None] * color
        np.clip(self.frame, 0.0, 1.0, out=self.frame)
        return self.frame
