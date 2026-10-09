"""Vague / plasma : ondes de couleur, amplitude sur les basses."""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class Vague(Effect):
    name = "Vague"
    params = {
        "vitesse": (0.0, 3.0, 0.35),
        "échelle": (0.3, 8.0, 1.6),       # nombre d'ondes sur la longueur
        "réactivité": (0.0, 1.0, 0.6),    # part de l'intensite pilotee par les basses
        "décalage": (0.0, 1.0, 0.25),     # dephasage d'une ligne a l'autre
    }

    def reset(self) -> None:
        self._x = (np.arange(self.leds, dtype=np.float32) / max(1, self.leds))[None, :]
        self._y = (np.arange(self.strips, dtype=np.float32) / max(1, self.strips))[:, None]

    def render(self, t, dt, audio, palette, p):
        x, y = self._x, self._y
        k, v = p["échelle"], p["vitesse"]
        phase = y * p["décalage"]
        # Deux ondes de periodes differentes : le motif ne se repete pas a l'oeil.
        w = (np.sin(2 * np.pi * (x * k + t * v + phase))
             + np.sin(2 * np.pi * (x * k * 0.63 - t * v * 0.8 + phase * 1.7))) * 0.25 + 0.5

        intensity = np.float32(self.reactive(audio, "bass", p["réactivité"]))

        np.multiply(palette.sample(w.astype(np.float32)), intensity, out=self.frame)
        return self.frame
