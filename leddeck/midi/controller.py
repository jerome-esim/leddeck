"""Contrôleur MIDI : relie les messages aux actions, et renvoie l'état aux pads."""

from __future__ import annotations

from typing import Callable

from .actions import CONTINU, SoftTakeover
from .mapping import Mapping
from .midi import NOTE, Control, MidiLink

# Palette de l'APC mini MK2 (indices standard de la palette du controleur).
OFF, WHITE, RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PINK = 0, 3, 5, 9, 13, 21, 33, 45, 53

# Sur MK2, le *canal* porte la luminosite et le clignotement :
#   canal 0 = 10 %, 6 = 100 %, 11 a 15 = clignotement de plus en plus lent.
CH_DIM, CH_FULL, CH_BLINK = 0, 6, 13

# Couleur fixe par fonction live, pour la reconnaitre sans lire l'etiquette.
HOLD_COLORS = {"electric": BLUE, "strobe": ORANGE, "flash": WHITE, "blackout": RED}


GRID_LAST_NOTE = 63      # au-dela, les boutons n'ont qu'une LED monochrome


def pad_style(binding, active: bool, note: int = 0) -> tuple[int, int]:
    """(velocite, canal) a envoyer pour ce binding, selon qu'il est actif ou non.

    Les effets sont en blanc : faible au repos, clignotant a fond quand ils
    jouent — c'est le seul endroit ou il faut voir d'un coup d'oeil ce qui tourne.
    Les couleurs unies et les palettes gardent leur teinte propre.

    Hors de la grille, les boutons track et scene n'ont qu'une LED monochrome :
    leur envoyer une couleur a faible intensite les laisse simplement allumes en
    permanence. On s'y limite donc a eteint / allume.
    """
    if note > GRID_LAST_NOTE:
        return (1 if active else 0), 0
    action = binding.action
    if action == "deck.effect":
        return WHITE, (CH_BLINK if active else CH_DIM)
    if action == "deck.palette":
        deck = str(binding.args.get("deck", "a")).lower()
        return (PINK if deck == "b" else CYAN), (CH_FULL if active else CH_DIM)
    if action == "deck.color":
        return int(binding.args.get("pad", WHITE)), (CH_FULL if active else CH_DIM)
    if action == "master.hold":
        color = HOLD_COLORS.get(str(binding.args.get("name", "")), RED)
        return color, (CH_FULL if active else CH_DIM)
    return GREEN, (CH_FULL if active else CH_DIM)


class MidiController:
    """Fait vivre un mapping : reception, soft takeover, retour visuel."""

    def __init__(self, mapping: Mapping, actions: dict, port: str | None = None,
                 on_learn: Callable[[Control], None] | None = None) -> None:
        self.mapping = mapping
        self.actions = actions
        self.takeover = SoftTakeover()
        self.link = MidiLink(port or mapping.port or None, on_control=self._on_control)
        self.on_learn = on_learn
        self.learning = False
        self.last_control: Control | None = None
        self.ignored = 0              # messages recus sans binding
        self._led_cache: dict[int, tuple[int, int]] = {}

    # --- cycle de vie ---------------------------------------------------

    def start(self) -> None:
        self.link.start()

    def stop(self) -> None:
        self.all_pads_off()
        self.link.stop()

    @property
    def connected(self) -> bool:
        return self.link._in is not None

    # --- reception --------------------------------------------------------

    def _on_control(self, control: Control, value: float, msg) -> None:
        self.last_control = control
        if self.learning:
            self.learning = False
            if self.on_learn is not None:
                self.on_learn(control)
            return

        binding = self.mapping.get(control)
        if binding is None:
            self.ignored += 1
            return
        action = self.actions.get(binding.action)
        if action is None:
            return

        if action.kind == CONTINU and action.read is not None:
            # Le fader ne prend la main qu'une fois revenu sur la valeur courante.
            if not self.takeover.allows(control.key, value, action.read(binding.args)):
                return
        action.write(value, binding.args)

    def learn_next(self) -> None:
        """La prochaine commande touchee sera rapportee a `on_learn`."""
        self.learning = True

    # --- retour visuel ----------------------------------------------------

    def _send_pad(self, note: int, color: int, channel: int = CH_FULL) -> None:
        if self._led_cache.get(note) == (color, channel):
            return                      # ne rien renvoyer d'inchange : le MIDI est lent
        self._led_cache[note] = (color, channel)
        self.link.send_note(note, color, channel)

    def refresh_leds(self) -> None:
        """Reporte l'etat de l'application sur les pads et boutons."""
        if self.link._out is None:
            return
        for key, binding in self.mapping.bindings.items():
            control = Control.parse(key)
            if control.kind != NOTE:
                continue
            action = self.actions.get(binding.action)
            if action is None or action.read is None:
                continue
            if action.exists is not None and not action.exists(binding.args):
                # Emplacement assigne mais vide : pad eteint, pas « blanc faible ».
                self._send_pad(control.number, OFF, 0)
                continue
            color, channel = pad_style(binding, action.read(binding.args) > 0.5,
                                       control.number)
            self._send_pad(control.number, color, channel)

    def all_pads_off(self) -> None:
        for note in list(self._led_cache):
            self.link.send_note(note, OFF, 0)
        self._led_cache.clear()
