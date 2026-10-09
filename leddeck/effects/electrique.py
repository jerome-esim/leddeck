"""Electrique : courts eclats blancs, comme un contact qui claque."""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class Electrique(Effect):
    """Eclats blancs breves et courts, repartis au hasard sur les bandeaux.

    Ce n'est pas un strobe : les eclats ne prennent qu'un petit morceau de tube
    a la fois, ce qui donne le gresillement plutot que le flash plein.
    """

    name = "Électrique"
    params = {
        "densité": (0.0, 1.0, 0.4),       # nombre d'eclats par seconde
        "longueur": (1, 80, 10),          # taille d'un eclat, en LED
        "durée": (0.01, 0.4, 0.06),       # temps d'extinction d'un eclat
        "blancheur": (0.0, 1.0, 1.0),     # 1 = blanc pur, 0 = couleur de la palette
        "sur le beat": (0.0, 1.0, 0.5),   # rafale supplementaire sur chaque beat
    }

    def reset(self) -> None:
        self._rng = np.random.default_rng()
        self._bright = np.zeros((self.strips, self.leds), dtype=np.float32)

    def _sparks(self, count: int, length: float) -> None:
        for _ in range(int(count)):
            row = int(self._rng.integers(0, self.strips))
            size = max(1, int(length * (0.35 + self._rng.random())))
            start = int(self._rng.integers(0, max(1, self.leds)))
            self._bright[row, start:start + size] = 1.0

    def render(self, t, dt, audio, palette, p):
        self._bright *= float(np.exp(-dt / max(0.005, p["durée"])))

        count = self._rng.poisson(max(0.0, p["densité"] * 30.0 * dt))
        if self.beat_happened(audio):
            count += int(p["sur le beat"] * 8)
        self._sparks(count, p["longueur"])

        white = np.float32(p["blancheur"])
        color = np.float32(1.0) * white + palette.sample(1.0) * (1.0 - white)
        np.multiply(self._bright[..., None], color, out=self.frame)
        return self.frame
