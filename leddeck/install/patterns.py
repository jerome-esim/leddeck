"""Motifs de test et d'identification, dessines directement sur la matrice.

Deux familles :
  - les motifs *matrice* (verification du patch) : balayage, arc-en-ciel, numero de ligne
  - les motifs *bandeau* (identification physique) : numero de la sortie, sens du bandeau
"""

from __future__ import annotations

import numpy as np

GREEN = (0.0, 1.0, 0.0)
RED = (1.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)


def hsv_to_rgb(h, s=1.0, v=1.0) -> np.ndarray:
    """h, s, v : scalaires ou tableaux (0..1) -> tableau (..., 3) float 0..1."""
    h = np.asarray(h, dtype=np.float32) % 1.0
    s = np.broadcast_to(np.asarray(s, np.float32), h.shape)
    v = np.broadcast_to(np.asarray(v, np.float32), h.shape)
    i = np.floor(h * 6.0).astype(np.int32)
    f = h * 6.0 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    order = np.array([[0, 3, 1], [2, 0, 1], [1, 0, 3], [1, 2, 0], [3, 1, 0], [0, 1, 2]])
    comp = np.stack([v, p, q, t], axis=-1)            # (..., 4)
    idx = order[i % 6]                                # (..., 3)
    return np.take_along_axis(comp, idx, axis=-1)


# --- motifs bandeau (identification) -----------------------------------------


def number_line(number: int, leds: int, edge: int | None = None) -> np.ndarray:
    """Un bandeau qui affiche son numero : debut vert, fin rouge, N blocs blancs.

    Retourne (leds, 3) float 0..1.
    """
    line = np.zeros((leds, 3), dtype=np.float32)
    edge = edge if edge is not None else max(2, leds // 60)
    line[:edge] = GREEN
    line[leds - edge :] = RED

    block = max(2, leds // 45)
    gap = block
    start = edge + block
    room = leds - edge - start
    if room > 0 and number > 0:
        needed = number * (block + gap)
        if needed > room:  # bandeau court : on resserre
            block = max(1, room // (2 * number))
            gap = max(1, block)
        for k in range(number):
            a = start + k * (block + gap)
            b = min(a + block, leds - edge)
            if a >= b:
                break
            line[a:b] = WHITE
    return line


def identify(profile, t: float = 0.0) -> dict[int, np.ndarray]:
    """{output_id: ligne} : chaque sortie affiche son propre numero."""
    return {o.id: number_line(o.id, o.led_count) for o in profile.outputs if o.enabled}


def blink_line(number: int, leds: int, t: float, hz: float = 2.0) -> np.ndarray:
    """Le bandeau clignote en blanc, avec son numero visible quand il est allume."""
    on = (t * hz) % 1.0 < 0.5
    return number_line(number, leds) if on else np.zeros((leds, 3), np.float32)


def ruler_line(leds: int, base=(0.25, 0.0, 0.0)) -> np.ndarray:
    """Regle graduee : un repere tous les 10, plus marque tous les 50.

    Sert a compter ou s'arrete la partie eclairee quand on soupconne un bandeau
    plus long que ce qui est declare.
    """
    line = np.zeros((leds, 3), dtype=np.float32)
    line[:] = base
    idx = np.arange(leds)
    line[idx % 10 == 0] = (1.0, 1.0, 1.0)
    line[idx % 50 == 0] = (0.0, 0.6, 1.0)
    line[0] = GREEN
    return line


def ends_line(leds: int, mark: int = 5) -> np.ndarray:
    """Debut vert, fin bleue, milieu rouge sombre : ou tombe la fin declaree ?"""
    line = np.zeros((leds, 3), dtype=np.float32)
    line[:] = (0.2, 0.0, 0.0)
    line[:mark] = GREEN
    line[leds - mark:] = (0.0, 0.3, 1.0)
    return line


# --- motifs matrice (verification du patch) ----------------------------------


def solid(leds: int, strips: int, color=(1.0, 1.0, 1.0)) -> np.ndarray:
    frame = np.empty((strips, leds, 3), dtype=np.float32)
    frame[:] = np.asarray(color, np.float32)
    return frame


def sweep(t: float, leds: int, strips: int, speed: float = 0.5, width: int = 8) -> np.ndarray:
    """Un point qui balaie gauche -> droite sur toutes les lignes en meme temps.

    Toutes les lignes doivent avancer dans le meme sens : sinon, le patch est
    a inverser sur les lignes fautives.
    """
    frame = np.zeros((strips, leds, 3), dtype=np.float32)
    pos = (t * speed) % 1.0 * leds
    x = np.arange(leds, dtype=np.float32)
    d = np.abs(x - pos)
    d = np.minimum(d, leds - d)  # boucle propre
    intensity = np.clip(1.0 - d / max(1.0, width), 0.0, 1.0) ** 2
    frame[:] = intensity[:, None] * np.float32(WHITE)
    frame[:, 0] = GREEN                       # repere debut de ligne
    frame[:, leds - 1] = RED                  # repere fin de ligne
    return frame


def rainbow(t: float, leds: int, strips: int, speed: float = 0.1) -> np.ndarray:
    """Degrade arc-en-ciel de la ligne 1 a la ligne N : l'ordre du patch se lit d'un coup."""
    h = (np.arange(strips, dtype=np.float32) / max(1, strips) + t * speed) % 1.0
    colors = hsv_to_rgb(h)                    # (strips, 3)
    return np.repeat(colors[:, None, :], leds, axis=1).astype(np.float32)


def row_numbers(t: float, leds: int, strips: int) -> np.ndarray:
    """Chaque ligne de la matrice affiche *son* numero (1..N) : verifie le patch."""
    frame = np.zeros((strips, leds, 3), dtype=np.float32)
    for row in range(strips):
        frame[row] = number_line(row + 1, leds)
    return frame


def flow(t: float, leds: int, strips: int, speed: float = 0.15, cycles: float = 1.0) -> np.ndarray:
    """Arc-en-ciel qui defile le long des bandeaux : verifie le sens des LED d'un coup d'oeil."""
    x = np.arange(leds, dtype=np.float32) / max(1, leds)
    line = hsv_to_rgb((x * cycles - t * speed) % 1.0)      # (leds, 3)
    return np.repeat(line[None, :, :], strips, axis=0).astype(np.float32)


def chase(t: float, leds: int, strips: int, speed: float = 0.25) -> np.ndarray:
    """Un point par ligne, decale d'une ligne a l'autre : verifie l'ordre des lignes."""
    frame = np.zeros((strips, leds, 3), dtype=np.float32)
    x = np.arange(leds, dtype=np.float32)
    for row in range(strips):
        pos = ((t * speed + row / max(1, strips)) % 1.0) * leds
        d = np.abs(x - pos)
        inten = np.clip(1.0 - d / 6.0, 0.0, 1.0) ** 2
        frame[row] = inten[:, None] * hsv_to_rgb(row / max(1, strips))
    return frame


def audio_bars(leds: int, strips: int, spectrum: np.ndarray,
               level: float = 1.0, flash: float = 0.0) -> np.ndarray:
    """Spectre etale sur la longueur du bandeau : grave = bleu, aigu = rouge.

    `flash` (0..1) ajoute une impulsion blanche sur le beat. Sert a valider
    l'analyse audio sur le vrai materiel avant d'avoir les effets.
    """
    bands = np.asarray(spectrum, dtype=np.float32)
    if bands.size == 0:
        return np.zeros((strips, leds, 3), np.float32)
    x = np.linspace(0.0, bands.size - 1, leds)
    v = np.interp(x, np.arange(bands.size), bands).astype(np.float32)
    hue = np.linspace(0.66, 0.0, leds, dtype=np.float32)          # bleu -> rouge
    rgb = hsv_to_rgb(hue, 1.0, np.clip(v * max(0.0, level), 0.0, 1.0))
    frame = np.repeat(rgb[None, :, :], strips, axis=0).astype(np.float32)
    if flash > 0.0:
        frame = np.clip(frame + np.float32(flash), 0.0, 1.0)
    return frame


def beat_pulse(leds: int, strips: int, env: float, color=RED, floor: float = 0.04) -> np.ndarray:
    """Couleur unie dont l'intensite retombe apres chaque beat."""
    v = max(floor, min(1.0, float(env)))
    return (solid(leds, strips, color) * np.float32(v)).astype(np.float32)


MATRIX_PATTERNS = {
    "sweep": sweep,
    "rainbow": rainbow,
    "rows": row_numbers,
    "chase": chase,
    "flow": flow,
    "white": lambda t, leds, strips: solid(leds, strips, (1, 1, 1)),
    "red": lambda t, leds, strips: solid(leds, strips, RED),
    "green": lambda t, leds, strips: solid(leds, strips, GREEN),
    "blue": lambda t, leds, strips: solid(leds, strips, (0, 0, 1)),
    "off": lambda t, leds, strips: solid(leds, strips, (0, 0, 0)),
}
