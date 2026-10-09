"""Analyse audio : bandes de frequences, gain auto, detection de beat, BPM.

L'analyse tourne dans le thread audio (un appel par bloc, ~86 fois par seconde).
Le moteur, lui, lit un instantane `AudioState` : l'objet est remplace d'un coup
a chaque bloc, donc la lecture ne demande aucun verrou.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

# Bandes utiles en club : le kick vit sous 150 Hz, les voix et la caisse claire
# au milieu, les charlestons en haut.
BASS = (30.0, 150.0)
MID = (150.0, 2000.0)
TREBLE = (2000.0, 12000.0)

SPECTRUM_BANDS = 32
SPECTRUM_RANGE = (40.0, 16000.0)

# La fenetre d'analyse est plus large que le pas d'avancement : le pas donne la
# resolution temporelle (11,6 ms, pour caler un beat), la fenetre la resolution
# frequentielle. Avec 512 points seulement, toute la bande des basses tiendrait
# dans un seul bin a 86 Hz — inexploitable pour un kick.
FFT_SIZE = 2048            # 21,5 Hz de resolution a 44,1 kHz

BEAT_BAND = (20.0, 250.0)  # la detection d'attaque ne regarde que le bas du spectre :
                           # en club le beat est porte par le kick, et les charlestons
                           # de contretemps feraient sortir le double du tempo.
MIN_BPM, MAX_BPM = 70.0, 180.0
MIN_BEAT_GAP = 0.22        # s : evite de compter deux fois la meme attaque
BEAT_WINDOW = 0.25         # tolerance autour de la pulsation prevue, en fraction de beat
BAND_RELEASE = 0.88        # descente des bandes par bloc (~160 ms) : evite le scintillement
ENV_SECONDS = 6.0          # fenetre d'autocorrelation pour le BPM
BPM_EVERY = 0.5            # s entre deux estimations de BPM
SILENCE_PEAK = 1e-4


@dataclass(frozen=True)
class AudioState:
    """Instantane de l'analyse, consomme par les effets."""

    t: float = 0.0
    level: float = 0.0          # niveau global 0..1 (apres gain auto)
    bass: float = 0.0
    mid: float = 0.0
    treble: float = 0.0
    spectrum: np.ndarray = field(default_factory=lambda: np.zeros(SPECTRUM_BANDS, np.float32))
    onset: float = 0.0          # force de l'attaque en cours, 0..1
    beat_count: int = 0         # compteur monotone : +1 a chaque beat
    last_beat: float = 0.0
    period: float = 0.0         # duree d'un beat, en secondes
    bpm: float = 0.0
    bpm_confidence: float = 0.0
    silent: bool = True

    @property
    def phase(self) -> float:
        """Position dans le beat courant, 0..1 (utile pour animer entre deux beats)."""
        if self.period <= 0.0:
            return 0.0
        return ((time.monotonic() - self.last_beat) / self.period) % 1.0


class Follower:
    """Gain automatique : normalise entre le plancher de bruit et la crete recente.

    Normaliser par la seule crete ne suffit pas : l'echelle des magnitudes FFT
    depend du nombre de bins de la bande (5 pour les basses, 465 pour les aigus),
    donc aucun seuil absolu ne convient. On suit donc les deux bornes :
      - la crete redescend lentement  -> l'appli s'adapte au volume du club
      - le plancher remonte lentement -> le bruit de fond de la salle est soustrait
    """

    def __init__(self, decay: float = 0.9992, rise: float = 1.0002, eps: float = 1e-9,
                 subtract_floor: bool = True) -> None:
        self.decay = decay          # descente de la crete, par bloc (~7 %/s)
        self.rise = rise            # montee du plancher, par bloc (~1,7 %/s)
        self.eps = eps
        # Soustraire le plancher donne du contraste sur une bande (le bruit de salle
        # disparait), mais fausserait le niveau global : celui-ci doit rester haut
        # tant que la musique joue, pas retomber entre deux kicks.
        self.subtract_floor = subtract_floor
        self.peak = eps
        self.floor = 0.0

    def update(self, value: float) -> float:
        value = float(value)
        self.peak = max(value, self.peak * self.decay, self.eps)
        if value < self.floor:
            self.floor = value                     # un creux plus bas : on suit tout de suite
        else:
            self.floor = min(self.floor * self.rise + self.eps, self.peak)
        if not self.subtract_floor:
            return float(min(1.0, value / self.peak)) if self.peak > self.eps else 0.0
        span = self.peak - self.floor
        if span <= self.eps:
            return 0.0
        return float(min(1.0, max(0.0, (value - self.floor) / span)))

    def reset(self) -> None:
        self.peak = self.eps
        self.floor = 0.0


class Analyzer:
    """Transforme les blocs audio en `AudioState`."""

    def __init__(self, samplerate: int = 44100, blocksize: int = 512,
                 bands: int = SPECTRUM_BANDS, fft_size: int = FFT_SIZE) -> None:
        self.sr = samplerate
        self.n = blocksize                      # pas d'avancement (hop)
        self.fft_size = max(fft_size, blocksize)
        self.block_dt = blocksize / samplerate
        self.window = np.hanning(self.fft_size).astype(np.float32)
        self.freqs = np.fft.rfftfreq(self.fft_size, 1.0 / samplerate)
        self._buf = np.zeros(self.fft_size, dtype=np.float32)

        self._slice_beat = self._slice(*BEAT_BAND)
        self._slice_bass = self._slice(*BASS)
        self._slice_mid = self._slice(*MID)
        self._slice_treble = self._slice(*TREBLE)

        edges = np.geomspace(SPECTRUM_RANGE[0], SPECTRUM_RANGE[1], bands + 1)
        self._spec_slices = [self._slice(edges[i], edges[i + 1]) for i in range(bands)]
        self._spec_followers = [Follower(decay=0.9990) for _ in range(bands)]

        self._f_level = Follower(subtract_floor=False)
        self._f_bass = Follower()
        self._f_mid = Follower()
        self._f_treble = Follower()
        self._f_flux = Follower(decay=0.9990)
        self._band_prev = np.zeros(3, dtype=np.float32)
        self._level_prev = 0.0

        self._prev_mag = np.zeros(len(self.freqs), dtype=np.float32)
        self._flux_hist: deque[float] = deque(maxlen=int(ENV_SECONDS / self.block_dt))
        self._beat_flux_hist: deque[float] = deque(maxlen=int(1.5 / self.block_dt))
        self._prev_beat_flux = 0.0

        self._beat_count = 0
        self._last_beat = 0.0        # ancre de la grille
        self._last_emit = 0.0        # dernier beat reellement emis
        self._period = 0.0
        self._bpm = 0.0
        self._bpm_conf = 0.0
        self._next_bpm_at = 0.0
        self._taps: list[float] = []
        self._tapped = False
        # Correction d'octave : l'autocorrelation se verrouille parfois sur le
        # double ou la moitie du tempo reel. Ce facteur persiste d'une estimation
        # a l'autre, sinon la correction serait effacee a la seconde suivante.
        self._octave = 1.0

        self._state = AudioState()

    # --- outils ---------------------------------------------------------

    def _slice(self, lo: float, hi: float) -> slice:
        i0 = int(np.searchsorted(self.freqs, lo))
        i1 = max(i0 + 1, int(np.searchsorted(self.freqs, hi)))
        return slice(i0, min(i1, len(self.freqs)))

    def state(self) -> AudioState:
        return self._state

    # --- analyse d'un bloc ----------------------------------------------

    def process(self, mono: np.ndarray, now: float | None = None) -> AudioState:
        """Analyse un bloc. `now` permet de piloter l'horloge (tests hors temps reel)."""
        now = time.monotonic() if now is None else now
        block = np.asarray(mono, dtype=np.float32).ravel()[: self.n]
        if block.shape[0] < self.n:
            block = np.pad(block, (0, self.n - block.shape[0]))
        # Fenetre glissante : on garde les `fft_size` derniers echantillons.
        self._buf = np.concatenate((self._buf[block.shape[0]:], block))
        x = self._buf
        mag = np.abs(np.fft.rfft(x * self.window)).astype(np.float32) / self.fft_size

        peak = float(np.max(np.abs(block)))
        silent = peak < SILENCE_PEAK

        level = self._f_level.update(float(np.sqrt(np.mean(block * block))))
        self._level_prev = level = max(level, self._level_prev * BAND_RELEASE)
        # Attaque immediate, descente amortie : une bande qui retombe a zero entre
        # deux kicks ferait clignoter les effets a 86 Hz.
        raw = np.array([
            self._f_bass.update(float(mag[self._slice_bass].mean())),
            self._f_mid.update(float(mag[self._slice_mid].mean())),
            self._f_treble.update(float(mag[self._slice_treble].mean())),
        ], dtype=np.float32)
        self._band_prev = np.maximum(raw, self._band_prev * BAND_RELEASE)
        bass, mid, treble = (float(v) for v in self._band_prev)

        spectrum = np.fromiter(
            (f.update(float(mag[s].mean())) for f, s in zip(self._spec_followers, self._spec_slices)),
            dtype=np.float32, count=len(self._spec_slices),
        )

        # Flux spectral : somme des augmentations d'energie = une attaque.
        rise = np.maximum(mag - self._prev_mag, 0.0)
        flux = float(rise.sum())                           # large bande : diagnostic
        beat_flux = float(rise[self._slice_beat].sum())     # bas du spectre : beat *et* tempo
        self._prev_mag = mag
        onset = self._f_flux.update(beat_flux)

        # Detection AVANT d'ajouter a l'historique : le seuil doit se comparer
        # au passe, pas s'inclure lui-meme.
        beat = self._detect_beat(now, beat_flux, silent)
        # L'enveloppe du tempo se calcule aussi sur le bas du spectre : en large
        # bande, les charlestons a la demi-mesure rendent l'enveloppe periodique a
        # T/2, et l'autocorrelation peut se caler sur 1,5 x T (155 BPM lu 103).
        self._flux_hist.append(beat_flux)
        self._beat_flux_hist.append(beat_flux)
        self._prev_beat_flux = beat_flux
        if now >= self._next_bpm_at and not silent:
            self._next_bpm_at = now + BPM_EVERY
            self._estimate_bpm()

        self._state = AudioState(
            t=now, level=level, bass=bass, mid=mid, treble=treble, spectrum=spectrum,
            onset=onset, beat_count=self._beat_count, last_beat=self._last_beat,
            period=self._period, bpm=self._bpm, bpm_confidence=self._bpm_conf, silent=silent,
        )
        return self._state

    # --- beat ------------------------------------------------------------

    def _onset_detected(self, flux: float, silent: bool) -> bool:
        """Attaque : franchissement d'un seuil cale sur la *dynamique* recente.

        Un seuil du type « mediane x 1,8 » ne marche que si le signal a un plancher
        de bruit. Dans le bas du spectre, le flux est nul entre deux kicks : la
        mediane vaut zero et tout declenche. On se cale donc entre la mediane et le
        maximum de la derniere seconde, et on n'accepte que les fronts montants.
        """
        if silent or len(self._beat_flux_hist) <= 20:
            return False
        recent = np.fromiter(self._beat_flux_hist, dtype=np.float32)[-int(1.0 / self.block_dt):]
        med, mx = float(np.median(recent)), float(recent.max())
        if mx <= 1e-9:
            return False
        threshold = med + 0.35 * (mx - med)
        return flux > threshold and flux > 0.2 * mx and flux >= self._prev_beat_flux

    def _detect_beat(self, now: float, flux: float, silent: bool) -> bool:
        """Beat = attaque *sur la grille du tempo*, ou pulsation prevue si elle manque.

        Sans cette mise a la grille, le detecteur suit les charlestons de contretemps
        et sort le double du tempo reel (verifie : 256 BPM annonces sur un 128).
        """
        onset = self._onset_detected(flux, silent)
        period = self._period

        # Periode refractaire : jamais deux beats trop rapproches, quoi qu'il arrive.
        # Sans elle, un changement d'estimation de tempo peut declencher une rafale.
        refractory = MIN_BEAT_GAP if period <= 0.0 else max(MIN_BEAT_GAP, 0.5 * period)
        if now - self._last_emit < refractory:
            return False

        if period <= 0.0:                      # tempo inconnu : toute attaque fait foi
            if onset:
                self._last_beat = self._last_emit = now
                self._beat_count += 1
                return True
            return False

        # Grille perdue (demarrage, silence, changement de morceau) : on repart d'ici.
        if self._last_beat <= 0.0 or now - self._last_beat > 4.0 * period:
            self._last_beat = now - period

        next_beat = self._last_beat + period
        tol = BEAT_WINDOW * period

        if onset and abs(now - next_beat) <= tol:
            # Resynchronisation douce : on suit la derive sans sauter d'un coup.
            self._last_beat = next_beat + 0.5 * (now - next_beat)
            self._last_emit = now
            self._beat_count += 1
            return True
        if now > next_beat + tol:
            # Attaque masquee par la musique : la pulsation continue quand meme.
            # On saute directement au dernier point de grille : avancer d'une seule
            # periode par bloc produirait une rafale de beats pour rattraper.
            missed = max(1, int((now - self._last_beat) / period))
            self._last_beat += missed * period
            self._last_emit = now
            self._beat_count += 1
            return True
        return False

    def _estimate_bpm(self) -> None:
        """BPM par autocorrelation de l'enveloppe d'attaques."""
        if self._tapped:
            return  # un tap tempo manuel fait autorite
        if len(self._flux_hist) < int(2.0 / self.block_dt):
            return
        env = np.fromiter(self._flux_hist, dtype=np.float32)
        env = env - env.mean()
        if not np.any(env):
            return
        ac = np.correlate(env, env, mode="full")[len(env) - 1:]
        if ac[0] <= 0:
            return
        ac = ac / ac[0]

        lag_min = max(1, int(60.0 / MAX_BPM / self.block_dt))
        lag_max = min(len(ac) - 2, int(60.0 / MIN_BPM / self.block_dt))
        if lag_max <= lag_min:
            return
        seg = ac[lag_min : lag_max + 1]
        k = int(np.argmax(seg)) + lag_min
        conf = float(ac[k])

        # Interpolation parabolique : le pic tombe rarement pile sur un echantillon.
        y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]
        denom = y0 - 2.0 * y1 + y2
        lag = k + (0.5 * (y0 - y2) / denom if abs(denom) > 1e-12 else 0.0)

        bpm = 60.0 / (lag * self.block_dt) * self._octave
        self._bpm_conf = conf
        if conf < 0.12:
            return
        # Lissage : on suit le tempo sans sauter a chaque estimation.
        self._bpm = bpm if self._bpm <= 0 else 0.7 * self._bpm + 0.3 * bpm
        self._period = 60.0 / self._bpm

    # --- tap tempo --------------------------------------------------------

    def tap(self, now: float | None = None) -> float:
        """Un appui de plus sur le tap tempo. Retourne le BPM courant."""
        now = time.monotonic() if now is None else now
        if self._taps and now - self._taps[-1] > 2.0:
            self._taps.clear()
        self._taps.append(now)
        del self._taps[:-5]
        if len(self._taps) >= 2:
            intervals = np.diff(self._taps)
            period = float(intervals.mean())
            if 60.0 / MAX_BPM <= period <= 60.0 / MIN_BPM * 1.5:
                self._period = period
                self._bpm = 60.0 / period
                self._bpm_conf = 1.0
                self._tapped = True
        self._last_beat = now
        self._beat_count += 1
        return self._bpm

    @property
    def octave(self) -> float:
        return self._octave

    def scale_tempo(self, factor: float) -> None:
        """Divise ou multiplie le tempo detecte (correction d'octave)."""
        self._octave = min(4.0, max(0.25, self._octave * factor))
        if self._bpm > 0:
            self._bpm *= factor
            self._period = 60.0 / self._bpm
        self._tapped = False      # on repasse en suivi automatique, corrige

    def release_tap(self) -> None:
        """Rend la main a la detection automatique."""
        self._tapped = False
        self._taps.clear()

    def reset_gain(self) -> None:
        for f in (self._f_level, self._f_bass, self._f_mid, self._f_treble, self._f_flux):
            f.reset()
        for f in self._spec_followers:
            f.reset()
