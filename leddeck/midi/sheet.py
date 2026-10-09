"""Fiche de mapping imprimable, generee depuis le fichier de mapping.

Le but est qu'elle reste juste : elle lit les assignations reelles et les vrais
noms d'effets et de palettes, au lieu d'etre recopiee a la main.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from ..core.mixer import Deck
from ..i18n import language, tr
from .mapping import (
    COLOR_ROWS, EFFECT_ROWS, FADER_CC, PALETTE_ROWS, SCENE_NOTES, SHIFT_NOTE, TRACK_NOTES,
    Mapping, pad_note,
)
from .midi import CC, NOTE, Control

CSS = """
:root{
  --paper:#faf9f7; --surface:#fff; --ink:#14161a; --muted:#6c7480; --hairline:#dedbd4;
  --deck-a:#0d93ad; --deck-b:#c43c74;
  --fx:#4338ca; --fx-soft:#ebeafa; --pal:#0f766e; --pal-soft:#e2f3f0;
  --live:#a8741c; --live-soft:#f8f0de; --free:#f1efeb;
}
:root:not([data-theme="light"]){}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#0f1013; --surface:#171920; --ink:#e8ebf1; --muted:#8a93a3; --hairline:#272b35;
    --deck-a:#22d3ee; --deck-b:#f472b6;
    --fx:#a5b4fc; --fx-soft:#1d1b38; --pal:#5eead4; --pal-soft:#0c2a26;
    --live:#e0a53c; --live-soft:#2f2611; --free:#1b1e25;
  }
}
:root[data-theme="dark"]{
  --paper:#0f1013; --surface:#171920; --ink:#e8ebf1; --muted:#8a93a3; --hairline:#272b35;
  --deck-a:#22d3ee; --deck-b:#f472b6;
  --fx:#a5b4fc; --fx-soft:#1d1b38; --pal:#5eead4; --pal-soft:#0c2a26;
  --live:#e0a53c; --live-soft:#2f2611; --free:#1b1e25;
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif;
  font-size:14px; line-height:1.45;
}
.sheet{max-width:1180px; margin:0 auto; padding-block:28px; padding-left:20px; padding-right:20px;}

header{display:flex; flex-wrap:wrap; align-items:baseline; gap:10px 18px; margin-bottom:18px;}
h1{
  font-family:"Barlow Condensed","Arial Narrow",sans-serif;
  font-weight:700; font-size:34px; letter-spacing:.02em; margin:0; text-wrap:balance;
}
.sub{color:var(--muted); font-size:13px;}
.sub code{font-family:"IBM Plex Mono",monospace; font-size:12px;}

.panel{
  display:grid;
  grid-template-columns:20px repeat(4, 1fr) 13px repeat(4, 1fr) 1.15fr;
  gap:5px; align-items:stretch;
  background:var(--surface); border:1px solid var(--hairline); border-radius:10px;
  padding:12px; margin-bottom:16px;
}
.zone{
  writing-mode:vertical-rl; transform:rotate(180deg);
  display:flex; align-items:center; justify-content:center;
  font-family:"Barlow Condensed",sans-serif; font-weight:700; font-size:11px;
  letter-spacing:.22em; color:var(--muted);
}
.cell{
  border:1px solid var(--hairline); border-radius:5px; padding:5px 6px;
  min-height:44px; display:flex; flex-direction:column; justify-content:space-between; gap:2px;
  background:var(--free);
}
.num{
  font-family:"IBM Plex Mono",monospace; font-size:9px; color:var(--muted);
  letter-spacing:.04em; font-variant-numeric:tabular-nums;
}
.name{
  font-family:"Barlow Condensed",sans-serif; font-weight:600; font-size:14px; line-height:1.1;
}
.cell.fx{background:var(--fx-soft); border-color:color-mix(in srgb, var(--fx) 35%, transparent);}
.cell.fx .name{color:var(--fx);}
.cell.pal{background:var(--pal-soft); border-color:color-mix(in srgb, var(--pal) 35%, transparent);}
.cell.pal .name{color:var(--pal);}
.cell.color{border-color:rgba(0,0,0,.28);}
.cell.color .num{color:inherit; opacity:.65;}
.gap{}
.head{
  display:flex; align-items:end; justify-content:center; padding-bottom:3px;
  font-family:"Barlow Condensed",sans-serif; font-weight:800; font-size:12px;
  letter-spacing:.2em;
}
.head.a{color:var(--deck-a);} .head.b{color:var(--deck-b);} .head.right{color:var(--live);}
.cell.empty .name{color:var(--muted); font-weight:400; font-style:italic;}
.cell.live{background:var(--live-soft); border-color:color-mix(in srgb, var(--live) 40%, transparent);}
.cell.live .name{color:var(--live);}
.cell.fader{min-height:52px;}
.cell.fader .name{font-size:13px;}
.spacer{grid-column:1;}

.legend{display:grid; grid-template-columns:repeat(auto-fit, minmax(230px,1fr)); gap:14px;}
.note{
  background:var(--surface); border:1px solid var(--hairline); border-radius:10px; padding:12px 14px;
}
.note h2{
  font-family:"Barlow Condensed",sans-serif; font-weight:700; font-size:12px;
  letter-spacing:.18em; text-transform:uppercase; color:var(--muted); margin:0 0 8px;
}
.note p{margin:0 0 8px; font-size:12.5px;}
.note p:last-child{margin-bottom:0;}
.note ul{margin:0; padding-left:16px; font-size:12.5px;}
.note li{margin-bottom:3px;}
kbd{
  font-family:"IBM Plex Mono",monospace; font-size:11px; background:var(--free);
  border:1px solid var(--hairline); border-radius:4px; padding:1px 5px;
}
.swatch{display:inline-block; width:10px; height:10px; border-radius:2px; vertical-align:middle; margin-right:5px;}
footer{margin-top:16px; color:var(--muted); font-size:11px;}

@media (max-width:760px){
  .panel{grid-template-columns:16px repeat(4,1fr); font-size:12px;}
  .gap{display:none;}
  .zone{display:none;}
}
@media print{
  :root{
    --paper:#fff; --surface:#fff; --ink:#000; --muted:#555; --hairline:#bbb;
    --deck-a:#06697d; --deck-b:#a42a5c;
    --fx:#312ba8; --fx-soft:#f0effb; --pal:#0b5f58; --pal-soft:#eaf5f3;
    --live:#7d5510; --live-soft:#fbf4e4; --free:#f4f3f1;
  }
  @page{size:A4 landscape; margin:9mm;}
  body{background:#fff;}
  .sheet{max-width:none; padding:0;}
  .panel, .note{break-inside:avoid;}
  h1{font-size:26px;}
}
"""




SHEET_TEXT = {
    "fr": {
        "title": "Mapping APC mini mk2",
        "port": "port",
        "channel": "canal 1",
        "zone_fx": "EFFETS",
        "zone_pal": "PALETTES",
        "zone_col": "COULEURS",
        "footer": "Généré par <code>leddeck midi sheet</code> depuis le mapping — "
                  "les emplacements sans effet ou sans palette sont libres et assignables.",
        "legend": """
  <div class="note">
    <h2>Trois zones dans la grille</h2>
    <p>Rangées&nbsp;1&nbsp;à&nbsp;3&nbsp;: les effets. Rangées&nbsp;4&nbsp;à&nbsp;6&nbsp;: les
    palettes. Rangées&nbsp;7&nbsp;et&nbsp;8&nbsp;: huit couleurs unies, qui remplacent la palette
    perso — un appui met le deck sur cette couleur.</p>
  </div>
  <div class="note">
    <h2>Lire les numéros</h2>
    <p>Les pads portent leur numéro de note, les faders leur numéro de CC.
    Sur la grille&nbsp;: <code>note = rangée depuis le bas × 8 + colonne</code>,
    le pad en bas à gauche vaut <code>0</code>.</p>
    <p>Relevés sur le matériel, pas sur la documentation.</p>
  </div>
  <div class="note">
    <h2>Couleurs</h2>
    <p><span class="swatch" style="background:var(--fx)"></span>Effets<br>
    <span class="swatch" style="background:var(--pal)"></span>Palettes<br>
    <span class="swatch" style="background:var(--live)"></span>Fonctions live et master</p>
    <p>Les pads du bas portent leur vraie couleur. Deck&nbsp;A à gauche de la séparation,
    deck&nbsp;B à droite.</p>
    <p>Les effets s'allument en <strong>blanc faible</strong> au repos et
    <strong>blanc clignotant</strong> quand ils jouent. Les palettes prennent la couleur du deck,
    les fonctions live leur couleur propre, et les deux rangées du bas leur propre teinte.</p>
  </div>
  <div class="note">
    <h2>Deux façons d'appuyer</h2>
    <p><strong>Tant qu'on appuie</strong>&nbsp;: l'effet dure le temps de l'appui et s'arrête
    au relâchement. C'est le geste du strobe ou du kill.</p>
    <p><strong>Bascule on/off</strong>&nbsp;: un appui enclenche, un autre relâche.
    Le blackout existe dans les deux formes — à vous de choisir votre geste.</p>
  </div>
  <div class="note">
    <h2>Faders&nbsp;: reprise en douceur</h2>
    <p>Un fader ne prend la main qu'une fois revenu sur la valeur courante,
    et se ré-arme dès que la valeur change ailleurs (souris, auto-mix).</p>
    <p>Effleurer un fader ne fait donc jamais sauter un réglage.</p>
  </div>
  <div class="note">
    <h2>Au clavier</h2>
    <ul>
      <li><kbd>S</kbd> strobe · <kbd>E</kbd> électrique</li>
      <li><kbd>espace</kbd> flash · <kbd>B</kbd> blackout</li>
      <li><kbd>Maj</kbd> + la même touche&nbsp;: verrou au lieu du maintien</li>
    </ul>
  </div>""",
    },
    "en": {
        "title": "APC mini mk2 mapping",
        "port": "port",
        "channel": "channel 1",
        "zone_fx": "EFFECTS",
        "zone_pal": "PALETTES",
        "zone_col": "COLOURS",
        "footer": "Generated by <code>leddeck midi sheet</code> from the mapping — "
                  "slots with no effect and no palette are free and assignable.",
        "legend": """
  <div class="note">
    <h2>Three zones in the grid</h2>
    <p>Rows&nbsp;1&nbsp;to&nbsp;3&nbsp;: effects. Rows&nbsp;4&nbsp;to&nbsp;6&nbsp;: palettes.
    Rows&nbsp;7&nbsp;and&nbsp;8&nbsp;: eight solid colours, which stand in for the custom
    palette — one press puts the deck on that colour.</p>
  </div>
  <div class="note">
    <h2>Reading the numbers</h2>
    <p>Pads carry their note number, faders their CC number.
    On the grid&nbsp;: <code>note = row from the bottom × 8 + column</code>,
    and the bottom-left pad is <code>0</code>.</p>
    <p>Measured on the hardware, not taken from the documentation.</p>
  </div>
  <div class="note">
    <h2>Colours</h2>
    <p><span class="swatch" style="background:var(--fx)"></span>Effects<br>
    <span class="swatch" style="background:var(--pal)"></span>Palettes<br>
    <span class="swatch" style="background:var(--live)"></span>Live and master functions</p>
    <p>The bottom pads carry their real colour. Deck&nbsp;A left of the split,
    deck&nbsp;B right.</p>
    <p>Effects light <strong>dim white</strong> at rest and <strong>blinking white</strong>
    while they play. Palettes take the deck colour, live functions their own colour, and the
    two bottom rows their own hue.</p>
  </div>
  <div class="note">
    <h2>Two ways to press</h2>
    <p><strong>While held</strong>&nbsp;: the effect lasts as long as the press and stops on
    release. That is the strobe or kill gesture.</p>
    <p><strong>On/off latch</strong>&nbsp;: one press engages, another releases.
    Blackout exists in both forms — pick the gesture you want.</p>
  </div>
  <div class="note">
    <h2>Faders&nbsp;: soft takeover</h2>
    <p>A fader only takes over once it is back on the current value, and re-arms as soon as
    the value changes elsewhere (mouse, auto-mix).</p>
    <p>Brushing a fader therefore never makes a setting jump.</p>
  </div>
  <div class="note">
    <h2>Keyboard</h2>
    <ul>
      <li><kbd>S</kbd> strobe · <kbd>E</kbd> electric</li>
      <li><kbd>space</kbd> flash · <kbd>B</kbd> blackout</li>
      <li><kbd>Shift</kbd> + the same key&nbsp;: latch instead of hold</li>
    </ul>
  </div>""",
    },
}



def _cell(number_label: str, name: str, classes: str = "", style: str = "") -> str:
    empty = "" if name else " empty"
    shown = escape(name) if name else "libre"
    attr = f' style="{style}"' if style else ""
    return (f'<div class="cell {classes}{empty}"{attr}>'
            f'<span class="num">{escape(number_label)}</span>'
            f'<span class="name">{shown}</span></div>')


def _color_style(rgb) -> str:
    """Fond a la vraie couleur du pad, texte lisible dessus."""
    r, g, b = (float(v) for v in rgb)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    ink = "#101010" if luminance > 0.55 else "#ffffff"
    return (f"background:rgb({int(r * 255)},{int(g * 255)},{int(b * 255)});"
            f"color:{ink};")


def build_html(mapping: Mapping, profile) -> str:
    T = SHEET_TEXT.get(language(), SHEET_TEXT["fr"])
    deck = Deck("A", profile.leds, profile.strips)
    # La fiche doit montrer la grille telle qu'elle sera sous les doigts : les
    # effets choisis pour les pads, pas le catalogue complet.
    effects = profile.pad_effects(list(deck.effects))
    palettes = list(deck.palettes)

    def label_for(binding) -> str:
        if binding is None:
            return ""
        if binding.action in ("deck.effect", "deck.palette"):
            names = effects if binding.action == "deck.effect" else palettes
            index = int(binding.args.get("index", 0))
            return tr(names[index]) if index < len(names) else ""
        return tr(binding.label or binding.action)

    rows: list[str] = []
    rows.append('<div class="spacer"></div>')
    rows.append('<div class="head a" style="grid-column:span 4">DECK A</div>')
    rows.append('<div class="gap"></div>')
    rows.append('<div class="head b" style="grid-column:span 4">DECK B</div>')
    rows.append('<div class="head right">MASTER</div>')

    for row in range(8):
        zones = {0: (T["zone_fx"], EFFECT_ROWS),
                 EFFECT_ROWS: (T["zone_pal"], PALETTE_ROWS),
                 EFFECT_ROWS + PALETTE_ROWS: (T["zone_col"], COLOR_ROWS)}
        if row in zones:
            zone, span = zones[row]
            rows.append(f'<div class="zone" style="grid-row:span {span}">{zone}</div>')
        for column in range(8):
            if column == 4:
                rows.append('<div class="gap"></div>')
            note = pad_note(row, column)
            binding = mapping.get(Control(NOTE, 0, note))
            style = ""
            if binding is None:
                kind = ""
            elif binding.action == "deck.effect":
                kind = "fx"
            elif binding.action == "deck.palette":
                kind = "pal"
            else:
                kind = "color"
                style = _color_style(binding.args.get("rgb", (1, 1, 1)))
            rows.append(_cell(f"{note}", label_for(binding), kind, style))
        scene = SCENE_NOTES[row]
        rows.append(_cell(f"{scene}", label_for(mapping.get(Control(NOTE, 0, scene))), "live"))

    rows.append('<div class="spacer"></div>')
    for index, note in enumerate(TRACK_NOTES):
        if index == 4:
            rows.append('<div class="gap"></div>')
        rows.append(_cell(f"{note}", label_for(mapping.get(Control(NOTE, 0, note))), "live"))
    rows.append(_cell(f"{SHIFT_NOTE}", "Shift", "live"))

    rows.append('<div class="spacer"></div>')
    for index, cc in enumerate(FADER_CC[:8]):
        if index == 4:
            rows.append('<div class="gap"></div>')
        rows.append(_cell(f"CC {cc}", label_for(mapping.get(Control(CC, 0, cc))), "fader"))
    last = FADER_CC[8]
    rows.append(_cell(f"CC {last}", label_for(mapping.get(Control(CC, 0, last))), "fader live"))

    return f"""<title>{T["title"]}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="sheet">
<header>
  <h1>{T["title"]}</h1>
  <span class="sub">leddeck · {T["port"]} <code>{escape(mapping.port)}</code> · {T["channel"]} ·
  mapping <code>{escape(mapping.name)}.json</code></span>
</header>

<div class="panel">
{chr(10).join(rows)}
</div>

<div class="legend">
{T["legend"]}
</div>

<footer>{T["footer"]}</footer>
</div>
"""


def write_sheet(mapping: Mapping, path: Path, profile) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html(mapping, profile))
    return path
