"""Actions pilotables au MIDI, et reprise en douceur des faders.

Une action a un identifiant stable (« deck.effect »), d'eventuels arguments
(« quel deck, quel index »), et sait lire *et* ecrire la valeur : la lecture sert
au soft takeover et au retour visuel sur le controleur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..core.mixer import CUSTOM_NAME, MAX_CUSTOM_COLORS, speed_from_unit, speed_to_unit
from .mapping import FIXED_COLORS

# Couleurs que le controleur sait basculer. Une couleur venue du selecteur RGB
# n'en fait pas partie : aucun pad ne pourrait la retirer.
PAD_COLORS = {tuple(round(float(v), 3) for v in rgb) for _, rgb, _ in FIXED_COLORS}

CONTINU, GACHETTE = "continu", "gachette"


@dataclass
class Action:
    name: str
    label: str
    kind: str                                   # CONTINU (fader) ou GACHETTE (bouton)
    write: Callable[[float, dict], None]
    read: Callable[[dict], float] | None = None  # 0..1, pour le soft takeover
    # Un emplacement peut etre assigne sans rien avoir derriere (12 pads d'effets
    # pour 9 effets) : son pad doit rester eteint, pas juste « inactif ».
    exists: Callable[[dict], bool] | None = None
    args_hint: tuple[str, ...] = ()


class SoftTakeover:
    """Un fader ne prend la main qu'une fois arrive sur la valeur courante.

    Sans cela, toucher un fader fait sauter le reglage a la position physique du
    fader — inacceptable en live quand la valeur vient d'etre changee ailleurs.
    """

    def __init__(self, tolerance: float = 0.03) -> None:
        self.tolerance = tolerance
        self._caught: dict[str, bool] = {}
        self._previous: dict[str, float] = {}
        self._written: dict[str, float] = {}

    def allows(self, key: str, hardware: float, current: float) -> bool:
        # La valeur a bouge ailleurs (souris, auto-mix) : le fader doit reprendre.
        written = self._written.get(key)
        if written is not None and abs(current - written) > self.tolerance:
            self._caught[key] = False

        previous = self._previous.get(key)
        self._previous[key] = hardware

        if self._caught.get(key):
            self._written[key] = hardware
            return True
        crossed = previous is not None and (previous - current) * (hardware - current) <= 0.0
        if abs(hardware - current) <= self.tolerance or crossed:
            self._caught[key] = True
            self._written[key] = hardware
            return True
        return False

    def release(self, key: str | None = None) -> None:
        if key is None:
            self._caught.clear()
        else:
            self._caught.pop(key, None)

    def is_caught(self, key: str) -> bool:
        return bool(self._caught.get(key))


def build_actions(mixer, master, profile, analyzer=None) -> dict[str, Action]:
    """Table des actions, reliee aux objets vivants de l'application."""

    def deck_of(args: dict):
        return mixer.b if str(args.get("deck", "a")).lower() == "b" else mixer.a

    def set_crossfade(value: float, args: dict) -> None:
        mixer.auto.enabled = False          # le geste manuel reprend la main
        mixer.crossfade = value

    def set_param(value: float, args: dict) -> None:
        effect = deck_of(args).effect
        keys = list(effect.p)
        index = int(args.get("index", 0))
        if 0 <= index < len(keys):
            effect.p.set_normalized(keys[index], value)

    def read_param(args: dict) -> float:
        effect = deck_of(args).effect
        keys = list(effect.p)
        index = int(args.get("index", 0))
        return effect.p.normalized(keys[index]) if 0 <= index < len(keys) else 0.0

    def pick_effect(value: float, args: dict) -> None:
        if value <= 0.0:
            return
        deck = deck_of(args)
        names = profile.pad_effects(list(deck.effects))
        index = int(args.get("index", 0))
        if 0 <= index < len(names):
            deck.set_effect(names[index])

    def read_effect(args: dict) -> float:
        deck = deck_of(args)
        names = profile.pad_effects(list(deck.effects))
        index = int(args.get("index", 0))
        return 1.0 if 0 <= index < len(names) and names[index] == deck.effect_name else 0.0

    def pick_palette(value: float, args: dict) -> None:
        if value <= 0.0:
            return
        deck = deck_of(args)
        names = list(deck.palettes)
        index = int(args.get("index", 0))
        if 0 <= index < len(names):
            deck.set_palette(names[index])

    def read_palette(args: dict) -> float:
        deck = deck_of(args)
        names = list(deck.palettes)
        index = int(args.get("index", 0))
        return 1.0 if 0 <= index < len(names) and names[index] == deck.palette_name else 0.0

    def _custom_colors(deck) -> list[tuple]:
        return [tuple(round(float(v), 3) for v in c) for c in deck.custom.colors]

    def pick_color(value: float, args: dict) -> None:
        """Coche ou decoche une couleur : la palette perso se construit ainsi.

        Tant qu'aucune couleur du controleur n'est active — deck sur une autre
        palette, ou palette perso composee au selecteur RGB — le premier appui
        *remplace* la selection. Sans cela, une couleur choisie a l'ecran restait
        en tete sans qu'aucun pad puisse la retirer.
        """
        if value <= 0.0:
            return
        deck = deck_of(args)
        rgb = tuple(round(float(v), 3) for v in args.get("rgb", (1, 1, 1)))
        current = _custom_colors(deck)
        on_custom = deck.palette_name == CUSTOM_NAME
        active_pads = [c for c in current if c in PAD_COLORS] if on_custom else []
        if not active_pads:
            colors = [rgb]
        elif rgb in current:
            colors = [c for c in current if c != rgb] or [rgb]   # jamais vide
        elif len(current) >= MAX_CUSTOM_COLORS:
            colors = current                                     # plein
        else:
            colors = current + [rgb]
        deck.set_custom_colors(colors)
        deck.set_palette(CUSTOM_NAME)

    def read_color(args: dict) -> float:
        deck = deck_of(args)
        if deck.palette_name != CUSTOM_NAME:
            return 0.0
        rgb = tuple(round(float(v), 3) for v in args.get("rgb", (1, 1, 1)))
        return 1.0 if rgb in _custom_colors(deck) else 0.0

    def hold(value: float, args: dict) -> None:
        target = getattr(master, str(args.get("name", "blackout")), None)
        if target is None:
            return
        if str(args.get("mode", "momentary")) == "latch":
            if value > 0.0:                 # on bascule a l'appui seulement
                target.latched = not target.latched
        else:
            target.momentary = value > 0.0

    def read_hold(args: dict) -> float:
        target = getattr(master, str(args.get("name", "blackout")), None)
        return 1.0 if target is not None and bool(target) else 0.0

    def toggle_audio(value: float, args: dict) -> None:
        if value > 0.0:
            master.audio_enabled = not master.audio_enabled

    def tap(value: float, args: dict) -> None:
        if value > 0.0 and analyzer is not None:
            analyzer.tap()

    def toggle_auto(value: float, args: dict) -> None:
        if value <= 0.0:
            return
        if not mixer.auto.enabled:
            mixer.auto.arm(mixer)
        mixer.auto.enabled = not mixer.auto.enabled

    def set_auto_beats(value: float, args: dict) -> None:
        if value > 0.0:
            mixer.auto.beats = int(args.get("beats", 16))

    actions = [
        Action("crossfade", "Crossfader", CONTINU, set_crossfade, lambda a: mixer.crossfade),
        Action("master.brightness", "Luminosité", CONTINU,
               lambda v, a: setattr(profile, "brightness", v), lambda a: profile.brightness),
        Action("master.speed", "Vitesse globale", CONTINU,
               lambda v, a: setattr(mixer, "speed", speed_from_unit(v)),
               lambda a: speed_to_unit(mixer.speed)),
        Action("deck.param", "Réglage d'effet", CONTINU, set_param, read_param,
               None, ("deck", "index")),
        Action("deck.effect", "Choisir un effet", GACHETTE, pick_effect, read_effect,
               lambda a: int(a.get("index", 0)) < len(deck_of(a).effects), ("deck", "index")),
        Action("deck.palette", "Choisir une palette", GACHETTE, pick_palette, read_palette,
               lambda a: int(a.get("index", 0)) < len(deck_of(a).palettes), ("deck", "index")),
        Action("deck.color", "Couleur unie", GACHETTE, pick_color, read_color,
               None, ("deck", "rgb", "pad")),
        Action("master.hold", "Strobe / flash / blackout / électrique", GACHETTE, hold, read_hold,
               None, ("name", "mode")),
        Action("master.audio", "Son réactif", GACHETTE, toggle_audio,
               lambda a: 1.0 if master.audio_enabled else 0.0),
        Action("tap", "Tap tempo", GACHETTE, tap),
        Action("auto.toggle", "Crossfade auto", GACHETTE, toggle_auto,
               lambda a: 1.0 if mixer.auto.enabled else 0.0),
        Action("auto.beats", "Durée de l'auto-mix", GACHETTE, set_auto_beats,
               lambda a: 1.0 if mixer.auto.beats == int(a.get("beats", 16)) else 0.0,
               None, ("beats",)),
    ]
    return {action.name: action for action in actions}
