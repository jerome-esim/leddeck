"""Serpents qui parcourent la matrice."""

from __future__ import annotations

import numpy as np

from .base import Effect, register


@register
class Serpent(Effect):
    """Un ou plusieurs serpents parcourent la matrice comme une seule longue chaine.

    La matrice est vue a plat (ligne 1 puis ligne 2...) : le serpent passe donc
    d'un bandeau au suivant, ce qui donne du mouvement sur l'ensemble.
    """

    name = "Serpent"
    params = {
        "vitesse": (0.05, 6.0, 1.0),      # longueurs de bandeau par seconde
        "longueur": (2, 250, 40),
        "nombre": (1, 8, 2),
        "réactivité": (0.0, 1.0, 0.5),    # acceleration sur les basses
    }

    def reset(self) -> None:
        self._pos = 0.0

    def render(self, t, dt, audio, palette, p):
        total = self.strips * self.leds
        bass = self.audio_value(audio, "bass")
        speed = p["vitesse"] * (1.0 + 2.0 * p["réactivité"] * bass)
        self._pos = (self._pos + speed * dt * self.leds) % total

        length = max(2, int(p["longueur"]))
        count = max(1, int(p["nombre"]))

        self.frame.fill(0.0)
        flat = self.frame.reshape(-1, 3)
        tail = np.arange(length, dtype=np.float32)
        fade = ((1.0 - tail / length) ** 2)[:, None]

        for k in range(count):
            head = self._pos + k * total / count
            ids = (head - tail).astype(np.int64) % total
            # La couleur suit la queue : la palette se lit sur le serpent lui-meme.
            cols = palette.sample((tail / length * 0.6 + k / count + t * 0.05) % 1.0)
            flat[ids] = np.maximum(flat[ids], cols * fade)
        return self.frame
