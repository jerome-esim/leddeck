# Plan — Appli de contrôle LED pour club (WLED / DDP)

## 1. Objectif

Appli de bureau **multiplateforme, cible principale macOS** (fonctionne aussi sous Windows) pour piloter des bandeaux LED WLED en live dans un club :
- 2 decks (A / B) : effet + palette de couleurs + réglages, crossfader entre les deux
- Transition manuelle (slider) ou automatique sur les beats
- Synchro musique via entrée audio (micro ou ligne)
- Pilotage complet au contrôleur MIDI (sliders + boutons)
- Mode installation : identifier et réordonner les bandeaux sans contrainte de câblage

## 2. Concepts clés

### Matrice
- Les effets dessinent sur une **matrice L × N** : `L` = LED par bandeau (colonnes), `N` = nombre de bandeaux (lignes).
- Par défaut 250 × 16, **paramétrable** dans les réglages.

### Sorties (le matériel)
- Une **sortie** = un ESP WLED : IP, nom, nombre de LED, port DDP (4048), actif/inactif.
- Liste paramétrable (ajout manuel ou détection automatique sur le réseau).
- Chaque sortie a un **numéro d'identification** (#1, #2…) fixe, indépendant de sa place dans la matrice.

### Patch (sortie → ligne de la matrice)
- Chaque ligne de la matrice reçoit une sortie : `ligne 3 ← sortie #11 (inversée)`.
- Options par ligne : **inverser le sens**, décalage (offset) si besoin.
- Si le bandeau a plus/moins de LED que `L` : on tronque / on complète en noir.
- Une sortie non patchée reste noire, une ligne sans sortie est simplement ignorée.

→ On installe les bandeaux au hasard, et on remet l'ordre **dans l'appli**, pas dans le câblage.

## 3. Mode installation

1. **Découverte** : scan du réseau (requête `http://<ip>/json/info` en parallèle sur le sous-réseau + mDNS `_wled._tcp`).
   Liste des WLED trouvés : nom, IP, MAC, nombre de LED, version, signal WiFi. Ajout manuel possible.
2. **Identification sur les bandeaux** : chaque bandeau affiche physiquement son numéro :
   - 1re LED(s) **vertes** = début du bandeau, dernières LED **rouges** = fin → on voit le sens
   - entre les deux, **N blocs blancs** séparés par du noir = numéro de la sortie (ex. 7 blocs = #7)
   - option « clignoter » : clic sur une sortie dans l'appli → le bandeau correspondant flashe
3. **Patch visuel** : la matrice est affichée en N lignes ; on glisse-dépose chaque sortie sur sa ligne,
   bouton ⇄ pour inverser le sens, bouton « test » qui fait défiler un point sur la ligne.
4. **Vérification** : motifs de contrôle sur la matrice finale
   - numéro de **ligne** (au lieu du numéro de sortie)
   - dégradé arc-en-ciel ligne 1 → ligne N
   - point qui balaie gauche → droite sur toutes les lignes (tout doit aller dans le même sens)
5. **Profils de salle** : sauvegarde (sorties + patch + taille de matrice) dans un JSON, plusieurs profils possibles.

## 4. Architecture

```
 Entrée audio ──► Analyse (FFT, basses/médiums/aigus, beat, BPM, gain auto)
                                  │
 Interface Qt ──┐                 ▼
 MIDI (learn) ──┼──► BUS DE PARAMÈTRES ◄── Auto-mix (beats)
                                  │
                                  ▼
        MOTEUR (thread dédié, cadence fixe 40 fps)
        Deck A (effet + palette + params) ─┐
                                           ├─► Mixer ─► Master (lumi, strobe, blackout)
        Deck B (effet + palette + params) ─┘                │
                                                            ▼  matrice L × N
                                  Patch (réordonne, inverse, gamma) 
                                                            ▼
                                  Envoi DDP ──► N sorties WLED
```

- **Bus de paramètres** : chaque réglage a un identifiant et une plage ; UI, MIDI et auto-mix écrivent au même endroit.
- **Moteur indépendant de l'UI** : si l'interface rame, les LED ne saccadent pas.
- **Palettes séparées des effets** : un effet pioche ses couleurs dans la palette du deck → n'importe quel effet se recolore instantanément.

### Interface d'un effet

```python
class Effect:
    name = "Serpent"
    params = {"vitesse": (0.1, 5.0, 1.0), "longueur": (1, 100, 20)}  # min, max, défaut

    def render(self, t, dt, audio, palette, p) -> np.ndarray:
        """Retourne un tableau (N, L, 3) de floats 0..1."""
```

## 5. Stack technique

| Brique | Choix |
|---|---|
| Langage | Python 3.12 |
| Calcul | numpy |
| Interface | PySide6 (Qt) |
| Audio | sounddevice (+ numpy FFT) |
| MIDI | mido + python-rtmidi |
| Réseau | UDP / DDP (socket standard), requests pour l'API JSON WLED |
| Config | fichiers JSON |
| Distribution | PyInstaller → `.app` (macOS) / `.exe` (Windows) |
| Environnement | `uv` + `pyproject.toml` (Python 3.12 épinglé, pas de `requirements.txt`) |

## 6. Arborescence

```
LED/
  PLAN.md
  pyproject.toml            ✅ (uv ; pas de requirements.txt)
  leddeck/
    main.py                 ✅ CLI (profile / discover / test / identify / blink / off)
    core/      config.py ✅  engine.py ✅  params.py ✅  palette.py ✅  mixer.py ✅
    output/    ddp.py ✅  wled.py ✅ (découverte, état)  patch.py ✅
    audio/     input.py ✅  analysis.py ✅
    midi/      midi.py ✅  actions.py ✅  mapping.py ✅  controller.py ✅
    effects/   base.py ✅  serpent.py ✅  etoiles.py ✅  vague.py ✅
               arcenciel.py ✅  pulse.py ✅  couleur.py ✅  tubes.py ✅
               electrique.py ✅  neon.py ✅        (chargés automatiquement)
    install/   patterns.py ✅ (motifs d'identification / test)
    ui/        main_window.py ✅  preview.py ✅  deck_panel.py ✅  master_panel.py ✅
               style.py ✅  thumbnails.py ✅  install_page.py ✅
               midi_page.py  settings_page.py
  profiles/    default.json ✅  club.json ✅  demo16.json ✅
  midi/        apcmini-mk2.json ✅ (mappings MIDI)
  presets/     (effets + palettes sauvegardés)
```

✅ = écrit et testé.

## 7. Effets prévus (première série)

| Effet | Description | Réaction au son |
|---|---|---|
| Serpent | un ou plusieurs serpents qui parcourent la matrice | vitesse / taille sur les basses |
| Ciel étoilé | scintillement aléatoire | pluie d'étoiles sur le beat |
| Vague / plasma | ondes de couleur | amplitude sur les basses |
| Arc-en-ciel | défilement de la palette | — |
| Pulse | flash global | sur chaque beat |
| Spectre | 16 lignes = 16 bandes de fréquence | spectre en direct |
| Pluie | gouttes qui tombent le long des bandeaux | densité sur les aigus |
| Feu | flammes | intensité sur les basses |
| Couleur unie / Strobe | utilitaires | strobe calé sur le beat |

## 8. Étapes

| # | Étape | Terminé quand… |
|---|---|---|
| 0 | ✅ **Préparation** : Python, dépendances, vérif config WLED (DDP actif, IP fixes) | l'environnement tourne |
| 1 | ✅ **Cœur + sortie** : config JSON, envoi DDP, patch, boucle 40 fps, motif de test en ligne de commande | ✅ validé sur 16 récepteurs simulés **et sur 3 ESP réels** (40 fps, sans saccade) |
| 2 | 🔶 **Mode installation** : découverte, identification sur bandeau, patch, inversion, profils | écran complet ✅ ; **gestion des profils** et validation sur les 16 bandeaux à faire |
| 3 | ✅ **Effets + palettes** : moteur d'effets, 5 premiers effets, aperçu de la matrice dans l'appli | ✅ 5 effets à 40 fps sur les 3 tubes, recoloration instantanée par la palette |
| 4 | ✅ **Audio** : entrée micro/ligne, FFT, gain auto, beat, BPM, tap tempo | ✅ BPM verrouillé de 75 à 174 BPM (erreur < 0,3 %, jitter < 6 ms), validé au micro |
| 5 | ✅ **Interface Live** : 2 decks, listes d'effets, palettes, crossfader, master | ✅ deux decks mixés à la souris, 0,41 ms/frame dans le pire cas sur 16 × 250 |
| 6 | 🔶 **MIDI** : MIDI learn, soft takeover, retour LED sur le contrôleur | mapping complet, soft takeover et retour LED ✅ ; **interface de MIDI learn à faire** |
| 7 | **Auto-mix + presets** : transition tous les X beats, rotation d'effets, presets sur pads | l'appli tourne seule toute une soirée |
| 8 | ⏳ **Fiabilité club** : `.app`, reprise du dernier état, ESP hors ligne signalé, blackout d'urgence, logs | test de 6 h sans incident |

## 8 bis. Ce qui tourne aujourd'hui (étapes 0 et 1)

### Environnement
`uv sync` installe tout (Python 3.12.13, numpy 2.5, PySide6 6.11, sounddevice, mido + python-rtmidi, requests, zeroconf).
Vérifié : audio et MIDI vus par le système.

### Modules écrits
- `core/config.py` — profil de salle : matrice (L × N), sorties, patch ; JSON dans `profiles/`.
- `output/ddp.py` — émetteur DDP/UDP : en-tête 10 octets (version 1, type `0x0B` RGB24, destination 1),
  numéro de séquence 1-15, bit PUSH sur le dernier paquet, découpe à 1440 octets.
  250 LED RGB = 750 octets → **un seul paquet par bandeau et par frame**.
  Socket non bloquant : un ESP absent ne fait jamais tomber le moteur (compteur d'erreurs).
- `output/patch.py` — matrice (N, L, 3) float 0..1 → un buffer uint8 par sortie :
  offset, inversion, troncature / complément en noir, gamma (LUT 256) et luminosité master.
  `send_direct()` court-circuite le patch pour adresser les bandeaux par numéro (mode installation).
- `core/engine.py` — boucle 40 fps dans un thread dédié, cadence sans dérive, pas de rattrapage en
  rafale si retard, une exception de rendu n'arrête pas les LED ; stats (fps réel, retards, ms de rendu).
- `output/wled.py` — découverte : balayage du sous-réseau (`/json/info`, 128 threads) + mDNS `_wled._tcp`,
  nom / IP / MAC / nb de LED / version / RSSI, avertissement si version < 0.13 (DDP).
- `install/patterns.py` — motifs : `sweep`, `rainbow`, `rows`, `chase`, `flow`, couleurs unies, `off`,
  plus l'identification bandeau (début vert, fin rouge, N blocs blancs = numéro) et le clignotement.

### Uniformiser les ESP avant d'émettre
Deux ESP recevant exactement les mêmes octets peuvent rendre différemment : le curseur de
**luminosité de WLED** (`bri`) s'applique par-dessus le flux temps réel, sauf si l'option
« Force max brightness » est cochée — et elle ne l'est pas forcément partout
(constaté : `WLED-01` bri 255 + maxbri, `WLED-10` bri 128 sans maxbri → blanc deux fois plus faible).
Plutôt que de dépendre d'un réglage par ESP, l'appli force `{"on": true, "bri": 255}` sur chaque
sortie avant d'émettre (`wake_all`). **La luminosité est gérée uniquement par le master de l'appli.**

### Extinction : le noir DDP ne suffit pas
2,5 s après le dernier paquet DDP, WLED **sort du mode temps réel et reprend son propre état**
(typiquement un effet interne allumé à fond). `leddeck off` fait donc les deux :
noir en DDP, puis `POST /json/state {"on": false}` sur chaque ESP.
Symétriquement, `test` / `identify` / `blink` **rallument** les ESP avant d'émettre (`on: true`),
et `leddeck on` le fait à la demande. C'est la base du blackout d'urgence de l'étape 8.

### Ligne de commande
```bash
uv run leddeck profile init --leds 250 --strips 16     # créer un profil de salle
uv run leddeck discover --add --autopatch              # trouver les WLED et les patcher 1→1
uv run leddeck profile show                            # sorties + patch
uv run leddeck test sweep --seconds 20                 # motif sur la matrice (sweep/rainbow/rows/chase/…)
uv run leddeck identify                                # chaque bandeau affiche son numéro
uv run leddeck blink 7                                 # faire clignoter la sortie #7
uv run leddeck off                                     # blackout : noir DDP + extinction des WLED
uv run leddeck on                                      # rallumer les WLED
```
`--profile <nom>` pour choisir un autre profil de salle.

### Tests effectués
- DDP : en-tête, fragmentation et bit PUSH vérifiés sur socket local.
- Chaîne complète sur **16 faux récepteurs DDP** : 40,4 fps mesurés, 0 retard, 0 erreur,
  750 octets par sortie et par frame, ligne inversée bien inversée, blackout en sortie.
- Moteur : 40,1 fps mesurés sur 2 s, rendu 0,07 ms par frame (matrice 16 × 250).
- **Validation matérielle (2026-09-22)** — profil `club`, matrice 250 × 3 :

  | Sortie | Nom | IP | RSSI |
  |---|---|---|---|
  | #1 | `WLED-01` | 192.168.8.10 | −43 dBm |
  | #2 | `WLED-10` | 192.168.8.19 | −43 dBm |
  | #3 | `WLED-15` | 192.168.8.24 | −58 dBm |

  Motifs `sweep`, `white`, `red`/`green`/`blue`, `flow`, `rainbow`, `chase`, `identify` envoyés
  sur les 3 sorties : **40 fps constants, 0 erreur réseau, aucune saccade visible**.
  L'ESP confirme `live = true`, `source = DDP`, ~40 fps de son côté.
  L'autorisation « Réseau local » de macOS est bien accordée.
  Tous les ESP sont en v0.15.3, 250 LED, un seul bus local.

  À noter : les tubes n'ont pas exactement le même blanc (teinte, pas luminosité) — différence
  physique de LED, jugée acceptable. Si besoin un jour : balance des blancs par sortie dans le patch.

## 8 quinquies. Étape 5 — Interface live (terminée le 2026-09-22)

### Decks et mixer (`core/mixer.py`)
- Chaque deck a ses **propres instances d'effets** : le même effet peut tourner des deux côtés
  avec des réglages et un état différents.
- **Les deux decks sont toujours calculés**, même crossfader à fond d'un côté. Ne pas rendre le
  deck masqué le figerait, et il sauterait au moment de le ramener. Le coût le permet.
- Trois modes de mélange :

  | Mode | Poids (A, B) | Usage |
  |---|---|---|
  | `fondu` | (1−x, x) | crossfade classique |
  | `addition` | (min(1, 2−2x), min(1, 2x)) puis écrêtage | pas de creux au centre, ça écrête |
  | `maximum` | mêmes poids, puis `max` | pas de creux, sans écrêtage — couleurs propres |

- **Vitesse globale** : le mixer tient son propre temps, avancé de `dt × vitesse`. Les effets ne
  savent pas que le temps est étiré. Course **géométrique** ×0,1 → ×4 (une course linéaire rendrait
  la moitié basse inutilisable), et les **3 % du bas valent zéro : arrêt net**.
  À l'arrêt, on coupe aussi l'audio des effets — sinon un effet calé sur le beat continuerait de
  bouger alors qu'on a demandé l'arrêt. Le crossfader et le master, eux, restent vivants : on peut
  fondre entre deux images figées et envoyer un strobe par-dessus.
  La conversion de course est **partagée** entre l'interface et le MIDI : le fader de l'APC et le
  curseur à l'écran ont exactement le même comportement.

### Master — deux boutons par fonction
Strobe, **électrique**, flash et blackout ont chacun **un verrou (on/off) et un appui momentané**
(classe `Hold`, active si l'un *ou* l'autre l'est) : en club on veut les deux gestes pour la même
fonction. Strobe réglable en fréquence, avec calage optionnel sur le beat.
La luminosité, elle, reste dans l'étage de sortie, avant le gamma.

**L'électrique est aussi une surcouche live**, posée par-dessus le mélange sans occuper un deck
(il reste disponible comme effet normal). Trois choix :
- superposition **en maximum** : la surcouche ajoute de la lumière, elle n'assombrit jamais ;
- ses réglages sont ceux de l'effet, exposés tels quels sous le master ;
- quand `blancheur` baisse, elle emprunte **la palette du deck dominant**, donc elle suit les
  couleurs de ce qui joue au lieu d'une teinte arbitraire.
Raccourci : **E** en momentané, **Maj+E** pour le verrou.

### Crossfade automatique sur le tempo (`AutoCross`)
Bascule d'un deck à l'autre toutes les N pulsations (1 à 64), transition de 0 (coupure franche)
à 16 pulsations. Deux choix :
- **sans musique, une horloge interne prend le relais** — l'auto-mix doit tourner même sans son ;
- **bouger le crossfader à la main coupe l'automatique** : reprendre la main doit être immédiat.

(C'est une avance sur l'étape 7, demandée en cours de route.)

### Palette perso par deck
Chaque deck a une palette `Perso (RGB)`, à **nombre de couleurs variable** (1 à 8, boutons `+`/`−`),
chacune éditée par le sélecteur du système. Le sélecteur reste ouvert et émet `currentColorChanged` :
**la couleur bouge sur les bandeaux pendant qu'on la choisit**. Elle est **à paliers par défaut**.
Toucher une couleur bascule le deck sur cette palette.

### Interface (`ui/`)
Thème sombre (`style.py`), une **couleur par deck** — cyan pour A, rose pour B — reprise par les
sélections, les curseurs et les deux moitiés du crossfader : on sait toujours de quel côté on agit.

**Trois aperçus** : chaque deck a le sien (préparer un effet sans l'envoyer), plus le grand en haut
qui montre le mélange réellement envoyé aux LED.

**Sélection visuelle** (`thumbnails.py`) : les effets sont des vignettes calculées en faisant tourner
l'effet sur une mini-matrice avec la palette du deck, les palettes sont leurs dégradés.
Deux détails appris en regardant le rendu :
- la vignette garde le **maximum des dernières images**, sinon un effet à éclats brefs
  (Électrique, Ciel étoilé, Pulse) tombe une fois sur deux sur une image noire ;
- la hauteur des grilles suit le **nombre réel de colonnes**, qui dépend de la largeur — une hauteur
  calculée à l'avance laissait des rangées vides.

**L'onglet est au niveau de l'effet** : `Effets` / `Réglages · <nom de l'effet>` — on choisit
l'effet, puis on passe à ses réglages, qui sont les siens. Les **palettes restent toujours visibles**
en dessous : en changer est un geste fréquent, il ne doit pas coûter un aller-retour d'onglet.
Cela raccourcit la colonne d'environ 200 px et rend les boutons live visibles d'emblée.
Raccourcis : **espace** = flash, **S** = strobe, **B** = blackout, en momentané ;
**Maj + la même touche** enclenche le verrou.

### Mise en page : trois pièges
- **Oscillation au redimensionnement** : recalculer la hauteur d'une grille dans son `resizeEvent`
  relance la mise en page, et la boucle largeur → colonnes → hauteur → ascenseur → largeur se met à
  osciller (spectaculaire en plein écran). Correctif : recalcul différé (`QTimer.singleShot(0, …)`)
  et changement de géométrie seulement si la valeur change vraiment.
- **Largeur en plein écran** : sans plafond, les colonnes s'étirent et les 9 vignettes s'alignent sur
  une seule rangée. Les panneaux sont plafonnés, le surplus va sur les côtés.
- **`QScrollArea` ne reprend pas les largeurs de son contenu** : il se laisse écraser sous le
  minimum et tronque le panneau. Il faut lui donner la largeur réellement exigée par la mise en page
  (`minimumSizeHint()`), pas un minimum fixé à la main.

### Deux pièges rencontrés
- **Police** : `-apple-system` est un mot-clé propre aux navigateurs, que Qt ne résout pas — la
  police n'était jamais appliquée et Qt perdait du temps au démarrage à chercher un remplaçant.
  On prend la police d'interface du système via `QFontDatabase`.
- **Arrêter l'interface** : `SIGINT` ne fait rien sur une application Qt (Python ne traite ses
  signaux qu'entre deux instructions, or la boucle d'événements reste dans du code C) — il faut
  `SIGTERM`. Et un motif `pkill -f` doit être choisi pour ne pas filtrer le shell qui l'exécute.

### Textes
L'interface est en français **accentué**. La recherche par nom (effets, palettes, réglages) est
insensible aux accents : la ligne de commande reste tapable en ASCII (`--set reactivite=0.8`).

### Mesures
Les 25 combinaisons d'effets A × B sur une matrice **16 × 250** : pire cas **0,41 ms par frame**,
soit 61× de marge sur le budget de 25 ms à 40 fps.

## 8 quater. Étape 3 — Effets, palettes et aperçu (terminée le 2026-09-22)

### Palettes (`core/palette.py`)
Un effet ne choisit **jamais** une couleur : il demande « la couleur à la position x » (0..1).
Changer de palette recolore donc n'importe quel effet sans le modifier — c'est le critère de
fin d'étape, vérifié sur les tubes (`Serpent` en `Feu` puis en `Ocean`).
Deux familles : **cycliques** (la dernière couleur rejoint la première — indispensable pour tout
ce qui défile) et **orientées** (sombre → clair, pour le feu ou les effets à intensité).

**Interpolation ou paliers** (`smooth`) : à `False`, on ne passe pas par les teintes intermédiaires,
chaque couleur occupe une tranche nette. C'est le comportement attendu d'une palette perso — deux
couleurs choisies doivent sortir telles quelles. Réglable par deck, sur la palette sélectionnée
(chaque deck possède ses **copies** des palettes : cocher la case d'un côté ne doit pas changer
l'autre). `Pulse` va plus loin : sur une palette à paliers il **saute de couleur en couleur**,
`variation` comptant alors en nombre de couleurs — d'où l'alternance exacte sur deux couleurs.
12 palettes fournies ; `presets/palettes/*.json` en ajoute sans toucher au code.

### Paramètres (`core/params.py`)
Chaque réglage a un identifiant, des bornes et un défaut, avec conversion depuis/vers 0..1 —
c'est ce que fournira un fader MIDI. C'est l'amorce du bus de paramètres de l'étape 6.

### Effets (`effects/`)
`Effect.render(t, dt, audio, palette, p) -> (N, L, 3)`, chargement automatique du dossier.
Deux règles apprises en chemin :
- un effet doit rester **pleinement visible sans son** (`audio` à None) — d'où l'aide `reactive()`,
  qui ignore la réactivité quand le micro est coupé plutôt que d'assombrir l'effet ;
- chaque effet garde son tampon et écrit dedans (`out=`) : pas d'allocation par frame.

| Effet | Réglages | Réaction au son |
|---|---|---|
| Serpent | vitesse, longueur, nombre, réactivité | accélère sur les basses |
| Ciel étoilé | densité, durée, pluie, teinte | pluie d'étoiles sur le beat |
| Vague | vitesse, échelle, réactivité, décalage | amplitude sur les basses |
| Arc-en-ciel | vitesse, étalement, décalage, réactivité | luminosité sur le niveau |
| Pulse | retombée, résiduel, couleur, variation | flash sur chaque beat |
| Couleur | couleur, étalement, décalage, réactivité | luminosité sur le niveau |
| Tubes | nombre, vitesse, hasard, fondu, sur le beat | change de tube à chaque beat |
| Électrique | densité, longueur, durée, blancheur, sur le beat | rafale d'éclats sur le beat |
| Néon | nombre, vitesse, amorçage, durée, extinction, électrodes, répartition | — |

`Tubes` allume des bandeaux entiers ; `hasard` est un **continuum** (0 = dans l'ordre, 1 = au sort,
entre les deux les deux gestes se mélangent) plutôt qu'un choix de mode.
`Électrique` n'est pas un strobe : les éclats ne prennent qu'un court morceau de tube, ce qui donne
le grésillement plutôt que le flash plein.
`Néon` reprend le modèle du **shader ISF « Néons qui chauffent »** utilisé dans MadMapper
(fourni par l'utilisateur) : `nombre` créneaux indépendants, chacun tirant un tube au hasard à
chaque cycle, et un cycle = amorçage → allumé → fondu linéaire.
Le trait essentiel, qui manquait à ma première version : pendant l'amorçage l'amplitude **monte**
(`progression × scintillement` à 30 Hz), donc le tube grelotte d'abord faiblement puis de plus en
plus fort — c'est ça, la sensation de chauffe. La fonction aléatoire du shader
(`fract(sin(x) * 43758.5453)`) est reprise telle quelle.

Deux écarts assumés :
- **la couleur vient de la palette** du deck, là où le shader n'avait qu'une `neonColor` ;
- **`répartition`** corrige un défaut du shader : il décalait les créneaux d'un demi-cycle chacun
  (`fi * totalDuration * 0.5`), ce qui modulo un cycle ne fait que **deux phases distinctes** — les
  créneaux 1 et 3 sont synchrones, d'où des moments où tous les tubes s'éteignent ensemble.
  À 1 (défaut) les créneaux sont étalés régulièrement ; à 0 on retrouve le shader à l'identique.
- La lueur orangée des électrodes pendant la chauffe est un ajout, réglable (`électrodes`).

Coût mesuré sur une matrice **16 × 250** : 0,03 à 0,20 ms par frame (budget 25 ms à 40 fps).

### Interface (`ui/`)
`preview.py` affiche la matrice en une barre par bandeau, numérotée ; `main_window.py` ajoute
la liste des effets, celle des palettes, les réglages de l'effet courant (reconstruits à chaque
changement), luminosité, case « Son », Blackout et une barre d'état (fps, sorties, erreurs, BPM).
Le moteur tourne à 40 fps dans son thread, l'UI lit la dernière frame à 30 fps : **si l'interface
rame, les LED ne bougent pas**. L'étage de sortie garde une *copie* de la frame (`keep_frame`) —
les effets réutilisent leur tampon, une simple référence serait modifiée sous les yeux de l'UI.

### Commandes
```bash
uv run leddeck fx list                                       # effets, réglages, palettes
uv run leddeck --profile club fx run Serpent --palette Feu   # sans interface
uv run leddeck --profile club fx run Vague --set vitesse=2.5 --set echelle=4
uv run leddeck --profile club ui                             # interface
```

### Mesures
Les 5 effets joués sur les 3 tubes : **40 fps, 0 retard, 0 erreur réseau** à chaque fois.

## 8 ter. Étape 4 — Audio (terminée le 2026-09-22)

### Modules
- `audio/input.py` — capture `sounddevice` en mono, callback par bloc, liste et résolution des
  périphériques (index ou fragment de nom), compteurs de diagnostic, détection de silence prolongé
  (→ message sur l'autorisation micro de macOS).
- `audio/analysis.py` — `Analyzer` : FFT, bandes, gain auto, détection de beat, BPM, tap tempo.
  Sort un `AudioState` immuable, remplacé d'un bloc à chaque analyse : le moteur le lit **sans verrou**.

### Quatre choix dictés par les mesures

1. **Fenêtre d'analyse (2048) ≠ pas d'avancement (512).**
   Avec une FFT de 512 points, la résolution est de 86 Hz : toute la bande des basses
   (30-150 Hz) tient dans **un seul bin**, inexploitable pour un kick. La fenêtre glissante de
   2048 points donne 21,5 Hz (5 bins de basses) tout en gardant un pas de 11,6 ms pour caler le beat.

2. **Détection d'attaque et tempo sur le bas du spectre (< 250 Hz).**
   En large bande, les charlestons de contretemps rendent l'enveloppe périodique à T/2 :
   le détecteur sortait **le double du tempo** (256 BPM sur un 128), et l'autocorrélation se calait
   parfois sur 1,5 × T (155 BPM lu 103). En ne gardant que le bas du spectre, les deux disparaissent.

3. **Beats calés sur la grille du tempo.**
   Une fois le BPM connu, une attaque n'est acceptée que si elle tombe à ±25 % de la pulsation
   prévue (resynchronisation douce, moitié de l'écart) ; sinon la pulsation prévue est émise quand
   même. Un kick masqué par la musique ne fait donc pas décrocher la lumière.

4. **Période réfractaire entre deux beats.**
   Constaté en écoute réelle : des doubles flashs. Cause mesurée — quand l'estimation de tempo
   change, la grille peut se retrouver plusieurs pulsations en retard et le rattrapage émettait
   **un beat par bloc audio** (toutes les 11,6 ms), soit une rafale. Deux correctifs : saut direct
   au dernier point de grille au lieu d'avancer d'une période à la fois, et interdiction absolue
   d'émettre deux beats à moins d'une demi-période (minimum 220 ms).
   Après correction, lors de changements 128 → 170 → 95 BPM : intervalle minimum **267 ms**.

5. **Gain auto entre plancher de bruit et crête, sauf pour le niveau global.**
   L'échelle des magnitudes FFT dépend du nombre de bins de la bande (5 pour les basses, 465 pour
   les aigus) : aucun seuil absolu ne convient. On suit donc une crête qui redescend (~7 %/s → le
   volume du club) et un plancher qui remonte (~1,7 %/s → le bruit de salle est soustrait).
   Le **niveau global**, lui, ne soustrait pas le plancher, sinon il retombe à zéro entre deux kicks.
   Les bandes ont une descente amortie (~160 ms) pour éviter de clignoter à 86 Hz.

### Détection de saturation
L'entrée compte les blocs écrêtés (crête ≥ 0,99) et l'affiche en direct (`SATURE`), parce qu'un
signal écrêté remplit le spectre de distorsion et crée de fausses attaques. Utile pour trancher
entre « le son est trop fort » et un défaut d'algorithme — hypothèse testée puis **écartée** ici :
0 bloc saturé sur 3799, crête d'entrée 0,05.

### Mesures
- Hors ligne, kick + charleston + nappe, de 75 à 174 BPM : **BPM exact à moins de 0,3 %**,
  jitter des beats **2 à 6 ms**, calage sur le kick **+5 ms** (une demi-fenêtre, incompressible).
- Changement de tempo 128 → 140 : re-verrouillé en ~10 s. Silence : bandes à zéro, reprise immédiate.
- Tap tempo : prioritaire sur l'estimation automatique jusqu'à `release_tap()`.
- **Au micro** (haut-parleurs → pièce → micro du MacBook) : BPM 128,1 pour une piste à 128,
  confiance 0,77, 0 dépassement audio.
- **Audio + LED ensemble** sur les 3 tubes : 39,9 fps, 0 erreur réseau, 0 dépassement audio.

### Commandes
```bash
uv run leddeck audio devices                  # lister les entrées
uv run leddeck audio monitor                  # bandes / niveau / BPM / beats dans le terminal
uv run leddeck --profile club audio leds      # spectre sur les bandeaux + flash sur le beat
```
`--device` accepte un index ou un fragment de nom ; le profil mémorise `audio_device`.

### Écoute réelle (musique du club, micro du MacBook)
*Le test en conditions de club réelles n'est pas réalisable pour l'instant — à faire sur place.*
- Les beats tombent juste, plus de double flash après la période réfractaire.
- **Niveau d'entrée très faible : crête 0,05** (≈ −26 dBFS), 0 saturation. C'est probablement la
  raison de la confiance de tempo basse (0,25 contre 0,77 sur une source proche).
  → Piste : entrée ligne, ou micro mieux placé.
- **En cas de break, la pulsation continue** (c'est voulu : un kick masqué ne doit pas faire
  décrocher la lumière). Jugé acceptable, sera géré manuellement (blackout / crossfader).
  Si besoin plus tard : couper les beats prédits quand l'énergie des basses s'effondre.

### Reste à faire
- Vérifier en conditions réelles de club (niveau fort, réverbération, grosses basses) et
  décider si une entrée ligne est préférable au micro. **Impossible à tester hors du club** :
  à faire lors de la première installation sur place.
- Le tap tempo n'a pas encore de déclencheur : il arrivera avec le MIDI (étape 6).

## 8 sexies. Étape 6 — MIDI (2026-09-22)

### Numéros relevés sur le matériel
Plutôt que de se fier à la documentation, les numéros ont été **relevés sur l'APC mini MK2**
avec `leddeck midi monitor` (port `APC mini mk2 Control`, canal 1) :

| Commande | Numéros |
|---|---|
| Grille 8×8 | notes **0 à 63**, `note = rangée_depuis_le_bas × 8 + colonne` (bas-gauche = 0) |
| 9 faders | **CC 48 à 56**, de gauche à droite |
| Boutons track (bas) | notes **100 à 107** |
| Boutons scene (droite) | notes **112 à 119** |
| Shift | note **122** |

### Mapping par défaut
Grille : moitié gauche = deck A, moitié droite = deck B ; 4 rangées du haut = effets,
4 rangées du bas = palettes. Faders : réglages A 1-3, luminosité, réglages B 1-3, vitesse globale,
crossfader. Scene : tap, crossfade auto, auto 8/16/32 (trois boutons libres).

**Rangée du bas : les 4 fonctions live × leurs 2 gestes**, dans le même ordre à chaque fois —
maintenu à gauche, bascule à droite : électrique, strobe, flash, blackout. On retrouve donc
toujours le même geste au même endroit relatif.
Les libellés disent le geste en clair (« tant qu'on appuie » / « bascule on/off »), pas un jargon.

**Tout est dans `midi/apcmini-mk2.json`** — rien n'est câblé en dur, c'est la base du MIDI learn.

### Fiche imprimable
`leddeck midi sheet` génère une page A4 paysage **depuis le mapping** : disposition physique du
contrôleur, numéro de note ou de CC sur chaque case, couleurs des decks, et les emplacements
libres signalés comme tels. Elle reste juste quand le mapping change, au lieu d'être recopiée
à la main.

### Soft takeover
Un fader ne prend la main qu'une fois revenu sur la valeur courante (tolérance 3 %, ou au
croisement), et il **se ré-arme dès que la valeur change ailleurs** (souris, auto-mix). Sans cela,
effleurer un fader ferait sauter le réglage à la position physique du fader.

### Retour visuel
Les pads reprennent la couleur du deck (cyan / rose) sur la sélection courante, les boutons simples
s'allument selon l'état. Seuls les changements sont envoyés : le MIDI est lent, réémettre 83 pads
à 30 Hz le saturerait. **Couleurs vérifiées sur le matériel le 2026-09-22 : correctes.**

### Deux bugs corrigés, tous deux réels
- **Boucle d'écho** : sur un bus en boucle (IAC, utilisé pour tester sans le contrôleur), le retour
  visuel revient en entrée et redéclenche les actions à l'infini. `MidiLink` mémorise ses propres
  envois et les ignore pendant 250 ms.
- **Blocage à la fermeture** : fermer un port pendant qu'un callback arrive **fige rtmidi**. Il faut
  détacher le callback, laisser la file se vider, puis fermer. Cela aurait bloqué la fermeture
  de l'application, pas seulement les tests.

### Reste à faire
- **Interface de MIDI learn** : `MidiController.learn_next()` existe, il manque la page qui permet
  de cliquer un réglage puis de toucher une commande.
- **Où mettre les presets** (étape 7) : la rangée du bas est prise par les fonctions live, et les
  trois boutons scene libérés ne suffisent pas pour huit presets. Piste : des pads libres de la
  grille (sept par deck dans la zone effets, trois dans la zone palettes).

## 8 octies. Étape 2 — Écran d'installation (2026-09-22)

`leddeck --profile <nom> install` ouvre une **fenêtre séparée de l'interface live** — volontairement :
deux moteurs qui émettraient en même temps sur les mêmes ESP se marcheraient dessus.

**Sorties WLED** : signal en direct (barres + dBm + qualité), état en ligne / hors ligne, version,
nombre de LED. Interrogation toutes les 4 s **dans un thread séparé** : l'interface ne doit jamais
attendre le réseau. Un bouton ouvre `http://<ip>` dans le navigateur, un autre fait clignoter le
bandeau pour le repérer. Le scan (sous-réseau au choix + mDNS) ajoute les nouveaux WLED trouvés.

**Patch** : une rangée par ligne de matrice — sortie choisie dans une liste, inversion, décalage,
et un bouton qui fait courir un point sur cette ligne seule. Plus la taille de matrice et le patch
automatique. *Écart assumé au plan* : liste déroulante plutôt que glisser-déposer — plus rapide à
l'usage et infaillible sur un portable en cabine.

**Vérification** : identification (chaque bandeau affiche son numéro), numéro de ligne,
arc-en-ciel, balayage, chenillard, extinction — avec l'aperçu de ce qui part.
`leddeck diag <sortie>` complète, hors interface : règle graduée (repère toutes les 10 LED, marque
toutes les 50), extrémités marquées, et aplats par couleur — pour trancher entre « bandeau plus
long que déclaré », chute de tension et problème de données.

**Le mode éteint adresse toutes les sorties, patchées ou non.** Une sortie découverte mais pas
encore patchée ne recevrait rien : WLED sortirait du temps réel au bout de 2,5 s et repartirait
sur son effet interne. C'est le cas courant juste après un scan.

Détail d'interface : les boutons du thème ont un remplissage généreux, adapté aux gros boutons
live, qui **tronque tout dans une cellule de tableau**. Les boutons de cellule ont donc leur propre
style compact et les lignes une hauteur fixe.

### Enregistrement : un scan s'enregistre seul
Un scan ajoutait les sorties **en mémoire seulement**. En fermant la fenêtre sans cliquer
« Enregistrer », l'ajout était perdu — et l'appli n'envoyait rien à un ESP pourtant bien détecté,
ce qui ressemble à s'y méprendre à une panne matérielle (perdu une heure là-dessus le 2026-09-23).
Désormais : **un scan qui ajoute des sorties enregistre le profil immédiatement** (un scan est un
constat, pas un choix), les modifications de patch affichent « modifications non enregistrées »,
et la fermeture demande confirmation.
Une sortie découverte est aussi **réveillée aussitôt** (`on` + luminosité max) : sans cela elle
reste éteinte côté WLED et n'affiche rien. Un bouton « Préparer les ESP » applique la
configuration club depuis l'écran.

### Reste à faire
- **Gestion des profils de salle** depuis cet écran : en créer, en charger, en renommer
  (aujourd'hui il n'y a qu'« Enregistrer »).
- Valider le scénario complet sur les 16 bandeaux : « posés au hasard, remis en ordre en 2 min ».

## 8 septies. Tenue dans la durée — premiers relevés

- **2026-09-22 : 29 minutes en continu** (3 tubes, audio + MIDI + interface), fermeture propre,
  aucune erreur réseau, contrôleur toujours répondant. Rien n'a dérivé.
- **2026-09-23 : 4 h 20 en continu** (14 tubes), interrompue par le système faute de mémoire —
  pas par un plantage. Au même instant : rekordbox 1,7 Go, cinq processus Chrome ≈ 3,2 Go,
  60 Mo de mémoire libre. L'application, elle, démarre à **116 Mo**.
  Rien n'accuse leddeck, rien ne l'innocente non plus : c'est le deuxième arrêt de ce type.
  La barre d'état affiche désormais **la mémoire occupée et sa dérive depuis le démarrage** —
  une dérive plate innocentera la machine, une dérive régulière désignera une fuite.
- Une session plus tôt a été **tuée par le système faute de mémoire** — pas un plantage de l'appli.
  Arrêtée de force, elle ne peut pas faire son blackout : les ESP reprennent leur effet interne
  au bout de 2,5 s. L'étape 8 devra donc prévoir un **preset de démarrage noir** côté WLED, pour
  qu'une coupure brutale n'allume pas les tubes au milieu d'une soirée.

Ce que ces 29 minutes ne prouvent pas : les 6 h visées, les 16 ESP, le Wi-Fi chargé d'un club,
ni le niveau sonore réel.

## 8 nonies. Étape 8 — Fiabilité club, en détail

Le critère reste « **6 h sans incident** ». Six chantiers, du plus structurant au plus simple.

### 8.1 Blackout garanti, même quand l'appli meurt — 🔶 fait, à valider
C'est le risque n° 1 : 2,5 s après le dernier paquet DDP, **WLED reprend son propre état** et
rallume les tubes sur son effet interne. Constaté en vrai quand le système a tué l'appli faute
de mémoire. `leddeck off` couvre l'arrêt volontaire, pas l'arrêt brutal.

**Un preset de démarrage ne suffit pas** : en sortant du temps réel, WLED revient à l'état qu'il
avait *avant*, pas à son preset de boot — et c'est nous qui le mettions à « allumé » pour émettre.
La parade retenue : **laisser WLED éteint en permanence** et activer « Force max brightness »,
qui affiche le flux temps réel quel que soit l'état on/off. Flux actif → les tubes montrent nos
données ; flux coupé → WLED est éteint, donc noir.

`leddeck prepare` applique tout cela à distance par l'API JSON (`maxbri`, `no-gc`, `en`,
`def.on = false`, puis état de repos éteint) ; `--check` affiche sans modifier.
Appliqué aux 4 ESP le 2026-09-23.

**Piège** : WLED applique et sauvegarde sa configuration **de façon différée**. Relire juste après
l'écriture renvoie encore les anciennes valeurs — la commande annonçait un échec alors que tout
avait fonctionné. Il faut attendre ~1,5 s avant de vérifier.

**Reste à valider sur le matériel** : que les tubes s'allument bien alors que WLED est éteint.
Toute l'approche en dépend. Si non, repli possible : renvoyer périodiquement « éteint » pendant
l'émission. Tant que ce n'est pas vérifié, l'appli continue d'envoyer `on + bri 255` au lancement.

### 8.2 Distribution : `.app` macOS
PyInstaller, avec dans l'`Info.plist` les deux autorisations que macOS exige :
`NSMicrophoneUsageDescription` et `NSLocalNetworkUsageDescription` — sans elles, l'app se voit
refuser le micro et l'envoi UDP **sans message d'erreur**.
Application non signée : prévoir la signature ad-hoc et la manip Gatekeeper au premier lancement.
Étape intermédiaire utile tout de suite : un `leddeck.command` lançable au double-clic.

### 8.3 Reprise du dernier état
Enregistrer à la fermeture — et périodiquement, pour survivre à un arrêt brutal — les effets,
palettes, réglages, position du crossfader, luminosité et mode de mélange des deux decks ;
les restaurer au lancement. À garder dans un fichier d'état distinct du profil de salle :
le profil décrit le lieu, l'état décrit la soirée.

### 8.4 ESP hors ligne signalé
Le mécanisme existe déjà dans l'écran d'installation (interrogation toutes les 4 s dans un thread).
Reste à le porter dans l'interface live : un compteur discret « 15/16 en ligne », la ligne
concernée marquée dans l'aperçu, et **une reprise automatique** — quand un ESP revient, il faut
lui renvoyer `on + bri 255`, sinon il reste éteint alors que les paquets arrivent.

### 8.5 Journal
Fichier tournant (dans `~/Library/Logs/leddeck/`), pour pouvoir répondre le lendemain à
« qu'est-ce qui s'est passé à 1 h 20 ». À consigner : démarrage et profil chargé, découverte,
erreurs réseau par sortie, frames en retard, dépassements audio, connexion et perte du MIDI,
exceptions de rendu. Volume à surveiller : à 40 fps, rien ne doit être écrit par frame.

### 8.6 Test de tenue
*La mesure mémoire existe déjà dans la barre d'état ; il reste à la relever sans interface.*
Une commande `leddeck soak` sans interface, qui joue une rotation d'effets et écrit
périodiquement : fps réel, frames en retard, erreurs réseau par sortie, dépassements audio,
mémoire occupée, RSSI de chaque ESP. C'est le seul moyen de distinguer une vraie fuite d'une
impression. Premier relevé disponible : 29 min sans dérive (§8 septies).

### Mesures de terrain (2026-09-23)
- **Les ESP8266 tiennent les 40 fps** avec 250 LED : mesuré à 40 fps rendus pendant qu'on émet à 40.
  *Correction d'une erreur d'analyse* : un premier relevé montrait 20 fps, mais il avait été pris
  **alors qu'aucun flux ne tournait** — WLED affichait son propre effet, et ce chiffre ne mesurait
  rien. Ne pas conclure sur une cadence relevée hors émission.
- **Le RSSI ne dit pas si la liaison porte les paquets.** `WLED-01` affichait −42 dBm (« excellent »)
  en perdant **66 % des paquets** au ping, d'où un rendu saccadé et un serveur web injoignable.
  L'écran d'installation affiche donc maintenant le **taux de joignabilité réel** (`3/10`) à côté
  du signal, et le temps de réponse.
- Un ESP qui reçoit bien (`live=true`, `lm='DDP'`, fps > 0) mais n'allume rien : vérifier
  **en premier qu'il est dans le profil**. Un ESP absent du profil ne reçoit simplement rien.

### Risques déjà identifiés en séance
- **Mémoire** : l'appli a été tuée une fois par le système. À mesurer sur la durée.
- **Wi-Fi chargé** : 16 ESP sur un seul point d'accès, jamais testé. Le tube n° 3 était déjà à
  −58 dBm avec trois clients.
- **Niveau sonore réel** : le micro captait à −26 dBFS ici, d'où une confiance de tempo faible.
  À rejouer sur place avant de décider micro ou entrée ligne.

## 9. Spécificités macOS

- **Micro** : macOS demande l'autorisation d'accès au micro (Terminal / l'app) au premier lancement.
  ✅ accordée pour le Terminal (vérifié le 2026-09-22).
- **Réseau local** : depuis macOS 15, il faut autoriser « Réseau local » pour le Terminal / l'app
  (Réglages → Confidentialité et sécurité → Réseau local), sinon l'envoi UDP vers les ESP échoue.
- MIDI : CoreMIDI, supporté nativement par python-rtmidi.

## 9 bis. Réseau (validé le 2026-09-22)

Le routeur dédié n'a pas Internet : s'y connecter en Wi-Fi coupe tout le reste.
**Solution retenue : deux interfaces en parallèle.**

| Interface | Réseau | Rôle |
|---|---|---|
| Wi-Fi `en0` | 192.168.0.210/24, passerelle 192.168.0.1 | Internet (route par défaut) |
| Ethernet USB `en5` | 192.168.8.101/24 | Routeur dédié → les ESP (pas de passerelle) |

- Les deux sous-réseaux doivent être **différents** (ici 192.168.0.x et 192.168.8.x) : sinon conflit de routage.
- Le Wi-Fi doit être **en tête de l'ordre des services** (Réglages → Réseau → ⋯ → Définir l'ordre des services),
  sinon macOS bascule la route par défaut sur l'Ethernet et l'on perd Internet.
  Ceinture et bretelles : configurer l'Ethernet en IPv4 manuelle avec le champ **Routeur vide**.
- Vérification : `route -n get default` doit rester sur `en0` / 192.168.0.1.
- `leddeck discover --cidr 192.168.8.0/24` : sans `--cidr`, le balayage couvre aussi le réseau maison pour rien.

### Configuration attendue côté WLED (une par ESP)

- **Un seul bus LED** : 250 LED, sortie locale (GPIO), type WS281x — **aucun bus réseau**.
  (La config trouvée au départ était un « virtual LED » de 1000 LED : un ESP maître relayait en DDP vers
  trois autres. Abandonné : latence, trafic Wi-Fi doublé sur le maître, point unique de panne.)
- **IP fixe** par ESP, nom explicite (`WLED-01` … `WLED-16`).
- DDP en réception : toujours à l'écoute sur le **port 4048**, rien à activer.
- `no-gc: true` (pas de gamma WLED sur le flux temps réel) → le gamma est appliqué par l'appli.
- `maxbri: true` (luminosité forcée au max en temps réel) → la luminosité est gérée par l'appli.
- Limiteur de courant (ABL) désactivé ou réglé large, sinon WLED assombrit tout seul.

## 10. Contrôleur MIDI : Akai APC Mini MK2

Matériel : grille 8×8 de pads RGB, 9 faders, 8 boutons « track » (bas), 8 boutons « scene » (droite), Shift.
Les pads RGB permettent un retour visuel en couleur (couleur des palettes, effet actif…).

Mapping proposé par défaut (tout reste modifiable via MIDI learn) :

| Contrôle | Rôle |
|---|---|
| Pads colonnes 1-4, rangées 1-4 | Deck A : 16 effets |
| Pads colonnes 1-4, rangées 5-8 | Deck A : 16 palettes (pads allumés de la couleur de la palette) |
| Pads colonnes 5-8, rangées 1-4 | Deck B : 16 effets |
| Pads colonnes 5-8, rangées 5-8 | Deck B : 16 palettes |
| Faders 1-3 | Deck A : vitesse, taille, réactivité son |
| Faders 5-7 | Deck B : vitesse, taille, réactivité son |
| Fader 4 | Luminosité master |
| Fader 8 | Vitesse globale |
| Fader 9 | **Crossfader A ↔ B** |
| Boutons scene (droite) | tap tempo, auto-mix on/off, durée auto (8/16/32 beats), strobe (maintenu), flash (maintenu), blackout… |
| Boutons track (bas) | presets 1-8 |

## 11. Décisions / réponses

- Plateforme : **macOS** (développement et utilisation), code gardé multiplateforme.
- Contrôleur : Akai APC Mini MK2.
- Son : **micro** pour l'instant (entrée ligne possible plus tard).
- 16 bandeaux de **250 LED**, WiFi via routeur dédié, IP fixes.
- Modèle simple : **matrice L × N** (pas de mapping spatial 2D).
- Bandeaux **RGB** (3 octets par LED en DDP).
- Gestion des dépendances : `pyproject.toml` + `uv` (le `requirements.txt` du plan initial est abandonné).
- Correction **gamma appliquée à la sortie** (étage patch, LUT 256 valeurs), pas dans les effets.
- Moteur : en cas de retard, on **saute** la frame au lieu de rattraper en rafale (pas de saccade d'effet).
- Réseau : **Ethernet vers le routeur dédié + Wi-Fi pour Internet**, sous-réseaux distincts (cf. §9 bis).
- Topologie LED : l'appli envoie **en DDP directement à chacun des 16 ESP** (250 LED chacun).
  Pas de relais / virtual LED entre ESP.
- Extinction : `off` coupe **aussi** WLED via l'API JSON, sinon l'ESP reprend son effet interne
  2,5 s après le dernier paquet DDP.
- Luminosité : forcée à 255 côté WLED avant chaque émission ; seul le master de l'appli la règle.
- Audio : fenêtre d'analyse 2048 / pas 512 ; détection de beat et tempo sur le bas du spectre ;
  beats calés sur la grille ; gain auto plancher-crête (cf. §8 ter).
- `AudioState` immuable remplacé à chaque bloc : le moteur lit l'analyse sans verrou.
- Les effets ne choisissent jamais de couleur : tout passe par la palette du deck (§8 quater).
- Un effet doit rester pleinement visible sans son : la réactivité ne sert jamais à assombrir.
- Les deux decks tournent en permanence (cf. §8 quinquies).
- Strobe, flash et blackout ont **chacun un verrou et un momentané** (les deux gestes existent en club).
- L'auto-mix ne doit jamais dépendre du son : horloge interne en secours.
- Une action manuelle reprend toujours la main sur l'automatique.

## 11 bis. Application unique et publication (25/09/2026)

- **Une seule fenêtre** : la page *Live* et la page *Installation* sont deux pages d'un
  `QStackedWidget`, avec un seul `Engine` et un seul `OutputStage`. C'était la raison
  d'être des deux fenêtres séparées : deux moteurs auraient émis en même temps vers les
  mêmes ESP. Un moteur unique qui interroge la page affichée supprime le problème.
  - `_render` demande la frame à `install.render()` quand la page installation est devant.
  - `OutputStage.send_frame` accepte désormais un dictionnaire `{sortie: ligne}` : c'est
    la forme utilisée par l'installation, qui adresse les bandeaux avant tout patch.
  - Le sondage réseau et l'aperçu de la page installation ne tournent que quand elle est
    visible : pas de requêtes HTTP en concurrence avec le DDP pendant le live.
  - Changer la taille de matrice reconstruit le mixer, le master et la page live
    (`_rebuild_matrix`) — les effets sont dimensionnés à la construction.
- `leddeck install` reste, mais ouvre la même application sur la page installation.
- **16 effets pour 12 pads** : le profil garde une liste `fav_effects` — les effets posés
  sur la grille du contrôleur, dans l'ordre des pads. `Profile.pad_effects()` complète
  avec l'ordre du catalogue, donc la grille est toujours pleine même sans choix fait.
  Réglage depuis « Effets du contrôleur… » dans la barre de navigation ; la fiche
  imprimable montre la grille réellement sous les doigts.
- **16 effets** au total après le portage des shaders MadMapper ; tous rendus en moins de
  0,35 ms par frame en 250 × 14 (le plus lourd : Vortex).
- `--no-audio` est désormais respecté : la surveillance audio ne rouvre plus une entrée
  que l'on a demandé de laisser fermée.
- **Interface en français et en anglais** (`ui/i18n.py`) : les chaînes françaises sont les
  clés, l'anglais est une table de correspondance, et une clé absente ressort en français
  plutôt que de casser l'affichage. Les noms d'effets, de palettes et de paramètres sont
  traduits **à l'affichage seulement** — la clé enregistrée reste française, parce que les
  profils et le mapping MIDI s'appuient dessus. La langue vit dans le profil et se choisit
  dans la barre de navigation ; en changer reconstruit l'interface.
  **La ligne de commande suit aussi** : `--lang fr|en`, globale, placée avant la commande.
  Elle doit être lue **avant** de construire l'analyseur d'arguments, sinon les textes
  d'aide seraient déjà figés — d'où `pick_language()`, qui lit `sys.argv` à la main puis
  retombe sur le profil. Les noms d'effets et de palettes s'affichent traduits et
  **les deux orthographes sont acceptées en saisie**, quelle que soit la langue : un nom
  appris dans `fx list` en anglais ne doit pas cesser de marcher en repassant au français.
  Le module vit en `leddeck/i18n.py` (et non dans `ui/`) : `main.py` s'en sert sans
  dépendre de Qt.
- Captures du README : générées **hors écran** (`QT_QPA_PLATFORM=offscreen` + `QWidget.grab()`),
  donc reproductibles sans toucher à la souris et régénérables après un changement d'interface.
  `docs/live.png`, `docs/setup.png`.
- **Publication GitHub** : `README.md` (anglais), `LICENSE` (MIT, association Eclipse),
  `PLAN.en.md` (traduction de ce document — **le français reste la référence**),
  `.gitignore` complété. Les profils de `profiles/` contiennent les IP privées du club
  (192.168.8.x) : sans danger, mais à retirer si le dépôt doit rester neutre.

## 12. Questions ouvertes

- Développement sur **3 bandeaux** (profil `club`, matrice 250 × 3) : suffisant pour l'ordre des
  lignes, l'inversion et l'identification. Le passage à 16 n'est qu'une question de nombre.
- Le tube #3 a un signal plus faible (−58 dBm) : à surveiller quand les 16 seront en place
  (nombre de clients sur le routeur, position des antennes).
