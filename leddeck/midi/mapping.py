"""Correspondance commande MIDI -> action, et mapping par defaut de l'APC mini MK2.

Le mapping est un simple fichier JSON : tout est reassignable par MIDI learn,
rien n'est cable en dur dans le code des actions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import ROOT
from .midi import CC, NOTE, Control

MAPPINGS_DIR = ROOT / "midi"
DEFAULT_MAPPING = "apcmini-mk2"

# Releve sur le materiel (APC mini MK2, port « Control », canal 1) :
PAD_BASE = 0                 # grille 8x8 : note = rangee_depuis_le_bas * 8 + colonne
FADER_CC = tuple(range(48, 57))     # 9 faders, de gauche a droite
TRACK_NOTES = tuple(range(100, 108))  # 8 boutons du bas
SCENE_NOTES = tuple(range(112, 120))  # 8 boutons de droite
SHIFT_NOTE = 122

# Deux rangees du bas : huit couleurs unies par deck. L'index « pad » est celui
# de la palette de couleurs du controleur, pour que le pad s'allume juste.
FIXED_COLORS = [
    ("Rouge", (1.0, 0.0, 0.0), 5),
    ("Orange", (1.0, 0.35, 0.0), 9),
    ("Jaune", (1.0, 0.9, 0.0), 13),
    ("Vert", (0.0, 1.0, 0.15), 21),
    ("Cyan", (0.0, 0.85, 1.0), 33),
    ("Bleu", (0.1, 0.2, 1.0), 45),
    ("Rose", (1.0, 0.1, 0.6), 53),
    ("Blanc", (1.0, 1.0, 1.0), 3),
]

EFFECT_ROWS = 3       # rangees 1 a 3 : effets
PALETTE_ROWS = 3      # rangees 4 a 6 : palettes fournies
COLOR_ROWS = 2        # rangees 7 et 8 : couleurs unies


def pad_note(row_from_top: int, column: int) -> int:
    """Note du pad a la position visuelle donnee (rangee 0 = en haut)."""
    return (7 - row_from_top) * 8 + column


@dataclass
class Binding:
    action: str
    args: dict = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> dict:
        data = {"action": self.action}
        if self.args:
            data["args"] = self.args
        if self.label:
            data["label"] = self.label
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Binding":
        return cls(action=data["action"], args=dict(data.get("args", {})),
                   label=data.get("label", ""))


@dataclass
class Mapping:
    name: str = DEFAULT_MAPPING
    port: str = "APC mini mk2 Control"
    bindings: dict[str, Binding] = field(default_factory=dict)

    # --- acces ------------------------------------------------------------

    def get(self, control: Control) -> Binding | None:
        return self.bindings.get(control.key)

    def bind(self, control: Control, action: str, args: dict | None = None,
             label: str = "") -> Binding:
        binding = Binding(action=action, args=dict(args or {}), label=label)
        self.bindings[control.key] = binding
        return binding

    def unbind(self, control: Control) -> None:
        self.bindings.pop(control.key, None)

    def controls_for(self, action: str, args: dict | None = None) -> list[Control]:
        """Commandes liees a une action donnee — sert au retour visuel."""
        found = []
        for key, binding in self.bindings.items():
            if binding.action != action:
                continue
            if args and any(binding.args.get(k) != v for k, v in args.items()):
                continue
            found.append(Control.parse(key))
        return found

    # --- fichiers ---------------------------------------------------------

    def to_dict(self) -> dict:
        return {"name": self.name, "port": self.port,
                "bindings": {k: b.to_dict() for k, b in sorted(self.bindings.items())}}

    @classmethod
    def from_dict(cls, data: dict) -> "Mapping":
        return cls(name=data.get("name", DEFAULT_MAPPING),
                   port=data.get("port", ""),
                   bindings={k: Binding.from_dict(v)
                             for k, v in data.get("bindings", {}).items()})

    @staticmethod
    def path_for(name: str) -> Path:
        return MAPPINGS_DIR / f"{name}.json"

    def save(self, name: str | None = None) -> Path:
        self.name = name or self.name
        path = self.path_for(self.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return path

    @classmethod
    def load(cls, name: str = DEFAULT_MAPPING) -> "Mapping":
        path = cls.path_for(name)
        if not path.exists():
            return default_apc_mapping(name)
        return cls.from_dict(json.loads(path.read_text()))

    @staticmethod
    def list_mappings() -> list[str]:
        if not MAPPINGS_DIR.exists():
            return []
        return sorted(p.stem for p in MAPPINGS_DIR.glob("*.json"))


def default_apc_mapping(name: str = DEFAULT_MAPPING) -> Mapping:
    """Mapping propose par defaut, entierement reassignable.

    Grille : moitie gauche = deck A, moitie droite = deck B ;
    4 rangees du haut = effets, 4 rangees du bas = palettes.
    """
    mapping = Mapping(name=name, port="APC mini mk2 Control")

    for row in range(8):
        for column in range(8):
            deck = "a" if column < 4 else "b"
            slot = column % 4
            control = Control(NOTE, 0, pad_note(row, column))
            if row < EFFECT_ROWS:
                index = row * 4 + slot
                mapping.bind(control, "deck.effect", {"deck": deck, "index": index},
                             f"Deck {deck.upper()} — effet {index + 1}")
            elif row < EFFECT_ROWS + PALETTE_ROWS:
                # Index 0 est la palette perso : les pads couleur en tiennent lieu,
                # on commence donc aux palettes fournies.
                index = 1 + (row - EFFECT_ROWS) * 4 + slot
                mapping.bind(control, "deck.palette", {"deck": deck, "index": index},
                             f"Deck {deck.upper()} — palette {index}")
            else:
                position = (row - EFFECT_ROWS - PALETTE_ROWS) * 4 + slot
                name, rgb, pad = FIXED_COLORS[position]
                mapping.bind(control, "deck.color",
                             {"deck": deck, "rgb": list(rgb), "pad": pad}, name)

    faders = [
        ("deck.param", {"deck": "a", "index": 0}, "Deck A — réglage 1"),
        ("deck.param", {"deck": "a", "index": 1}, "Deck A — réglage 2"),
        ("deck.param", {"deck": "a", "index": 2}, "Deck A — réglage 3"),
        ("master.brightness", {}, "Luminosité master"),
        ("deck.param", {"deck": "b", "index": 0}, "Deck B — réglage 1"),
        ("deck.param", {"deck": "b", "index": 1}, "Deck B — réglage 2"),
        ("deck.param", {"deck": "b", "index": 2}, "Deck B — réglage 3"),
        ("master.speed", {}, "Vitesse globale"),
        ("crossfade", {}, "Crossfader"),
    ]
    for cc, (action, args, label) in zip(FADER_CC, faders):
        mapping.bind(Control(CC, 0, cc), action, args, label)

    scenes = [
        ("tap", {}, "Tap tempo"),
        ("auto.toggle", {}, "Crossfade auto"),
        ("auto.beats", {"beats": 8}, "Auto — 8 pulsations"),
        ("auto.beats", {"beats": 16}, "Auto — 16 pulsations"),
        ("auto.beats", {"beats": 32}, "Auto — 32 pulsations"),
        ("master.audio", {}, "Son réactif · bascule on/off"),
    ]
    for note, (action, args, label) in zip(SCENE_NOTES, scenes):
        mapping.bind(Control(NOTE, 0, note), action, args, label)

    # Les 8 boutons du bas portent les 4 fonctions live, chacune dans ses deux
    # gestes : l'appui maintenu a gauche, la bascule a droite. On trouve donc
    # toujours le meme geste au meme endroit relatif.
    live = ("electric", "strobe", "flash", "blackout")
    titles = {"electric": "Électrique", "strobe": "Strobe",
              "flash": "Flash", "blackout": "Blackout"}
    for index, name in enumerate(live):
        for offset, (mode, suffix) in enumerate(
                (("momentary", "tant qu'on appuie"), ("latch", "bascule on/off"))):
            mapping.bind(Control(NOTE, 0, TRACK_NOTES[index * 2 + offset]),
                         "master.hold", {"name": name, "mode": mode},
                         f"{titles[name]} · {suffix}")
    return mapping
