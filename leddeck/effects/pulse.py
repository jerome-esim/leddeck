"""Pulse : la matrice entiere s'allume sur chaque beat."""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class Pulse(Effect):
    name = "Pulse"
    params = {
        # Les trois premiers tombent sur les faders : ce sont ceux qu'on touche.
        "retombée": (0.05, 1.5, 0.3),     # en fraction de beat
        "couleur": (0.0, 1.0, 0.6),       # position de depart dans la palette
        "variation": (0.0, 0.5, 0.13),    # avance dans la palette a chaque beat
        "résiduel": (0.0, 0.5, 0.03),     # niveau entre deux beats
    }

    def reset(self) -> None:
        self._env = 0.0
        self._index = 0
        self._free_beat = 0.0

    def render(self, t, dt, audio, palette, p):
        period = self.audio_value(audio, "period", 0.5) or 0.5
        if audio is None:
            # Sans son, on pulse tout seul a 120 BPM pour rester utilisable.
            self._free_beat += dt
            beat = self._free_beat >= 0.5
            if beat:
                self._free_beat -= 0.5
        else:
            beat = self.beat_happened(audio)

        if beat:
            self._env = 1.0
            self._index += 1

        self._env *= float(np.exp(-dt / max(0.02, p["retombée"] * period)))
        value = max(p["résiduel"], self._env)
        if palette.smooth:
            color = palette.sample((p["couleur"] + self._index * p["variation"]) % 1.0)
        else:
            # Palette a paliers : on saute de couleur en couleur, sans teinte
            # intermediaire. « variation » compte alors en nombre de couleurs.
            k = palette.count
            step = max(1, int(round(p["variation"] * k)))
            color = palette.color_at(int(p["couleur"] * k) + self._index * step)
        self.frame[:] = color * np.float32(value)
        return self.frame
