"""Moteur : boucle a cadence fixe, dans un thread dedie, independante de l'UI.

Le moteur appelle une fonction de rendu qui retourne la matrice (N, L, 3) en
float 0..1, puis la pousse vers l'etage de sortie (patch + DDP).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Protocol

import numpy as np

from ..i18n import tr

# Le moteur ne regarde pas le contenu de la frame : il la transmet telle quelle au
# sink. Normalement une matrice (N, L, 3), mais le mode installation envoie un
# dictionnaire {output_id: ligne} au sink direct.
Frame = Any
RenderFn = Callable[[float, float], Frame]


class Sink(Protocol):
    def send_frame(self, frame: Frame, brightness: float | None = None) -> None: ...


class Engine:
    """Boucle temps reel : cadence stable, jamais bloquante, sans derive."""

    def __init__(self, render: RenderFn, sink: Sink, fps: int = 40, name: str = "engine") -> None:
        self.render = render
        self.sink = sink
        self.fps = fps
        self.name = name
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # statistiques, lues par l'UI
        self.frames = 0
        self.late_frames = 0
        self.measured_fps = 0.0
        self.last_render_ms = 0.0

    # --- cycle de vie ---------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
            self._thread = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def run_for(self, seconds: float | None = None) -> None:
        """Version bloquante (outils en ligne de commande) : Ctrl-C pour sortir."""
        self.start()
        try:
            deadline = None if seconds is None else time.monotonic() + seconds
            while self.running and (deadline is None or time.monotonic() < deadline):
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # --- boucle ---------------------------------------------------------

    def _run(self) -> None:
        period = 1.0 / self.fps
        start = time.monotonic()
        next_frame = start
        last = start
        fps_mark, fps_count = start, 0

        while not self._stop.is_set():
            now = time.monotonic()
            t, dt = now - start, now - last
            last = now

            try:
                t0 = time.perf_counter()
                frame = self.render(t, dt)
                if frame is not None:
                    self.sink.send_frame(frame)
                self.last_render_ms = (time.perf_counter() - t0) * 1000.0
            except Exception as exc:  # un effet qui plante ne doit pas tuer les LED
                print(tr("[engine] erreur de rendu : {!r}").format(exc))

            self.frames += 1
            fps_count += 1
            if now - fps_mark >= 1.0:
                self.measured_fps = fps_count / (now - fps_mark)
                fps_mark, fps_count = now, 0

            next_frame += period
            delay = next_frame - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            else:
                # On a pris du retard : on repart de maintenant (pas de rattrapage
                # en rafale, qui ferait sauter les effets).
                self.late_frames += 1
                next_frame = time.monotonic()
