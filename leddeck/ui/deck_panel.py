"""Panneau d'un deck : apercu, effets en vignettes, reglages, palettes."""

from __future__ import annotations

import math

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget,
)

from ..core.mixer import CUSTOM_NAME, MAX_CUSTOM_COLORS, Deck
from .preview import MatrixPreview
from ..i18n import tr
from .style import DECK_QSS, section
from .thumbnails import EFFECT_H, EFFECT_W, PALETTE_H, PALETTE_W, effect_pixmap, palette_pixmap

SLIDER_STEPS = 1000


class IconGrid(QListWidget):
    """Grille de vignettes dont la hauteur suit le nombre reel de colonnes.

    Le nombre de colonnes depend de la largeur disponible : figer une hauteur
    calculee a l'avance laissait des rangees vides en bas.
    """

    def __init__(self, icon_w: int, icon_h: int, label_h: int, max_rows: int | None = None,
                 columns: int | None = None):
        super().__init__()
        self.max_rows = max_rows
        # Colonnes figees : la grille reproduit alors celle du controleur MIDI,
        # ou le meme pad se trouve au meme endroit.
        self.columns = columns
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(icon_w, icon_h))
        self.setGridSize(QSize(icon_w + 16, icon_h + label_h))
        self.setMovement(QListWidget.Static)
        self.setResizeMode(QListWidget.Adjust)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QListWidget.ScrollPerItem)
        self.setSelectionMode(QListWidget.SingleSelection)
        # Pas d'espacement quand le nombre de colonnes est impose : Qt l'ajoute
        # entre les cellules et en fait alors tenir une de moins que prevu.
        self.setSpacing(0 if columns else 2)
        if columns:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(icon_h + label_h + 14)

    def fit_height(self) -> None:
        grid = self.gridSize()
        if self.columns:
            extra = 2 * self.frameWidth() + 6
            if self.verticalScrollBarPolicy() != Qt.ScrollBarAlwaysOff:
                extra += self.verticalScrollBar().sizeHint().width()
            self.setFixedWidth(self.columns * grid.width() + extra)
            columns = self.columns
        else:
            columns = max(1, self.viewport().width() // max(1, grid.width()))
        rows = max(1, math.ceil(self.count() / columns))
        if self.max_rows:
            rows = min(rows, self.max_rows)
        height = rows * grid.height() + 14
        # Ne toucher a la geometrie que si elle change reellement. Un
        # setFixedHeight relance la mise en page : avec l'ascenseur du panneau,
        # la boucle largeur -> colonnes -> hauteur -> ascenseur -> largeur peut
        # se mettre a osciller (visible en passant en plein ecran).
        if height != self.maximumHeight():
            self.setFixedHeight(height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        #Recalcul differe : changer la hauteur pendant le resize relance une
        # mise en page imbriquee.
        QTimer.singleShot(0, self.fit_height)


class ParamsForm(QWidget):
    """Un curseur par reglage de l'effet, reconstruit a chaque changement d'effet."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._form = QFormLayout(self)
        self._form.setContentsMargins(4, 4, 4, 4)
        self._effect = None
        self._widgets: dict[str, tuple] = {}

    def sync(self) -> None:
        """Recopie les valeurs du modèle : le MIDI modifie les réglages aussi."""
        effect = self._effect
        if effect is None:
            return
        for key, (widget, label) in self._widgets.items():
            if isinstance(widget, QCheckBox):
                wanted = effect.p[key] >= 0.5
                if widget.isChecked() != wanted:
                    widget.blockSignals(True)
                    widget.setChecked(wanted)
                    widget.blockSignals(False)
                continue
            target = int(round(effect.p.normalized(key) * SLIDER_STEPS))
            if abs(widget.value() - target) > 1:
                widget.blockSignals(True)
                widget.setValue(target)
                widget.blockSignals(False)
                label.setText(f"{effect.p[key]:.2f}")

    def show_effect(self, effect) -> None:
        self._effect = effect
        self._widgets = {}
        while self._form.rowCount():
            self._form.removeRow(0)
        if effect is None:
            return
        for key in effect.p:
            if effect.p.specs[key].is_switch:
                box = QCheckBox()
                box.setChecked(effect.p[key] >= 0.5)
                box.toggled.connect(lambda on, k=key, fx=effect: fx.p.__setitem__(k, 1.0 if on else 0.0))
                self._form.addRow(tr(key), box)
                self._widgets[key] = (box, None)
                continue
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, SLIDER_STEPS)
            slider.setValue(int(effect.p.normalized(key) * SLIDER_STEPS))
            value = QLabel(f"{effect.p[key]:.2f}")
            value.setFixedWidth(46)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(slider, 1)
            row.addWidget(value)
            holder = QWidget()
            holder.setLayout(row)

            def on_change(v, k=key, lab=value, fx=effect):
                fx.p.set_normalized(k, v / SLIDER_STEPS)
                lab.setText(f"{fx.p[k]:.2f}")

            slider.valueChanged.connect(on_change)
            self._form.addRow(tr(key), holder)
            self._widgets[key] = (slider, value)


class ColorButton(QPushButton):
    """Bouton affichant sa couleur, qui ouvre le selecteur RGB du systeme.

    Le selecteur reste ouvert et previent a chaque mouvement (`currentColorChanged`) :
    on voit la couleur changer sur les bandeaux pendant qu'on la choisit.
    """

    color_changed = Signal(tuple)

    def __init__(self, label: str, rgb: tuple[float, float, float], parent=None) -> None:
        super().__init__(label, parent)
        self._label = label
        self._rgb = tuple(rgb)
        self._dialog = None
        self._restyle()
        self.clicked.connect(self._open)

    @property
    def rgb(self) -> tuple[float, float, float]:
        return self._rgb

    def _open(self) -> None:
        dialog = QColorDialog(QColor.fromRgbF(*self._rgb), self)
        dialog.setWindowTitle(self._label)
        dialog.currentColorChanged.connect(self._from_qcolor)
        dialog.open()
        self._dialog = dialog          # garder une reference : sinon il se ferme aussitot

    def _from_qcolor(self, color: QColor) -> None:
        if not color.isValid():
            return
        self._rgb = (color.redF(), color.greenF(), color.blueF())
        self._restyle()
        self.color_changed.emit(self._rgb)

    def set_rgb(self, rgb) -> None:
        self._rgb = tuple(float(v) for v in rgb)
        self._restyle()
        self.color_changed.emit(self._rgb)

    def _restyle(self) -> None:
        r, g, b = (int(round(v * 255)) for v in self._rgb)
        fg = "black" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "white"
        self.setStyleSheet(f"background: rgb({r},{g},{b}); color: {fg}; padding: 6px;")


class CustomPaletteEditor(QWidget):
    """Palette perso : autant de couleurs qu'on veut, franches par defaut.

    Les couleurs sont des paliers, pas un degrade : deux couleurs choisies
    sortent telles quelles. La case « Degrade » retablit l'interpolation.
    """

    changed = Signal()
    MAX_COLORS = MAX_CUSTOM_COLORS

    def __init__(self, deck, parent=None) -> None:
        super().__init__(parent)
        self.deck = deck

        self._colors_row = QHBoxLayout()
        self._colors_row.setContentsMargins(0, 0, 0, 0)
        self._colors_row.setSpacing(4)
        colors_holder = QWidget()
        colors_holder.setLayout(self._colors_row)

        self.add = QPushButton("+")
        self.add.setFixedWidth(34)
        self.add.setToolTip(tr("Ajouter une couleur"))
        self.add.clicked.connect(self._add)

        self.remove = QPushButton("−")
        self.remove.setFixedWidth(34)
        self.remove.setToolTip(tr("Supprimer la derniere couleur"))
        self.remove.clicked.connect(self._remove)

        controls = QHBoxLayout()
        controls.addWidget(self.add)
        controls.addWidget(self.remove)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(colors_holder)
        layout.addLayout(controls)
        self._rebuild()

    # --- edition ----------------------------------------------------------

    def _rebuild(self) -> None:
        while self._colors_row.count():
            item = self._colors_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, rgb in enumerate(self.deck.custom.colors):
            button = ColorButton(str(index + 1), rgb)
            button.setToolTip(tr("Couleur {}").format(index + 1))
            button.color_changed.connect(lambda c, i=index: self._set_color(i, c))
            self._colors_row.addWidget(button, 1)
        self.add.setEnabled(len(self.deck.custom.colors) < self.MAX_COLORS)
        self.remove.setEnabled(len(self.deck.custom.colors) > 1)

    def _apply(self, colors) -> None:
        self.deck.custom.set_colors(colors)
        self.changed.emit()

    def _set_color(self, index: int, rgb) -> None:
        colors = list(self.deck.custom.colors)
        colors[index] = rgb
        self._apply(colors)

    def _add(self) -> None:
        colors = list(self.deck.custom.colors)
        if len(colors) >= self.MAX_COLORS:
            return
        colors.append(colors[-1])      # copie la derniere : on la retouche ensuite
        self._apply(colors)
        self._rebuild()

    def _remove(self) -> None:
        colors = list(self.deck.custom.colors)
        if len(colors) <= 1:
            return
        colors.pop()
        self._apply(colors)
        self._rebuild()


class DeckPanel(QWidget):
    """Apercu du deck, effets en vignettes, reglages juste dessous, puis palettes."""

    def __init__(self, deck: Deck, accent: str, parent=None) -> None:
        super().__init__(parent)
        self.deck = deck
        self.accent = accent
        self.setStyleSheet(DECK_QSS.format(accent=accent))

        title = QLabel(f"DECK {deck.name}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color: {accent}; font-weight: 800; font-size: 14px; letter-spacing: 2px;")

        # Previsualisation du deck seul : c'est tout l'interet d'avoir deux decks,
        # preparer un effet sans l'envoyer sur les bandeaux.
        self.preview = MatrixPreview(deck.strips, deck.leds, compact=True)

        self.effects = IconGrid(EFFECT_W, EFFECT_H, 22, columns=4)
        for name in deck.effects:
            item = QListWidgetItem(QIcon(), tr(name))
            item.setData(Qt.UserRole, name)
            self.effects.addItem(item)
        self.effects.setCurrentRow(list(deck.effects).index(deck.effect_name))
        self.effects.currentRowChanged.connect(self._choose_effect)

        self.palettes = IconGrid(PALETTE_W, PALETTE_H, 22, max_rows=4, columns=4)
        for name, pal in deck.palettes.items():
            item = QListWidgetItem(QIcon(palette_pixmap(pal)), tr(name))
            item.setData(Qt.UserRole, name)
            self.palettes.addItem(item)
        self.palettes.setCurrentRow(list(deck.palettes).index(deck.palette_name))
        self.palettes.currentRowChanged.connect(self._choose_palette)

        # Les reglages suivent immediatement les effets : ce sont ceux de l'effet choisi.
        self.params = ParamsForm()
        self.params.show_effect(deck.effect)

        self.custom_editor = CustomPaletteEditor(deck)
        self.custom_editor.changed.connect(self._update_custom)

        # Effets à gauche sur 4 colonnes — comme le contrôleur — et les réglages
        # de l'effet choisi juste à droite, visibles en même temps.
        effects_column = QVBoxLayout()
        effects_column.setContentsMargins(0, 0, 0, 0)
        effects_column.addWidget(section(tr("Effets")))
        effects_column.addWidget(self.effects)
        effects_column.addStretch(1)
        effects_holder = QWidget()
        effects_holder.setLayout(effects_column)

        self.params_title = section(
            tr("Réglages · {}").format(tr(deck.effect_name)))
        params_column = QVBoxLayout()
        params_column.setContentsMargins(0, 0, 0, 0)
        params_column.addWidget(self.params_title)
        params_column.addWidget(self.params)
        params_column.addStretch(1)
        params_holder = QWidget()
        params_holder.setLayout(params_column)
        params_holder.setMinimumWidth(168)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(10)
        middle.addWidget(effects_holder)
        middle.addWidget(params_holder, 1)

        presets_tab = QWidget()
        presets_layout = QVBoxLayout(presets_tab)
        presets_layout.setContentsMargins(4, 4, 4, 4)
        presets_layout.addWidget(self.palettes)

        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        custom_layout.setContentsMargins(4, 4, 4, 4)
        custom_layout.addWidget(self.custom_editor)
        custom_layout.addStretch(1)

        self.palette_tabs = QTabWidget()
        self.palette_tabs.addTab(presets_tab, tr("Presets"))
        self.palette_tabs.addTab(custom_tab, tr("Perso"))

        self.interpolation = QCheckBox(tr("Interpolation (dégradé entre les couleurs)"))
        self.interpolation.setChecked(deck.palette.smooth)
        self.interpolation.toggled.connect(self._set_interpolation)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(self.preview)
        layout.addLayout(middle)
        layout.addWidget(section(tr("Palettes")))
        layout.addWidget(self.palette_tabs)
        layout.addWidget(self.interpolation)
        layout.addStretch(1)
        # Largeur minimale = grille 4 colonnes + colonne des réglages, sinon la
        # dernière colonne de vignettes est rognée.
        self.setMinimumWidth(4 * (EFFECT_W + 16) + 200)
        self.setMaximumWidth(4 * (EFFECT_W + 16) + 320)

        self.refresh_thumbnails()

    # --- vignettes ---------------------------------------------------------

    def refresh_thumbnails(self) -> None:
        """Redessine les vignettes d'effets avec la palette courante du deck."""
        palette = self.deck.palette
        for row in range(self.effects.count()):
            item = self.effects.item(row)
            effect = self.deck.effects.get(item.data(Qt.UserRole))
            if effect is not None:
                item.setIcon(QIcon(effect_pixmap(type(effect), palette)))

    # --- choix -------------------------------------------------------------

    def _choose_effect(self, row: int) -> None:
        item = self.effects.item(row)
        if item is None:
            return
        name = item.data(Qt.UserRole)
        self.deck.set_effect(name)
        self.params.show_effect(self.deck.effect)
        self.params_title.setText(tr("Réglages · {}").format(tr(name)))

    def _choose_palette(self, row: int) -> None:
        item = self.palettes.item(row)
        if item is None:
            return
        self.deck.set_palette(item.data(Qt.UserRole))
        self.interpolation.blockSignals(True)
        self.interpolation.setChecked(self.deck.palette.smooth)
        self.interpolation.blockSignals(False)
        self.refresh_thumbnails()

    def _set_interpolation(self, on: bool) -> None:
        self.deck.palette.smooth = on
        self._refresh_swatch(self.deck.palette_name, self.deck.palette)
        self.refresh_thumbnails()

    def _refresh_swatch(self, name: str, palette) -> None:
        for item in self.palettes.findItems(name, Qt.MatchExactly):
            item.setIcon(QIcon(palette_pixmap(palette)))

    def _update_custom(self, *_) -> None:
        """Toute retouche de la palette perso bascule le deck dessus."""
        items = self.palettes.findItems(CUSTOM_NAME, Qt.MatchExactly)
        if items:
            items[0].setIcon(QIcon(palette_pixmap(self.deck.custom)))
            self.palettes.setCurrentRow(self.palettes.row(items[0]))
        self.refresh_thumbnails()
