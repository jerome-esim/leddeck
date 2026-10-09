"""Fenetre principale (etape 5) : deux decks, crossfader, master.

Le moteur tourne dans son thread a 40 fps et alimente les bandeaux ; l'interface
se contente de lire la derniere frame a 30 fps. Si l'UI rame, les LED ne bougent pas.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.config import Profile
from ..core.engine import Engine
from ..core.mixer import Master, Mixer
from ..output.patch import OutputStage
from .deck_panel import DeckPanel
from .install_page import InstallPage
from .master_panel import MasterPanel
from .preview import MatrixPreview
from ..i18n import LANGUAGES, language, set_language, tr
from .style import ACCENT_A, ACCENT_B, MUTED, apply_theme


class MainWindow(QMainWindow):
    def __init__(self, profile: Profile, audio_device=None, use_audio: bool = True,
                 midi_mapping: str | None = "apcmini-mk2", page: int = 0) -> None:
        super().__init__()
        self.profile = profile
        self.stage = OutputStage(profile, keep_frame=True)
        self.mixer = Mixer(profile.leds, profile.strips, keep_frames=True)
        self.master = Master(profile.leds, profile.strips)
        # Deux decks sur le meme effet des le depart serait deroutant : on decale.
        names = list(self.mixer.b.effects)
        if len(names) > 1:
            self.mixer.b.set_effect(names[1])
        pals = list(self.mixer.b.palettes)
        if len(pals) > 3:
            self.mixer.b.set_palette(pals[3])

        # Etat declare avant toute ouverture : _start_audio s'en sert.
        self.audio = None
        self.analyzer = None
        self.midi = None
        self.wanted_audio = None
        self.audio_fallback = False
        self._beat_marks: list[tuple[float, int]] = []
        # Mémoire occupée : l'application a déjà été tuée deux fois par le système
        # faute de mémoire. Sans mesure, impossible de distinguer une fuite d'une
        # machine saturée par d'autres logiciels.
        self._memory_mb = 0.0
        self._memory_start = 0.0
        self._memory_at = 0.0

        # « --no-audio » est un choix, pas une panne : la surveillance ne doit
        # pas rouvrir une entree que l'on a demande de laisser fermee.
        self.audio_off = not use_audio
        if use_audio:
            self._start_audio(audio_device)
        if midi_mapping:
            self._start_midi(midi_mapping)

        self._build_ui()
        self._show_page(page)
        self.engine = Engine(self._render, self.stage, fps=profile.fps)
        self.engine.start()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(33)

        # Surveillance de l'entrée audio : rebranchée, elle doit repartir seule.
        self._audio_watchdog = QTimer(self)
        self._audio_watchdog.timeout.connect(self._check_audio)
        self._audio_watchdog.start(3000)

    # --- audio ------------------------------------------------------------

    def _start_audio(self, device=None) -> None:
        """Ouvre l'entrée demandée, ou celle par défaut si elle est absente.

        Démarrer sans aucun son parce qu'une carte n'est pas branchée serait
        pénalisant : on prend ce qui existe, on le dit, et on bascule sur la
        bonne carte dès qu'elle apparaît.
        """
        from ..audio.analysis import Analyzer
        from ..audio.input import AudioInput

        if device or self.wanted_audio is None:
            self.wanted_audio = device or (self.profile.audio_device or None)
        if self.analyzer is None:
            self.analyzer = Analyzer()
        for target, fallback in ((self.wanted_audio, False), (None, True)):
            if target is None and not fallback:
                continue
            try:
                audio = AudioInput(device=target, on_block=self.analyzer.process,
                                   channels=self.profile.audio_channels)
                audio.start()
            except Exception as exc:
                if not fallback:
                    print(tr("[audio] « {} » indisponible : {}").format(target, exc))
                    continue
                print(tr("[audio] aucune entrée disponible : {}").format(exc))
                self.audio = None
                return
            self.audio = audio
            self.audio.gain = self.profile.audio_gain
            self.analyzer.__init__(audio.samplerate, audio.blocksize)
            self.audio_fallback = fallback
            print(f"[audio] {audio.device_name} — {audio.samplerate} Hz"
                  + (tr("  (repli)") if fallback else ""))
            return

    # --- MIDI -------------------------------------------------------------

    def _start_midi(self, mapping_name: str) -> None:
        try:
            from ..midi.actions import build_actions
            from ..midi.controller import MidiController
            from ..midi.mapping import Mapping
            from ..midi.midi import find_port, input_ports

            mapping = Mapping.load(mapping_name)
            if find_port(input_ports(), mapping.port or None) is None:
                print(tr("[midi] aucun contrôleur trouvé"))
                return
            actions = build_actions(self.mixer, self.master, self.profile, self.analyzer)
            self.midi = MidiController(mapping, actions, port=mapping.port or None)
            self.midi.start()
            print(tr("[midi] {} — mapping « {} », {} assignation(s)").format(self.midi.link.input_name, mapping.name, len(mapping.bindings)))
        except Exception as exc:
            print(tr("[midi] indisponible : {!r}").format(exc))
            self.midi = None

    def _audio_state(self):
        if self.analyzer is None or not self.master.audio_enabled:
            return None
        # Carte débranchée : on repasse en « pas de son » plutôt que de laisser
        # les effets figés sur la dernière analyse reçue.
        if self.audio is not None and not self.audio.alive:
            return None
        return self.analyzer.state()

    # --- rendu ------------------------------------------------------------

    def _render(self, t: float, dt: float):
        # Un seul moteur pour les deux pages : c'est ce qui permet de les reunir
        # dans la meme fenetre sans que deux flux DDP se marchent dessus.
        if self.pages.currentWidget() is self.install:
            return self.install.render(t, dt)
        audio = self._audio_state()
        frame = self.mixer.render(t, dt, audio)
        # La surcouche electrique emprunte la palette du deck dominant : elle suit
        # les couleurs de ce qui joue quand on baisse sa « blancheur ».
        palette = self.mixer.a.palette if self.mixer.crossfade < 0.5 else self.mixer.b.palette
        return self.master.apply(frame, t, dt, audio, palette)

    # --- interface --------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle(f"leddeck — {self.profile.name}")
        self._build_live_page()

        self.install = InstallPage(self.profile, self.stage)
        self.install.matrix_changed.connect(self._rebuild_matrix)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.live_page)
        self.pages.addWidget(self.install)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._nav_bar())
        root.addWidget(self.pages, 1)
        holder = QWidget()
        holder.setLayout(root)
        self.setCentralWidget(holder)
        self.resize(1240, 880)

    def _build_live_page(self) -> None:
        self.preview = MatrixPreview(self.profile.strips, self.profile.leds)
        self.preview.setMinimumHeight(170)
        mix_title = QLabel(tr("SORTIE  ·  mélange des deux decks"))
        mix_title.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.2px;")

        self.deck_a = DeckPanel(self.mixer.a, ACCENT_A)
        self.deck_b = DeckPanel(self.mixer.b, ACCENT_B)
        self.master_panel = MasterPanel(self.mixer, self.master, self.profile.brightness)
        self.master_panel.brightness_changed.connect(self._set_brightness)
        self.master_panel.tempo_scaled.connect(self._scale_tempo)
        self.master_panel.tapped.connect(self._tap)
        self.master_panel.gain_changed.connect(self._set_gain)
        self.master_panel.audio_device_changed.connect(self._choose_audio_device)
        self.master_panel.audio_channels_changed.connect(self._choose_audio_channels)
        self.master_panel.set_gain_value(self.profile.audio_gain)
        if self.audio is not None:
            self.audio.gain = self.profile.audio_gain
        self.master_panel.audio_box.setChecked(self.analyzer is not None)
        self.master_panel.audio_box.setEnabled(self.analyzer is not None)

        # Les decks sont defilants : sur un petit ecran, rien n'est inaccessible.
        # Les colonnes ont une largeur plafonnee ; en plein ecran, le surplus va
        # sur les cotes plutot que d'etirer les panneaux.
        middle = QHBoxLayout()
        middle.addStretch(1)
        middle.addWidget(self._scrollable(self.deck_a), 4)
        middle.addWidget(self._scrollable(self.master_panel), 2)
        middle.addWidget(self._scrollable(self.deck_b), 4)
        middle.addStretch(1)

        self.status = QLabel("")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setStyleSheet(f"color: {MUTED}; font-size: 11px;")

        live = QVBoxLayout()
        live.setContentsMargins(14, 8, 14, 10)
        live.setSpacing(8)
        live.addWidget(mix_title)
        live.addWidget(self.preview, 1)
        live.addLayout(middle, 3)
        live.addWidget(self.status)
        self.live_page = QWidget()
        self.live_page.setLayout(live)

    def _nav_bar(self) -> QWidget:
        """Bascule entre les deux pages. Le moteur, lui, ne bascule pas."""
        bar = QHBoxLayout()
        bar.setContentsMargins(14, 8, 14, 0)
        bar.setSpacing(6)
        self.nav_buttons = []
        for index, label in enumerate(("Live", "Installation")):
            button = QPushButton(tr(label))
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setMinimumWidth(110)
            button.clicked.connect(lambda _=False, i=index: self._show_page(i))
            self.nav_buttons.append(button)
            bar.addWidget(button)
        bar.addStretch(1)
        self.lang_box = QComboBox()
        for code, label in LANGUAGES.items():
            self.lang_box.addItem(label, code)
        self.lang_box.setCurrentIndex(list(LANGUAGES).index(language()))
        self.lang_box.currentIndexChanged.connect(
            lambda i: self._set_language(self.lang_box.itemData(i)))
        bar.addWidget(self.lang_box)
        pads = QPushButton(tr("Effets du contrôleur…"))
        pads.setObjectName("nav")
        pads.clicked.connect(self._edit_pad_effects)
        bar.addWidget(pads)
        self.nav_note = QLabel("")
        self.nav_note.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        bar.addWidget(self.nav_note)
        holder = QWidget()
        holder.setLayout(bar)
        return holder

    def _set_language(self, code: str) -> None:
        """Change la langue et reconstruit l'interface.

        Les libellés sont posés à la construction des widgets : les retraduire un
        par un demanderait de tous les retrouver. Reconstruire est plus simple, et
        ne coûte que la page installation, qui se recharge d'elle-même.
        """
        if code == language():
            return
        set_language(code)
        self.profile.language = code
        try:
            self.profile.save()
        except Exception as exc:
            print(tr("[profil] enregistrement impossible : {!r}").format(exc))
        page = self.pages.currentIndex()
        self.install.shutdown()
        self._build_ui()
        self._show_page(page)

    def _edit_pad_effects(self) -> None:
        """Choisit les effets posés sur les pads : il y en a plus que de pads."""
        from .pads_dialog import PadEffectsDialog

        dialog = PadEffectsDialog(self.profile, list(self.mixer.a.effects), self)
        if dialog.exec() != PadEffectsDialog.Accepted:
            return
        self.profile.fav_effects = dialog.selection()
        # Les actions MIDI relisent le profil a chaque appui : rien a reconstruire,
        # les pads suivent des le prochain rafraichissement des LED.
        try:
            self.profile.save()
        except Exception as exc:
            print(tr("[profil] enregistrement impossible : {!r}").format(exc))

    def _show_page(self, index: int) -> None:
        for i, button in enumerate(self.nav_buttons):
            button.blockSignals(True)
            button.setChecked(i == index)
            button.blockSignals(False)
        self.pages.setCurrentIndex(index)
        self.install.activate(index == 1)
        self.nav_note.setText(
            tr("les bandeaux suivent les motifs d'installation") if index == 1 else "")

    def _rebuild_matrix(self) -> None:
        """La taille de matrice a change : effets, master et apercus la suivent.

        Les effets sont dimensionnes a la construction ; les recreer est plus sur
        que de les redimensionner un par un.
        """
        self.stage.reload()
        self.mixer = Mixer(self.profile.leds, self.profile.strips, keep_frames=True)
        self.master = Master(self.profile.leds, self.profile.strips)
        old = self.live_page
        self._build_live_page()
        self.pages.insertWidget(0, self.live_page)
        old.setParent(None)
        old.deleteLater()
        if self.midi is not None:
            from ..midi.actions import build_actions
            self.midi.actions = build_actions(
                self.mixer, self.master, self.profile, self.analyzer)

    @staticmethod
    def _scrollable(widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidget(widget)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Un QScrollArea ne reprend pas les largeurs de son contenu : sans cela il
        # se laisse ecraser et le panneau se retrouve tronque. On prend la largeur
        # reellement exigee par la mise en page, pas un minimum fixe a la main.
        needed = max(widget.minimumWidth(), widget.minimumSizeHint().width(),
                     widget.sizeHint().width())
        area.setMinimumWidth(needed + 16)
        area.setMaximumWidth(widget.maximumWidth() + 16)
        return area

    def _memory(self) -> float:
        """Mémoire résidente du processus, en Mo. Relevée toutes les 5 s."""
        import subprocess
        import time as _time

        now = _time.monotonic()
        if now - self._memory_at < 5.0 and self._memory_mb:
            return self._memory_mb
        self._memory_at = now
        try:
            out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                                 capture_output=True, text=True, timeout=1.0)
            self._memory_mb = int(out.stdout.strip() or 0) / 1024.0
        except Exception:
            return self._memory_mb
        if not self._memory_start:
            self._memory_start = self._memory_mb
        return self._memory_mb

    def _measured_beat_rate(self, beat_count: int) -> float:
        """Impulsions par minute réellement émises, sur les 10 dernières secondes."""
        import time as _time

        now = _time.monotonic()
        self._beat_marks.append((now, beat_count))
        while self._beat_marks and now - self._beat_marks[0][0] > 10.0:
            self._beat_marks.pop(0)
        if len(self._beat_marks) < 2:
            return 0.0
        span = now - self._beat_marks[0][0]
        beats = beat_count - self._beat_marks[0][1]
        return (beats / span * 60.0) if span > 3.0 and beats > 0 else 0.0

    def _check_audio(self) -> None:
        """Rétablit l'entrée perdue, et récupère la carte voulue dès qu'elle arrive."""
        from ..audio.input import find_device, list_devices

        if self.audio_off:
            return
        if self.analyzer is None:
            self._start_audio(None)
            return
        if self.audio is None:
            self._start_audio(None)
            return
        if not self.audio.alive:
            if self.audio.restart():
                self.audio.gain = self.profile.audio_gain
                print(tr("[audio] entrée rétablie : {}").format(self.audio.device_name))
            return
        if self.audio_fallback and self.wanted_audio:
            try:
                present = find_device(self.wanted_audio) is not None
            except ValueError:
                present = False
            if present:
                print(tr("[audio] « {} » détectée, bascule").format(self.wanted_audio))
                self.audio.stop()
                self._start_audio(None)

    def _choose_audio_device(self, index) -> None:
        """L'utilisateur choisit une entrée : elle devient celle du profil."""
        from ..audio.input import list_devices

        name = next((d.name for d in list_devices() if d.index == index), None)
        if name is None:
            return
        self.profile.audio_device = name
        self.wanted_audio = name
        if self.audio is not None:
            self.audio.stop()
        self.audio = None
        self._start_audio(name)

    def _choose_audio_channels(self, channels: list) -> None:
        self.profile.audio_channels = [int(c) for c in channels]
        if self.audio is not None:
            self.audio.stop()
        self.audio = None
        self._start_audio(self.wanted_audio)

    def _set_gain(self, gain: float) -> None:
        self.profile.audio_gain = gain
        if self.audio is not None:
            self.audio.gain = gain

    def _scale_tempo(self, factor: float) -> None:
        if self.analyzer is not None:
            self.analyzer.scale_tempo(factor)

    def _tap(self) -> None:
        if self.analyzer is not None:
            self.analyzer.tap()

    def _set_brightness(self, value: float) -> None:
        self.profile.brightness = value

    # --- raccourcis live ---------------------------------------------------

    _KEYS = {Qt.Key_Space: "flash", Qt.Key_S: "strobe", Qt.Key_B: "blackout",
             Qt.Key_E: "electric"}

    def _hold_for(self, name: str):
        return getattr(self.master, name)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        name = self._KEYS.get(event.key())
        if name is None:
            super().keyPressEvent(event)
            return
        if event.modifiers() & Qt.ShiftModifier:
            # Maj + raccourci : on enclenche le verrou (le bouton suit).
            self.master_panel.latches[name].toggle()
        else:
            self._hold_for(name).momentary = True

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        name = self._KEYS.get(event.key())
        if name is None:
            super().keyReleaseEvent(event)
            return
        self._hold_for(name).momentary = False

    # --- boucle d'affichage ------------------------------------------------

    def _refresh(self) -> None:
        self.preview.set_frame(self.stage.last_frame)
        self.deck_a.preview.set_frame(self.mixer.last_a)
        self.deck_b.preview.set_frame(self.mixer.last_b)
        self.master_panel.sync_crossfader()
        if self.midi is not None:
            self.midi.refresh_leds()
        self._sync_from_midi()
        x = self.mixer.crossfade
        bits = [
            f"{self.engine.measured_fps:4.1f} fps",
            f"A {tr(self.mixer.a.effect_name)}/{tr(self.mixer.a.palette_name)}",
            f"{int((1 - x) * 100):3d}% - {int(x * 100):3d}%",
            f"B {tr(self.mixer.b.effect_name)}/{tr(self.mixer.b.palette_name)}",
            tr("{} sortie(s)").format(len(self.stage.patch.targets())),
        ]
        if self.stage.sender.errors:
            bits.append(tr("{} erreur(s)").format(self.stage.sender.errors))
        if self.audio is not None:
            import math as _math
            from ..audio.input import list_devices
            self.master_panel.set_audio_devices(list_devices(), self.audio.device)
            self.master_panel.set_audio_channels(getattr(self.audio, "available", 1),
                                                 getattr(self.audio, "selected", [0]))
            if not self.audio.alive:
                self.master_panel.show_audio(
                    tr("entrée perdue — reconnexion…"), -99.0, False)
            elif self.audio_fallback:
                rms = self.audio.rms
                dbfs = -99.0 if rms <= 1e-9 else 20.0 * _math.log10(rms)
                self.master_panel.show_audio(
                    tr("{}  ·  repli, « {} » absente").format(
                        self.audio.device_name, self.wanted_audio),
                    dbfs, self.audio.clipping)
            else:
                rms = self.audio.rms
                dbfs = -99.0 if rms <= 1e-9 else 20.0 * _math.log10(rms)
                voies = ", ".join(str(c + 1) for c in getattr(self.audio, "selected", []))
                self.master_panel.show_audio(
                    tr("{} · voies {}").format(self.audio.device_name, voies),
                                             dbfs, self.audio.clipping)
        if self.analyzer is not None:
            st = self.analyzer.state()
            self.master_panel.show_tempo(st.bpm, st.bpm_confidence, self.analyzer.octave,
                                         self._measured_beat_rate(st.beat_count))
            bits.append(f"BPM {st.bpm:5.1f} ({st.bpm_confidence:.2f})")
            if self.audio is not None and self.audio.clipping:
                bits.append(tr("ENTREE SATUREE"))
        bits.append(f"MIDI {self.midi.link.input_name}" if self.midi is not None else "MIDI —")
        memory = self._memory()
        if memory:
            drift = memory - self._memory_start
            bits.append(tr("mém {:.0f} Mo").format(memory)
                        + (f" ({drift:+.0f})" if abs(drift) >= 1 else ""))
        self.status.setText("   |   ".join(bits))

    def _sync_from_midi(self) -> None:
        """Reporte dans l'interface ce que le MIDI a change dans le modele."""
        if self.midi is None:
            return
        for panel, deck in ((self.deck_a, self.mixer.a), (self.deck_b, self.mixer.b)):
            panel.params.sync()
            editor = panel.custom_editor
            if len(deck.custom.colors) != editor._colors_row.count() or any(
                    tuple(round(v, 3) for v in deck.custom.colors[i])
                    != tuple(round(v, 3) for v in editor._colors_row.itemAt(i).widget().rgb)
                    for i in range(editor._colors_row.count())):
                editor._rebuild()          # une couleur choisie au MIDI se voit a l'ecran
            if panel.effects.currentItem() and panel.effects.currentItem().text() != deck.effect_name:
                panel.effects.setCurrentRow(list(deck.effects).index(deck.effect_name))
            if panel.palettes.currentItem() and panel.palettes.currentItem().text() != deck.palette_name:
                panel.palettes.setCurrentRow(list(deck.palettes).index(deck.palette_name))
        box = self.master_panel.audio_box
        if box.isEnabled() and box.isChecked() != self.master.audio_enabled:
            box.blockSignals(True)
            box.setChecked(self.master.audio_enabled)
            box.blockSignals(False)
        for name, button in self.master_panel.latches.items():
            latched = getattr(self.master, name).latched
            if button.isChecked() != latched:
                button.blockSignals(True)
                button.setChecked(latched)
                button.blockSignals(False)

    def closeEvent(self, event) -> None:
        self._audio_watchdog.stop()
        # La fenêtre live modifie des réglages durables (entrée audio, gain,
        # luminosité) : sans cela ils étaient perdus à la fermeture.
        try:
            self.profile.save()
        except Exception as exc:
            print(tr("[profil] enregistrement impossible : {!r}").format(exc))
        if self.midi is not None:
            self.midi.stop()
        self.engine.stop()
        self.install.shutdown()
        if self.audio is not None:
            self.audio.stop()
        try:
            from ..output import wled
            self.stage.blackout()
            wled.power_all(self.profile.outputs, False)
        finally:
            self.stage.close()
        super().closeEvent(event)


def run(profile: Profile, audio_device=None, use_audio: bool = True,
        midi_mapping: str | None = "apcmini-mk2", page: int = 0) -> int:
    from PySide6.QtWidgets import QApplication

    from ..output import wled

    app = QApplication.instance() or QApplication([])
    # La langue est deja choisie par la ligne de commande (« --lang », sinon le
    # profil) : la reimposer ici ecraserait un « --lang » explicite.
    apply_theme(app)
    wled.wake_all(profile.outputs)
    window = MainWindow(profile, audio_device=audio_device, use_audio=use_audio,
                        midi_mapping=midi_mapping, page=page)
    window.show()
    return app.exec()
