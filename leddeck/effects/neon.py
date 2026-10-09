"""Neon : tubes qui chauffent avant d'accrocher.

Reprend le modele du shader ISF « Neons qui chauffent » utilise dans MadMapper :
  - `nombre` creneaux independants, decales d'un demi-cycle les uns des autres ;
  - chaque creneau tire un tube au hasard a chaque cycle ;
  - un cycle = amorcage (scintillement d'amplitude croissante) -> allume -> fondu lineaire.

La difference avec un simple clignotement : pendant l'amorcage l'amplitude *monte*
(`progression x scintillement`), donc le tube grelotte d'abord faiblement puis de
plus en plus fort. C'est ce qui donne la sensation de chauffe.

Ajouts par rapport au shader : la couleur vient de la palette du deck (le shader
n'en avait qu'une), et la lueur orangee des electrodes est optionnelle.
"""

from __future__ import annotations

import numpy as np

from .base import Effect, register

# Lueur orangee des electrodes avant l'amorcage.
ELECTRODE = np.array([0.35, 0.12, 0.03], dtype=np.float32)
FLICKER_HZ = 30.0


def _random(x: float) -> float:
    """`fract(sin(x) * 43758.5453)` — le generateur du shader, repris tel quel."""
    return float(np.modf(np.sin(x) * 43758.5453)[0] % 1.0)


@register
class Neon(Effect):
    name = "Néon"
    params = {
        # Les trois premiers tombent sur les faders : ce sont ceux qu'on touche.
        "nombre": (1, 16, 3),             # creneaux actifs en meme temps
        "amorçage": (0.1, 3.0, 0.5),      # duree de la chauffe
        "durée": (0.5, 10.0, 2.0),        # duree allume
        "vitesse": (0.1, 3.0, 0.5),       # < 1 : tout se deroule plus lentement
        "extinction": (0.1, 2.0, 0.3),    # fondu de sortie
        "électrodes": (0.0, 1.0, 0.5),    # lueur orangee pendant la chauffe
        "répartition": (0.0, 1.0, 1.0),   # 0 = comme le shader, 1 = creneaux repartis
    }

    def reset(self) -> None:
        self._ends = max(1, self.leds // 25)

    def render(self, t, dt, audio, palette, p):
        warmup, on_time, off_time = p["amorçage"], p["durée"], p["extinction"]
        total = warmup + on_time + off_time
        glow_amount = p["électrodes"]

        self.frame.fill(0.0)
        count = max(1, int(p["nombre"]))
        # Le shader decalait les creneaux d'un demi-cycle chacun : modulo un cycle,
        # cela ne fait que *deux* phases distinctes (les creneaux 1 et 3 sont
        # synchrones), d'ou des moments ou tous les tubes s'eteignent ensemble.
        # « repartition » a 1 les etale regulierement sur le cycle.
        spread = p["répartition"]
        offset = total * (0.5 * (1.0 - spread) + spread / count)
        for slot in range(count):
            local = t * p["vitesse"] + slot * offset
            cycle = np.floor(local / total)
            phase = local % total
            row = int(_random(float(cycle) + slot * 100.0) * self.strips) % self.strips

            glow = 0.0
            if phase < warmup:
                progress = phase / max(1e-3, warmup)
                # Scintillement rapide dont l'amplitude monte avec la chauffe.
                flicker = 1.0 if _random(np.floor(t * FLICKER_HZ + slot)) > 0.5 else 0.0
                intensity = progress * flicker
                glow = glow_amount * (1.0 - progress * 0.7)
            elif phase < warmup + on_time:
                intensity = 1.0
            else:
                intensity = 1.0 - (phase - warmup - on_time) / max(1e-3, off_time)

            if intensity <= 0.0 and glow <= 0.0:
                continue

            color = palette.sample(_random(float(cycle) + slot * 7.0))
            line = self.frame[row]
            # Superposition en maximum, comme le `max(maxIntensity, intensity)` du
            # shader : deux creneaux peuvent tomber sur le meme tube.
            np.maximum(line, color * np.float32(max(0.0, intensity)), out=line)
            if glow > 0.0:
                warm = ELECTRODE * np.float32(glow)
                np.maximum(line[: self._ends], warm, out=line[: self._ends])
                np.maximum(line[-self._ends :], warm, out=line[-self._ends :])
        return self.frame
