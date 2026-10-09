"""Apercu de la matrice : une barre horizontale par bandeau."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from .style import BORDER, MUTED

BACKDROP = QColor("#0b0c0f")


class MatrixPreview(QWidget):
    """Affiche une frame (N, L, 3) float 0..1 telle que la verront les bandeaux."""

    def __init__(self, strips: int, leds: int, compact: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.compact = compact
        self.show_numbers = not compact
        self._border = QColor(BORDER)
        self._muted = QColor(MUTED)
        self.set_matrix(strips, leds)

    def set_matrix(self, strips: int, leds: int) -> None:
        self.strips, self.leds = max(1, strips), max(1, leds)
        self._buf = np.zeros((self.strips, self.leds, 3), dtype=np.uint8)
        # Le QImage partage la memoire du tableau : on garde les deux vivants.
        self._img = QImage(self._buf.data, self.leds, self.strips,
                           self.leds * 3, QImage.Format_RGB888)
        self._tmp = np.zeros((self.strips, self.leds, 3), dtype=np.float32)
        # La hauteur suit le nombre de bandeaux : lisible aussi bien a 3 qu'a 16.
        per_row = 7 if self.compact else 14
        self.setMinimumHeight(max(54 if self.compact else 130, self.strips * per_row + 18))
        self.update()

    def set_frame(self, frame: np.ndarray | None) -> None:
        if frame is None or frame.shape[:2] != (self.strips, self.leds):
            return
        np.clip(frame, 0.0, 1.0, out=self._tmp)
        self._tmp *= 255.0
        np.copyto(self._buf, self._tmp.astype(np.uint8))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        shell = QPainterPath()
        shell.addRoundedRect(outer, 10, 10)
        painter.fillPath(shell, BACKDROP)

        pad = 8
        left = pad + (22 if self.show_numbers else 0)
        w = self.width() - left - pad
        h = self.height() - 2 * pad
        if w <= 0 or h <= 0:
            return

        gap = 3 if self.strips > 1 else 0
        row_h = (h - gap * (self.strips - 1)) / self.strips
        if row_h < 2:
            row_h, gap = h / self.strips, 0
        radius = min(row_h / 2.0, 5.0)

        for r in range(self.strips):
            y = pad + r * (row_h + gap)
            rect = QRectF(left, y, w, max(1.0, row_h))
            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)
            painter.save()
            painter.setClipPath(path)
            painter.drawImage(rect, self._img, QRectF(0, r, self.leds, 1))
            painter.restore()
            if self.show_numbers and row_h >= 11:
                painter.setPen(self._muted)
                painter.drawText(QRect(pad, int(y), 18, max(1, int(row_h))),
                                 Qt.AlignRight | Qt.AlignVCenter, str(r + 1))

        painter.setPen(self._border)
        painter.drawPath(shell)
