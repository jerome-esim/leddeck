"""Choix des effets posés sur la grille du contrôleur.

Il y a plus d'effets que de pads : cette fenêtre décide lesquels sont au doigt,
et à quelle place. La grille affichée reproduit celle de l'APC mini.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QPushButton,
    QVBoxLayout,
)

from ..core.config import PAD_EFFECTS, Profile
from ..i18n import tr
from .style import ACCENT, MUTED

COLUMNS = 4


class PadEffectsDialog(QDialog):
    def __init__(self, profile: Profile, available: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Effets du contrôleur"))
        self.profile = profile
        self.available = list(available)
        self._previous: list[str] = []

        intro = QLabel(
            tr("{} effets, {} pads par deck.\n"
               "Choisis lesquels sont sous les doigts, et dans quel ordre.")
            .format(len(self.available), PAD_EFFECTS))
        intro.setStyleSheet(f"color: {MUTED}; font-size: 11px;")

        grid = QGridLayout()
        grid.setSpacing(6)
        self.boxes: list[QComboBox] = []
        current = profile.pad_effects(self.available)
        for slot in range(PAD_EFFECTS):
            row, column = divmod(slot, COLUMNS)
            number = QLabel(str(slot + 1))
            number.setAlignment(Qt.AlignCenter)
            number.setFixedWidth(18)
            number.setStyleSheet(f"color: {ACCENT}; font-size: 10px; font-weight: 700;")
            box = QComboBox()
            for name in self.available:
                box.addItem(tr(name), name)
            box.setCurrentIndex(self.available.index(current[slot]))
            box.currentIndexChanged.connect(lambda _=0, s=slot: self._chosen(s))
            self.boxes.append(box)
            grid.addWidget(number, row, column * 2)
            grid.addWidget(box, row, column * 2 + 1)
        self._remember()

        reset = QPushButton(tr("Ordre du catalogue"))
        reset.clicked.connect(self._reset)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.addButton(reset, QDialogButtonBox.ResetRole)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)
        root.addWidget(intro)
        root.addLayout(grid)
        root.addWidget(buttons)

    def _chosen(self, slot: int) -> None:
        """Un effet ne peut pas occuper deux pads : on échange les deux cases."""
        name = self.boxes[slot].currentData()
        for other, box in enumerate(self.boxes):
            if other != slot and box.currentData() == name:
                box.blockSignals(True)
                box.setCurrentIndex(self.available.index(self._previous[slot]))
                box.blockSignals(False)
                break
        self._remember()

    def _remember(self) -> None:
        self._previous = [box.currentData() for box in self.boxes]

    def showEvent(self, event) -> None:
        self._remember()
        super().showEvent(event)

    def _reset(self) -> None:
        for slot, box in enumerate(self.boxes):
            box.blockSignals(True)
            box.setCurrentIndex(slot)
            box.blockSignals(False)
        self._remember()

    def selection(self) -> list[str]:
        return [box.currentData() for box in self.boxes]
