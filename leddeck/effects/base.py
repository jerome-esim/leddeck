"""Classe de base des effets et chargement automatique du dossier `effects/`.

Un effet dessine sur la matrice (N, L, 3) en float 0..1 et ne choisit jamais de
couleur en dur : il interroge la palette du deck. Il doit fonctionner sans son
(`audio` a None) : le club n'est pas toujours en musique.
"""

from __future__ import annotations

import importlib
import pkgutil
import unicodedata
from typing import TYPE_CHECKING

import numpy as np

from ..i18n import EN, tr

from ..core.params import ParamSet

if TYPE_CHECKING:  # pragma: no cover
    from ..audio.analysis import AudioState
    from ..core.palette import Palette


class Effect:
    """A heriter pour creer un effet.

    `name`   : nom affiche
    `params` : {identifiant: (min, max, defaut)}
    """

    name: str = "Effet"
    params: dict[str, tuple[float, float, float]] = {}

    def __init__(self, leds: int, strips: int) -> None:
        self.leds = leds
        self.strips = strips
        self.p = ParamSet(self.params)
        self.frame = np.zeros((strips, leds, 3), dtype=np.float32)
        self.reset()

    def reset(self) -> None:
        """Remet l'effet a zero (changement de deck, de taille de matrice...)."""

    def render(self, t: float, dt: float, audio: "AudioState | None",
               palette: "Palette", p: ParamSet) -> np.ndarray:
        """Retourne un tableau (N, L, 3) de floats 0..1."""
        raise NotImplementedError

    # --- aides pour les effets -------------------------------------------

    @staticmethod
    def audio_value(audio: "AudioState | None", field: str, default: float = 0.0) -> float:
        return default if audio is None else float(getattr(audio, field, default))

    @staticmethod
    def reactive(audio: "AudioState | None", field: str, react: float,
                 floor: float = 0.25, gain: float = 1.3) -> float:
        """Intensite 0..1 melangeant une base fixe et une bande audio.

        Sans son, la reactivite est ignoree : un effet ne doit jamais etre sombre
        simplement parce que le micro est coupe.
        """
        if audio is None:
            return 1.0
        v = float(getattr(audio, field, 0.0))
        react = min(1.0, max(0.0, react))
        return float(min(1.0, (1.0 - react) + react * (floor + (1.0 - floor) * v * gain)))

    def beat_happened(self, audio: "AudioState | None") -> bool:
        """True une seule fois par beat, quel que soit le nombre d'appels."""
        if audio is None:
            return False
        last = getattr(self, "_last_beat_count", None)
        self._last_beat_count = audio.beat_count
        return last is not None and audio.beat_count != last


def shader_random(x):
    """`fract(sin(x) * 43758.5453)` — le generateur des shaders MadMapper.

    Repris tel quel pour que les effets portes depuis un shader gardent
    exactement le meme grain aleatoire que l'original.
    """
    v = np.sin(np.asarray(x, dtype=np.float64)) * 43758.5453
    return np.asarray(v - np.floor(v), dtype=np.float32)


def shader_random2(a, b):
    """Variante a deux entrees des shaders : `dot(st, vec2(12.9898, 78.233))`."""
    v = np.sin(np.asarray(a, dtype=np.float64) * 12.9898
               + np.asarray(b, dtype=np.float64) * 78.233) * 43758.5453
    return np.asarray(v - np.floor(v), dtype=np.float32)


def smoothstep(edge0, edge1, x):
    t = np.clip((np.asarray(x, dtype=np.float32) - edge0) / max(1e-6, edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


_REGISTRY: dict[str, type[Effect]] = {}


def search_key(name: str) -> str:
    """Cle de recherche sans accents ni casse : « Ciel étoilé » se tape « ciel etoile »."""
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def register(cls: type[Effect]) -> type[Effect]:
    _REGISTRY[search_key(cls.name)] = cls
    return cls


def load_effects() -> dict[str, type[Effect]]:
    """Importe tous les modules de `leddeck.effects` et collecte les effets."""
    if _REGISTRY:
        return dict(_REGISTRY)
    package = importlib.import_module(__package__)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name != "base":
            importlib.import_module(f"{__package__}.{info.name}")
    return dict(_REGISTRY)


def effect_names() -> list[str]:
    # Tri sans les accents : sinon « Électrique » passe après « Vague » et
    # « Néon » après « Noir », l'ordre des octets n'étant pas l'ordre français.
    return [cls.name for cls in sorted(load_effects().values(), key=lambda c: search_key(c.name))]


def by_name(name: str) -> type[Effect]:
    effects = load_effects()
    key = search_key(name)
    if key in effects:
        return effects[key]
    # Nom anglais : accepte quelle que soit la langue d'affichage, sinon le nom
    # appris dans « fx list » cesserait de marcher en rebasculant en francais.
    for cls in effects.values():
        if search_key(EN.get(cls.name, cls.name)) == key:
            return cls
    known = ", ".join(tr(n) for n in effect_names())
    raise KeyError(tr("effet inconnu : {!r} (connus : {})").format(name, known))
