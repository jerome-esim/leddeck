"""Theme sombre de l'application.

Un seul endroit pour les couleurs : l'interface doit rester lisible dans un club,
donc fond tres sombre, contrastes francs, et une couleur par deck pour savoir en
un coup d'oeil de quel cote on agit.
"""

from __future__ import annotations

BG = "#101114"
PANEL = "#17191f"
PANEL_HI = "#1e212a"
BORDER = "#272b36"
TEXT = "#e7eaf1"
MUTED = "#828b a0".replace(" ", "")
ACCENT = "#4da3ff"
ACCENT_A = "#22d3ee"      # deck A : cyan
ACCENT_B = "#f472b6"      # deck B : rose
DANGER = "#ef4444"
WARN = "#f59e0b"

QSS = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QLabel {{ background: transparent; }}
QMainWindow, QDialog {{ background: {BG}; }}

QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 20px;
    padding: 12px 10px 10px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
}}

QListWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 5px;
    outline: none;
}}
QListWidget::item {{ padding: 7px 10px; border-radius: 7px; color: {TEXT}; }}
QListWidget[viewMode="1"]::item {{ padding: 4px; }}
QListWidget::item:hover {{ background: {PANEL_HI}; }}
QListWidget::item:selected {{ background: {ACCENT}; color: #0a0b0e; font-weight: 700; }}

QPushButton {{
    background: {PANEL_HI};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ background: #262a35; }}
QPushButton:pressed {{ background: {ACCENT}; color: #0a0b0e; }}
QPushButton:disabled {{ color: #555c6b; }}

QPushButton#nav {{
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 700;
    letter-spacing: 0.6px;
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
}}
QPushButton#nav:hover {{ background: {PANEL_HI}; color: {TEXT}; }}
QPushButton#nav:checked {{
    background: {PANEL_HI};
    border: 1px solid {ACCENT};
    color: {TEXT};
}}

QComboBox {{
    background: {PANEL_HI};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 6px 10px;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    selection-color: #0a0b0e;
    padding: 4px;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid #3a4150;
    border-radius: 5px;
    background: {PANEL_HI};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QSlider::groove:horizontal {{ height: 5px; background: #23262f; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 15px; height: 15px; margin: -6px 0;
    border-radius: 8px; background: #eef2f9; border: none;
}}
QSlider::handle:horizontal:hover {{ background: #ffffff; }}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {PANEL};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 7px 16px;
    margin-right: 4px;
    border-radius: 8px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.1px;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ background: {PANEL_HI}; color: {TEXT}; }}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #333947; border-radius: 4px; min-height: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

# La liste d'un deck prend sa couleur : on sait toujours de quel cote on agit.
DECK_QSS = """
QListWidget::item:selected {{ background: {accent}; color: #0a0b0e; }}
QTabBar::tab:selected {{ color: {accent}; }}
QSlider::sub-page:horizontal {{ background: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
"""

# Le crossfader porte les deux couleurs : cyan du cote A, rose du cote B.
CROSSFADER_QSS = f"""
QSlider::groove:horizontal {{ height: 7px; background: #23262f; border-radius: 4px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT_A}; border-radius: 4px; }}
QSlider::add-page:horizontal {{ background: {ACCENT_B}; border-radius: 4px; }}
QSlider::handle:horizontal {{
    width: 20px; height: 20px; margin: -7px 0;
    border-radius: 10px; background: #f5f8ff; border: 2px solid {BG};
}}
"""


def section(text: str):
    """Intitule de section : meme traitement que les titres de cadre."""
    from PySide6.QtWidgets import QLabel

    label = QLabel(text)
    label.setStyleSheet(
        f"color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.2px;")
    return label


def apply_theme(app) -> None:
    """Theme sombre + police de l'interface du systeme.

    On ne force pas de famille en CSS : « -apple-system » est un mot-cle propre
    aux navigateurs, que Qt ne resout pas — la police n'etait pas appliquee et
    Qt perdait du temps au demarrage a chercher un remplacant.
    """
    from PySide6.QtGui import QFont, QFontDatabase

    app.setStyle("Fusion")
    font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
    font.setPointSizeF(max(12.0, font.pointSizeF()))
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    app.setStyleSheet(QSS)
