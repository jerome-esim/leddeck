# Plan — Club LED control app (WLED / DDP)

> English translation of `PLAN.md`. **French is the reference**: decisions are
> recorded there first, and this file follows.

## 1. Goal

A **cross-platform desktop app, macOS first** (it also runs on Windows) to drive WLED LED strips live in a club:
- 2 decks (A / B): effect + colour palette + settings, crossfader between them
- Manual transition (slider) or automatic on the beats
- Music sync through an audio input (microphone or line)
- Full control from a MIDI controller (faders + buttons)
- Setup mode: identify and reorder the strips without any wiring constraint

## 2. Key concepts

### Matrix
- Effects draw onto an **L × N matrix**: `L` = LEDs per strip (columns), `N` = number of strips (rows).
- 250 × 16 by default, **configurable** in the settings.

### Outputs (the hardware)
- One **output** = one WLED ESP: IP, name, LED count, DDP port (4048), enabled/disabled.
- Configurable list (manual entry or automatic discovery on the network).
- Every output has a fixed **identification number** (#1, #2…), independent of its place in the matrix.

### Patch (output → matrix row)
- Each matrix row receives one output: `row 3 ← output #11 (reversed)`.
- Per-row options: **reverse the direction**, offset if needed.
- If the strip has more or fewer LEDs than `L`: truncate, or pad with black.
- An unpatched output stays black; a row with no output is simply ignored.

→ Install the strips in any order, then fix the order **in the app**, not in the wiring.

## 3. Setup mode

1. **Discovery**: network scan (parallel `http://<ip>/json/info` requests across the subnet + mDNS `_wled._tcp`).
   A list of the WLED devices found: name, IP, MAC, LED count, version, WiFi signal. Manual entry is possible.
2. **Identification on the strips**: every strip physically displays its own number:
   - the first LEDs **green** = start of the strip, the last LEDs **red** = end → the direction is visible
   - between them, **N white blocks** separated by black = the output number (e.g. 7 blocks = #7)
   - a "blink" option: click an output in the app → the matching strip flashes
3. **Visual patch**: the matrix is shown as N rows; drag each output onto its row,
   a ⇄ button reverses the direction, a "test" button runs a dot along the row.
4. **Check**: control patterns on the final matrix
   - the **row** number (instead of the output number)
   - a rainbow gradient from row 1 to row N
   - a dot sweeping left → right on every row (everything must travel the same way)
5. **Room profiles**: outputs + patch + matrix size saved to a JSON file; several profiles are possible.

## 4. Architecture

```
 Audio input ───► Analysis (FFT, bass/mid/treble, beat, BPM, auto gain)
                                  │
 Qt interface ──┐                 ▼
 MIDI (learn) ──┼──► PARAMETER BUS ◄── Auto-mix (beats)
                                  │
                                  ▼
        ENGINE (dedicated thread, fixed 40 fps rate)
        Deck A (effect + palette + params) ─┐
                                            ├─► Mixer ─► Master (brightness, strobe, blackout)
        Deck B (effect + palette + params) ─┘                │
                                                             ▼  L × N matrix
                                  Patch (reorder, reverse, gamma)
                                                             ▼
                                  DDP send ──► N WLED outputs
```

- **Parameter bus**: every setting has an identifier and a range; UI, MIDI and auto-mix all write to the same place.
- **Engine independent of the UI**: if the interface stutters, the LEDs do not.
- **Palettes separate from effects**: an effect takes its colours from the deck palette → any effect recolours instantly.

### An effect's interface

```python
class Effect:
    name = "Serpent"
    params = {"vitesse": (0.1, 5.0, 1.0), "longueur": (1, 100, 20)}  # min, max, default

    def render(self, t, dt, audio, palette, p) -> np.ndarray:
        """Returns an (N, L, 3) array of floats 0..1."""
```

## 5. Technical stack

| Piece | Choice |
|---|---|
| Language | Python 3.12 |
| Computation | numpy |
| Interface | PySide6 (Qt) |
| Audio | sounddevice (+ numpy FFT) |
| MIDI | mido + python-rtmidi |
| Network | UDP / DDP (standard socket), requests for the WLED JSON API |
| Config | JSON files |
| Distribution | PyInstaller → `.app` (macOS) / `.exe` (Windows) |
| Environment | `uv` + `pyproject.toml` (Python 3.12 pinned, no `requirements.txt`) |

## 6. Tree

```
LED/
  PLAN.md
  pyproject.toml            ✅ (uv; no requirements.txt)
  leddeck/
    main.py                 ✅ CLI (profile / discover / test / identify / blink / off)
    core/      config.py ✅  engine.py ✅  params.py ✅  palette.py ✅  mixer.py ✅
    output/    ddp.py ✅  wled.py ✅ (discovery, state)  patch.py ✅
    audio/     input.py ✅  analysis.py ✅
    midi/      midi.py ✅  actions.py ✅  mapping.py ✅  controller.py ✅  sheet.py ✅
    i18n.py                 ✅ French / English (outside ui/ so main.py uses it without Qt)
    effects/   base.py ✅  arcenciel.py ✅  blob.py ✅  eclairs.py ✅  electrique.py ✅
               etoiles.py ✅  fixe.py ✅  forme.py ✅  ligne.py ✅  neon.py ✅  noir.py ✅
               pluie.py ✅  pulse.py ✅  serpent.py ✅  tubes.py ✅  vague.py ✅
               vortex.py ✅                          (loaded automatically — 16 effects)
    install/   patterns.py ✅ (identification / test patterns)
    ui/        main_window.py ✅  preview.py ✅  deck_panel.py ✅  master_panel.py ✅
               style.py ✅  thumbnails.py ✅  install_page.py ✅  pads_dialog.py ✅
               (midi_page.py and settings_page.py turned out unnecessary: setup is a
                page, and the settings live in the panels)
  profiles/    default.json ✅  club.json ✅  club16.json ✅  demo16.json ✅  test16.json ✅
  midi/        apcmini-mk2.json ✅  mapping-apcmini-mk2[.en].html ✅ (printable sheets)
  docs/        live.png ✅  setup.png ✅ (README screenshots, generated offscreen)
  presets/     (saved effects + palettes)
```

✅ = written and tested.

## 7. Planned effects (first series)

| Effect | Description | Audio reaction |
|---|---|---|
| Snake | one or more snakes running across the matrix | speed / size on the bass |
| Starfield | random twinkling | star shower on the beat |
| Wave / plasma | colour waves | amplitude on the bass |
| Rainbow | palette scrolling | — |
| Pulse | global flash | on every beat |
| Spectrum | 16 rows = 16 frequency bands | live spectrum |
| Rain | drops falling along the strips | density on the treble |
| Fire | flames | intensity on the bass |
| Solid colour / Strobe | utilities | strobe locked to the beat |

## 8. Steps

| # | Step | Done when… |
|---|---|---|
| 0 | ✅ **Preparation**: Python, dependencies, WLED config check (DDP on, static IPs) | the environment runs |
| 1 | ✅ **Core + output**: JSON config, DDP send, patch, 40 fps loop, command-line test pattern | ✅ validated on 16 simulated receivers **and on 3 real ESPs** (40 fps, no stutter) |
| 2 | 🔶 **Setup mode**: discovery, on-strip identification, patch, reverse, profiles | screen complete ✅; **profile management** and validation on all 16 strips still to do |
| 3 | ✅ **Effects + palettes**: effect engine, first 5 effects, matrix preview in the app | ✅ 5 effects at 40 fps on the 3 tubes, instant recolouring from the palette |
| 4 | ✅ **Audio**: mic/line input, FFT, auto gain, beat, BPM, tap tempo | ✅ BPM locked from 75 to 174 BPM (error < 0.3 %, jitter < 6 ms), validated on the microphone |
| 5 | ✅ **Live interface**: 2 decks, effect lists, palettes, crossfader, master | ✅ two decks mixed with the mouse, 0.41 ms/frame worst case on 16 × 250 |
| 6 | 🔶 **MIDI**: MIDI learn, soft takeover, LED feedback on the controller | full mapping, soft takeover and LED feedback ✅; **MIDI learn UI still to do** |
| 7 | **Auto-mix + presets**: transition every X beats, effect rotation, presets on pads | the app runs on its own for a whole night |
| 8 | ⏳ **Club reliability**: `.app`, last-state restore, offline ESP reported, emergency blackout, logs | a 6 h test with no incident |

## 8 bis. What runs today (steps 0 and 1)

### Environment
`uv sync` installs everything (Python 3.12.13, numpy 2.5, PySide6 6.11, sounddevice, mido + python-rtmidi, requests, zeroconf).
Verified: audio and MIDI seen by the system.

### Modules written
- `core/config.py` — room profile: matrix (L × N), outputs, patch; JSON in `profiles/`.
- `output/ddp.py` — DDP/UDP sender: 10-byte header (version 1, type `0x0B` RGB24, destination 1),
  sequence number 1-15, PUSH bit on the last packet, split at 1440 bytes.
  250 RGB LEDs = 750 bytes → **a single packet per strip per frame**.
  Non-blocking socket: a missing ESP never brings the engine down (error counter).
- `output/patch.py` — (N, L, 3) float 0..1 matrix → one uint8 buffer per output:
  offset, reverse, truncate / pad with black, gamma (256-entry LUT) and master brightness.
  `send_direct()` bypasses the patch to address strips by number (setup mode).
- `core/engine.py` — 40 fps loop in a dedicated thread, drift-free rate, no burst catch-up when
  late, a render exception does not stop the LEDs; stats (real fps, late frames, render ms).
- `output/wled.py` — discovery: subnet sweep (`/json/info`, 128 threads) + mDNS `_wled._tcp`,
  name / IP / MAC / LED count / version / RSSI, warning if the version is below 0.13 (DDP).
- `install/patterns.py` — patterns: `sweep`, `rainbow`, `rows`, `chase`, `flow`, solid colours, `off`,
  plus strip identification (green start, red end, N white blocks = number) and blinking.

### Make the ESPs uniform before sending
Two ESPs receiving exactly the same bytes can render differently: WLED's **brightness** slider
(`bri`) applies on top of the realtime stream unless "Force max brightness" is ticked — and it is
not necessarily ticked everywhere
(observed: `WLED-01` bri 255 + maxbri, `WLED-10` bri 128 without maxbri → white half as bright).
Rather than depend on a per-ESP setting, the app forces `{"on": true, "bri": 255}` on every output
before sending (`wake_all`). **Brightness is handled by the app's master alone.**

### Switching off: DDP black is not enough
2.5 s after the last DDP packet, WLED **leaves realtime mode and resumes its own state**
(typically an internal effect at full brightness). `leddeck off` therefore does both:
black over DDP, then `POST /json/state {"on": false}` on every ESP.
Symmetrically, `test` / `identify` / `blink` **wake** the ESPs before sending (`on: true`),
and `leddeck on` does it on demand. This is the basis of the step 8 emergency blackout.

### Command line
```bash
uv run leddeck profile init --leds 250 --strips 16     # create a room profile
uv run leddeck discover --add --autopatch              # find the WLED devices and patch them 1→1
uv run leddeck profile show                            # outputs + patch
uv run leddeck test sweep --seconds 20                 # pattern on the matrix (sweep/rainbow/rows/chase/…)
uv run leddeck identify                                # every strip displays its number
uv run leddeck blink 7                                 # blink output #7
uv run leddeck off                                     # blackout: DDP black + WLED powered off
uv run leddeck on                                      # power the WLED devices back on
```
`--profile <name>` picks another room profile.

### Tests carried out
- DDP: header, fragmentation and PUSH bit verified on a local socket.
- Full chain against **16 fake DDP receivers**: 40.4 fps measured, 0 late frames, 0 errors,
  750 bytes per output per frame, a reversed row properly reversed, blackout on exit.
- Engine: 40.1 fps measured over 2 s, 0.07 ms render per frame (16 × 250 matrix).
- **Hardware validation (2026-09-22)** — `club` profile, 250 × 3 matrix:

  | Output | Name | IP | RSSI |
  |---|---|---|---|
  | #1 | `WLED-01` | 192.168.8.10 | −43 dBm |
  | #2 | `WLED-10` | 192.168.8.19 | −43 dBm |
  | #3 | `WLED-15` | 192.168.8.24 | −58 dBm |

  The `sweep`, `white`, `red`/`green`/`blue`, `flow`, `rainbow`, `chase` and `identify` patterns were
  sent to all 3 outputs: **a constant 40 fps, 0 network errors, no visible stutter**.
  The ESP confirms `live = true`, `source = DDP`, ~40 fps on its side.
  The macOS "Local network" permission is granted.
  Every ESP is on v0.15.3, 250 LEDs, a single local bus.

  Worth noting: the tubes do not produce exactly the same white (hue, not brightness) — a physical
  LED difference, judged acceptable. If it ever matters: per-output white balance in the patch.

## 8 quinquies. Step 5 — Live interface (finished 2026-09-22)

### Decks and mixer (`core/mixer.py`)
- Each deck has its **own effect instances**: the same effect can run on both sides with
  different settings and different state.
- **Both decks are always computed**, even with the crossfader all the way to one side. Not
  rendering the hidden deck would freeze it, and it would jump when brought back. The cost allows it.
- Three blend modes:

  | Mode | Weights (A, B) | Use |
  |---|---|---|
  | `fondu` (fade) | (1−x, x) | classic crossfade |
  | `addition` | (min(1, 2−2x), min(1, 2x)) then clipping | no dip in the middle, it clips |
  | `maximum` | same weights, then `max` | no dip, no clipping — clean colours |

- **Global speed**: the mixer keeps its own time, advanced by `dt × speed`. Effects do not know
  time is being stretched. A **geometric** travel ×0.1 → ×4 (a linear travel would make the bottom
  half useless), and the **bottom 3 % is zero: a hard stop**.
  At a stop, effect audio is cut too — otherwise an effect locked to the beat would keep moving
  after a stop was asked for. The crossfader and the master stay alive: you can fade between two
  frozen images and send a strobe over them.
  The travel conversion is **shared** between the interface and MIDI: the APC fader and the
  on-screen slider behave exactly alike.

### Master — two buttons per function
Strobe, **electric**, flash and blackout each have **a latch (on/off) and a momentary press**
(`Hold` class, active if either one is): in a club you want both gestures for the same function.
The strobe rate is adjustable, with optional beat lock.
Brightness stays in the output stage, before the gamma.

**Electric is also a live overlay**, laid over the mix without taking up a deck (it remains
available as a normal effect). Three choices:
- **maximum** compositing: the overlay adds light, it never darkens;
- its settings are the effect's own, exposed as they are under the master;
- when `whiteness` drops, it borrows **the dominant deck's palette**, so it follows the colours
  of whatever is playing instead of an arbitrary hue.
Shortcut: **E** momentary, **Shift+E** to latch.

### Automatic crossfade on the tempo (`AutoCross`)
Switches from one deck to the other every N beats (1 to 64), with a transition from 0 (hard cut)
to 16 beats. Two choices:
- **without music, an internal clock takes over** — the auto-mix must run even with no sound;
- **moving the crossfader by hand cuts the automation**: taking back control must be immediate.

(This is an advance on step 7, asked for along the way.)

### Custom palette per deck
Each deck has a `Perso (RGB)` palette with a **variable number of colours** (1 to 8, `+`/`−`
buttons), each edited through the system colour picker. The picker stays open and emits
`currentColorChanged`: **the colour moves on the strips while you pick it**. It is **stepped by
default**. Touching a colour switches the deck to that palette.

### Interface (`ui/`)
Dark theme (`style.py`), **one colour per deck** — cyan for A, pink for B — carried through
selections, sliders and the two halves of the crossfader: you always know which side you are on.

**Three previews**: each deck has its own (prepare an effect without sending it), plus the large
one at the top showing the mix actually sent to the LEDs.

**Visual selection** (`thumbnails.py`): effects are thumbnails computed by running the effect on a
mini matrix with the deck palette; palettes are their gradients.
Two details learned by looking at the result:
- the thumbnail keeps the **maximum over the last frames**, otherwise an effect made of short
  bursts (Electric, Starfield, Pulse) lands on a black frame every other time;
- grid height follows the **real column count**, which depends on the width — a height computed in
  advance left empty rows.

**The tab sits at the effect level**: `Effects` / `Settings · <effect name>` — you pick the effect,
then move to its settings, which are its own. **Palettes stay visible** underneath: changing one is
a frequent gesture and must not cost a tab round trip.
That shortens the column by about 200 px and makes the live buttons visible straight away.
Shortcuts: **space** = flash, **S** = strobe, **B** = blackout, momentary;
**Shift + the same key** engages the latch.

### Layout: three traps
- **Oscillation on resize**: recomputing a grid's height inside its `resizeEvent` restarts the
  layout, and the width → columns → height → scrollbar → width loop starts oscillating
  (spectacular in full screen). Fix: deferred recompute (`QTimer.singleShot(0, …)`) and a geometry
  change only when the value really changes.
- **Width in full screen**: with no cap, columns stretch and the 9 thumbnails line up in a single
  row. Panels are capped, and the surplus goes to the sides.
- **`QScrollArea` does not adopt its content's widths**: it lets itself be squeezed below the
  minimum and truncates the panel. It must be given the width the layout actually demands
  (`minimumSizeHint()`), not a hand-set minimum.

### Two traps hit
- **Font**: `-apple-system` is a browser-only keyword that Qt cannot resolve — the font was never
  applied and Qt wasted startup time looking for a substitute. Take the system UI font through
  `QFontDatabase`.
- **Stopping the interface**: `SIGINT` does nothing to a Qt application (Python only handles its
  signals between two instructions, and the event loop stays inside C code) — `SIGTERM` is needed.
  And a `pkill -f` pattern must be chosen so that it does not match the shell running it.

### Text
The interface is in **accented** French. Search by name (effects, palettes, settings) is
accent-insensitive: the command line stays typable in ASCII (`--set reactivite=0.8`).

### Measurements
All 25 A × B effect combinations on a **16 × 250** matrix: worst case **0.41 ms per frame**,
61× headroom on the 25 ms budget at 40 fps.

## 8 quater. Step 3 — Effects, palettes and preview (finished 2026-09-22)

### Palettes (`core/palette.py`)
An effect **never** picks a colour: it asks for "the colour at position x" (0..1).
Changing palette therefore recolours any effect without modifying it — that is the step's
completion criterion, verified on the tubes (`Serpent` in `Feu`, then in `Ocean`).
Two families: **cyclic** (the last colour joins the first — essential for anything that scrolls)
and **directional** (dark → light, for fire or intensity-driven effects).

**Interpolation or steps** (`smooth`): at `False`, intermediate hues are skipped and each colour
takes a clean slice. That is the expected behaviour of a custom palette — two chosen colours must
come out as they are. Adjustable per deck, on the selected palette (each deck holds its **own
copies** of the palettes: ticking the box on one side must not change the other). `Pulse` goes
further: on a stepped palette it **jumps from colour to colour**, `variation` then counting in
number of colours — hence the exact alternation between two colours.
12 palettes are supplied; `presets/palettes/*.json` adds more without touching the code.

### Parameters (`core/params.py`)
Every setting has an identifier, bounds and a default, with conversion to and from 0..1 — which is
what a MIDI fader will provide. This is the seed of the step 6 parameter bus.

### Effects (`effects/`)
`Effect.render(t, dt, audio, palette, p) -> (N, L, 3)`, with automatic loading of the folder.
Two rules learned along the way:
- an effect must stay **fully visible without sound** (`audio` at None) — hence the `reactive()`
  helper, which ignores reactivity when the microphone is off instead of darkening the effect;
- each effect keeps its buffer and writes into it (`out=`): no allocation per frame.

| Effect | Settings | Audio reaction |
|---|---|---|
| Snake | speed, length, count, reactivity | speeds up on the bass |
| Starfield | density, duration, rain, hue | star shower on the beat |
| Wave | speed, scale, reactivity, offset | amplitude on the bass |
| Rainbow | speed, spread, offset, reactivity | brightness on the level |
| Pulse | decay, residual, colour, variation | flash on every beat |
| Solid | colour, spread, offset, reactivity | brightness on the level |
| Tubes | count, speed, random, fade, on the beat | changes tube on every beat |
| Electric | density, length, duration, whiteness, on the beat | burst of sparks on the beat |
| Neon | count, speed, strike, duration, fade out, electrodes, spread | — |

`Tubes` lights whole strips; `random` is a **continuum** (0 = in order, 1 = by lot, in between the
two gestures mix) rather than a mode choice.
`Electric` is not a strobe: sparks only take a short piece of tube, which gives the crackle rather
than a full flash.
`Neon` follows the model of the **"warming neon" ISF shader** used in MadMapper (supplied by the
user): `count` independent slots, each drawing a tube at random on every cycle, and one cycle =
strike → lit → linear fade.
The essential trait, missing from my first version: during the strike the amplitude **rises**
(`progress × flicker` at 30 Hz), so the tube first shivers faintly and then more and more strongly
— that is the sensation of warming up. The shader's random function
(`fract(sin(x) * 43758.5453)`) is taken as is.

Two deliberate departures:
- **the colour comes from the deck palette**, where the shader only had a `neonColor`;
- **`spread`** fixes a shader flaw: it offset the slots by half a cycle each
  (`fi * totalDuration * 0.5`), which modulo one cycle gives only **two distinct phases** — slots 1
  and 3 are in sync, hence moments when every tube goes dark together.
  At 1 (default) the slots are spread evenly; at 0 the shader is reproduced exactly.
- The orange glow of the electrodes during warm-up is an addition, adjustable (`electrodes`).

Measured cost on a **16 × 250** matrix: 0.03 to 0.20 ms per frame (25 ms budget at 40 fps).

### Interface (`ui/`)
`preview.py` shows the matrix as one numbered bar per strip; `main_window.py` adds the effect list,
the palette list, the current effect's settings (rebuilt on every change), brightness, an "Audio"
checkbox, Blackout and a status bar (fps, outputs, errors, BPM).
The engine runs at 40 fps in its thread, the UI reads the last frame at 30 fps: **if the interface
stutters, the LEDs do not**. The output stage keeps a *copy* of the frame (`keep_frame`) — effects
reuse their buffer, and a plain reference would be modified under the UI's eyes.

### Commands
```bash
uv run leddeck fx list                                       # effects, settings, palettes
uv run leddeck --profile club fx run Serpent --palette Feu   # headless
uv run leddeck --profile club fx run Vague --set vitesse=2.5 --set echelle=4
uv run leddeck --profile club ui                             # interface
```

### Measurements
The 5 effects played on the 3 tubes: **40 fps, 0 late frames, 0 network errors** every time.

## 8 ter. Step 4 — Audio (finished 2026-09-22)

### Modules
- `audio/input.py` — mono `sounddevice` capture, per-block callback, device listing and resolution
  (index or name fragment), diagnostic counters, detection of prolonged silence (→ a message about
  the macOS microphone permission).
- `audio/analysis.py` — `Analyzer`: FFT, bands, auto gain, beat detection, BPM, tap tempo.
  It produces an immutable `AudioState`, replaced wholesale on every analysis: the engine reads it
  **without a lock**.

### Four choices dictated by the measurements

1. **Analysis window (2048) ≠ hop size (512).**
   With a 512-point FFT the resolution is 86 Hz: the whole bass band (30-150 Hz) fits in **a single
   bin**, useless for a kick. The 2048-point sliding window gives 21.5 Hz (5 bass bins) while
   keeping an 11.6 ms hop to lock the beat.

2. **Onset detection and tempo on the low end of the spectrum (< 250 Hz).**
   Broadband, off-beat hats make the envelope periodic at T/2: the detector reported **double the
   tempo** (256 BPM on a 128), and the autocorrelation sometimes locked onto 1.5 × T (155 BPM read
   as 103). Keeping only the low end makes both disappear.

3. **Beats snapped to the tempo grid.**
   Once the BPM is known, an onset is only accepted if it falls within ±25 % of the expected beat
   (soft resynchronisation, half the gap); otherwise the expected beat is emitted anyway. A kick
   buried by the music therefore does not make the light drop out.

4. **Refractory period between two beats.**
   Observed in real listening: double flashes. Measured cause — when the tempo estimate changes,
   the grid can find itself several beats behind, and catching up emitted **one beat per audio
   block** (every 11.6 ms), i.e. a burst. Two fixes: jump straight to the latest grid point instead
   of advancing one period at a time, and an absolute ban on emitting two beats less than half a
   period apart (minimum 220 ms).
   After the fix, across 128 → 170 → 95 BPM changes: minimum interval **267 ms**.

5. **Auto gain between noise floor and peak, except for the global level.**
   The scale of the FFT magnitudes depends on the number of bins in the band (5 for the bass, 465
   for the treble): no absolute threshold works. So we follow a peak that decays (~7 %/s → the
   club's volume) and a floor that rises (~1.7 %/s → the room noise is subtracted).
   The **global level** does not subtract the floor, otherwise it falls back to zero between kicks.
   The bands have a damped release (~160 ms) to avoid flickering at 86 Hz.

### Clipping detection
The input counts clipped blocks (peak ≥ 0.99) and displays it live (`CLIPPING`), because a clipped
signal fills the spectrum with distortion and creates false onsets. Useful for telling "the sound
is too loud" apart from an algorithm flaw — a hypothesis tested and then **ruled out** here:
0 clipped blocks out of 3799, input peak 0.05.

### Measurements
- Offline, kick + hat + pad, from 75 to 174 BPM: **BPM accurate to better than 0.3 %**, beat jitter
  **2 to 6 ms**, alignment on the kick **+5 ms** (half a window, incompressible).
- Tempo change 128 → 140: re-locked in ~10 s. Silence: bands at zero, immediate recovery.
- Tap tempo: takes priority over the automatic estimate until `release_tap()`.
- **On the microphone** (speakers → room → MacBook mic): BPM 128.1 for a 128 track, confidence
  0.77, 0 audio overruns.
- **Audio + LEDs together** on the 3 tubes: 39.9 fps, 0 network errors, 0 audio overruns.

### Commands
```bash
uv run leddeck audio devices                  # list the inputs
uv run leddeck audio monitor                  # bands / level / BPM / beats in the terminal
uv run leddeck --profile club audio leds      # spectrum on the strips + flash on the beat
```
`--device` accepts an index or a name fragment; the profile remembers `audio_device`.

### Real listening (club music, MacBook microphone)
*A test in real club conditions is not possible for now — to be done on site.*
- The beats land right; no more double flashes after the refractory period.
- **Very low input level: peak 0.05** (≈ −26 dBFS), 0 clipping. That is probably the reason for the
  low tempo confidence (0.25 against 0.77 on a close source).
  → Lead: a line input, or a better-placed microphone.
- **During a break, the beat keeps running** (that is intentional: a masked kick must not make the
  light drop out). Judged acceptable, to be handled manually (blackout / crossfader).
  If needed later: cut the predicted beats when the bass energy collapses.

### Still to do
- Check in real club conditions (high level, reverberation, heavy bass) and decide whether a line
  input is preferable to the microphone. **Impossible to test outside the club**: to be done at the
  first on-site installation.
- Tap tempo has no trigger yet: it arrives with MIDI (step 6).

## 8 sexies. Step 6 — MIDI (2026-09-22)

### Numbers measured on the hardware
Rather than trusting the documentation, the numbers were **measured on the APC mini MK2** with
`leddeck midi monitor` (port `APC mini mk2 Control`, channel 1):

| Control | Numbers |
|---|---|
| 8×8 grid | notes **0 to 63**, `note = row_from_the_bottom × 8 + column` (bottom-left = 0) |
| 9 faders | **CC 48 to 56**, left to right |
| Track buttons (bottom) | notes **100 to 107** |
| Scene buttons (right) | notes **112 to 119** |
| Shift | note **122** |

### Default mapping
Grid: left half = deck A, right half = deck B; **rows 1 to 3 = effects, 4 to 6 = supplied
palettes, 7 and 8 = eight solid colours** (they stand in for the custom palette). There are
16 effects for 12 pads: the profile remembers which ones sit on the grid (see §11 bis). Faders: A settings 1-3, brightness, B settings 1-3, global speed, crossfader.
Scene: tap, auto crossfade, auto 8/16/32 (three free buttons).

**Bottom row: the 4 live functions × their 2 gestures**, in the same order every time — hold on the
left, latch on the right: electric, strobe, flash, blackout. The same gesture is therefore always
in the same relative place.
The labels state the gesture in plain words ("while held" / "on/off latch"), not jargon.

**Everything lives in `midi/apcmini-mk2.json`** — nothing is hard-wired; this is the basis for MIDI
learn.

### Printable sheet
`leddeck midi sheet` generates a landscape A4 page **from the mapping**: the controller's physical
layout, the note or CC number on every cell, the deck colours, and free slots marked as such. It
stays correct when the mapping changes, instead of being copied by hand.

### Soft takeover
A fader only takes over once it is back on the current value (3 % tolerance, or on crossing), and
it **re-arms as soon as the value changes elsewhere** (mouse, auto-mix). Without that, brushing a
fader would make the setting jump to the fader's physical position.

### Visual feedback
Pads take the deck colour (cyan / pink) on the current selection; simple buttons light according to
state. Only changes are sent: MIDI is slow, and re-sending 83 pads at 30 Hz would saturate it.
**Colours verified on the hardware on 2026-09-22: correct.**

### Two bugs fixed, both real
- **Echo loop**: on a loopback bus (IAC, used to test without the controller), the visual feedback
  comes back as input and retriggers the actions endlessly. `MidiLink` remembers its own sends and
  ignores them for 250 ms.
- **Freeze on close**: closing a port while a callback is arriving **freezes rtmidi**. The callback
  must be detached, the queue allowed to drain, then the port closed. This would have blocked the
  application's shutdown, not just the tests.

### Still to do
- **MIDI learn UI**: `MidiController.learn_next()` exists; what is missing is the page that lets
  you click a setting and then touch a control.
- **Where to put the presets** (step 7): the bottom row is taken by the live functions, and the
  three freed scene buttons are not enough for eight presets. Lead: free pads in the grid (seven
  per deck in the effect zone, three in the palette zone).

## 8 octies. Step 2 — Setup screen (2026-09-23)

*(Historical note: this screen used to open in a separate window. Since 2026-09-25 it is a page of
the single application — see §11 bis.)*

**WLED outputs**: live signal (bars + dBm + quality), online / offline state, version, LED count.
Polled every 4 s **in a separate thread**: the interface must never wait on the network. One button
opens `http://<ip>` in the browser, another blinks the strip to find it. The scan (a chosen subnet
+ mDNS) adds the new WLED devices it finds.

**Patch**: one row per matrix row — output chosen from a list, reverse, offset, and a button that
runs a dot along that row alone. Plus the matrix size and the automatic patch. *A deliberate
departure from the plan*: a dropdown rather than drag and drop — faster in use and foolproof on a
laptop in the booth.

**Check**: identification (every strip displays its number), row number, rainbow, sweep, chase,
off — with a preview of what is being sent.
`leddeck diag <output>` completes it outside the interface: a graduated ruler (a mark every 10
LEDs, a bigger one every 50), marked ends, and solid colour fills — to tell "strip longer than
declared" apart from a voltage drop and a data problem.

**The off mode addresses every output, patched or not.** An output that has been discovered but not
yet patched would receive nothing: WLED would leave realtime after 2.5 s and fall back to its
internal effect. That is the common case right after a scan.

An interface detail: the theme's buttons have generous padding, suited to the big live buttons,
which **truncates everything inside a table cell**. Cell buttons therefore have their own compact
style, and rows a fixed height.

### Saving: a scan saves itself
A scan used to add outputs **in memory only**. Closing the window without clicking "Save" lost the
addition — and the app sent nothing to an ESP that had been correctly detected, which looks exactly
like a hardware fault (an hour lost on this on 2026-09-23).
From now on: **a scan that adds outputs saves the profile immediately** (a scan is an observation,
not a choice), patch changes display "unsaved changes", and closing asks for confirmation.
A discovered output is also **woken immediately** (`on` + max brightness): without that it stays
off on the WLED side and shows nothing. A "Prepare the ESPs" button applies the venue configuration
from the screen.

### Still to do
- **Room profile management** from this screen: create, load, rename (today there is only "Save").
- Validate the full scenario on all 16 strips: "laid out at random, put back in order in 2 min".

## 8 septies. Endurance — first readings

- **2026-09-22: 29 minutes continuous** (3 tubes, audio + MIDI + interface), clean shutdown, no
  network errors, controller still responding. Nothing drifted.
- **2026-09-23: 4 h 20 continuous** (14 tubes), stopped by the system for lack of memory — not by
  a crash. At that same moment: rekordbox 1.7 GB, five Chrome processes ≈ 3.2 GB, 60 MB of free
  memory. The application itself starts at **116 MB**.
  Nothing accuses leddeck, and nothing clears it either: this is the second stop of its kind.
  The status bar now shows **memory used and its drift since startup** — a flat drift will clear
  the machine, a steady drift will point at a leak.
- An earlier session was **killed by the system for lack of memory** — not an app crash. Forced to
  stop, it cannot do its blackout: the ESPs resume their internal effect after 2.5 s. Step 8 must
  therefore provide a **black boot preset** on the WLED side, so that an abrupt cut does not light
  the tubes in the middle of a night.

What those 29 minutes do not prove: the 6 h target, the 16 ESPs, a club's loaded WiFi, or the real
sound level.

## 8 nonies. Step 8 — Club reliability, in detail

The criterion remains "**6 h with no incident**". Six work items, from the most structural to the
simplest.

### 8.1 Guaranteed blackout, even when the app dies — 🔶 done, to be validated
This is risk no. 1: 2.5 s after the last DDP packet, **WLED resumes its own state** and relights
the tubes on its internal effect. Seen for real when the system killed the app for lack of memory.
`leddeck off` covers a deliberate shutdown, not an abrupt one.

**A boot preset is not enough**: on leaving realtime, WLED returns to the state it had *before*,
not to its boot preset — and we were the ones setting it to "on" in order to send. The chosen
counter-measure: **leave WLED permanently off** and enable "Force max brightness", which displays
the realtime stream whatever the on/off state. Stream running → the tubes show our data; stream
cut → WLED is off, therefore dark.

`leddeck prepare` applies all of that remotely through the JSON API (`maxbri`, `no-gc`, `en`,
`def.on = false`, then an off resting state); `--check` displays without modifying.
Applied to the 4 ESPs on 2026-09-23.

**Trap**: WLED applies and saves its configuration **with a delay**. Reading back right after
writing still returns the old values — the command reported a failure although everything had
worked. You have to wait ~1.5 s before checking.

**Still to validate on the hardware**: that the tubes do light while WLED is off. The whole
approach depends on it. If not, a possible fallback: periodically re-send "off" while streaming.
Until this is verified, the app keeps sending `on + bri 255` at launch.

### 8.2 Distribution: macOS `.app`
PyInstaller, with the two permissions macOS requires in the `Info.plist`:
`NSMicrophoneUsageDescription` and `NSLocalNetworkUsageDescription` — without them the app is
denied the microphone and UDP sending **with no error message**.
The application is unsigned: plan for ad-hoc signing and the Gatekeeper step at first launch.
A useful intermediate step right now: a `leddeck.command` that can be launched by double-click.

### 8.3 Last-state restore
Save on close — and periodically, to survive an abrupt stop — the effects, palettes, settings,
crossfader position, brightness and blend mode of both decks; restore them at launch. To be kept in
a state file separate from the room profile: the profile describes the place, the state describes
the night.

### 8.4 Offline ESP reported
The mechanism already exists in the setup screen (polled every 4 s in a thread). What remains is
to carry it into the live interface: a discreet "15/16 online" counter, the row concerned marked in
the preview, and **automatic recovery** — when an ESP comes back it must be sent `on + bri 255`
again, otherwise it stays dark while the packets arrive.

### 8.5 Log
A rotating file (in `~/Library/Logs/leddeck/`), so that the next day you can answer "what happened
at 1:20". To record: startup and loaded profile, discovery, network errors per output, late frames,
audio overruns, MIDI connection and loss, render exceptions. Volume to watch: at 40 fps, nothing
must be written per frame.

### 8.6 Endurance test
*The memory reading already exists in the status bar; what remains is to read it headless.*
A headless `leddeck soak` command that plays an effect rotation and periodically writes: real fps,
late frames, network errors per output, audio overruns, memory used, RSSI of every ESP. It is the
only way to tell a real leak from an impression. First reading available: 29 min with no drift
(§8 septies).

### Field measurements (2026-09-23)
- **The ESP8266s hold 40 fps** with 250 LEDs: measured at 40 rendered fps while sending at 40.
  *Correcting an analysis error*: a first reading showed 20 fps, but it had been taken **while no
  stream was running** — WLED was displaying its own effect, and that figure measured nothing.
  Do not draw conclusions from a frame rate read outside of streaming.
- **RSSI does not tell you whether the link carries the packets.** `WLED-01` showed −42 dBm
  ("excellent") while losing **66 % of the packets** on ping, hence a stuttering render and an
  unreachable web server. The setup screen therefore now shows the **real reachability ratio**
  (`3/10`) next to the signal, along with the response time.
- An ESP that receives properly (`live=true`, `lm='DDP'`, fps > 0) but lights nothing: check
  **first that it is in the profile**. An ESP absent from the profile simply receives nothing.

### Risks already identified in session
- **Memory**: the app was killed once by the system. To be measured over time.
- **Loaded WiFi**: 16 ESPs on a single access point, never tested. Tube no. 3 was already at
  −58 dBm with three clients.
- **Real sound level**: the microphone was picking up at −26 dBFS here, hence the low tempo
  confidence. To be replayed on site before deciding between microphone and line input.

## 9. macOS specifics

- **Microphone**: macOS asks for microphone permission (Terminal / the app) at first launch.
  ✅ granted for Terminal (verified 2026-09-22).
- **Local network**: since macOS 15, "Local network" must be allowed for Terminal / the app
  (Settings → Privacy & Security → Local Network), otherwise UDP sending to the ESPs fails.
- MIDI: CoreMIDI, supported natively by python-rtmidi.

## 9 bis. Network (validated 2026-09-22)

The dedicated router has no Internet: connecting to it over WiFi cuts everything else.
**Chosen solution: two interfaces in parallel.**

| Interface | Network | Role |
|---|---|---|
| WiFi `en0` | 192.168.0.210/24, gateway 192.168.0.1 | Internet (default route) |
| USB Ethernet `en5` | 192.168.8.101/24 | Dedicated router → the ESPs (no gateway) |

- The two subnets must be **different** (here 192.168.0.x and 192.168.8.x): otherwise routing conflicts.
- WiFi must be **at the top of the service order** (Settings → Network → ⋯ → Set Service Order),
  otherwise macOS moves the default route to Ethernet and Internet is lost.
  Belt and braces: configure Ethernet with manual IPv4 and an **empty Router field**.
- Check: `route -n get default` must stay on `en0` / 192.168.0.1.
- `leddeck discover --cidr 192.168.8.0/24`: without `--cidr`, the sweep also covers the home network for nothing.

### Expected WLED configuration (one per ESP)

- **A single LED bus**: 250 LEDs, local output (GPIO), WS281x type — **no network bus**.
  (The configuration found initially was a 1000-LED "virtual LED": one master ESP relayed over DDP
  to three others. Dropped: latency, doubled WiFi traffic on the master, single point of failure.)
- **A static IP** per ESP, with an explicit name (`WLED-01` … `WLED-16`).
- DDP receiving: always listening on **port 4048**, nothing to enable.
- `no-gc: true` (no WLED gamma on the realtime stream) → gamma is applied by the app.
- `maxbri: true` (brightness forced to max in realtime) → brightness is handled by the app.
- Current limiter (ABL) disabled or set wide, otherwise WLED dims on its own.

## 10. MIDI controller: Akai APC Mini MK2

Hardware: an 8×8 grid of RGB pads, 9 faders, 8 "track" buttons (bottom), 8 "scene" buttons (right), Shift.
The RGB pads allow colour feedback (palette colour, active effect…).

Default proposed mapping (everything stays changeable through MIDI learn):

| Control | Role |
|---|---|
| Pads columns 1-4, rows 1-3 | Deck A: 12 chosen effects (see §11 bis) |
| Pads columns 1-4, rows 4-6 | Deck A: 12 palettes (pads lit in the palette's colour) |
| Pads columns 1-4, rows 7-8 | Deck A: 8 solid colours |
| Pads columns 5-8 | Deck B, same layout |
| Faders 1-3 | Deck A: speed, size, audio reactivity |
| Faders 5-7 | Deck B: speed, size, audio reactivity |
| Fader 4 | Master brightness |
| Fader 8 | Global speed |
| Fader 9 | **Crossfader A ↔ B** |
| Scene buttons (right) | tap tempo, auto-mix on/off, auto length (8/16/32 beats), strobe (held), flash (held), blackout… |
| Track buttons (bottom) | presets 1-8 |

## 11. Decisions / answers

- Platform: **macOS** (development and use), code kept cross-platform.
- Controller: Akai APC Mini MK2.
- Sound: **microphone** for now (a line input is possible later).
- 16 strips of **250 LEDs**, WiFi through a dedicated router, static IPs.
- A simple model: **an L × N matrix** (no 2D spatial mapping).
- **RGB** strips (3 bytes per LED over DDP).
- Dependency management: `pyproject.toml` + `uv` (the initial plan's `requirements.txt` is dropped).
- **Gamma correction applied at the output** (patch stage, 256-value LUT), not in the effects.
- Engine: when late, **skip** the frame instead of catching up in a burst (no effect stutter).
- Network: **Ethernet to the dedicated router + WiFi for Internet**, distinct subnets (see §9 bis).
- LED topology: the app sends **over DDP directly to each of the 16 ESPs** (250 LEDs each).
  No relay / virtual LED between ESPs.
- Switching off: `off` **also** turns WLED off through the JSON API, otherwise the ESP resumes its
  internal effect 2.5 s after the last DDP packet.
- Brightness: forced to 255 on the WLED side before each send; only the app's master sets it.
- Audio: 2048 analysis window / 512 hop; beat and tempo detection on the low end of the spectrum;
  beats snapped to the grid; floor-to-peak auto gain (see §8 ter).
- An immutable `AudioState` replaced on every block: the engine reads the analysis without a lock.
- Effects never choose a colour: everything goes through the deck palette (§8 quater).
- An effect must stay fully visible without sound: reactivity is never used to darken.
- Both decks run permanently (see §8 quinquies).
- Strobe, flash and blackout each have **a latch and a momentary** (both gestures exist in a club).
- The auto-mix must never depend on sound: an internal clock as backup.
- A manual action always takes priority over the automation.

## 11 bis. Single application and publication (2026-09-25)

- **A single window**: the *Live* page and the *Setup* page are two pages of a `QStackedWidget`,
  with one `Engine` and one `OutputStage`. That was the whole reason for two separate windows: two
  engines would have sent to the same ESPs at the same time. A single engine that asks the visible
  page removes the problem.
  - `_render` asks `install.render()` for the frame when the setup page is in front.
  - `OutputStage.send_frame` now accepts a `{output: row}` dictionary: that is the form used by
    setup, which addresses strips before any patch exists.
  - The setup page's network polling and preview only run while it is visible: no HTTP requests
    competing with DDP during a live set.
  - Changing the matrix size rebuilds the mixer, the master and the live page (`_rebuild_matrix`) —
    effects are sized at construction.
- `leddeck install` remains, but opens the same application on the setup page.
- **16 effects for 12 pads**: the profile keeps a `fav_effects` list — the effects placed on the
  controller grid, in pad order. `Profile.pad_effects()` fills the rest from the catalogue order,
  so the grid is always full even with no choice made. Set from "Controller effects…" in the
  navigation bar; the printable sheet shows the grid that is really under your fingers.
- **16 effects** in total after porting the MadMapper shaders; all rendered in under 0.35 ms per
  frame at 250 × 14 (the heaviest: Vortex).
- `--no-audio` is now honoured: the audio watchdog no longer reopens an input that was asked to
  stay closed.
- **Interface in French and English** (`ui/i18n.py`): French strings are the keys, English is a
  lookup table, and a missing key falls back to French rather than breaking. Effect, palette and
  parameter names are translated **for display only** — the stored key stays French, because
  profiles and the MIDI mapping rely on it. The language lives in the profile and is chosen from
  the navigation bar; changing it rebuilds the interface.
  **The command line follows too**: `--lang fr|en`, global, placed before the command. It has to be
  read **before** the argument parser is built, otherwise the help texts would already be fixed —
  hence `pick_language()`, which reads `sys.argv` by hand and then falls back to the profile.
  Effect and palette names are displayed translated and **both spellings are accepted as input**,
  whatever the language: a name learned from `fx list` in English must not stop working when you
  switch back to French. The module lives at `leddeck/i18n.py` (not in `ui/`), so `main.py` can use
  it without depending on Qt.
- **GitHub publication**: `README.md` (English), `LICENSE` (MIT, association Eclipse), completed
  `.gitignore`. The profiles in `profiles/` contain the club's private IPs (192.168.8.x): harmless,
  but to be removed if the repository should stay neutral.

## 12. Open questions

- Development on **3 strips** (`club` profile, 250 × 3 matrix): enough for row order, reversing and
  identification. Going to 16 is only a matter of number.
- Tube #3 has a weaker signal (−58 dBm): to watch when all 16 are in place (number of clients on
  the router, antenna positions).
