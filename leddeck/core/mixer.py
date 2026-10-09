"""Decks, crossfader et master.

Deck A et Deck B ont chacun leur effet, leur palette et leurs reglages. Le mixer
les combine selon la position du crossfader, puis le master applique strobe,
flash et blackout.
"""

from __future__ import annotations

import math
import time

import numpy as np

from ..effects.base import Effect, load_effects
from .palette import Palette, all_palettes

BLEND_MODES = ("fondu", "addition", "maximum")
CUSTOM_NAME = "Perso (RGB)"
MAX_CUSTOM_COLORS = 8

# Vitesse globale : course geometrique de x0,1 a x4 (une course lineaire rendrait
# la moitie basse inutilisable), avec le tout dernier cran a zero — arret net.
# Divisions du strobe quand il est calé sur le tempo : éclats par pulsation.
STROBE_DIVISIONS = (
    ("tous les 8 beats", 0.125),
    ("tous les 4 beats", 0.25),
    ("tous les 2 beats", 0.5),
    ("chaque beat", 1.0),
    ("2 par beat", 2.0),
    ("4 par beat", 4.0),
    ("8 par beat", 8.0),
)

SPEED_MIN, SPEED_MAX = 0.1, 4.0
SPEED_FREEZE = 0.03          # fraction basse de la course reservee a l'arret


def speed_from_unit(x: float) -> float:
    """Position de fader 0..1 -> vitesse. En dessous du seuil : arret complet."""
    x = min(1.0, max(0.0, float(x)))
    if x <= SPEED_FREEZE:
        return 0.0
    f = (x - SPEED_FREEZE) / (1.0 - SPEED_FREEZE)
    return math.exp(math.log(SPEED_MIN) + f * (math.log(SPEED_MAX) - math.log(SPEED_MIN)))


def speed_to_unit(speed: float) -> float:
    """Vitesse -> position de fader 0..1."""
    if speed <= 0.0:
        return 0.0
    speed = min(SPEED_MAX, max(SPEED_MIN, float(speed)))
    f = (math.log(speed) - math.log(SPEED_MIN)) / (math.log(SPEED_MAX) - math.log(SPEED_MIN))
    return SPEED_FREEZE + f * (1.0 - SPEED_FREEZE)


class Deck:
    """Un effet + une palette + ses reglages.

    Chaque deck possede ses *propres* instances d'effets : les deux decks peuvent
    jouer le meme effet avec des reglages et un etat differents.
    """

    def __init__(self, name: str, leds: int, strips: int) -> None:
        self.name = name
        self.leds, self.strips = leds, strips
        from ..effects.base import search_key

        classes = load_effects()
        self.effects: dict[str, Effect] = {
            cls.name: cls(leds, strips)
            for cls in sorted(classes.values(), key=lambda c: search_key(c.name))
        }
        # Chaque deck a sa palette perso, editable au selecteur RGB, en tete de liste.
        # Sans degrade : les couleurs choisies sortent telles quelles.
        self.custom = Palette(CUSTOM_NAME, [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)], smooth=False)
        # Copies et non references : l'interpolation se regle par deck, cocher la
        # case d'un cote ne doit pas changer l'autre.
        builtin = {q.name: Palette(q.name, list(q.colors), q.cyclic, q.smooth)
                   for q in all_palettes()}
        self.palettes: dict[str, Palette] = {CUSTOM_NAME: self.custom, **builtin}
        self.effect = next(iter(self.effects.values()))
        self.palette = next(iter(builtin.values()))

    def set_custom_colors(self, colors) -> None:
        self.custom.set_colors(list(colors))

    @property
    def effect_name(self) -> str:
        return self.effect.name

    @property
    def palette_name(self) -> str:
        return self.palette.name

    def set_effect(self, name: str) -> None:
        if name in self.effects:
            self.effect = self.effects[name]

    def set_palette(self, name: str) -> None:
        if name in self.palettes:
            self.palette = self.palettes[name]

    def render(self, t: float, dt: float, audio) -> np.ndarray:
        effect = self.effect
        return effect.render(t, dt, audio, self.palette, effect.p)


def blend_weights(mode: str, x: float) -> tuple[float, float]:
    """Poids (A, B) pour une position de crossfader x (0 = A, 1 = B)."""
    x = min(1.0, max(0.0, x))
    if mode == "fondu":
        return 1.0 - x, x
    # addition / maximum : chaque deck est a fond des la moitie de la course,
    # ce qui evite le creux de luminosite au centre du crossfader.
    return min(1.0, 2.0 * (1.0 - x)), min(1.0, 2.0 * x)


class Mixer:
    """Combine les deux decks. `crossfade` : 0 = A seul, 1 = B seul."""

    def __init__(self, leds: int, strips: int, keep_frames: bool = False) -> None:
        self.a = Deck("A", leds, strips)
        self.b = Deck("B", leds, strips)
        self.crossfade = 0.0
        self.mode = "fondu"
        self.auto = AutoCross()
        self.speed = 1.0            # vitesse globale, appliquee au temps des effets
        self._t = 0.0
        self._out = np.zeros((strips, leds, 3), dtype=np.float32)
        self._tmp = np.zeros((strips, leds, 3), dtype=np.float32)
        # Copies pour la previsualisation de chaque deck : les effets reutilisent
        # leur tampon, une reference se ferait modifier sous les yeux de l'UI.
        self.last_a = np.zeros((strips, leds, 3), dtype=np.float32) if keep_frames else None
        self.last_b = np.zeros((strips, leds, 3), dtype=np.float32) if keep_frames else None

    def render(self, t: float, dt: float, audio) -> np.ndarray:
        self.auto.update(self, dt, audio)
        if self.speed <= 0.0:
            # Arret net : le temps des effets ne s'ecoule plus, et on leur coupe
            # le son — sinon un effet cale sur le beat continuerait de bouger.
            # Le crossfader et le master, eux, restent vivants.
            dts, audio = 0.0, None
        else:
            dts = dt * self.speed
        self._t += dts
        # Les deux decks sont toujours calcules, meme a fond d'un cote : sinon
        # l'effet masque se fige et saute au moment ou on le fait revenir.
        a = self.a.render(self._t, dts, audio)
        b = self.b.render(self._t, dts, audio)
        if self.last_a is not None:
            np.copyto(self.last_a, a)
            np.copyto(self.last_b, b)

        fa, fb = blend_weights(self.mode, self.crossfade)
        np.multiply(a, np.float32(fa), out=self._out)
        np.multiply(b, np.float32(fb), out=self._tmp)
        if self.mode == "maximum":
            np.maximum(self._out, self._tmp, out=self._out)
        else:
            np.add(self._out, self._tmp, out=self._out)
            if self.mode == "addition":
                np.clip(self._out, 0.0, 1.0, out=self._out)
        return self._out


class Hold:
    """Fonction live pilotee par deux boutons : un verrou et un appui momentane.

    En club on veut les deux gestes pour la meme fonction : enclencher le strobe
    et le laisser, ou le donner par a-coups. La fonction est active si l'un ou
    l'autre l'est.
    """

    __slots__ = ("latched", "momentary")

    def __init__(self) -> None:
        self.latched = False
        self.momentary = False

    @property
    def active(self) -> bool:
        return self.latched or self.momentary

    def __bool__(self) -> bool:
        return self.active


class AutoCross:
    """Bascule le crossfader d'un deck a l'autre toutes les N pulsations."""

    def __init__(self) -> None:
        self.enabled = False
        self.beats = 16              # pulsations entre deux transitions
        self.fade_beats = 4.0        # duree de la transition (0 = coupure franche)
        self._count = 0
        self._last_beat: int | None = None
        self._target = 1.0
        self._free = 0.0             # accumulateur quand il n'y a pas de son

    def arm(self, mixer: "Mixer") -> None:
        """Prepare la prochaine transition vers le deck oppose."""
        self._target = 0.0 if mixer.crossfade > 0.5 else 1.0
        self._count = 0
        self._last_beat = None

    @property
    def beats_left(self) -> int:
        return max(0, int(self.beats) - self._count)

    def update(self, mixer: "Mixer", dt: float, audio) -> None:
        if not self.enabled:
            return
        period = audio.period if (audio is not None and audio.period > 0) else 0.5

        # Compter les pulsations : celles de l'analyse si le son est la, sinon
        # une horloge interne, pour que l'auto-mix tourne aussi sans musique.
        beats = 0
        if audio is not None:
            if self._last_beat is None:
                self._last_beat = audio.beat_count
            elif audio.beat_count != self._last_beat:
                beats = audio.beat_count - self._last_beat
                self._last_beat = audio.beat_count
        else:
            self._free += dt
            while self._free >= period:
                self._free -= period
                beats += 1

        if beats > 0:
            self._count += beats
            if self._count >= max(1, int(self.beats)):
                self._count = 0
                self._target = 0.0 if self._target > 0.5 else 1.0

        if self.fade_beats <= 0.0:
            mixer.crossfade = self._target
            return
        step = dt / max(1e-3, self.fade_beats * period)
        x = mixer.crossfade
        mixer.crossfade = min(self._target, x + step) if self._target > x else max(self._target, x - step)


class Master:
    """Traitements appliques apres le mixer : electrique, strobe, flash, blackout.

    Chacun a un verrou et un appui momentane (cf. `Hold`).
    La luminosite, elle, reste dans l'etage de sortie (avant le gamma).
    """

    def __init__(self, leds: int, strips: int) -> None:
        # Interrupteur global de la reactivite au son : dans le modele et non
        # dans l'interface, pour etre atteignable au MIDI.
        self.audio_enabled = True
        self.blackout = Hold()
        self.flash = Hold()
        self.strobe = Hold()
        self.strobe_hz = 12.0
        self.strobe_sync = False      # cale le strobe sur le beat
        self.strobe_division = 1.0    # eclats par pulsation, quand cale
        self.strobe_duty = 0.4

        # L'electrique est aussi une surcouche live : on le pose par-dessus ce qui
        # joue, comme le strobe, sans occuper un deck.
        from ..effects.electrique import Electrique

        self.electric = Hold()
        self.electric_fx = Electrique(leds, strips)
        self._black = np.zeros((strips, leds, 3), dtype=np.float32)
        self._white = np.ones((strips, leds, 3), dtype=np.float32)
        self._over = np.zeros((strips, leds, 3), dtype=np.float32)

    def apply(self, frame: np.ndarray, t: float, dt: float, audio, palette=None) -> np.ndarray:
        # Le flash passe avant tout, blackout compris : c'est le geste d'urgence
        # inverse, on veut de la lumiere immediatement quoi qu'il arrive.
        if self.flash:
            return self._white

        if self.electric and palette is not None:
            # L'electrique passe lui aussi devant le blackout et le strobe : sur
            # fond noir il ne reste que les eclats, ce qui est tout l'interet.
            sparks = self.electric_fx.render(t, dt, audio, palette, self.electric_fx.p)
            base = self._black if self.blackout else frame
            np.maximum(base, sparks, out=self._over)
            return self._over

        if self.blackout:
            return self._black

        if self.strobe:
            if self.strobe_sync and audio is not None and audio.period > 0:
                # Position continue en *beats* : le compteur de pulsations plus la
                # fraction écoulée depuis la dernière. Se caler sur le seul écart au
                # dernier beat ne marchait que pour les divisions d'un beat ou moins
                # — au-delà, la phase ne parcourait jamais le cycle entier et le
                # strobe restait allumé en continu.
                since = (time.monotonic() - audio.last_beat) / audio.period
                beats = audio.beat_count + min(1.0, max(0.0, since))
                phase = (beats * self.strobe_division) % 1.0
            else:
                period = 1.0 / max(0.5, self.strobe_hz)
                phase = (t % period) / period
            if phase >= self.strobe_duty:
                return self._black
        return frame
