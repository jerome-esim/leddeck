"""Page d'installation : découvrir les WLED, les identifier, les patcher.

Elle partage le moteur et l'étage de sortie de la fenêtre principale : un seul
flux DDP part vers les ESP, quelle que soit la page affichée.
"""

from __future__ import annotations

import time
import webbrowser
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core.config import Profile
from ..install import patterns as P
from ..output import wled
from ..output.patch import OutputStage
from .preview import MatrixPreview
from ..i18n import tr
from .style import ACCENT, MUTED, section

POLL_SECONDS = 4.0
AUTO_SCAN_SECONDS = 15.0
POLL_TIMEOUT = 2.5      # le serveur web d'un ESP est affame pendant qu'il recoit le flux
OFFLINE_AFTER = 3       # ratés consecutifs avant de declarer hors ligne
HISTORY = 10            # fenetre du taux de reussite

# Les boutons du theme ont un remplissage genereux : dans une cellule de tableau
# ils se retrouvent tronques. On les compacte et on monte la hauteur des lignes.
CELL_BUTTON_QSS = "QPushButton{padding:3px 10px; font-size:12px; border-radius:6px;}"
ROW_HEIGHT = 34


def signal_bars(rssi: int) -> tuple[str, str]:
    """(barres, qualité) à partir du RSSI en dBm."""
    if rssi == 0:
        return "····", "—"
    if rssi >= -55:
        return "▮▮▮▮", "excellent"
    if rssi >= -65:
        return "▮▮▮·", "bon"
    if rssi >= -75:
        return "▮▮··", "moyen"
    return "▮···", "faible"


class InfoPoller(QThread):
    """Interroge les WLED en tâche de fond : l'interface ne doit jamais attendre."""

    updated = Signal(dict)

    def __init__(self, profile: Profile, parent=None) -> None:
        super().__init__(parent)
        self.profile = profile
        self._running = True
        self._misses: dict[str, int] = {}
        # Le RSSI ne dit pas si la liaison *porte* les paquets : un ESP a -42 dBm
        # peut en perdre les deux tiers. On mesure donc le taux de reussite reel.
        self._history: dict[str, deque] = {}

    @staticmethod
    def _probe(out) -> tuple[object, float]:
        started = time.monotonic()
        info = wled.info(out.ip, POLL_TIMEOUT)
        return info, (time.monotonic() - started) * 1000.0

    def run(self) -> None:
        while self._running:
            targets = [o for o in self.profile.outputs if o.ip]
            result: dict[str, object] = {}
            if targets:
                with ThreadPoolExecutor(max_workers=min(16, len(targets))) as pool:
                    for out, (info, ms) in zip(targets, pool.map(self._probe, targets)):
                        seen = self._history.setdefault(out.ip, deque(maxlen=HISTORY))
                        seen.append(info is not None)
                        if info is None:
                            # Un raté isolé ne veut rien dire : l'ESP donne la
                            # priorite aux LED sur son serveur web.
                            self._misses[out.ip] = self._misses.get(out.ip, 0) + 1
                            result[out.ip] = ("offline" if self._misses[out.ip] >= OFFLINE_AFTER
                                              else "unstable", None, ms, tuple(seen))
                        else:
                            self._misses[out.ip] = 0
                            result[out.ip] = ("online", info, ms, tuple(seen))
            self.updated.emit(result)
            for _ in range(int(POLL_SECONDS * 10)):
                if not self._running:
                    return
                self.msleep(100)

    def stop(self) -> None:
        self._running = False
        self.wait(1500)


class ScanWorker(QThread):
    """Découverte réseau hors du fil de l'interface : elle la figeait plusieurs
    secondes à chaque scan, et le mode automatique l'aurait rendue inutilisable."""

    done = Signal(list)

    def __init__(self, cidr, use_mdns: bool, timeout: float, parent=None) -> None:
        super().__init__(parent)
        self.cidr, self.use_mdns, self.timeout = cidr, use_mdns, timeout

    def run(self) -> None:
        try:
            found = wled.discover(self.cidr, use_mdns=self.use_mdns, timeout=self.timeout)
        except Exception:
            found = []
        self.done.emit(found)


class InstallPage(QWidget):
    """Page d'installation, hebergee par la fenetre principale.

    Elle ne possede ni moteur ni etage de sortie : la fenetre les lui prete,
    pour qu'une seule boucle de rendu alimente les bandeaux.
    """

    matrix_changed = Signal()

    def __init__(self, profile: Profile, stage: OutputStage, parent=None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.profile.ensure_patch()
        self.stage = stage
        self.infos: dict[str, object] = {}
        self.mode: tuple[str, object] = ("off", None)
        self.dirty = False
        self.scan_worker: ScanWorker | None = None
        self.buses: dict[str, tuple] = {}      # ip -> (total, locales, relais)

        self._build_ui()

        self.poller = InfoPoller(profile, self)
        self.poller.updated.connect(self._on_infos)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_preview)

        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(lambda: self._scan(auto=True))

    # --- rendu ------------------------------------------------------------

    def activate(self, active: bool) -> None:
        """Le sondage reseau et l'apercu ne tournent que sur la page visible."""
        if active:
            self.poller.start()
            self._timer.start(40)
        else:
            self._timer.stop()
            self._auto_timer.stop()
            if self.auto_scan.isChecked():
                self.auto_scan.setChecked(False)
            self.poller.stop()

    def shutdown(self) -> None:
        self._auto_timer.stop()
        self._timer.stop()
        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.scan_worker.wait(3000)
        self.poller.stop()
        if self.dirty:
            self.profile.save()

    def render(self, t: float, dt: float):
        kind, arg = self.mode
        leds, strips = self.profile.leds, self.profile.strips
        if kind == "identify":
            return {o.id: P.number_line(o.id, o.led_count) for o in self.profile.outputs}
        if kind == "blink":
            out = self.profile.output(arg)
            return {} if out is None else {out.id: P.blink_line(out.id, out.led_count, t)}
        if kind == "line":
            frame = np.zeros((strips, leds, 3), np.float32)
            if 0 <= arg < strips:
                pos = int((t * 0.6) % 1.0 * leds)
                frame[arg, max(0, pos - 3):pos + 4] = 1.0
                frame[arg, 0] = (0, 1, 0)
                frame[arg, leds - 1] = (1, 0, 0)
            return frame
        if kind in P.MATRIX_PATTERNS and kind != "off":
            return P.MATRIX_PATTERNS[kind](t, leds, strips)
        # Eteint : on adresse *toutes* les sorties, patchees ou non. Une sortie
        # sans ligne ne recevrait rien, WLED sortirait du mode temps reel au bout
        # de 2,5 s et repartirait sur son effet interne — c'est le cas courant
        # juste apres un scan, avant d'avoir patche.
        return {o.id: np.zeros((o.led_count, 3), np.float32) for o in self.profile.outputs}

    def _set_mode(self, kind: str, arg=None) -> None:
        # Un seul sink pour tous les modes : il reconnait lui-meme la forme du
        # rendu. Echanger le sink selon le mode etait une source d'erreurs.
        self.mode = (kind, arg)
        self.mode_label.setText({"off": "éteint", "identify": "identification",
                                 "blink": "clignotement"}.get(kind, f"motif « {kind} »"))

    # --- interface ---------------------------------------------------------

    def _build_ui(self) -> None:
        self.outputs_table = QTableWidget(0, 8)
        self.outputs_table.setHorizontalHeaderLabels(
            [tr("N°"), tr("Nom"), tr("IP"), tr("LED"), tr("Signal"), tr("Version"),
             tr("État"), ""])
        self.outputs_table.verticalHeader().setVisible(False)
        self.outputs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.outputs_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.scan_button = QPushButton(tr("Scanner le réseau"))
        self.scan_button.clicked.connect(self._scan)
        self.prepare_button = QPushButton(tr("Préparer les ESP"))
        self.prepare_button.setToolTip(
            tr("Configure chaque WLED pour le club : affichage du flux à fond même éteint,\n"
            "pas de gamma WLED, démarrage éteint. À faire une fois par ESP."))
        self.prepare_button.clicked.connect(self._prepare)
        self.auto_scan = QCheckBox(tr("Scan auto + patch"))
        self.auto_scan.setToolTip(
            tr("Cherche les nouveaux WLED toutes les {:g} s,\n"
               "les ajoute, les patche sur la première ligne libre et enregistre.")
            .format(AUTO_SCAN_SECONDS))
        self.auto_scan.toggled.connect(self._toggle_auto_scan)
        self.cidr = QComboBox()
        self.cidr.setEditable(True)
        self.cidr.addItems([tr("(réseaux locaux)"), "192.168.8.0/24", "192.168.0.0/24"])

        top = QHBoxLayout()
        top.addWidget(self.scan_button)
        top.addWidget(self.cidr, 1)
        top.addWidget(self.auto_scan)
        top.addWidget(self.prepare_button)
        self.scan_status = QLabel("")
        self.scan_status.setStyleSheet(f"color:{MUTED};")
        top.addWidget(self.scan_status)

        outputs_box = QGroupBox(tr("Sorties WLED"))
        outputs_layout = QVBoxLayout(outputs_box)
        outputs_layout.addLayout(top)
        outputs_layout.addWidget(self.outputs_table)

        # --- patch ---
        self.patch_table = QTableWidget(0, 5)
        self.patch_table.setHorizontalHeaderLabels(
            [tr("Ligne"), tr("Sortie"), tr("Inversée"), tr("Décalage"), ""])
        self.patch_table.verticalHeader().setVisible(False)
        self.patch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.leds_spin = QSpinBox()
        self.leds_spin.setRange(1, 2000)
        self.leds_spin.setValue(self.profile.leds)
        self.strips_spin = QSpinBox()
        self.strips_spin.setRange(1, 64)
        self.strips_spin.setValue(self.profile.strips)
        apply_size = QPushButton(tr("Appliquer"))
        apply_size.clicked.connect(self._apply_size)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(tr("LED par bandeau")))
        size_row.addWidget(self.leds_spin)
        size_row.addWidget(QLabel(tr("bandeaux")))
        size_row.addWidget(self.strips_spin)
        size_row.addWidget(apply_size)
        size_row.addStretch(1)
        auto = QPushButton(tr("Patch automatique (#1 → ligne 1)"))
        auto.clicked.connect(self._autopatch)
        size_row.addWidget(auto)

        patch_box = QGroupBox(tr("Patch — quelle sortie sur quelle ligne"))
        patch_layout = QVBoxLayout(patch_box)
        patch_layout.addLayout(size_row)
        patch_layout.addWidget(self.patch_table)

        # --- motifs ---
        self.preview = MatrixPreview(self.profile.strips, self.profile.leds, compact=True)
        self.mode_label = QLabel(tr("éteint"))
        self.mode_label.setStyleSheet(f"color:{ACCENT}; font-weight:600;")

        buttons = QHBoxLayout()
        for label, kind, tip in (
            ("Identifier", "identify", "Chaque bandeau affiche son numéro de sortie"),
            ("Numéro de ligne", "rows", "Chaque ligne affiche son numéro dans la matrice"),
            ("Arc-en-ciel", "rainbow", "Dégradé de la ligne 1 à la ligne N"),
            ("Balayage", "sweep", "Un point traverse toutes les lignes, même sens attendu"),
            ("Chenillard", "chase", "Un point par ligne, décalé"),
            ("Éteindre", "off", "Tout noir"),
        ):
            button = QPushButton(tr(label))
            button.setToolTip(tr(tip))
            button.clicked.connect(lambda _=False, k=kind: self._set_mode(k))
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(QLabel(tr("en cours :")))
        buttons.addWidget(self.mode_label)

        patterns_box = QGroupBox(tr("Vérification"))
        patterns_layout = QVBoxLayout(patterns_box)
        patterns_layout.addLayout(buttons)
        patterns_layout.addWidget(self.preview)

        save = QPushButton(tr("Enregistrer le profil"))
        save.clicked.connect(self._save)
        self.saved_label = QLabel("")
        self.saved_label.setStyleSheet(f"color:{MUTED};")
        bottom = QHBoxLayout()
        bottom.addWidget(save)
        bottom.addWidget(self.saved_label, 1)

        left = QVBoxLayout()
        left.addWidget(outputs_box, 1)
        left.addWidget(patterns_box)
        right = QVBoxLayout()
        right.addWidget(patch_box, 1)
        right.addLayout(bottom)

        root = QHBoxLayout(self)
        left_box, right_box = QWidget(), QWidget()
        left_box.setLayout(left)
        right_box.setLayout(right)
        root.addWidget(left_box, 3)
        root.addWidget(right_box, 2)

        self._fill_outputs()
        self._fill_patch()

    # --- tableau des sorties ------------------------------------------------

    def _fill_outputs(self) -> None:
        table = self.outputs_table
        table.setRowCount(len(self.profile.outputs))
        for row, out in enumerate(self.profile.outputs):
            state, info, ms, seen = self.infos.get(out.ip, ("unknown", None, 0.0, ()))
            ok_ratio = (sum(seen) / len(seen)) if seen else None
            rssi = int(getattr(info, "rssi", 0) or 0)
            bars, quality = signal_bars(rssi)
            online = info is not None
            label = {"online": tr("en ligne"), "unstable": tr("lent"),
                     "offline": tr("hors ligne")}.get(state, "—")
            if online:
                label += f"  ({ms:.0f} ms)"
            cells = [
                f"#{out.id}", out.name or "—", out.ip,
                (str(out.led_count) if not online or info.leds in (0, out.led_count)
                 else f"{info.leds}  (profil : {out.led_count})"),
                (f"{bars}  {rssi} dBm  {quality}"
                 + (f"  ·  {sum(seen)}/{len(seen)} joignable" if seen and ok_ratio < 1.0 else "")
                 ) if online else (f"{sum(seen)}/{len(seen)} joignable" if seen else "—"),
                (f"v{getattr(info, 'version', '')}"
                 + ("  ⚠ relais DDP" if self.buses.get(out.ip, (0, 0, []))[2] else "")
                 ) if online else "—",
                label,
            ]
            colors = {"online": "#3fb950", "unstable": "#d08a20", "offline": "#d05050"}
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if column == 3 and online and info.leds not in (0, out.led_count):
                    item.setForeground(QColor("#d08a20"))
                if column == 5 and self.buses.get(out.ip, (0, 0, []))[2]:
                    item.setForeground(QColor("#d05050"))
                if column == 6:
                    item.setForeground(QColor(colors.get(state, "#888888")))
                # Une liaison qui perd des paquets est signalee meme si le RSSI est bon.
                if column == 4 and (rssi < -75 or ms > 800
                                    or (ok_ratio is not None and ok_ratio < 0.9)):
                    item.setForeground(QColor("#d08a20"))
                table.setItem(row, column, item)

            if table.cellWidget(row, 7) is None:
                actions = QWidget()
                actions.setStyleSheet(CELL_BUTTON_QSS)
                layout = QHBoxLayout(actions)
                layout.setContentsMargins(4, 2, 4, 2)
                layout.setSpacing(6)
                config = QPushButton(tr("Config"))
                config.setToolTip(tr("Ouvrir http://{} dans le navigateur").format(out.ip))
                config.setMinimumWidth(70)
                config.clicked.connect(lambda _=False, ip=out.ip: webbrowser.open(f"http://{ip}"))
                blink = QPushButton(tr("Clignoter"))
                blink.setToolTip(tr("Faire clignoter ce bandeau pour le repérer"))
                blink.setMinimumWidth(84)
                blink.clicked.connect(lambda _=False, i=out.id: self._set_mode("blink", i))
                layout.addWidget(config)
                layout.addWidget(blink)
                table.setCellWidget(row, 7, actions)
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        # La colonne d'actions contient des boutons : la laisser se dimensionner
        # sur son en-tete vide les tronque.
        table.setColumnWidth(7, 190)
        table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)

    def _on_infos(self, infos: dict) -> None:
        self.infos = infos
        online = sum(1 for entry in infos.values() if entry[1] is not None)
        self.scan_status.setText(
            tr("{}/{} en ligne").format(online, len(self.profile.outputs)))
        self._fill_outputs()

    def _scan(self, auto: bool = False) -> None:
        if self.scan_worker is not None and self.scan_worker.isRunning():
            return
        cidr = self.cidr.currentText().strip()
        cidr = None if cidr.startswith("(") else cidr
        self.scan_button.setEnabled(False)
        self.scan_status.setText(tr("recherche en cours…"))
        # Le mode automatique se passe de mDNS : il tourne souvent, il doit être bref.
        self.scan_worker = ScanWorker(cidr, use_mdns=not auto, timeout=0.8 if not auto else 0.5,
                                      parent=self)
        self.scan_worker.done.connect(lambda found, a=auto: self._on_scan_done(found, a))
        self.scan_worker.start()

    def _on_scan_done(self, found: list, auto: bool) -> None:
        by_ip = {o.ip: o for o in self.profile.outputs}
        by_mac = {o.mac: o for o in self.profile.outputs if o.mac}
        fresh, updated = [], []
        for info in found:
            known = by_ip.get(info.ip) or (by_mac.get(info.mac) if info.mac else None)
            if known is not None:
                # L'appareil fait autorite : sa configuration a pu changer depuis
                # la decouverte (une config « virtual LED » annonçait 1000 LED).
                changes = []
                if info.leds and info.leds != known.led_count:
                    changes.append(f"{known.led_count} → {info.leds} LED")
                    known.led_count = info.leds
                if info.name and info.name != known.name:
                    changes.append(f"« {known.name} » → « {info.name} »")
                    known.name = info.name
                if info.ip != known.ip:
                    changes.append(f"{known.ip} → {info.ip}")
                    known.ip = info.ip
                if changes:
                    updated.append(f"{known.label} : " + ", ".join(changes))
                continue
            out = info.to_output(self.profile.next_output_id())
            self.profile.outputs.append(out)
            fresh.append(out)

        patched = []
        if updated and not fresh:
            self.profile.save()
            self.saved_label.setText(tr("mis à jour : ") + " · ".join(updated))
        if fresh:
            # Sans ce réveil, un ESP tout juste découvert reste éteint côté WLED
            # et n'affiche rien, quoi qu'on lui envoie.
            wled.wake_all(fresh)
            if auto or self.auto_scan.isChecked():
                patched = self._patch_free_lines(fresh)
            # Un scan est un constat, pas un choix : on l'enregistre tout de suite.
            self.profile.save()
            note = f"{len(fresh)} ajoutée(s)"
            if patched:
                note += f", patchée(s) sur les lignes {', '.join(str(n) for n in patched)}"
            if updated:
                note += f", {len(updated)} mise(s) à jour"
            self.saved_label.setText(note + " et enregistré")

        # Une configuration « virtual LED » (bus reseau) fait ramer l'ESP :
        # on la reperé une fois par scan, pas a chaque interrogation.
        for info in found:
            detail = wled.inspect(info.ip, 1.5)
            if detail is not None:
                self.buses[info.ip] = detail
        relays = [ip for ip, (_, _, r) in self.buses.items() if r]

        self.scan_button.setEnabled(True)
        message = f"{len(found)} trouvé(s), {len(fresh)} ajouté(s)"
        if relays:
            message += f" — {len(relays)} en relais DDP (à reconfigurer)"
        self.scan_status.setText(message)
        self._fill_outputs()
        self._fill_patch()

    def _patch_free_lines(self, outputs) -> list[int]:
        """Place chaque nouvelle sortie sur la première ligne encore libre."""
        used = {r.output_id for r in self.profile.patch if r.output_id is not None}
        lines = []
        for out in outputs:
            if out.id in used:
                continue
            for index, row in enumerate(self.profile.patch):
                if row.output_id is None:
                    row.output_id = out.id
                    lines.append(index + 1)
                    break
        return lines

    def _toggle_auto_scan(self, on: bool) -> None:
        if on:
            self._auto_timer.start(int(AUTO_SCAN_SECONDS * 1000))
            self._scan(auto=True)
        else:
            self._auto_timer.stop()

    def _prepare(self) -> None:
        self.prepare_button.setEnabled(False)
        self.scan_status.setText(tr("configuration en cours…"))
        QTimer.singleShot(50, self._prepare_now)

    def _prepare_now(self) -> None:
        done, failed = 0, []
        for out in [o for o in self.profile.outputs if o.enabled and o.ip]:
            before, after = wled.prepare(out.ip, settle=0.0)
            if after is None:
                failed.append(out.label)
            else:
                done += 1
        wled.wake_all(self.profile.outputs)
        self.prepare_button.setEnabled(True)
        self.scan_status.setText(
            f"{done} configuré(s)" + (f", échec : {', '.join(failed)}" if failed else ""))

    # --- patch --------------------------------------------------------------

    def _fill_patch(self) -> None:
        self.profile.ensure_patch()
        table = self.patch_table
        table.setRowCount(self.profile.strips)
        names = ["— aucune —"] + [o.label for o in self.profile.outputs]
        ids = [None] + [o.id for o in self.profile.outputs]
        for row in range(self.profile.strips):
            patch_row = self.profile.patch[row]
            item = QTableWidgetItem(tr("Ligne {}").format(row + 1))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 0, item)

            combo = QComboBox()
            combo.addItems(names)
            combo.setCurrentIndex(ids.index(patch_row.output_id) if patch_row.output_id in ids else 0)
            combo.currentIndexChanged.connect(
                lambda index, r=row, ids=ids: self._set_patch_output(r, ids[index]))
            table.setCellWidget(row, 1, combo)

            reverse = QCheckBox()
            reverse.setChecked(patch_row.reverse)
            reverse.toggled.connect(lambda on, r=row: self._set_reverse(r, on))
            holder = QWidget()
            layout = QHBoxLayout(holder)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignCenter)
            layout.addWidget(reverse)
            table.setCellWidget(row, 2, holder)

            offset = QSpinBox()
            offset.setStyleSheet("QSpinBox{padding:2px 4px;}")
            offset.setRange(-self.profile.leds, self.profile.leds)
            offset.setValue(patch_row.offset)
            offset.valueChanged.connect(lambda v, r=row: self._set_offset(r, v))
            table.setCellWidget(row, 3, offset)

            test = QPushButton(tr("Test"))
            test.setStyleSheet(CELL_BUTTON_QSS)
            test.setToolTip(tr("Faire courir un point sur cette ligne"))
            test.clicked.connect(lambda _=False, r=row: self._set_mode("line", r))
            table.setCellWidget(row, 4, test)
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        table.setColumnWidth(4, 80)

    def _touch(self) -> None:
        self.dirty = True
        self.saved_label.setText(tr("modifications non enregistrées"))

    def _set_patch_output(self, row: int, output_id) -> None:
        self.profile.patch[row].output_id = output_id
        self._touch()

    def _set_reverse(self, row: int, value: bool) -> None:
        self.profile.patch[row].reverse = value
        self._touch()

    def _set_offset(self, row: int, value: int) -> None:
        self.profile.patch[row].offset = value
        self._touch()

    def _autopatch(self) -> None:
        self.profile.autopatch()
        self._fill_patch()
        self._touch()

    def _apply_size(self) -> None:
        self._touch()
        self.profile.leds = self.leds_spin.value()
        self.profile.strips = self.strips_spin.value()
        self.profile.ensure_patch()
        self.preview.set_matrix(self.profile.strips, self.profile.leds)
        self._fill_patch()
        # Changer la taille de matrice touche aussi les effets et le patch :
        # la fenetre reconstruit tout.
        self.matrix_changed.emit()

    def _save(self) -> None:
        path = self.profile.save()
        self.dirty = False
        self.scan_worker: ScanWorker | None = None
        self.buses: dict[str, tuple] = {}      # ip -> (total, locales, relais)
        self.saved_label.setText(tr("enregistré dans {}").format(path.name))

    # --- boucle -------------------------------------------------------------

    def _refresh_preview(self) -> None:
        self.preview.set_frame(self.stage.last_frame)

