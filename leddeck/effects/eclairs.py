"""Eclairs : des tubes entiers frappes par rafales.

Porte du shader ISF « Eclair sur colonnes ». Un cycle = plusieurs flashs separes
de pauses sur les *memes* tubes, puis on en tire d'autres. Chaque flash monte
vite (30 % du temps) et retombe plus lentement.

A ne pas confondre avec « Electrique », qui fait de courts eclats epars sur de
petits morceaux de tube et sert aussi de surcouche au master.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register, shader_random


@register
class Eclairs(Effect):
    name = "Éclairs"
    params = {
        "tubes": (1, 12, 2),              # tubes frappes en meme temps
        "vitesse": (0.1, 4.0, 1.0),
        "durée": (0.05, 1.0, 0.15),       # duree d'un flash
        "flashs": (1, 10, 3),             # flashs avant de changer de tubes
        "pause": (0.05, 1.0, 0.2),
        "intensité": (0.1, 2.0, 1.0),
        "tube entier": (0.0, 1.0, 1.0, "interrupteur"),
        "traînée": (0.05, 0.5, 0.2),      # si le tube n'est pas entier
    }

    def reset(self) -> None:
        self._y = (np.arange(self.leds, dtype=np.float32) + 0.5) / self.leds
        self._grain = 0.8 + 0.2 * shader_random(self._y * 100.0)

    def render(self, t, dt, audio, palette, p):
        self.frame.fill(0.0)
        flash_time, pause = p["durée"], p["pause"]
        cycle = (flash_time + pause) * max(1, int(p["flashs"]))
        local = t * p["vitesse"]
        cycle_index = np.floor(local / cycle)
        in_flash = (local % cycle) % (flash_time + pause)
        if in_flash >= flash_time:
            return self.frame

        progress = in_flash / flash_time
        level = progress / 0.3 if progress < 0.3 else (1.0 - progress) / 0.7
        level *= p["intensité"]
        if level <= 0.0:
            return self.frame

        for index in range(max(1, int(p["tubes"]))):
            row = int(float(shader_random(cycle_index + index * 234.567)) * self.strips)
            row = min(self.strips - 1, max(0, row))
            color = palette.sample((float(shader_random(cycle_index + index * 77.3))) % 1.0)

            if p["tube entier"] >= 0.5:
                # Grain fixe le long du tube : un eclair n'est jamais parfaitement uni.
                self.frame[row] += color * (level * self._grain)[:, None]
            else:
                head_y = 1.0 - progress
                gap = self._y - head_y
                strike = (np.abs(gap) < 0.02).astype(np.float32) * level
                trail = np.where((gap > 0.0) & (gap < p["traînée"]),
                                 (1.0 - gap / p["traînée"]) * level * 0.6, 0.0)
                self.frame[row] += color * (strike + trail).astype(np.float32)[:, None]

        np.clip(self.frame, 0.0, 1.0, out=self.frame)
        return self.frame
