"""leddeck — outils en ligne de commande (etape 1 : coeur + sortie).

  leddeck profile init --outputs 16 --ip-base 192.168.0.101
  leddeck profile show
  leddeck discover --add
  leddeck test sweep --seconds 20
  leddeck identify
  leddeck blink 7
  leddeck fx list | fx run Serpent --palette Feu
  leddeck ui
  leddeck audio devices | audio monitor | audio leds
  leddeck off        # noir DDP + extinction des WLED
  leddeck on
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from .i18n import LANGUAGES, set_language, tr
from .core.config import DDP_PORT, Profile
from .core.engine import Engine
from .install import patterns as P
from .output.patch import OutputStage


# --- utilitaires -------------------------------------------------------------


class DirectSink:
    """Sink du mode installation : adresse les bandeaux par numero, sans patch."""

    def __init__(self, stage: OutputStage) -> None:
        self.stage = stage

    def send_frame(self, buffers, brightness=None) -> None:
        self.stage.send_direct(buffers, brightness)


def load(args) -> Profile:
    prof = Profile.load(args.profile)
    prof.ensure_patch()
    return prof


def run(engine: Engine, stage: OutputStage, seconds: float | None, label: str) -> None:
    dur = "en continu (Ctrl-C pour arreter)" if seconds is None else f"{seconds:g} s"
    print(f"{label} — {dur}")
    engine.run_for(seconds)
    stage.blackout()
    stage.close()
    print(
        tr("  {} frames, {:.1f} fps, {} retard(s), {} paquets, {} erreur(s) reseau").format(engine.frames, engine.measured_fps, engine.late_frames, stage.sender.packets_sent, stage.sender.errors)
    )


def wake(prof: Profile) -> None:
    """Prepare les WLED avant d'emettre : allumes, luminosite WLED au maximum.

    Uniformise les sorties quel que soit le reglage local de chaque ESP.
    """
    from .output import wled

    ok, total = wled.wake_all(prof.outputs)
    if total and ok < total:
        print(tr("  ({}/{} sortie(s) rallumee(s) — les autres n'ont pas repondu sur HTTP)").format(ok, total))


def check_outputs(prof: Profile) -> bool:
    usable = [o for o in prof.outputs if o.enabled and o.ip]
    if not usable:
        print(
            tr("Aucune sortie utilisable dans le profil '{}'.\n  -> leddeck discover --add   (ou)   leddeck profile init --outputs 16 --ip-base 192.168.0.101").format(prof.name),
            file=sys.stderr,
        )
        return False
    return True


# --- commandes ---------------------------------------------------------------


def cmd_profile_init(args) -> int:
    prof = Profile(name=args.profile, leds=args.leds, strips=args.strips, fps=args.fps)
    if args.outputs and args.ip_base:
        base = args.ip_base.rsplit(".", 1)
        first = int(base[1])
        for i in range(args.outputs):
            prof.add_output(
                name=f"Bandeau {i + 1}",
                ip=f"{base[0]}.{first + i}",
                led_count=args.leds,
                port=DDP_PORT,
            )
        prof.autopatch()
    path = prof.save()
    print(tr("Profil ecrit : {}").format(path))
    return cmd_profile_show(args)


def cmd_profile_show(args) -> int:
    prof = load(args)
    print(tr("Profil '{}' — matrice {} LED x {} bandeaux @ {} fps (gamma {}, luminosite {:g})").format(prof.name, prof.leds, prof.strips, prof.fps, prof.gamma, prof.brightness))
    print(tr("  {} sortie(s) :").format(len(prof.outputs)))
    for o in prof.outputs:
        state = "" if o.enabled else "  [desactivee]"
        print(tr("    #{:<3} {:<16} {:<16} {:>4} LED  port {}{}").format(o.id, o.name, o.ip, o.led_count, o.port, state))
    print(tr("  patch :"))
    for i, row in enumerate(prof.patch):
        out = prof.output(row.output_id)
        desc = out.label if out else "— (ligne noire)"
        flags = []
        if row.reverse:
            flags.append("inversee")
        if row.offset:
            flags.append(f"offset {row.offset}")
        print(tr("    ligne {:>2} <- {}{}").format(i + 1, desc, '  (' + ', '.join(flags) + ')' if flags else ''))
    return 0


def cmd_discover(args) -> int:
    from .output import wled

    print(tr("Recherche des WLED{}…").format(' sur ' + args.cidr if args.cidr else ' sur le reseau local'))
    found = wled.discover(args.cidr, use_mdns=not args.no_mdns, timeout=args.timeout)
    if not found:
        print(tr("Aucun WLED trouve. Verifier le reseau, et l'autorisation « Reseau local » "
              "(Reglages > Confidentialite et securite > Reseau local)."))
        return 1
    print(tr("{} WLED trouve(s) :").format(len(found)))
    for w in found:
        warn = "" if w.ddp_ok else "  /!\\ version < 0.13 : DDP non garanti"
        print(tr("  {:<16} {:<18} {:>4} LED  v{:<10} rssi {:>4} dBm  {}{}").format(w.ip, w.name, w.leds, w.version, w.rssi, w.mac, warn))
    if args.add:
        prof = load(args)
        known = {o.mac for o in prof.outputs if o.mac} | {o.ip for o in prof.outputs}
        added = 0
        for w in found:
            if w.mac in known or w.ip in known:
                continue
            prof.outputs.append(w.to_output(prof.next_output_id()))
            added += 1
        if args.autopatch:
            prof.autopatch()
        prof.save()
        print(tr("{} sortie(s) ajoutee(s) au profil '{}'.").format(added, prof.name))
    return 0


def cmd_test(args) -> int:
    prof = load(args)
    if not check_outputs(prof):
        return 1
    fn = P.MATRIX_PATTERNS[args.pattern]
    wake(prof)
    stage = OutputStage(prof)
    engine = Engine(lambda t, dt: fn(t, prof.leds, prof.strips), stage,
                    fps=args.fps or prof.fps)
    prof.brightness = args.brightness
    run(engine, stage, args.seconds,
        f"Motif '{args.pattern}' sur {len(stage.patch.targets())} sortie(s)")
    return 0


def cmd_identify(args) -> int:
    prof = load(args)
    if not check_outputs(prof):
        return 1
    wake(prof)
    stage = OutputStage(prof)
    prof.brightness = args.brightness
    engine = Engine(lambda t, dt: P.identify(prof, t), DirectSink(stage), fps=10)
    run(engine, stage, args.seconds,
        "Identification : debut vert, fin rouge, blocs blancs = numero de sortie")
    return 0


def cmd_blink(args) -> int:
    prof = load(args)
    out = prof.output(args.id)
    if out is None:
        print(tr("Sortie #{} inconnue dans le profil '{}'.").format(args.id, prof.name), file=sys.stderr)
        return 1
    wake(prof)
    stage = OutputStage(prof)
    prof.brightness = args.brightness
    engine = Engine(
        lambda t, dt: {out.id: P.blink_line(out.id, out.led_count, t)},
        DirectSink(stage), fps=20,
    )
    run(engine, stage, args.seconds, f"Clignotement de {out.label} ({out.ip})")
    return 0


# --- MIDI --------------------------------------------------------------------


def cmd_midi_ports(args) -> int:
    from .midi import midi

    print(tr("Entrées MIDI :"))
    for name in midi.input_ports():
        print(f"   {name}")
    print(tr("Sorties MIDI :"))
    for name in midi.output_ports():
        print(f"   {name}")
    return 0


def cmd_midi_monitor(args) -> int:
    """Affiche tout ce qui arrive : sert a relever les numeros du controleur."""
    import mido

    from .midi import midi

    names = [n for n in midi.input_ports()
             if not args.port or args.port.lower() in n.lower()]
    if not names:
        print(tr("Aucune entrée MIDI correspondante."), file=sys.stderr)
        return 1

    seen: dict[tuple, int] = {}
    order: list[tuple] = []

    def on_message(name):
        def handler(msg):
            control = midi.Control.from_message(msg)
            if control is None:
                return
            key = (name, control.kind, control.channel, control.number)
            if key not in seen:
                order.append(key)
                seen[key] = 0
                value = int(midi.message_value(msg) * 127)
                print(tr("  {:<22} {:<24} valeur {}").format(name, str(control), value))
            seen[key] += 1
        return handler

    ports = [mido.open_input(name, callback=on_message(name)) for name in names]
    print(tr("Écoute de {} port(s) — actionnez les commandes ({}) :").format(len(ports), 'en continu' if args.seconds is None else f'{args.seconds:g} s'))
    try:
        end = None if args.seconds is None else time.monotonic() + args.seconds
        while end is None or time.monotonic() < end:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        for port in ports:
            port.close()
    print(tr("\n{} commande(s) distincte(s), {} message(s).").format(len(order), sum(seen.values())))
    return 0


def cmd_midi_sheet(args) -> int:
    """Genere la fiche de mapping imprimable."""
    from pathlib import Path

    from .midi.mapping import Mapping
    from .midi.sheet import write_sheet

    prof = load(args)
    mapping = Mapping.load(args.mapping)
    path = write_sheet(mapping, Path(args.output), prof)
    print(tr("Fiche écrite : {}  ({} assignations)").format(path, len(mapping.bindings)))
    return 0


# --- effets et interface -----------------------------------------------------


def cmd_fx_list(args) -> int:
    from .core.palette import all_palettes
    from .effects.base import by_name as fx_by_name, effect_names

    print(tr("Effets :"))
    for name in effect_names():
        cls = fx_by_name(name)
        params = ", ".join(f"{tr(k)} [{v[0]:g}..{v[1]:g}, def {v[2]:g}]"
                           for k, v in cls.params.items())
        print(f"  {tr(name):<14} {params}")
    print(tr("\nPalettes :"))
    for pal in all_palettes():
        kind = tr("cyclique") if pal.cyclic else tr("orientee")
        print(tr("  {:<14} {} couleurs, {}").format(tr(pal.name), len(pal.colors), kind))
    return 0


def cmd_fx_run(args) -> int:
    """Joue un effet sur les bandeaux, sans interface."""
    from .core.palette import by_name as pal_by_name
    from .effects.base import by_name as fx_by_name

    prof = load(args)
    if not check_outputs(prof):
        return 1
    effect = fx_by_name(args.effect)(prof.leds, prof.strips)
    palette = pal_by_name(args.palette)
    for item in args.set or []:
        key, _, value = item.partition("=")
        if key not in effect.p:
            print(tr("parametre inconnu pour {} : {!r} (connus : {})").format(effect.name, key, ', '.join(effect.p)), file=sys.stderr)
            return 1
        effect.p[key] = float(value)

    analyzer = audio = None
    if not args.no_audio:
        try:
            from .audio.analysis import Analyzer
            from .audio.input import AudioInput

            analyzer = Analyzer()
            audio = AudioInput(device=args.device or (prof.audio_device or None),
                               on_block=analyzer.process)
            audio.start()
        except Exception as exc:
            print(tr("  (son indisponible : {!r})").format(exc))
            analyzer = audio = None

    wake(prof)
    stage = OutputStage(prof)
    prof.brightness = args.brightness
    engine = Engine(lambda t, dt: effect.render(t, dt, analyzer.state() if analyzer else None,
                                                palette, effect.p),
                    stage, fps=prof.fps)
    try:
        run(engine, stage, args.seconds,
            f"Effet '{effect.name}' / palette '{palette.name}'"
            f"{' (sans son)' if analyzer is None else ''}")
    finally:
        if audio is not None:
            audio.stop()
    return 0


def cmd_install(args) -> int:
    """Ouvre l'écran d'installation (découverte, identification, patch)."""
    from .ui.main_window import run as run_ui

    prof = load(args)
    print(tr("Installation — profil '{}', matrice {} x {}, {} sortie(s)").format(prof.name, prof.leds, prof.strips, len(prof.outputs)))
    # Meme application que « ui » : elle s'ouvre simplement sur la page installation.
    return run_ui(prof, audio_device=getattr(args, "device", None),
                  use_audio=not getattr(args, "no_audio", False), page=1)


def cmd_ui(args) -> int:
    from .ui.main_window import run as run_ui

    prof = load(args)
    print(tr("Interface — profil '{}', matrice {} x {}, {} sortie(s)").format(prof.name, prof.leds, prof.strips, len([o for o in prof.outputs if o.enabled and o.ip])))
    return run_ui(prof, audio_device=args.device, use_audio=not args.no_audio,
                  midi_mapping=None if args.no_midi else args.midi)


# --- audio -------------------------------------------------------------------


def _dbfs(value: float) -> float:
    """RMS 0..1 -> decibels pleine echelle."""
    import math

    return -99.0 if value <= 1e-9 else 20.0 * math.log10(value)


def _dbfs_unit(value: float, floor: float = -60.0) -> float:
    """RMS -> 0..1 sur une echelle en decibels, de `floor` a 0 dBFS."""
    return max(0.0, min(1.0, (_dbfs(value) - floor) / (-floor)))


def _bar(v: float, width: int = 18) -> str:
    n = int(round(max(0.0, min(1.0, v)) * width))
    return "#" * n + "." * (width - n)


def _audio_stack(args, prof: Profile):
    """Ouvre l'entree audio et branche l'analyseur dessus."""
    from .audio.analysis import Analyzer
    from .audio.input import AudioInput

    device = args.device if args.device else (prof.audio_device or None)
    channels = (parse_channels(args.channels) if getattr(args, "channels", None)
                else prof.audio_channels)
    analyzer = Analyzer()
    audio = AudioInput(device=device, on_block=analyzer.process, channels=channels)
    audio.start()
    analyzer.__init__(audio.samplerate, audio.blocksize)   # la carte impose sa frequence
    voies = ", ".join(str(c + 1) for c in audio.selected)
    print(tr("Entree audio : {} — {} Hz, {} voie(s), melange des voies {}").format(audio.device_name, audio.samplerate, audio.available, voies))
    return audio, analyzer


def parse_channels(text: str) -> list[int]:
    """« 3,4 » -> [2, 3] : l'utilisateur compte a partir de 1."""
    out = []
    for part in str(text).replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part) - 1)
    return out


def cmd_audio_levels(args) -> int:
    """Niveau de chaque entree de la carte : pour trouver ou arrive le signal."""
    from .audio.input import AudioInput

    prof = load(args)
    audio = AudioInput(device=args.device or (prof.audio_device or None))
    audio.start()
    print(tr("{} — {} entrée(s), {} Hz").format(audio.device_name, audio.available, audio.samplerate))
    print(tr("Envoyez du son, la voie qui bouge est la bonne. Ctrl-C pour arrêter.\n"))
    peaks = None
    try:
        end = None if args.seconds is None else time.monotonic() + args.seconds
        while end is None or time.monotonic() < end:
            levels = audio.channel_levels
            if levels is not None:
                peaks = levels.copy() if peaks is None else np.maximum(peaks * 0.98, levels)
                # Echelle en decibels : une jauge lineaire ne montre rien en
                # dessous de -20 dBFS, alors qu'une entree ligne y vit souvent.
                cells = "  ".join(f"{i + 1}:{_bar(_dbfs_unit(float(v)), 10)}"
                                  for i, v in enumerate(peaks))
                sys.stdout.write("\r" + cells + " ")
                sys.stdout.flush()
            time.sleep(0.08)
    except KeyboardInterrupt:
        pass
    finally:
        audio.stop()
    if peaks is not None:
        order = np.argsort(peaks)[::-1]
        print(tr("\n\nNiveaux relevés :"))
        for rank in order[:4]:
            print(tr("   voie {:<3} {:6.1f} dBFS").format(rank + 1, _dbfs(float(peaks[rank]))))
        best = int(order[0]) + 1
        second = int(order[1]) + 1 if len(order) > 1 else best
        pair = sorted({best, second}) if abs(_dbfs(float(peaks[order[0]]))
                                             - _dbfs(float(peaks[order[1]]))) < 6 else [best]
        print(tr("\nPour l'utiliser : --channels {}").format(','.join(str(c) for c in pair)))
    return 0


def _warn_if_silent(audio, warned: bool) -> bool:
    if not warned and audio.silent_seconds > 4.0:
        print(tr("\n  /!\\ rien ne rentre depuis 4 s — autorisation micro ? "
              "(Reglages > Confidentialite et securite > Microphone)"))
        return True
    return warned


def cmd_audio_devices(args) -> int:
    from .audio.input import list_devices

    for d in list_devices():
        print(" ", d)
    return 0


def cmd_audio_monitor(args) -> int:
    """Affiche en direct bandes, niveau, BPM et beats dans le terminal."""
    prof = load(args)
    audio, analyzer = _audio_stack(args, prof)
    print(tr("bandes / niveau / BPM — Ctrl-C pour arreter\n"))
    warned = False
    beats = 0
    last_beat_at = 0.0
    try:
        end = None if args.seconds is None else time.monotonic() + args.seconds
        while end is None or time.monotonic() < end:
            st = analyzer.state()
            now = time.monotonic()
            if st.beat_count != beats:
                beats, last_beat_at = st.beat_count, now
            flash = "BEAT" if now - last_beat_at < 0.12 else "    "
            conf = f"{st.bpm_confidence:.2f}"
            sat = "SATURE" if audio.clipping else "      "
            sys.stdout.write(
                f"\rbasses {_bar(st.bass)}  medium {_bar(st.mid)}  aigus {_bar(st.treble)}"
                f" | entree {audio.peak:4.2f} {sat} | niv {st.level:4.2f}"
                f" | BPM {st.bpm:6.1f} ({conf}) | {beats:4d} {flash} "
            )
            sys.stdout.flush()
            warned = _warn_if_silent(audio, warned)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        audio.stop()
    pct = 100.0 * audio.clipped / max(1, audio.blocks)
    print(tr("\n{} blocs analyses, {} depassement(s), {} beats, {} bloc(s) satures ({:.1f} %).").format(audio.blocks, audio.overflows, beats, audio.clipped, pct))
    if pct > 1.0:
        print(tr("  -> l'entree sature : baisser le volume ou eloigner le micro. "
              "La distorsion cree de fausses attaques."))
    return 0


COLORS = {
    "red": (1.0, 0.0, 0.0), "green": (0.0, 1.0, 0.0), "blue": (0.0, 0.0, 1.0),
    "white": (1.0, 1.0, 1.0), "cyan": (0.0, 1.0, 1.0), "magenta": (1.0, 0.0, 1.0),
    "amber": (1.0, 0.45, 0.0), "pink": (1.0, 0.1, 0.4),
}


def cmd_audio_leds(args) -> int:
    """Spectre, ou couleur unie pulsee sur le beat : validation materielle."""
    prof = load(args)
    if not check_outputs(prof):
        return 1
    audio, analyzer = _audio_stack(args, prof)
    wake(prof)
    stage = OutputStage(prof)
    prof.brightness = args.brightness

    state = {"beats": 0, "flash": 0.0, "env": 0.0}
    color = COLORS[args.color]

    def render(t, dt):
        st = analyzer.state()
        beat = st.beat_count != state["beats"]
        if beat:
            state["beats"] = st.beat_count
            state["flash"] = args.flash
            state["env"] = 1.0
        if args.mode == "pulse":
            # Retombee calee sur le tempo : un quart de beat, pour que la pulsation
            # reste lisible aussi bien a 90 qu'a 170 BPM.
            tau = max(0.05, (st.period or 0.5) * args.decay)
            state["env"] *= float(np.exp(-dt / tau))
            return P.beat_pulse(prof.leds, prof.strips, state["env"], color, floor=args.floor)
        state["flash"] *= float(np.exp(-dt / 0.08))   # retombee du flash en ~80 ms
        return P.audio_bars(prof.leds, prof.strips, st.spectrum,
                            level=1.0, flash=state["flash"])

    engine = Engine(render, stage, fps=prof.fps)
    engine.start()
    warned = False
    try:
        end = None if args.seconds is None else time.monotonic() + args.seconds
        while engine.running and (end is None or time.monotonic() < end):
            st = analyzer.state()
            sys.stdout.write(
                f"\rbasses {_bar(st.bass)}  aigus {_bar(st.treble)}"
                f" | entree {audio.peak:4.2f} {'SATURE' if audio.clipping else '      '}"
                f" | BPM {st.bpm:6.1f} ({st.bpm_confidence:.2f}) | {st.beat_count:4d} beats"
                f" | {engine.measured_fps:4.1f} fps "
            )
            sys.stdout.flush()
            warned = _warn_if_silent(audio, warned)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        audio.stop()
        stage.blackout()
        stage.close()
    pct = 100.0 * audio.clipped / max(1, audio.blocks)
    print(tr("\n{} frames, {:.1f} fps, {} erreur(s) reseau, {} depassement(s) audio, {} bloc(s) satures ({:.1f} %).").format(engine.frames, engine.measured_fps, stage.sender.errors, audio.overflows, audio.clipped, pct))
    if pct > 1.0:
        print(tr("  -> l'entree sature : baisser le volume ou eloigner le micro."))
    return 0


DIAG_LINES = {
    "ends": lambda leds, t: P.ends_line(leds),
    "ruler": lambda leds, t: P.ruler_line(leds),
    "rouge": lambda leds, t: np.tile(np.float32((1, 0, 0)), (leds, 1)),
    "vert": lambda leds, t: np.tile(np.float32((0, 1, 0)), (leds, 1)),
    "bleu": lambda leds, t: np.tile(np.float32((0, 0, 1)), (leds, 1)),
    "blanc": lambda leds, t: np.tile(np.float32((1, 1, 1)), (leds, 1)),
}


def cmd_diag(args) -> int:
    """Motif de diagnostic sur une seule sortie, sans passer par le patch."""
    prof = load(args)
    out = prof.output(args.output)
    if out is None:
        print(tr("Sortie #{} inconnue. Connues : {}").format(args.output, ', '.join(o.label for o in prof.outputs) or 'aucune'), file=sys.stderr)
        return 1
    leds = args.leds or out.led_count
    wake(prof)
    stage = OutputStage(prof)
    prof.brightness = args.brightness
    make = DIAG_LINES[args.pattern]
    engine = Engine(lambda t, dt: {out.id: make(leds, t)}, DirectSink(stage), fps=10)
    run(engine, stage, args.seconds,
        f"Diagnostic « {args.pattern} » sur {out.label} — {leds} LED adressées")
    return 0


def cmd_prepare(args) -> int:
    """Configure les ESP pour le club : temps reel a fond, repos eteint."""
    from .output import wled

    prof = load(args)
    targets = [o for o in prof.outputs if o.enabled and o.ip]
    if not targets:
        print(tr("Aucune sortie dans le profil '{}'.").format(prof.name), file=sys.stderr)
        return 1

    def label(settings) -> str:
        if settings is None:
            return "injoignable"
        marks = []
        marks.append(("✔" if settings["maxbri"] else "✘") + " force-max-bri")
        marks.append(("✔" if settings["no-gc"] else "✘") + " sans gamma")
        marks.append(("✔" if settings["en"] else "✘") + " temps réel")
        marks.append(("✔" if not settings["boot_on"] else "✘") + " démarrage éteint")
        return "  ".join(marks)

    verb = "État de" if args.check else "Préparation de"
    print(tr("{} {} sortie(s) — profil '{}'\n").format(verb, len(targets), prof.name))
    unreachable, misconfigured = 0, []
    for out in targets:
        if args.check:
            config = wled.get_config(out.ip)
            after = wled.club_settings(config) if config else None
            print(f"  {out.label:<22} {label(after)}")
        else:
            before, after = wled.prepare(out.ip)
            print(tr("  {:<22} avant : {}").format(out.label, label(before)))
            print(tr("  {:<22} après : {}").format('', label(after)))
        if after is None:
            unreachable += 1
        elif not (after["maxbri"] and after["no-gc"] and after["en"] and not after["boot_on"]):
            misconfigured.append(out.label)

    print()
    if unreachable:
        print(tr("{} sortie(s) injoignable(s).").format(unreachable))
    if misconfigured:
        # En mode --check on ne corrige rien : le dire clairement.
        what = "à configurer" if args.check else "toujours mal réglée(s) après écriture"
        print(tr("{} sortie(s) {} : {}").format(len(misconfigured), what, ', '.join(misconfigured)))
        if args.check:
            print(tr("  -> lancer « leddeck prepare » (sans --check) pour les corriger."))
    elif not unreachable:
        print(tr("Toutes les sorties sont correctement configurées."))
    print(tr("À vérifier sur le matériel : les tubes doivent s'allumer en émission "
          "et redevenir noirs 2,5 s après l'arrêt."))
    return 1 if (unreachable or misconfigured) else 0


def cmd_off(args) -> int:
    """Blackout reel : noir en DDP *puis* extinction de WLED via l'API JSON.

    Sans la seconde etape, WLED reprend son propre etat (souvent un effet allume)
    2,5 s apres le dernier paquet DDP.
    """
    from .output import wled

    prof = load(args)
    stage = OutputStage(prof)
    for _ in range(3):  # UDP : on insiste un peu
        stage.blackout()
    stage.close()
    n = len([o for o in prof.outputs if o.enabled and o.ip])
    print(tr("Noir envoye en DDP sur {} sortie(s).").format(n))
    if not args.ddp_only:
        ok, total = wled.power_all(prof.outputs, False)
        print(f"WLED eteint sur {ok}/{total} sortie(s)." if total else "Aucune sortie a eteindre.")
        if total and ok < total:
            print(tr("  (les sorties muettes seront rallumees par leur propre etat : verifier leur IP)"))
    return 0


def cmd_on(args) -> int:
    from .output import wled

    prof = load(args)
    ok, total = wled.wake_all(prof.outputs)
    print(tr("WLED rallume (luminosite au max) sur {}/{} sortie(s).").format(ok, total))
    return 0 if ok == total else 1


# --- interface ---------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="leddeck", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="default", help=tr("profil de salle (defaut : default)"))
    ap.add_argument("--lang", choices=tuple(LANGUAGES), default=None,
                    help=tr("langue des messages (defaut : celle du profil)"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help=tr("creer / afficher un profil de salle"))
    psub = p.add_subparsers(dest="sub", required=True)
    pi = psub.add_parser("init", help=tr("creer un profil"))
    pi.add_argument("--leds", type=int, default=250, help=tr("LED par bandeau (L)"))
    pi.add_argument("--strips", type=int, default=16, help=tr("nombre de bandeaux (N)"))
    pi.add_argument("--fps", type=int, default=40)
    pi.add_argument("--outputs", type=int, default=0, help=tr("creer N sorties d'office"))
    pi.add_argument("--ip-base", default="", help=tr("IP de la premiere sortie, ex. 192.168.0.101"))
    pi.set_defaults(func=cmd_profile_init)
    ps = psub.add_parser("show", help=tr("afficher le profil"))
    ps.set_defaults(func=cmd_profile_show)

    d = sub.add_parser("discover", help=tr("chercher les WLED sur le reseau"))
    d.add_argument("--cidr", default=None, help=tr("sous-reseau a balayer, ex. 192.168.0.0/24"))
    d.add_argument("--timeout", type=float, default=0.6)
    d.add_argument("--no-mdns", action="store_true")
    d.add_argument("--add", action="store_true", help=tr("ajouter les WLED trouves au profil"))
    d.add_argument("--autopatch", action="store_true", help=tr("patcher #1->ligne 1, #2->ligne 2…"))
    d.set_defaults(func=cmd_discover)

    t = sub.add_parser("test", help=tr("motif de test sur la matrice"))
    t.add_argument("pattern", choices=sorted(P.MATRIX_PATTERNS), nargs="?", default="sweep")
    t.add_argument("--seconds", type=float, default=None)
    t.add_argument("--fps", type=int, default=None)
    t.add_argument("--brightness", type=float, default=1.0)
    t.set_defaults(func=cmd_test)

    i = sub.add_parser("identify", help=tr("chaque bandeau affiche son numero"))
    i.add_argument("--seconds", type=float, default=None)
    i.add_argument("--brightness", type=float, default=1.0)
    i.set_defaults(func=cmd_identify)

    b = sub.add_parser("blink", help=tr("faire clignoter une sortie"))
    b.add_argument("id", type=int)
    b.add_argument("--seconds", type=float, default=None)
    b.add_argument("--brightness", type=float, default=1.0)
    b.set_defaults(func=cmd_blink)

    m = sub.add_parser("midi", help=tr("contrôleur MIDI"))
    msub = m.add_subparsers(dest="sub", required=True)
    mp = msub.add_parser("ports", help=tr("lister les ports MIDI"))
    mp.set_defaults(func=cmd_midi_ports)
    mm = msub.add_parser("monitor", help=tr("afficher les messages reçus"))
    mm.add_argument("--port", default=None, help=tr("fragment du nom du port"))
    mm.add_argument("--seconds", type=float, default=None)
    mm.set_defaults(func=cmd_midi_monitor)
    ms = msub.add_parser("sheet", help=tr("fiche de mapping imprimable (HTML)"))
    ms.add_argument("--mapping", default="apcmini-mk2")
    ms.add_argument("--output", default="midi/mapping-apcmini-mk2.html")
    ms.set_defaults(func=cmd_midi_sheet)

    f = sub.add_parser("fx", help=tr("effets et palettes"))
    fsub = f.add_subparsers(dest="sub", required=True)
    fl = fsub.add_parser("list", help=tr("lister effets et palettes"))
    fl.set_defaults(func=cmd_fx_list)
    fr = fsub.add_parser("run", help=tr("jouer un effet sur les bandeaux"))
    fr.add_argument("effect")
    fr.add_argument("--palette", default="Arc-en-ciel")
    fr.add_argument("--set", action="append", metavar="PARAM=VALEUR",
                    help=tr("regler un parametre, ex. --set vitesse=2.5"))
    fr.add_argument("--seconds", type=float, default=None)
    fr.add_argument("--brightness", type=float, default=0.8)
    fr.add_argument("--device", default=None, help=tr("entree audio"))
    fr.add_argument("--no-audio", action="store_true")
    fr.set_defaults(func=cmd_fx_run)

    i2 = sub.add_parser("install", help=tr("écran d'installation : découverte, identification, patch"))
    i2.set_defaults(func=cmd_install)

    u = sub.add_parser("ui", help=tr("ouvrir l'interface (apercu + effets + palettes)"))
    u.add_argument("--device", default=None, help=tr("entree audio"))
    u.add_argument("--no-audio", action="store_true")
    u.add_argument("--midi", default="apcmini-mk2", help=tr("mapping MIDI à charger"))
    u.add_argument("--no-midi", action="store_true")
    u.set_defaults(func=cmd_ui)

    a = sub.add_parser("audio", help=tr("entree audio : peripheriques, moniteur, test LED"))
    asub = a.add_subparsers(dest="sub", required=True)
    ad = asub.add_parser("devices", help=tr("lister les entrees audio"))
    ad.set_defaults(func=cmd_audio_devices)
    am = asub.add_parser("monitor", help=tr("bandes / BPM / beats dans le terminal"))
    am.add_argument("--device", default=None, help=tr("index ou nom partiel de l'entree"))
    am.add_argument("--seconds", type=float, default=None)
    am.add_argument("--channels", default=None, help=tr("voies à mélanger, ex. 3,4"))
    am.set_defaults(func=cmd_audio_monitor)
    al2 = asub.add_parser("levels", help=tr("niveau de chaque entrée de la carte"))
    al2.add_argument("--device", default=None)
    al2.add_argument("--seconds", type=float, default=None)
    al2.set_defaults(func=cmd_audio_levels)
    al = asub.add_parser("leds", help=tr("spectre sur les bandeaux + flash sur le beat"))
    al.add_argument("--device", default=None)
    al.add_argument("--channels", default=None, help=tr("voies à mélanger, ex. 3,4"))
    al.add_argument("--seconds", type=float, default=None)
    al.add_argument("--brightness", type=float, default=0.8)
    al.add_argument("--flash", type=float, default=0.5, help=tr("intensite du flash sur le beat"))
    al.add_argument("--mode", choices=("spectrum", "pulse"), default="spectrum",
                    help=tr("spectre sur la longueur, ou couleur unie pulsee sur le beat"))
    al.add_argument("--color", choices=sorted(COLORS), default="red", help=tr("couleur du mode pulse"))
    al.add_argument("--decay", type=float, default=0.25,
                    help=tr("duree de retombee, en fraction de beat (0,25 = un quart de beat)"))
    al.add_argument("--floor", type=float, default=0.04, help=tr("niveau residuel entre deux beats"))
    al.set_defaults(func=cmd_audio_leds)

    dg = sub.add_parser("diag", help=tr("motif de diagnostic sur une sortie"))
    dg.add_argument("output", type=int, help=tr("numéro de sortie"))
    dg.add_argument("--pattern", choices=sorted(DIAG_LINES), default="ends")
    dg.add_argument("--leds", type=int, default=None,
                    help=tr("forcer un nombre de LED différent de celui du profil"))
    dg.add_argument("--seconds", type=float, default=None)
    dg.add_argument("--brightness", type=float, default=0.6)
    dg.set_defaults(func=cmd_diag)

    pr = sub.add_parser("prepare", help=tr("configurer les ESP pour le club"))
    pr.add_argument("--check", action="store_true", help=tr("afficher sans rien modifier"))
    pr.set_defaults(func=cmd_prepare)

    o = sub.add_parser("off", help=tr("tout eteindre (noir DDP + extinction WLED)"))
    o.add_argument("--ddp-only", action="store_true",
                   help=tr("envoyer du noir sans eteindre WLED (il se rallumera seul apres 2,5 s)"))
    o.set_defaults(func=cmd_off)

    n = sub.add_parser("on", help=tr("rallumer les WLED (apres un off)"))
    n.set_defaults(func=cmd_on)
    return ap


def pick_language(argv: list[str]) -> str:
    """Langue a appliquer avant de construire l'analyseur d'arguments.

    Les textes d'aide sont figes a la construction : il faut donc connaitre la
    langue avant qu'argparse n'ait lu quoi que ce soit. D'ou cette lecture
    directe de la ligne de commande, puis du profil.
    """
    def value_of(flag: str) -> str | None:
        for i, token in enumerate(argv):
            if token == flag and i + 1 < len(argv):
                return argv[i + 1]
            if token.startswith(flag + "="):
                return token.split("=", 1)[1]
        return None

    asked = value_of("--lang")
    if asked in LANGUAGES:
        return asked
    try:
        return Profile.load(value_of("--profile") or "default").language
    except Exception:
        return "fr"          # profil absent ou illisible : l'aide reste affichable


def main(argv: list[str] | None = None) -> int:
    set_language(pick_language(list(sys.argv[1:] if argv is None else argv)))
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
