"""Vortex : spirale a plusieurs bras qui tourne autour d'un centre reglable.

Porte du shader ISF « Vortex/Spirale ». La spirale est dessinee dans l'espace
*logique* de la matrice — tube x position, comme le faisait MadMapper — et non
dans la geometrie reelle de la salle.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register, smoothstep

TWO_PI = 2.0 * np.pi


@register
class Vortex(Effect):
    name = "Vortex"
    params = {
        "rotation": (-5.0, 5.0, 1.0),
        "serrage": (0.5, 10.0, 3.0),
        "bras": (1, 12, 3),
        "centre X": (0.0, 1.0, 0.5),
        "centre Y": (0.0, 1.0, 0.5),
        "épaisseur": (0.05, 0.5, 0.15),
        "pulsation": (0.0, 5.0, 0.0),
    }

    def reset(self) -> None:
        x = (np.arange(self.strips, dtype=np.float32) + 0.5) / self.strips
        y = (np.arange(self.leds, dtype=np.float32) + 0.5) / self.leds
        self._x, self._y = x[:, None], y[None, :]

    def render(self, t, dt, audio, palette, p):
        dx = self._x - p["centre X"]
        dy = self._y - p["centre Y"]
        radius = np.sqrt(dx * dx + dy * dy)
        angle = np.arctan2(dy, dx)
        angle = np.where(angle < 0.0, angle + TWO_PI, angle)

        rotation = t * p["rotation"]
        arms = max(1, int(p["bras"]))
        closest = np.full(radius.shape, 999.0, dtype=np.float32)
        for index in range(arms):
            spiral = angle - radius * p["serrage"] + rotation + (index / arms) * TWO_PI
            spiral = (spiral + np.pi) % TWO_PI - np.pi
            np.minimum(closest, np.abs(spiral), out=closest)

        thickness = p["épaisseur"]
        level = smoothstep(0.0, 1.0, np.clip(1.0 - (closest * radius) / thickness, 0.0, 1.0))
        # Fondu au centre et sur les bords, comme dans le shader.
        level *= smoothstep(0.0, 0.1, radius) * (1.0 - smoothstep(0.7, 1.0, radius))
        if p["pulsation"] > 0.0:
            level *= 0.7 + 0.3 * np.sin(t * p["pulsation"] + radius * 5.0)

        phase = (angle / TWO_PI + rotation * 0.2) % 1.0
        np.multiply(palette.sample(phase.astype(np.float32)), level[..., None], out=self.frame)
        return self.frame
