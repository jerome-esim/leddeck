"""Ciel etoile : des LED isolees qui s'allument et s'eteignent en fondu.

Porte du shader ISF « Pixels aleatoires ». Chaque etoile vit un cycle
fondu d'entree → plateau → fondu de sortie, puis reapparait ailleurs.
`independant` donne a chacune son propre rythme ; sinon elles battent ensemble.

La version precedente decroissait en exponentielle et repartait sur chaque beat :
c'etait bien plus rapide, et moins proche du rendu d'origine.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register, shader_random


@register
class Etoiles(Effect):
    name = "Ciel étoilé"
    params = {
        "nombre": (1, 100, 10),
        "vitesse": (0.01, 4.0, 0.2),
        "fondu": (0.1, 0.9, 0.3),
        "indépendant": (0.0, 1.0, 1.0, "interrupteur"),
        "pluie": (0.0, 1.0, 0.0),         # etoiles supplementaires sur le beat
    }

    def reset(self) -> None:
        self._rng = np.random.default_rng()
        self._extra = np.zeros((self.strips, self.leds), dtype=np.float32)

    def render(self, t, dt, audio, palette, p):
        self.frame.fill(0.0)
        count = max(1, int(p["nombre"]))
        fade = p["fondu"]
        independent = p["indépendant"] >= 0.5

        for index in range(count):
            offset = float(shader_random(index * 789.123)) * 100.0 if independent else 0.0
            local = t * p["vitesse"] + offset
            cycle = np.floor(local)
            phase = local - cycle

            row = int(float(shader_random(cycle + index * 123.4)) * self.strips)
            col = int(float(shader_random(cycle + index * 456.7)) * self.leds)
            row = min(self.strips - 1, max(0, row))
            col = min(self.leds - 1, max(0, col))

            if phase < fade:
                level = phase / fade
            elif phase > 1.0 - fade:
                level = (1.0 - phase) / fade
            else:
                level = 1.0

            color = palette.sample(float(shader_random(cycle + index * 31.7)))
            self.frame[row, col] = np.maximum(self.frame[row, col], color * np.float32(level))

        # Pluie d'etoiles sur le beat : garde le cote reactif de la version d'avant.
        if p["pluie"] > 0.0:
            self._extra *= float(np.exp(-dt / 0.35))
            if self.beat_happened(audio):
                burst = int(p["pluie"] * self.strips * self.leds * 0.004)
                if burst:
                    rows = self._rng.integers(0, self.strips, burst)
                    cols = self._rng.integers(0, self.leds, burst)
                    self._extra[rows, cols] = 1.0
            np.maximum(self.frame, self._extra[..., None] * palette.sample(0.5), out=self.frame)
        else:
            self.beat_happened(audio)
        return self.frame
