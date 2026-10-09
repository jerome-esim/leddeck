"""Tubes : on allume des bandeaux entiers, dans l'ordre ou au hasard."""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class Tubes(Effect):
    """Un ou plusieurs tubes s'allument, en sequence ou au hasard.

    `hasard` est un continuum : a 0 on parcourt les tubes dans l'ordre, a 1 on
    tire au sort a chaque fois, et entre les deux on melange les deux gestes.
    """

    name = "Tubes"
    params = {
        "nombre": (1, 16, 1),             # tubes allumes simultanement
        "vitesse": (0.2, 10.0, 2.0),      # changements par seconde, hors beat
        "hasard": (0.0, 1.0, 0.0),        # 0 = dans l'ordre, 1 = au hasard
        "fondu": (0.0, 1.5, 0.12),        # extinction du tube precedent
        "sur le beat": (0.0, 1.0, 1.0, "interrupteur"),   # on change a chaque beat
    }

    def reset(self) -> None:
        self._rng = np.random.default_rng()
        self._level = np.zeros(self.strips, dtype=np.float32)
        self._pos = np.zeros(self.strips, dtype=np.float32)
        self._cursor = 0
        self._step = 0
        self._next = 0.0

    def _advance(self, p) -> None:
        self._step += 1
        for i in range(max(1, int(p["nombre"]))):
            if self._rng.random() < p["hasard"]:
                row = int(self._rng.integers(0, self.strips))
            else:
                row = self._cursor % self.strips
                self._cursor += 1
            self._level[row] = 1.0
            self._pos[row] = (self._step * 0.13 + i * 0.09) % 1.0

    def render(self, t, dt, audio, palette, p):
        self._level *= float(np.exp(-dt / max(0.01, p["fondu"])))

        on_beat = p["sur le beat"] >= 0.5 and audio is not None
        if on_beat:
            if self.beat_happened(audio):
                self._advance(p)
        else:
            self.beat_happened(audio)      # garde le compteur a jour
            self._next -= dt
            if self._next <= 0.0:
                self._next += 1.0 / max(0.05, p["vitesse"])
                self._advance(p)

        colors = palette.sample(self._pos)                    # (N, 3)
        self.frame[:] = colors[:, None, :] * self._level[:, None, None]
        return self.frame
