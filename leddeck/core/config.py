"""Modèle de configuration : matrice, sorties WLED, patch, profils de salle.

Un *profil de salle* décrit tout ce qui dépend du lieu :
  - la taille de la matrice (L LED x N bandeaux)
  - la liste des sorties (un ESP WLED = une sortie, avec un numero fixe)
  - le patch : quelle sortie alimente quelle ligne de la matrice, et dans quel sens
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT / "profiles"
DEFAULT_PROFILE = "default"
DDP_PORT = 4048


@dataclass
class Output:
    """Une sortie = un controleur WLED. `id` est le numero affiche sur le bandeau."""

    id: int
    name: str = ""
    ip: str = ""
    led_count: int = 250
    port: int = DDP_PORT
    enabled: bool = True
    mac: str = ""

    @property
    def label(self) -> str:
        return f"#{self.id} {self.name or self.ip}"


@dataclass
class PatchRow:
    """Une ligne de la matrice : quelle sortie, dans quel sens, avec quel decalage."""

    output_id: int | None = None
    reverse: bool = False
    offset: int = 0


# 3 rangees de 4 pads par deck sur l'APC mini : 12 effets accessibles au doigt.
PAD_EFFECTS = 12


@dataclass
class Profile:
    name: str = DEFAULT_PROFILE
    leds: int = 250          # L : LED par bandeau (colonnes de la matrice)
    strips: int = 16         # N : nombre de bandeaux (lignes de la matrice)
    fps: int = 40
    gamma: float = 2.2
    brightness: float = 1.0
    audio_device: str = ""   # index ou fragment de nom ; vide = peripherique par defaut
    audio_channels: list[int] = field(default_factory=list)   # voies melangees, vide = 1 et 2
    audio_gain: float = 1.0
    # Le contrôleur n'a que 12 pads d'effets par deck, et il y a plus d'effets
    # que cela : on choisit lesquels y posent leurs pieds, et dans quel ordre.
    fav_effects: list[str] = field(default_factory=list)
    language: str = "fr"
    outputs: list[Output] = field(default_factory=list)
    patch: list[PatchRow] = field(default_factory=list)

    def pad_effects(self, available: list[str]) -> list[str]:
        """Les effets posés sur la grille du contrôleur, dans l'ordre des pads.

        Les favoris d'abord, puis l'ordre du catalogue pour combler : une liste
        vide ou incomplète donne toujours une grille pleine, jamais de trou.
        Un favori dont l'effet a disparu est simplement ignoré.
        """
        chosen = [n for n in self.fav_effects if n in available]
        for name in available:
            if len(chosen) >= PAD_EFFECTS:
                break
            if name not in chosen:
                chosen.append(name)
        return chosen[:PAD_EFFECTS]

    # --- acces ---------------------------------------------------------

    def ensure_patch(self) -> None:
        """Ajuste la longueur du patch au nombre de bandeaux."""
        while len(self.patch) < self.strips:
            self.patch.append(PatchRow())
        del self.patch[self.strips :]

    def output(self, output_id: int | None) -> Output | None:
        if output_id is None:
            return None
        return next((o for o in self.outputs if o.id == output_id), None)

    def next_output_id(self) -> int:
        return max((o.id for o in self.outputs), default=0) + 1

    def add_output(self, **kwargs) -> Output:
        kwargs.setdefault("id", self.next_output_id())
        out = Output(**kwargs)
        self.outputs.append(out)
        return out

    def autopatch(self) -> None:
        """Patch par defaut : sortie #1 -> ligne 1, #2 -> ligne 2, ..."""
        self.ensure_patch()
        for row, out in zip(self.patch, sorted(self.outputs, key=lambda o: o.id)):
            row.output_id = out.id

    # --- serialisation -------------------------------------------------

    def to_dict(self) -> dict:
        self.ensure_patch()
        return {
            "name": self.name,
            "matrix": {"leds": self.leds, "strips": self.strips},
            "fps": self.fps,
            "gamma": self.gamma,
            "brightness": self.brightness,
            "audio_device": self.audio_device,
            "audio_channels": list(self.audio_channels),
            "audio_gain": self.audio_gain,
            "fav_effects": list(self.fav_effects),
            "language": self.language,
            "outputs": [vars(o) for o in self.outputs],
            "patch": [vars(r) for r in self.patch],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        matrix = data.get("matrix", {})
        prof = cls(
            name=data.get("name", DEFAULT_PROFILE),
            leds=int(matrix.get("leds", 250)),
            strips=int(matrix.get("strips", 16)),
            fps=int(data.get("fps", 40)),
            gamma=float(data.get("gamma", 2.2)),
            brightness=float(data.get("brightness", 1.0)),
            audio_device=str(data.get("audio_device", "")),
            audio_channels=[int(c) for c in data.get("audio_channels", [])],
            audio_gain=float(data.get("audio_gain", 1.0)),
            fav_effects=list(data.get("fav_effects", [])),
            language=str(data.get("language", "fr")),
            outputs=[Output(**o) for o in data.get("outputs", [])],
            patch=[PatchRow(**r) for r in data.get("patch", [])],
        )
        prof.ensure_patch()
        return prof

    # --- fichiers ------------------------------------------------------

    @staticmethod
    def path_for(name: str) -> Path:
        return PROFILES_DIR / f"{name}.json"

    def save(self, name: str | None = None) -> Path:
        self.name = name or self.name
        path = self.path_for(self.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return path

    @classmethod
    def load(cls, name: str = DEFAULT_PROFILE) -> "Profile":
        path = cls.path_for(name)
        if not path.exists():
            prof = cls(name=name)
            prof.ensure_patch()
            return prof
        return cls.from_dict(json.loads(path.read_text()))

    @staticmethod
    def list_profiles() -> list[str]:
        if not PROFILES_DIR.exists():
            return []
        return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))
