# Projet LED club

- L'utilisateur parle français : répondre en français.
- Projet perso (pour le fun) : appli Python / PySide6 pour piloter 16 bandeaux WLED (250 LED, WiFi, IP fixes) en DDP dans un club, en remplacement de MadMapper.
- **Tout le plan, les décisions et les étapes sont dans `PLAN.md`** : le lire avant de travailler, et le tenir à jour (cocher les étapes, noter les nouvelles décisions).
- Plateforme cible : macOS (garder le code multiplateforme).
- Modèle volontairement simple : matrice L LED × N bandeaux, paramétrable. Ne pas réintroduire de mapping spatial 2D (refusé par l'utilisateur car trop compliqué).
- Contrôleur MIDI : Akai APC Mini MK2. Son : micro. Bandeaux RGB.
