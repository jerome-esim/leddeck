"""Traduction de l'interface.

Le français est la langue source : les chaînes du code sont les clés, et
l'anglais est une table de correspondance. Une clé absente de la table ressort
telle quelle, donc oublier une traduction dégrade l'affichage sans rien casser.

Les noms d'effets, de palettes et de paramètres servent aussi de clés dans les
profils et le mapping MIDI : seul leur affichage est traduit, jamais la valeur
enregistrée.
"""

from __future__ import annotations

LANGUAGES = {"fr": "Français", "en": "English"}

_lang = "fr"

EN: dict[str, str] = {
    # --- navigation et fenêtre ---
    "Live": "Live",
    "Installation": "Setup",
    "Effets du contrôleur…": "Controller effects…",
    "les bandeaux suivent les motifs d'installation": "strips follow the setup patterns",
    "SORTIE  ·  mélange des deux decks": "OUTPUT  ·  mix of both decks",

    # --- decks ---
    "Effets": "Effects",
    "Palettes": "Palettes",
    "Presets": "Presets",
    "Perso": "Custom",
    "Réglages · {}": "Settings · {}",
    "Interpolation (dégradé entre les couleurs)": "Interpolation (fade between colours)",
    "Ajouter une couleur": "Add a colour",
    "Supprimer la derniere couleur": "Remove the last colour",
    "Couleur {}": "Colour {}",

    # --- master ---
    "Crossfader": "Crossfader",
    "Automatique": "Automatic",
    "Master": "Master",
    "Tempo": "Tempo",
    "Luminosité": "Brightness",
    "Vitesse globale   ·   à fond à gauche = arrêt": "Global speed   ·   full left = freeze",
    "Fréquence du strobe": "Strobe rate",
    "Live   ·   Maj + raccourci = verrou": "Live   ·   Shift + shortcut = latch",
    "Réglages de l'électrique": "Electric settings",
    "Crossfade auto, calé sur le tempo": "Auto crossfade, locked to tempo",
    "Toutes les (pulsations)": "Every (beats)",
    "Transition (pulsations)": "Transition (beats)",
    "Strobe calé sur le beat": "Strobe locked to the beat",
    "Son réactif": "Audio reactive",
    "Coupe la réaction au son de tous les effets": "Turns audio reaction off for every effect",
    "On / Off": "On / Off",
    "Momentané": "Momentary",
    "Maintenir — raccourci : {}": "Hold — shortcut: {}",
    "Le tempo détecté est deux fois trop rapide": "The detected tempo is twice too fast",
    "Le tempo détecté est deux fois trop lent": "The detected tempo is twice too slow",
    "Donner le tempo à la main": "Tap the tempo by hand",
    "Entrée audio": "Audio input",
    "Réglages de l'entrée audio": "Audio input settings",
    "Fermer": "Close",

    # --- fonctions live ---
    "Blackout": "Blackout",
    "Strobe": "Strobe",
    "Flash": "Flash",
    "Électrique": "Electric",

    # --- page installation ---
    "Sorties WLED": "WLED outputs",
    "Patch — quelle sortie sur quelle ligne": "Patch — which output on which row",
    "Vérification": "Check",
    "Scanner le réseau": "Scan the network",
    "Préparer les ESP": "Prepare the ESPs",
    "Configure chaque WLED pour le club : affichage du flux à fond même éteint,\n"
    "pas de gamma WLED, démarrage éteint. À faire une fois par ESP.":
        "Configures every WLED for the venue: show the stream at full brightness even\n"
        "when off, no WLED gamma, powered off at boot. Once per ESP.",
    "Scan auto + patch": "Auto scan + patch",
    "(réseaux locaux)": "(local networks)",
    "Appliquer": "Apply",
    "Patch automatique (#1 → ligne 1)": "Automatic patch (#1 → row 1)",
    "Enregistrer le profil": "Save the profile",
    "LED par bandeau": "LEDs per strip",
    "bandeaux": "strips",
    "en cours :": "running:",
    "éteint": "off",
    "Test": "Test",
    "Faire courir un point sur cette ligne": "Run a dot along this row",
    "Config": "Config",
    "Ouvrir http://{} dans le navigateur": "Open http://{} in the browser",
    "Clignoter": "Blink",
    "Faire clignoter ce bandeau pour le repérer": "Blink this strip to find it",
    "recherche en cours…": "scanning…",
    "configuration en cours…": "configuring…",
    "modifications non enregistrées": "unsaved changes",
    "enregistré dans {}": "saved to {}",
    "mis à jour : ": "updated: ",
    "{}/{} en ligne": "{}/{} online",
    "N°": "No.",
    "Nom": "Name",
    "IP": "IP",
    "LED": "LEDs",
    "Signal": "Signal",
    "Version": "Version",
    "État": "State",
    "Ligne": "Row",
    "Ligne {}": "Row {}",
    "Identifier": "Identify",
    "Chaque bandeau affiche son numéro de sortie": "Every strip displays its output number",
    "Numéro de ligne": "Row number",
    "Chaque ligne affiche son numéro dans la matrice":
        "Every row displays its number in the matrix",
    "Dégradé de la ligne 1 à la ligne N": "Gradient from row 1 to row N",
    "Balayage": "Sweep",
    "Un point traverse toutes les lignes, même sens attendu":
        "A dot crosses every row, all expected to travel the same way",
    "Chenillard": "Chase",
    "Un point par ligne, décalé": "One dot per row, offset",
    "Éteindre": "Turn off",
    "Tout noir": "All black",
    "Sortie": "Output",
    "Inversée": "Reversed",
    "Décalage": "Offset",

    # --- choix des pads ---
    "Effets du contrôleur": "Controller effects",
    "{} effets, {} pads par deck.\nChoisis lesquels sont sous les doigts, et dans quel ordre.":
        "{} effects, {} pads per deck.\nPick which ones sit under your fingers, and in what order.",
    "Ordre du catalogue": "Catalogue order",

    "fondu": "fade",
    "addition": "add",
    "maximum": "maximum",

    # --- états et messages ---
    "espace": "space",
    "en ligne": "online",
    "lent": "slow",
    "hors ligne": "offline",
    "ENTREE SATUREE": "INPUT CLIPPING",
    "entrée perdue — reconnexion…": "input lost — reconnecting…",
    "{}  ·  repli, « {} » absente": "{}  ·  fallback, « {} » missing",
    "{} · voies {}": "{} · channels {}",
    "Cherche les nouveaux WLED toutes les {:g} s,\n"
    "les ajoute, les patche sur la première ligne libre et enregistre.":
        "Looks for new WLED devices every {:g} s, adds them, patches them to the\n"
        "first free row and saves.",

    # --- barre d'état ---
    "{} sortie(s)": "{} output(s)",
    "{} erreur(s)": "{} error(s)",
    "sans son": "no audio",
    "son : {}": "audio: {}",
    "mém {:.0f} Mo": "mem {:.0f} MB",

    # --- noms d'effets ---
    "Arc-en-ciel": "Rainbow",
    "Blob": "Blob",
    "Ciel étoilé": "Starfield",
    "Éclairs": "Lightning",
    "Fixe": "Solid",
    "Forme": "Shape",
    "Ligne": "Line",
    "Néon": "Neon",
    "Noir": "Black",
    "Pluie": "Rain",
    "Pulse": "Pulse",
    "Serpent": "Snake",
    "Tubes": "Tubes",
    "Vague": "Wave",
    "Vortex": "Vortex",

    # --- noms de palettes ---
    "Perso (RGB)": "Custom (RGB)",
    "Club": "Club",
    "Feu": "Fire",
    "Braise": "Ember",
    "Océan": "Ocean",
    "Glace": "Ice",
    "Coucher": "Sunset",
    "Menthe": "Mint",
    "Violet": "Purple",
    "Blanc": "White",
    "Rouge": "Red",

    # --- noms de paramètres ---
    "amorçage": "strike",
    "blancheur": "whiteness",
    "bords doux": "soft edges",
    "bras": "arms",
    "centre X": "centre X",
    "centre Y": "centre Y",
    "couleur": "colour",
    "densité": "density",
    "direction": "direction",
    "douceur": "softness",
    "durée": "duration",
    "décalage": "offset",
    "déformation": "warp",
    "extinction": "fade out",
    "flashs": "flashes",
    "fondu": "fade",
    "hasard": "random",
    "indépendant": "independent",
    "intensité": "intensity",
    "longueur": "length",
    "nombre": "count",
    "organique": "organic",
    "pause": "pause",
    "pluie": "rain",
    "pulsation": "pulse",
    "rebond": "bounce",
    "retombée": "decay",
    "rotation": "rotation",
    "réactivité": "reactivity",
    "répartition": "spread",
    "résiduel": "residual",
    "sens": "direction",
    "serrage": "tightness",
    "son": "audio",
    "sur le beat": "on the beat",
    "taille": "size",
    "traînée": "trail",
    "tube entier": "whole tube",
    "tubes": "tubes",
    "variation": "variation",
    "vitesse": "speed",
    "échelle": "scale",
    "électrodes": "electrodes",
    "épaisseur": "thickness",
    "étalement": "spread",

    # --- couleurs fixes ---
    "Orange": "Orange",
    "Jaune": "Yellow",
    "Vert": "Green",
    "Cyan": "Cyan",
    "Bleu": "Blue",
    "Rose": "Pink",

    # --- ligne de commande : aide ---
    "profil de salle (defaut : default)": "room profile (default: default)",
    "creer / afficher un profil de salle": "create / show a room profile",
    "creer un profil": "create a profile",
    "LED par bandeau (L)": "LEDs per strip (L)",
    "nombre de bandeaux (N)": "number of strips (N)",
    "creer N sorties d'office": "create N outputs right away",
    "IP de la premiere sortie, ex. 192.168.0.101": "IP of the first output, e.g. 192.168.0.101",
    "afficher le profil": "show the profile",
    "chercher les WLED sur le reseau": "look for WLED devices on the network",
    "sous-reseau a balayer, ex. 192.168.0.0/24": "subnet to sweep, e.g. 192.168.0.0/24",
    "ajouter les WLED trouves au profil": "add the WLED devices found to the profile",
    "patcher #1->ligne 1, #2->ligne 2…": "patch #1->row 1, #2->row 2…",
    "motif de test sur la matrice": "test pattern on the matrix",
    "chaque bandeau affiche son numero": "every strip displays its number",
    "faire clignoter une sortie": "blink one output",
    "contrôleur MIDI": "MIDI controller",
    "lister les ports MIDI": "list the MIDI ports",
    "afficher les messages reçus": "show the messages received",
    "fragment du nom du port": "part of the port name",
    "fiche de mapping imprimable (HTML)": "printable mapping sheet (HTML)",
    "langue des messages (defaut : celle du profil)":
        "language of the messages (default: the profile's)",
    "effets et palettes": "effects and palettes",
    "lister effets et palettes": "list effects and palettes",
    "jouer un effet sur les bandeaux": "play an effect on the strips",
    "regler un parametre, ex. --set vitesse=2.5": "set a parameter, e.g. --set vitesse=2.5",
    "entree audio": "audio input",
    "écran d'installation : découverte, identification, patch":
        "setup screen: discovery, identification, patch",
    "ouvrir l'interface (apercu + effets + palettes)":
        "open the interface (preview + effects + palettes)",
    "mapping MIDI à charger": "MIDI mapping to load",
    "entree audio : peripheriques, moniteur, test LED":
        "audio input: devices, monitor, LED test",
    "lister les entrees audio": "list the audio inputs",
    "bandes / BPM / beats dans le terminal": "bands / BPM / beats in the terminal",
    "index ou nom partiel de l'entree": "index or partial name of the input",
    "voies à mélanger, ex. 3,4": "channels to mix, e.g. 3,4",
    "niveau de chaque entrée de la carte": "level of every input on the card",
    "spectre sur les bandeaux + flash sur le beat":
        "spectrum on the strips + flash on the beat",
    "intensite du flash sur le beat": "intensity of the flash on the beat",
    "spectre sur la longueur, ou couleur unie pulsee sur le beat":
        "spectrum along the length, or a solid colour pulsed on the beat",
    "couleur du mode pulse": "colour of the pulse mode",
    "duree de retombee, en fraction de beat (0,25 = un quart de beat)":
        "decay time, as a fraction of a beat (0.25 = a quarter of a beat)",
    "niveau residuel entre deux beats": "residual level between two beats",
    "motif de diagnostic sur une sortie": "diagnostic pattern on one output",
    "numéro de sortie": "output number",
    "forcer un nombre de LED différent de celui du profil":
        "force a LED count different from the profile's",
    "configurer les ESP pour le club": "configure the ESPs for the venue",
    "afficher sans rien modifier": "show without changing anything",
    "tout eteindre (noir DDP + extinction WLED)":
        "turn everything off (DDP black + WLED powered off)",
    "envoyer du noir sans eteindre WLED (il se rallumera seul apres 2,5 s)":
        "send black without powering WLED off (it comes back on its own after 2.5 s)",
    "rallumer les WLED (apres un off)": "power the WLED devices back on (after an off)",

    # --- ligne de commande : messages ---
    "  patch :": "  patch:",
    "Entrées MIDI :": "MIDI inputs:",
    "Sorties MIDI :": "MIDI outputs:",
    "Effets :": "Effects:",
    "\nPalettes :": "\nPalettes:",
    "Envoyez du son, la voie qui bouge est la bonne. Ctrl-C pour arrêter.\n":
        "Send some sound; the channel that moves is the right one. Ctrl-C to stop.\n",
    "bandes / niveau / BPM — Ctrl-C pour arreter\n":
        "bands / level / BPM — Ctrl-C to stop\n",
    "À vérifier sur le matériel : les tubes doivent s'allumer en émission et redevenir noirs 2,5 s après l'arrêt.":
        "To check on the hardware: the tubes must light while streaming and go dark again 2.5 s after it stops.",
    "Aucun WLED trouve. Verifier le reseau, et l'autorisation « Reseau local » (Reglages > Confidentialite et securite > Reseau local).":
        "No WLED found. Check the network, and the \u00ab Local network \u00bb permission (Settings > Privacy & Security > Local Network).",
    "Aucune entrée MIDI correspondante.": "No matching MIDI input.",
    "\n\nNiveaux relevés :": "\n\nLevels measured:",
    "\n  /!\\ rien ne rentre depuis 4 s — autorisation micro ? (Reglages > Confidentialite et securite > Microphone)":
        "\n  /!\\ nothing coming in for 4 s — microphone permission? (Settings > Privacy & Security > Microphone)",
    "  -> l'entree sature : baisser le volume ou eloigner le micro. La distorsion cree de fausses attaques.":
        "  -> the input is clipping: lower the volume or move the microphone away. Distortion creates false onsets.",
    "  -> l'entree sature : baisser le volume ou eloigner le micro.":
        "  -> the input is clipping: lower the volume or move the microphone away.",
    "  {} frames, {:.1f} fps, {} retard(s), {} paquets, {} erreur(s) reseau":
        "  {} frames, {:.1f} fps, {} late, {} packets, {} network error(s)",
    "Profil ecrit : {}": "Profile written: {}",
    "Profil '{}' — matrice {} LED x {} bandeaux @ {} fps (gamma {}, luminosite {:g})":
        "Profile '{}' — matrix {} LEDs x {} strips @ {} fps (gamma {}, brightness {:g})",
    "  {} sortie(s) :": "  {} output(s):",
    "Recherche des WLED{}…": "Looking for WLED devices{}…",
    "{} WLED trouve(s) :": "{} WLED device(s) found:",
    "Écoute de {} port(s) — actionnez les commandes ({}) :":
        "Listening on {} port(s) — move the controls ({}):",
    "\n{} commande(s) distincte(s), {} message(s).":
        "\n{} distinct control(s), {} message(s).",
    "Fiche écrite : {}  ({} assignations)": "Sheet written: {}  ({} bindings)",
    "Installation — profil '{}', matrice {} x {}, {} sortie(s)":
        "Setup — profile '{}', matrix {} x {}, {} output(s)",
    "Interface — profil '{}', matrice {} x {}, {} sortie(s)":
        "Interface — profile '{}', matrix {} x {}, {} output(s)",
    "Entree audio : {} — {} Hz, {} voie(s), melange des voies {}":
        "Audio input: {} — {} Hz, {} channel(s), mixing channels {}",
    "{} — {} entrée(s), {} Hz": "{} — {} input(s), {} Hz",
    "\n{} blocs analyses, {} depassement(s), {} beats, {} bloc(s) satures ({:.1f} %).":
        "\n{} blocks analysed, {} overrun(s), {} beats, {} clipped block(s) ({:.1f} %).",
    "\n{} frames, {:.1f} fps, {} erreur(s) reseau, {} depassement(s) audio, {} bloc(s) satures ({:.1f} %).":
        "\n{} frames, {:.1f} fps, {} network error(s), {} audio overrun(s), {} clipped block(s) ({:.1f} %).",
    "{} {} sortie(s) — profil '{}'\n": "{} {} output(s) — profile '{}'\n",
    "  -> lancer « leddeck prepare » (sans --check) pour les corriger.":
        "  -> run \u00ab leddeck prepare \u00bb (without --check) to fix them.",
    "Toutes les sorties sont correctement configurées.": "Every output is correctly configured.",
    "Noir envoye en DDP sur {} sortie(s).": "Black sent over DDP to {} output(s).",
    "  (les sorties muettes seront rallumees par leur propre etat : verifier leur IP)":
        "  (silent outputs will be relit by their own state: check their IP)",
    "WLED rallume (luminosite au max) sur {}/{} sortie(s).":
        "WLED powered back on (brightness at max) on {}/{} output(s).",
    "  ({}/{} sortie(s) rallumee(s) — les autres n'ont pas repondu sur HTTP)":
        "  ({}/{} output(s) powered back on — the others did not answer over HTTP)",
    "Aucune sortie utilisable dans le profil '{}'.\n  -> leddeck discover --add   (ou)   leddeck profile init --outputs 16 --ip-base 192.168.0.101":
        "No usable output in profile '{}'.\n  -> leddeck discover --add   (or)   leddeck profile init --outputs 16 --ip-base 192.168.0.101",
    "    #{:<3} {:<16} {:<16} {:>4} LED  port {}{}":
        "    #{:<3} {:<16} {:<16} {:>4} LEDs port {}{}",
    "    ligne {:>2} <- {}{}": "    row {:>2} <- {}{}",
    "  {:<16} {:<18} {:>4} LED  v{:<10} rssi {:>4} dBm  {}{}":
        "  {:<16} {:<18} {:>4} LEDs v{:<10} rssi {:>4} dBm  {}{}",
    "{} sortie(s) ajoutee(s) au profil '{}'.": "{} output(s) added to profile '{}'.",
    "Sortie #{} inconnue dans le profil '{}'.": "Output #{} unknown in profile '{}'.",
    "  {:<14} {} couleurs, {}": "  {:<14} {} colours, {}",
    "cyclique": "cyclic",
    "produire aussi le PDF (via Chrome, A4 paysage)":
        "also produce the PDF (through Chrome, A4 landscape)",
    "PDF écrit : {}": "PDF written: {}",
    "PDF non produit : {}": "PDF not produced: {}",
    "aucun navigateur Chrome / Chromium / Edge trouve pour produire le PDF ; "
    "la fiche HTML reste imprimable depuis le navigateur (Cmd-P)":
        "no Chrome / Chromium / Edge browser found to produce the PDF; the HTML sheet "
        "is still printable from the browser (Cmd-P)",
    "tous les 8 beats": "every 8 beats",
    "tous les 4 beats": "every 4 beats",
    "tous les 2 beats": "every 2 beats",
    "chaque beat": "every beat",
    "2 par beat": "2 per beat",
    "4 par beat": "4 per beat",
    "8 par beat": "8 per beat",
    "peripherique audio introuvable : {!r}": "audio device not found: {!r}",
    "  (repli)": "  (fallback)",
    "effet inconnu : {!r} (connus : {})": "unknown effect: {!r} (known: {})",
    "palette inconnue : {!r} (connues : {})": "unknown palette: {!r} (known: {})",
    "orientee": "directional",
    "[{}] {} — {} canal/aux, {:.0f} Hz, latence {:.0f} ms{}":
        "[{}] {} — {} channel(s), {:.0f} Hz, latency {:.0f} ms{}",
    "\nPour l'utiliser : --channels {}": "\nTo use it: --channels {}",
    "Sortie #{} inconnue. Connues : {}": "Output #{} unknown. Known: {}",
    "Aucune sortie dans le profil '{}'.": "No output in profile '{}'.",
    "{} sortie(s) injoignable(s).": "{} output(s) unreachable.",
    "{} sortie(s) {} : {}": "{} output(s) {}: {}",
    "parametre inconnu pour {} : {!r} (connus : {})":
        "unknown parameter for {}: {!r} (known: {})",
    "   voie {:<3} {:6.1f} dBFS": "   channel {:<3} {:6.1f} dBFS",
    "  {:<22} avant : {}": "  {:<22} before: {}",
    "  {:<22} après : {}": "  {:<22} after: {}",
    "  {:<22} {:<24} valeur {}": "  {:<22} {:<24} value {}",
    "  (son indisponible : {!r})": "  (sound unavailable: {!r})",
    "[engine] erreur de rendu : {!r}": "[engine] render error: {!r}",
    "[midi] erreur sur {} : {!r}": "[midi] error on {}: {!r}",
    "[midi] aucun contrôleur trouvé": "[midi] no controller found",
    "[midi] {} — mapping « {} », {} assignation(s)":
        "[midi] {} — mapping \u00ab {} \u00bb, {} binding(s)",
    "[midi] indisponible : {!r}": "[midi] unavailable: {!r}",
    "[profil] enregistrement impossible : {!r}": "[profile] could not save: {!r}",
    "[audio] entrée rétablie : {}": "[audio] input restored: {}",
    "[audio] « {} » détectée, bascule": "[audio] \u00ab {} \u00bb detected, switching",
    "[audio] aucune entrée disponible : {}": "[audio] no input available: {}",
    "[audio] « {} » indisponible : {}": "[audio] \u00ab {} \u00bb unavailable: {}",
}


def set_language(code: str) -> None:
    global _lang
    _lang = code if code in LANGUAGES else "fr"


def language() -> str:
    return _lang


def tr(text: str) -> str:
    """Traduit une chaîne source française, ou la rend telle quelle."""
    if _lang == "fr":
        return text
    return EN.get(text, text)
