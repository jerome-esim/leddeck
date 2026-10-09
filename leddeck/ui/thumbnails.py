"""Vignettes : un apercu dessine de chaque effet et de chaque palette.

Choisir un effet dans une liste de noms demande de se souvenir de ce que fait
chacun. Une vignette le montre. Elle est calculee en faisant tourner l'effet
quelques secondes sur une mini-matrice, avec la palette du deck.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

EFFECT_W, EFFECT_H = 64, 18
PALETTE_W, PALETTE_H = 64, 12


def _to_pixmap(frame: np.ndarray, width: int, height: int) -> QPixmap:
    buf = np.ascontiguousarray((np.clip(frame, 0.0, 1.0) * 255.0).astype(np.uint8))
    strips, leds = buf.shape[:2]
    image = QImage(buf.data, leds, strips, leds * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(
        image.scaled(width, height, Qt.IgnoreAspectRatio, Qt.FastTransformation))


def effect_pixmap(effect_cls, palette, width: int = EFFECT_W, height: int = EFFECT_H,
                  strips: int = 4, seconds: float = 2.5, fps: int = 25,
                  window: float = 0.3) -> QPixmap:
    """Fait tourner l'effet sur une mini-matrice et capture ce qu'il donne.

    On garde le maximum des dernieres images plutot qu'une seule : un effet a
    eclats brefs (Electrique, Ciel etoile, Pulse) tomberait sinon sur une image
    noire une fois sur deux. La fenetre reste courte pour ne pas etaler les
    effets continus.
    """
    effect = effect_cls(width, strips)
    dt = 1.0 / fps
    t = 0.0
    total = max(1, int(seconds * fps))
    keep = max(1, int(window * fps))
    out = np.zeros((strips, width, 3), dtype=np.float32)
    for i in range(total):
        t += dt
        frame = effect.render(t, dt, None, palette, effect.p)
        if i >= total - keep:
            np.maximum(out, frame, out=out)
    return _to_pixmap(out, width, height)


def palette_pixmap(palette, width: int = PALETTE_W, height: int = PALETTE_H) -> QPixmap:
    return _to_pixmap(palette.gradient(width)[None, :, :], width, height)
