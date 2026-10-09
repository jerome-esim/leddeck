"""Blob : tache ronde aux bords doux qui se deplace au hasard.

Porte du shader ISF « Blob aleatoire », y compris son cote saccade : la position
vient d'un tirage sur le temps, elle saute donc d'un endroit a l'autre.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register, shader_random2, smoothstep


@register
class Blob(Effect):
    name = "Blob"
    params = {
        "vitesse": (0.1, 5.0, 1.0),
        "taille": (0.1, 0.8, 0.3),
        "nombre": (1, 5, 1),
        "douceur": (0.01, 0.3, 0.1),
        "organique": (0.0, 1.0, 1.0, "interrupteur"),
    }

    def reset(self) -> None:
        x = (np.arange(self.strips, dtype=np.float32) + 0.5) / self.strips
        y = (np.arange(self.leds, dtype=np.float32) + 0.5) / self.leds
        self._x, self._y = x[:, None], y[None, :]
        self._ratio = self.strips / max(1.0, self.leds)

    def render(self, t, dt, audio, palette, p):
        self.frame.fill(0.0)
        count = max(1, int(p["nombre"]))
        size, softness = p["taille"], p["douceur"]
        organic = p["organique"] >= 0.5

        for index in range(count):
            local = t * p["vitesse"] + index * 100.0
            cx = float(shader_random2(local * 0.3, index * 234.567)) * 0.8 + 0.1
            cy = float(shader_random2(local * 0.2 + 100.0, index * 345.678)) * 0.8 + 0.1

            dx = (self._x - cx) * self._ratio
            dy = self._y - cy
            distance = np.sqrt(dx * dx + dy * dy)

            radius = size
            if organic:
                angle = np.arctan2(dy, dx)
                radius = size + (np.sin(angle * 3.0 + local) * 0.1
                                 + np.sin(angle * 5.0 - local * 0.7) * 0.05) * size

            level = 1.0 - smoothstep(0.0, 1.0, np.clip(
                (distance - (radius - softness)) / max(1e-5, softness), 0.0, 1.0))
            level = np.where(distance < radius, level, 0.0).astype(np.float32)
            color = palette.sample((index / count + t * 0.05) % 1.0)
            np.maximum(self.frame, level[..., None] * color, out=self.frame)
        return self.frame
