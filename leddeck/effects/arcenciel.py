"""Arc-en-ciel : la palette defile le long des bandeaux."""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class ArcEnCiel(Effect):
    name = "Arc-en-ciel"
    params = {
        "vitesse": (-2.0, 2.0, 0.12),
        "étalement": (0.1, 6.0, 1.0),     # palettes completes sur la longueur
        "décalage": (0.0, 1.0, 0.12),     # decalage d'une ligne a l'autre
        "son": (0.0, 1.0, 1.0, "interrupteur"),   # luminosite pilotee par le niveau
    }

    def reset(self) -> None:
        self._x = (np.arange(self.leds, dtype=np.float32) / max(1, self.leds))[None, :]
        self._rows = (np.arange(self.strips, dtype=np.float32))[:, None]

    def render(self, t, dt, audio, palette, p):
        pos = self._x * p["étalement"] + self._rows * p["décalage"] + t * p["vitesse"]
        react = 0.7 if p["son"] >= 0.5 else 0.0
        intensity = np.float32(self.reactive(audio, "level", react, floor=0.2))
        np.multiply(palette.sample(pos.astype(np.float32) % 1.0), intensity, out=self.frame)
        return self.frame
