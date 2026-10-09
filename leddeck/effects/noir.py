"""Noir : rien du tout, et c'est le but.

Sert de contrepartie au crossfader — poser Noir sur un deck permet de faire
entrer et sortir l'autre en fondu, au lieu de couper au blackout.
"""

from __future__ import annotations

from .base import Effect, register


@register
class Noir(Effect):
    name = "Noir"
    params: dict[str, tuple[float, float, float]] = {}

    def render(self, t, dt, audio, palette, p):
        self.frame.fill(0.0)
        return self.frame
