"""Panneau central : crossfader (manuel ou automatique), master, strobe/flash/blackout."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from ..core.mixer import (
    BLEND_MODES, STROBE_DIVISIONS, Hold, Master, Mixer, speed_from_unit, speed_to_unit,
)
from ..i18n import tr
from .style import ACCENT_A, ACCENT_B, CROSSFADER_QSS, MUTED, section

STEPS = 1000
BEAT_CHOICES = (1, 2, 4, 8, 16, 32, 64)
LATCH_STYLE = "QPushButton:checked { background: %s; color: white; font-weight: bold; }"


class MasterPanel(QWidget):
    """Tout ce qui ne depend pas d'un deck en particulier."""

    brightness_changed = Signal(float)
    gain_changed = Signal(float)
    audio_device_changed = Signal(object)
    audio_channels_changed = Signal(list)
    tempo_scaled = Signal(float)
    tapped = Signal()

    def __init__(self, mixer: Mixer, master: Master, brightness: float, parent=None) -> None:
        super().__init__(parent)
        self.mixer = mixer
        self.master = master
        self.latches: dict[str, QPushButton] = {}
        self._syncing_audio = False

        # Ordre dicte par l'usage en cabine : ce qu'on touche en urgence est en
        # haut, atteignable sans defiler.
        layout = QVBoxLayout(self)
        layout.addWidget(self._crossfader_box())
        auto = self._auto_box()          # construit avant : _set_crossfade y fait appel
        layout.addWidget(self._audio_row())
        layout.addWidget(self._tempo_box())
        layout.addWidget(self._live_box())
        layout.addWidget(self._master_box(brightness))
        layout.addWidget(auto)
        layout.addWidget(self._electric_box())
        layout.addStretch(1)
        self.setMinimumWidth(300)
        self.setMaximumWidth(360)

    # --- crossfader --------------------------------------------------------

    def _crossfader_box(self) -> QGroupBox:
        self.crossfader = QSlider(Qt.Horizontal)
        self.crossfader.setRange(0, STEPS)
        self.crossfader.setValue(int(self.mixer.crossfade * STEPS))
        self.crossfader.valueChanged.connect(self._set_crossfade)
        self.crossfader.setStyleSheet(CROSSFADER_QSS)
        self.crossfader.setMinimumHeight(28)

        label_a = QLabel("A")
        label_a.setStyleSheet(f"color: {ACCENT_A}; font-weight: 800; letter-spacing: 1px;")
        label_b = QLabel("B")
        label_b.setStyleSheet(f"color: {ACCENT_B}; font-weight: 800; letter-spacing: 1px;")
        self.cross_readout = QLabel("100 / 0")
        self.cross_readout.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        labels = QHBoxLayout()
        labels.addWidget(label_a)
        labels.addStretch(1)
        labels.addWidget(self.cross_readout)
        labels.addStretch(1)
        labels.addWidget(label_b)

        # Le mode affiche est traduit, la valeur envoyee au mixer reste la cle.
        self.mode = QComboBox()
        for name in BLEND_MODES:
            self.mode.addItem(tr(name), name)
        self.mode.setCurrentIndex(list(BLEND_MODES).index(self.mixer.mode))
        self.mode.currentIndexChanged.connect(
            lambda i: setattr(self.mixer, "mode", self.mode.itemData(i)))

        box = QGroupBox(tr("Crossfader"))
        v = QVBoxLayout(box)
        v.addLayout(labels)
        v.addWidget(self.crossfader)
        v.addWidget(self.mode)
        return box

    def _set_crossfade(self, value: int) -> None:
        # Toucher le crossfader a la main reprend la main sur l'automatique.
        if self.auto_on.isChecked() and not self._syncing:
            self.auto_on.setChecked(False)
        self.mixer.crossfade = value / STEPS
        self.cross_readout.setText(f"{100 - value // 10} / {value // 10}")

    # --- crossfade automatique ---------------------------------------------

    def _auto_box(self) -> QGroupBox:
        self._syncing = False
        auto = self.mixer.auto

        self.auto_on = QCheckBox(tr("Crossfade auto, calé sur le tempo"))
        self.auto_on.toggled.connect(self._toggle_auto)

        self.auto_beats = QComboBox()
        self.auto_beats.addItems([str(b) for b in BEAT_CHOICES])
        self.auto_beats.setCurrentText(str(auto.beats))
        self.auto_beats.currentTextChanged.connect(lambda s: setattr(auto, "beats", int(s)))

        self.auto_fade = QSlider(Qt.Horizontal)
        self.auto_fade.setRange(0, 32)          # demi-pulsations
        self.auto_fade.setValue(int(auto.fade_beats * 2))
        self.auto_fade_label = QLabel(f"{auto.fade_beats:.1f}")
        self.auto_fade_label.setFixedWidth(40)
        self.auto_fade.valueChanged.connect(self._set_fade)

        self.auto_status = QLabel("—")

        grid = QGridLayout()
        grid.addWidget(QLabel(tr("Toutes les (pulsations)")), 0, 0)
        grid.addWidget(self.auto_beats, 0, 1)
        grid.addWidget(QLabel(tr("Transition (pulsations)")), 1, 0)
        fade_row = QHBoxLayout()
        fade_row.addWidget(self.auto_fade, 1)
        fade_row.addWidget(self.auto_fade_label)
        holder = QWidget()
        holder.setLayout(fade_row)
        grid.addWidget(holder, 1, 1)

        box = QGroupBox(tr("Automatique"))
        v = QVBoxLayout(box)
        v.addWidget(self.auto_on)
        v.addLayout(grid)
        v.addWidget(self.auto_status)
        return box

    def _toggle_auto(self, on: bool) -> None:
        if on:
            self.mixer.auto.arm(self.mixer)
        self.mixer.auto.enabled = on

    def _set_fade(self, value: int) -> None:
        self.mixer.auto.fade_beats = value / 2.0
        self.auto_fade_label.setText(f"{value / 2.0:.1f}")

    def sync_crossfader(self) -> None:
        """Recopie l'état du modèle, sans reboucler.

        Le crossfader peut bouger sans passer par ce curseur — automatique ou
        MIDI — et l'automatique peut être coupé par un geste sur le contrôleur.
        L'interface doit suivre dans les deux cas.
        """
        target = int(round(self.mixer.crossfade * STEPS))
        if self.crossfader.value() != target:
            self._syncing = True
            self.crossfader.setValue(target)
            self._syncing = False

        if self.auto_on.isChecked() != self.mixer.auto.enabled:
            self.auto_on.blockSignals(True)
            self.auto_on.setChecked(self.mixer.auto.enabled)
            self.auto_on.blockSignals(False)

        if self.mixer.auto.enabled:
            self.auto_status.setText(
                f"prochaine bascule dans {self.mixer.auto.beats_left} pulsation(s)")
        else:
            self.auto_status.setText("—")

    # --- master ------------------------------------------------------------

    def _master_box(self, brightness: float) -> QGroupBox:
        self.brightness = QSlider(Qt.Horizontal)
        self.brightness.setRange(0, STEPS)
        self.brightness.setValue(int(brightness * STEPS))
        self.brightness.valueChanged.connect(lambda v: self.brightness_changed.emit(v / STEPS))

        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(0, STEPS)
        self.speed.setValue(int(round(speed_to_unit(self.mixer.speed) * STEPS)))
        self.speed_label = QLabel(self._speed_text(self.mixer.speed))
        self.speed_label.setFixedWidth(52)
        self.speed.valueChanged.connect(self._set_speed)

        row = QHBoxLayout()
        row.addWidget(self.speed, 1)
        row.addWidget(self.speed_label)

        box = QGroupBox(tr("Master"))
        v = QVBoxLayout(box)
        v.addWidget(section(tr("Luminosité")))
        v.addWidget(self.brightness)
        v.addWidget(section(tr("Vitesse globale   ·   à fond à gauche = arrêt")))
        v.addLayout(row)
        return box

    @staticmethod
    def _speed_text(speed: float) -> str:
        return "arrêt" if speed <= 0.0 else f"x{speed:.2f}"

    def _set_speed(self, value: int) -> None:
        speed = speed_from_unit(value / STEPS)
        self.mixer.speed = speed
        self.speed_label.setText(self._speed_text(speed))

    # --- strobe / flash / blackout ------------------------------------------

    def _hold_row(self, grid: QGridLayout, row: int, key: str, label: str,
                  hold: Hold, shortcut: str, color: str) -> None:
        """Deux boutons pour une meme fonction : un verrou et un appui momentane."""
        latch = QPushButton(tr("On / Off"))
        latch.setCheckable(True)
        latch.toggled.connect(lambda on, h=hold: setattr(h, "latched", on))
        latch.setStyleSheet(LATCH_STYLE % color)
        self.latches[key] = latch

        momentary = QPushButton(tr("Momentané"))
        momentary.setToolTip(tr("Maintenir — raccourci : {}").format(tr(shortcut)))
        momentary.pressed.connect(lambda h=hold: setattr(h, "momentary", True))
        momentary.released.connect(lambda h=hold: setattr(h, "momentary", False))

        grid.addWidget(QLabel(f"{tr(label)} · {tr(shortcut)}"), row, 0)
        grid.addWidget(latch, row, 1)
        grid.addWidget(momentary, row, 2)

    def _live_box(self) -> QGroupBox:
        grid = QGridLayout()
        self._hold_row(grid, 0, "strobe", "Strobe", self.master.strobe, "S", "#c08000")
        self._hold_row(grid, 1, "electric", "Électrique", self.master.electric, "E", "#7dd3fc")
        self._hold_row(grid, 2, "flash", "Flash", self.master.flash, "espace", "#c0c0c0")
        self._hold_row(grid, 3, "blackout", "Blackout", self.master.blackout, "B", "#a01020")

        self.strobe_hz = QSlider(Qt.Horizontal)
        self.strobe_hz.setRange(1, 30)
        self.strobe_hz.setValue(int(self.master.strobe_hz))
        self.strobe_hz.valueChanged.connect(lambda v: setattr(self.master, "strobe_hz", float(v)))
        self.strobe_division = QComboBox()
        for label, value in STROBE_DIVISIONS:
            self.strobe_division.addItem(tr(label), value)
        self.strobe_division.setCurrentIndex(
            [v for _, v in STROBE_DIVISIONS].index(self.master.strobe_division))
        self.strobe_division.currentIndexChanged.connect(
            lambda i: setattr(self.master, "strobe_division",
                              float(self.strobe_division.itemData(i))))

        self.strobe_sync = QCheckBox(tr("Strobe calé sur le beat"))
        self.strobe_sync.toggled.connect(self._set_strobe_sync)

        self.audio_box = QCheckBox(tr("Son réactif"))
        self.audio_box.setToolTip(tr("Coupe la réaction au son de tous les effets"))
        self.audio_box.setChecked(self.master.audio_enabled)
        self.audio_box.toggled.connect(lambda on: setattr(self.master, "audio_enabled", on))
        self.strobe_division.setEnabled(self.master.strobe_sync)

        box = QGroupBox(tr("Live   ·   Maj + raccourci = verrou"))
        v = QVBoxLayout(box)
        v.addLayout(grid)
        v.addWidget(section(tr("Fréquence du strobe")))
        v.addWidget(self.strobe_hz)
        v.addWidget(self.strobe_sync)
        v.addWidget(self.strobe_division)
        v.addWidget(self.audio_box)
        return box

    @staticmethod
    def _meter(height: int) -> QProgressBar:
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setFixedHeight(height)
        return bar

    def _audio_row(self) -> QWidget:
        """Ligne compacte : niveau en direct, et un bouton vers les réglages.

        Les listes de périphériques et le gain ne servent qu'au moment de la
        configuration ; le niveau, lui, doit rester visible en permanence.
        """
        self.audio_meter = self._meter(8)
        self.audio_level_label = QLabel("—")
        self.audio_level_label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        self.audio_level_label.setFixedWidth(96)

        self.audio_settings = QPushButton("⚙")
        self.audio_settings.setFixedWidth(30)
        self.audio_settings.setToolTip(tr("Réglages de l'entrée audio"))
        self.audio_settings.clicked.connect(self._open_audio_dialog)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.audio_meter, 1)
        row.addWidget(self.audio_level_label)
        row.addWidget(self.audio_settings)

        # Les commandes vivent dans la fenêtre de réglages, montée à la demande.
        self.audio_device = QComboBox()
        self.audio_device.currentIndexChanged.connect(self._pick_device)
        self.audio_channels = QComboBox()
        self.audio_channels.currentIndexChanged.connect(self._pick_channels)
        self.audio_device_label = QLabel("—")
        self.audio_device_label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        self.gain = QSlider(Qt.Horizontal)
        self.gain.setRange(0, STEPS)
        self.gain.valueChanged.connect(self._set_gain)
        self.gain_label = QLabel("x1.0")
        self.gain_label.setFixedWidth(46)
        self.audio_meter_big = self._meter(14)
        self.audio_dialog = None

        holder = QWidget()
        holder.setLayout(row)
        return holder

    def _open_audio_dialog(self) -> None:
        if self.audio_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle(tr("Entrée audio"))
            dialog.setMinimumWidth(380)

            gain_row = QHBoxLayout()
            gain_row.addWidget(self.gain, 1)
            gain_row.addWidget(self.gain_label)
            gain_holder = QWidget()
            gain_holder.setLayout(gain_row)

            form = QFormLayout()
            form.addRow("Périphérique", self.audio_device)
            form.addRow("Voies", self.audio_channels)
            form.addRow("Gain d'entrée", gain_holder)

            layout = QVBoxLayout(dialog)
            layout.addLayout(form)
            layout.addWidget(self.audio_meter_big)
            layout.addWidget(self.audio_device_label)
            close = QPushButton(tr("Fermer"))
            close.clicked.connect(dialog.accept)
            layout.addWidget(close)
            self.audio_dialog = dialog
        self.audio_dialog.show()
        self.audio_dialog.raise_()

    def show_audio(self, device: str, dbfs: float, clipping: bool) -> None:
        self.audio_device_label.setText(device)
        unit = max(0.0, min(1.0, (dbfs + 60.0) / 60.0))
        color = "#d05050" if clipping else ("#d08a20" if dbfs > -6 else "#3fb950")
        style = ("QProgressBar{border:none; border-radius:4px; background:#23262f;}"
                 f"QProgressBar::chunk{{border-radius:4px; background:{color};}}")
        for bar in (self.audio_meter, self.audio_meter_big):
            bar.setValue(int(unit * 100))
            bar.setStyleSheet(style)
        text = ("SATURÉ" if clipping else (f"{dbfs:.0f} dBFS" if dbfs > -99 else "silence"))
        self.audio_level_label.setText(text)

    def _pick_device(self, index: int) -> None:
        if self._syncing_audio or index < 0:
            return
        self.audio_device_changed.emit(self.audio_device.itemData(index))

    def _pick_channels(self, index: int) -> None:
        if self._syncing_audio or index < 0:
            return
        self.audio_channels_changed.emit(list(self.audio_channels.itemData(index) or []))

    def set_audio_devices(self, devices, current_index) -> None:
        """Remplit la liste des entrées, sans écraser un choix en cours."""
        wanted = [(d.name, d.index) for d in devices]
        existing = [(self.audio_device.itemText(i), self.audio_device.itemData(i))
                    for i in range(self.audio_device.count())]
        if wanted == existing and self.audio_device.currentData() == current_index:
            return
        self._syncing_audio = True
        self.audio_device.clear()
        for name, index in wanted:
            self.audio_device.addItem(name, index)
        position = next((i for i, (_, ix) in enumerate(wanted) if ix == current_index), -1)
        if position >= 0:
            self.audio_device.setCurrentIndex(position)
        self._syncing_audio = False

    def set_audio_channels(self, available: int, selected) -> None:
        """Propose les paires d'entrées de la carte (1-2, 3-4, …)."""
        pairs = [list(range(i, min(i + 2, available))) for i in range(0, available, 2)]
        labels = ["voies " + "-".join(str(c + 1) for c in pair) for pair in pairs]
        existing = [self.audio_channels.itemText(i) for i in range(self.audio_channels.count())]
        self.audio_channels.setVisible(available > 2)
        if labels == existing:
            wanted = next((i for i, pair in enumerate(pairs) if pair == list(selected)), -1)
            if wanted >= 0 and self.audio_channels.currentIndex() != wanted:
                self._syncing_audio = True
                self.audio_channels.setCurrentIndex(wanted)
                self._syncing_audio = False
            return
        self._syncing_audio = True
        self.audio_channels.clear()
        for label, pair in zip(labels, pairs):
            self.audio_channels.addItem(label, pair)
        position = next((i for i, pair in enumerate(pairs) if pair == list(selected)), 0)
        self.audio_channels.setCurrentIndex(position)
        self._syncing_audio = False

    @staticmethod
    def _gain_from_unit(x: float) -> float:
        return 0.25 * (64.0 ** min(1.0, max(0.0, x)))      # x0,25 a x16

    @staticmethod
    def _gain_to_unit(gain: float) -> float:
        return min(1.0, max(0.0, math.log(max(0.05, gain) / 0.25) / math.log(64.0)))

    def set_gain_value(self, gain: float) -> None:
        self.gain.blockSignals(True)
        self.gain.setValue(int(round(self._gain_to_unit(gain) * STEPS)))
        self.gain.blockSignals(False)
        self.gain_label.setText(f"x{gain:.2f}" if gain < 10 else f"x{gain:.1f}")

    def _set_gain(self, value: int) -> None:
        gain = self._gain_from_unit(value / STEPS)
        self.gain_label.setText(f"x{gain:.2f}" if gain < 10 else f"x{gain:.1f}")
        self.gain_changed.emit(gain)

    def show_audio(self, device: str, dbfs: float, clipping: bool) -> None:
        self.audio_device_label.setText(device)
        unit = max(0.0, min(1.0, (dbfs + 60.0) / 60.0))
        self.audio_meter.setValue(int(unit * 100))
        color = "#d05050" if clipping else ("#d08a20" if dbfs > -6 else "#3fb950")
        self.audio_meter.setStyleSheet(
            "QProgressBar{border:none; border-radius:5px; background:#23262f;}"
            f"QProgressBar::chunk{{border-radius:5px; background:{color};}}")
        self.audio_level_label.setText(
            ("SATURÉ  ·  " if clipping else "") + (f"{dbfs:.0f} dBFS" if dbfs > -99 else "silence"))

    def _tempo_box(self) -> QGroupBox:
        """Tempo : lecture, correction d'octave et tap, à portée de main.

        La détection se verrouille parfois sur le double du tempo réel ; il faut
        pouvoir la corriger pendant le morceau, pas dans les réglages.
        """
        self.bpm_label = QLabel("—")
        self.bpm_label.setStyleSheet(
            f"color:{ACCENT_A}; font-size:20px; font-weight:800; letter-spacing:1px;")
        self.bpm_detail = QLabel("")
        self.bpm_detail.setStyleSheet(f"color:{MUTED}; font-size:11px;")

        half = QPushButton("÷ 2")
        half.setToolTip(tr("Le tempo détecté est deux fois trop rapide"))
        half.clicked.connect(lambda: self.tempo_scaled.emit(0.5))
        double = QPushButton("× 2")
        double.setToolTip(tr("Le tempo détecté est deux fois trop lent"))
        double.clicked.connect(lambda: self.tempo_scaled.emit(2.0))
        tap = QPushButton("Tap")
        tap.setToolTip(tr("Donner le tempo à la main"))
        tap.clicked.connect(self.tapped.emit)

        row = QHBoxLayout()
        row.addWidget(self.bpm_label)
        row.addStretch(1)
        row.addWidget(half)
        row.addWidget(double)
        row.addWidget(tap)

        box = QGroupBox(tr("Tempo"))
        v = QVBoxLayout(box)
        v.addLayout(row)
        v.addWidget(self.bpm_detail)
        return box

    def show_tempo(self, bpm: float, confidence: float, octave: float,
                   measured: float = 0.0) -> None:
        self.bpm_label.setText(f"{bpm:.1f}" if bpm > 0 else "—")
        note = f"confiance {confidence:.2f}"
        if measured > 0:
            # Impulsions réellement émises : si ce nombre vaut le double du BPM,
            # l'analyse annonce le bon tempo mais bat deux fois par pulsation.
            note += f"  ·  {measured:.0f} impulsions/min"
        if abs(octave - 1.0) > 0.01:
            note += f"  ·  corrigé × {octave:g}"
        self.bpm_detail.setText(note)

    def _set_strobe_sync(self, on: bool) -> None:
        self.master.strobe_sync = on
        # Une seule des deux commandes a du sens a la fois.
        self.strobe_hz.setEnabled(not on)
        self.strobe_division.setEnabled(on)

    def _electric_box(self):
        """Reglages de la surcouche electrique (memes parametres que l'effet)."""
        from .deck_panel import ParamsForm

        form = ParamsForm()
        form.show_effect(self.master.electric_fx)
        box = QGroupBox(tr("Réglages de l'électrique"))
        QVBoxLayout(box).addWidget(form)
        return box
