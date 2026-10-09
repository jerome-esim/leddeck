"""Parametres nommes, bornes, et leur valeur courante.

Chaque reglage a un identifiant, une plage et une valeur par defaut. L'interface,
le MIDI et l'auto-mix ecriront tous au meme endroit : c'est l'amorce du bus de
parametres. La valeur normalisee 0..1 est ce que fournit un fader MIDI.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


SLIDER, SWITCH = "curseur", "interrupteur"


@dataclass(frozen=True)
class ParamSpec:
    name: str
    lo: float
    hi: float
    default: float
    kind: str = SLIDER          # SWITCH : oui/non, pas un reglage continu

    @property
    def is_switch(self) -> bool:
        return self.kind == SWITCH

    def clamp(self, value: float) -> float:
        return float(min(self.hi, max(self.lo, value)))

    def normalize(self, value: float) -> float:
        """Valeur reelle -> 0..1 (position d'un fader)."""
        span = self.hi - self.lo
        return 0.0 if span <= 0 else float((self.clamp(value) - self.lo) / span)

    def denormalize(self, x: float) -> float:
        """0..1 -> valeur reelle."""
        return self.clamp(self.lo + (self.hi - self.lo) * float(min(1.0, max(0.0, x))))


def search_key(name: str) -> str:
    """Cle sans accents ni casse : « réactivité » se tape « reactivite »."""
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


class ParamSet:
    """Valeurs courantes d'un jeu de parametres. `p["vitesse"]` renvoie un float.

    Les noms affiches sont accentues ; la recherche ne l'est pas, pour que la
    ligne de commande reste tapable sans accents.
    """

    def __init__(self, specs: dict[str, tuple]) -> None:
        # Un parametre se declare (min, max, defaut) ou (min, max, defaut, genre).
        self.specs = {k: ParamSpec(k, *v) for k, v in specs.items()}
        self.values = {k: s.default for k, s in self.specs.items()}
        self._keys = {search_key(k): k for k in self.specs}

    def resolve(self, key: str) -> str:
        return self._keys.get(search_key(key), key)

    def __getitem__(self, key: str) -> float:
        return self.values[self.resolve(key)]

    def __setitem__(self, key: str, value: float) -> None:
        key = self.resolve(key)
        self.values[key] = self.specs[key].clamp(value)

    def __contains__(self, key: str) -> bool:
        return self.resolve(key) in self.values

    def __iter__(self):
        return iter(self.specs)

    def get(self, key: str, default: float = 0.0) -> float:
        return self.values.get(self.resolve(key), default)

    def set_normalized(self, key: str, x: float) -> None:
        """Ecriture depuis un fader 0..1."""
        key = self.resolve(key)
        self.values[key] = self.specs[key].denormalize(x)

    def normalized(self, key: str) -> float:
        key = self.resolve(key)
        return self.specs[key].normalize(self.values[key])

    def reset(self) -> None:
        self.values = {k: s.default for k, s in self.specs.items()}

    def as_dict(self) -> dict[str, float]:
        return dict(self.values)

    def update(self, values: dict[str, float]) -> None:
        for k, v in values.items():
            if k in self:
                self[k] = v
