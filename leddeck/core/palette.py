"""Palettes de couleurs, separees des effets.

Un effet ne choisit jamais une couleur : il demande « la couleur a la position x »
(0..1) a la palette du deck. Changer de palette recolore donc instantanement
n'importe quel effet, sans le modifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import ROOT

PRESETS_DIR = ROOT / "presets" / "palettes"


@dataclass
class Palette:
    """Suite de couleurs de reference, interpolees lineairement.

    `cyclic` : la derniere couleur rejoint la premiere (degrade sans couture,
    indispensable pour tout ce qui defile). A laisser a False pour un degrade
    oriente comme le feu (noir -> rouge -> jaune -> blanc).

    `smooth` : a False, on ne passe pas par les teintes intermediaires — chaque
    couleur occupe une tranche nette. C'est ce qu'on veut d'une palette perso :
    deux couleurs choisies doivent sortir telles quelles, pas melangees.
    """

    name: str
    colors: list[tuple[float, float, float]]
    cyclic: bool = False
    smooth: bool = True          # False = couleurs franches, sans degrade entre elles
    _stops: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._stops = np.asarray(self.colors, dtype=np.float32).reshape(-1, 3)
        if self._stops.shape[0] == 0:
            raise ValueError(f"palette '{self.name}' sans couleur")

    def set_colors(self, colors) -> None:
        """Remplace les couleurs de reference (palette perso editee en direct)."""
        self.colors = [tuple(float(v) for v in c) for c in colors]
        self._stops = np.asarray(self.colors, dtype=np.float32).reshape(-1, 3)

    @property
    def count(self) -> int:
        return int(self._stops.shape[0])

    def color_at(self, index: int) -> np.ndarray:
        """Couleur de reference n° `index` (en boucle) — pour avancer d'un cran."""
        return self._stops[int(index) % self.count]

    def sample(self, x) -> np.ndarray:
        """x : scalaire ou tableau 0..1 -> tableau (..., 3) float 0..1."""
        x = np.asarray(x, dtype=np.float32)
        cols = self._stops
        k = cols.shape[0]
        if k == 1:
            return np.broadcast_to(cols[0], x.shape + (3,)).astype(np.float32)
        if not self.smooth:
            # Tranches nettes : chaque couleur occupe 1/k de la course.
            if self.cyclic:
                idx = np.floor((x % 1.0) * k).astype(np.int32) % k
            else:
                idx = np.clip(np.floor(x * k).astype(np.int32), 0, k - 1)
            return cols[idx].astype(np.float32)
        if self.cyclic:
            pos = (x % 1.0) * k
            i0 = np.floor(pos).astype(np.int32) % k
            i1 = (i0 + 1) % k
        else:
            pos = np.clip(x, 0.0, 1.0) * (k - 1)
            i0 = np.clip(np.floor(pos).astype(np.int32), 0, k - 1)
            i1 = np.clip(i0 + 1, 0, k - 1)
        f = (pos - np.floor(pos))[..., None].astype(np.float32)
        return (cols[i0] * (1.0 - f) + cols[i1] * f).astype(np.float32)

    def gradient(self, n: int) -> np.ndarray:
        """n couleurs reparties sur toute la palette : (n, 3)."""
        return self.sample(np.linspace(0.0, 1.0, n, endpoint=not self.cyclic))

    @property
    def average(self) -> tuple[float, float, float]:
        """Couleur moyenne — sert a colorer un pad du controleur MIDI."""
        return tuple(float(v) for v in self._stops.mean(axis=0))

    # --- serialisation ---------------------------------------------------

    def to_dict(self) -> dict:
        return {"name": self.name, "cyclic": self.cyclic, "smooth": self.smooth,
                "colors": [list(map(float, c)) for c in self.colors]}

    @classmethod
    def from_dict(cls, data: dict) -> "Palette":
        return cls(name=data["name"],
                   colors=[tuple(c) for c in data["colors"]],
                   cyclic=bool(data.get("cyclic", False)),
                   smooth=bool(data.get("smooth", True)))

    def save(self, directory: Path | None = None) -> Path:
        directory = directory or PRESETS_DIR
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.name}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return path


# Palettes fournies. Les cycliques defilent sans couture ; les autres sont
# orientees (du sombre vers le clair) et conviennent aux effets a intensite.
BUILTIN: list[Palette] = [
    Palette("Arc-en-ciel", [(1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1), (1, 0, 1)], cyclic=True),
    Palette("Néon", [(1, 0, 0.6), (0, 1, 1), (0.8, 1, 0)], cyclic=True),
    Palette("Club", [(1, 0, 0.2), (0.6, 0, 1), (0, 0.4, 1)], cyclic=True),
    Palette("Feu", [(0, 0, 0), (0.6, 0, 0), (1, 0.3, 0), (1, 0.8, 0.1), (1, 1, 0.85)]),
    Palette("Braise", [(0.15, 0, 0), (0.8, 0.1, 0), (1, 0.5, 0)]),
    Palette("Océan", [(0, 0, 0.15), (0, 0.15, 0.6), (0, 0.6, 0.9), (0.7, 1, 1)]),
    Palette("Glace", [(0, 0.05, 0.2), (0, 0.5, 1), (0.8, 0.95, 1), (1, 1, 1)]),
    Palette("Coucher", [(0.2, 0, 0.3), (0.8, 0, 0.4), (1, 0.4, 0.1), (1, 0.9, 0.4)]),
    Palette("Menthe", [(0, 0.1, 0.05), (0, 0.8, 0.4), (0.6, 1, 0.8)]),
    Palette("Violet", [(0.05, 0, 0.15), (0.4, 0, 0.8), (0.9, 0.3, 1)]),
    Palette("Blanc", [(0, 0, 0), (1, 1, 1)]),
    Palette("Rouge", [(0, 0, 0), (1, 0, 0), (1, 0.6, 0.4)]),
]


def by_name(name: str) -> Palette:
    from ..effects.base import search_key
    from ..i18n import EN, tr

    key = search_key(name)
    palettes = all_palettes()
    for p in palettes:
        if search_key(p.name) == key:
            return p
    # Nom anglais : accepte quelle que soit la langue d'affichage.
    for p in palettes:
        if search_key(EN.get(p.name, p.name)) == key:
            return p
    known = ", ".join(tr(p.name) for p in palettes)
    raise KeyError(tr("palette inconnue : {!r} (connues : {})").format(name, known))


def all_palettes() -> list[Palette]:
    """Palettes fournies + celles enregistrees dans presets/palettes/."""
    out = list(BUILTIN)
    if PRESETS_DIR.exists():
        known = {p.name.lower() for p in out}
        for path in sorted(PRESETS_DIR.glob("*.json")):
            try:
                p = Palette.from_dict(json.loads(path.read_text()))
            except Exception:
                continue
            if p.name.lower() not in known:
                out.append(p)
    return out
