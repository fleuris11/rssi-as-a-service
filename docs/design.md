# Direction visuelle — la salle de supervision

Document de référence de la refonte complète du front, septembre 2026.
Il remplace `docs/systeme_visuel.md` (direction « le trait plutôt que l'ombre »,
abandonnée sur décision du commanditaire).

---

## 1. Ce qui a été consulté

### 1.1 Skill `ui-ux-pro-max`

Sept recherches lancées, dans l'ordre :

| Recherche | Domaine | Ce que j'en ai retenu |
|---|---|---|
| `"B2B cybersecurity SaaS threat monitoring for small business"` | `--design-system` (variance 6, motion 5, densité 5) | **Écarté.** Le moteur propose Glassmorphism + bleu #2563EB + orange #EA580C + Plus Jakarta Sans. C'est très exactement le rendu « généré par IA » que le brief interdit. Retenu uniquement : la liste de contrôle de pré-livraison (contraste, focus, `prefers-reduced-motion`, 4 points d'arrêt) et l'avertissement `AVOID: Excessive animation + Dark mode by default`. |
| `"technical precision developer tool dark interface"` | `style` | Cyberpunk UI, Dark Mode OLED, HUD/Sci-Fi FUI. Les trois sont des costumes. **Écarté**, mais HUD/FUI confirme que la cybersécurité attire par défaut le néon sur noir : c'est l'ornière à éviter, pas la cible. |
| `"editorial swiss grid typographic minimal"` | `style` | Editorial Grid : grille asymétrique, hiérarchie par le texte, `risk:low`. **Retenu partiellement** : la hiérarchie portée par la typographie plutôt que par des boîtes. |
| `"bento grid dashboard modular"` | `style` | Bento Box Grid (**écarté** : « cartes modulaires de tailles variées » est la mise en page la plus reconnaissable du web généré) et **Data-Dense Dashboard** (`Type: BI/Analytics`, padding minimal, tableaux, survol → info-bulle, surbrillance de ligne). **Retenu pour le profil Technique et la console.** |
| `"premium modern saas dark elegant"` | `style` | Aurora UI, Soft UI Evolution, Glassmorphism. **Tous écartés** : dégradés maillés, néomorphisme, verre dépoli — la liste des interdits du brief, mot pour mot. |
| `"cybersecurity security monitoring trust"` | `color` | La seule palette « Cybersecurity Platform » du catalogue est `#00FF41` sur `#000000` (Matrix). **Écartée.** La deuxième la plus proche, « Insurance Platform » (`#0369A1` + `#16A34A` sur `#F0F9FF`), confirme le réflexe bleu-confiance. **Écartée aussi** : la couleur doit dire le risque, pas la confiance. |
| `"technical precise grotesque dashboard numbers"` et `"premium authority serious enterprise"` | `typography` | 16 appariements lus. Écartés : tout ce que le plancher de qualité d'`impeccable` liste comme défaut d'entraînement (IBM Plex, DM Sans, Plus Jakarta, Space Grotesk, Inter en display). **Retenue : la logique de l'appariement « Dashboard Data » et « Developer Mono » — une grotesque de labeur pour le texte, une mono pour tout ce qui se mesure.** Le choix des familles, lui, vient d'ailleurs (§4). |
| `"grotesque display tight headline variable"` | `google-fonts` | Inter Tight, Funnel Display, Anybody, Tourney… Aucune ne tient à la fois le titre, le texte long et le tableau. **Écartées.** |
| `"saas landing hero progressive disclosure secondary pages"` | `landing` | `pricing-focused-landing` : accroche → offres → comparatif → FAQ → action finale, avec les totaux réels affichés. **Retenu pour `/offres`.** `funnel-3-step-conversion` retenu pour la structure de l'accueil (un pas = une idée). |

### 1.2 Skill `impeccable`

- `impeccable context` : aucun `PRODUCT.md`, aucun `DESIGN.md`. J'ai donc écrit
  `PRODUCT.md` à partir du dépôt et du brief, en marquant les déductions —
  l'entretien prévu par `init` a été sauté sur consigne explicite du
  commanditaire (« tu enchaînes tout sans t'arrêter pour validation »).
- `reference/craft-floor.md` : le plancher de qualité. Ce qu'il change ici,
  concrètement :
  - **les sur-titres (« eyebrow ») sont interdits** — pas déconseillés,
    interdits. La classe `.t-eyebrow` disparaît des en-têtes de section ;
  - les cartes de taille identique (icône + titre + texte) comme structure de
    page sont refusées ; les cartes imbriquées sont toujours fausses ;
  - la mono comme costume « technique » est refusée — elle ne sert qu'à ce qui
    se compte, se date ou se mesure ;
  - **les surfaces du navigateur font partie du design** : sélection de texte,
    curseur de saisie, barres de défilement, anneau de focus, décalage de
    soulignement, chiffres tabulaires. C'est le point que les modèles sautent
    le plus souvent ; il est traité au §7 ;
  - clair ou sombre se décide sur la scène d'usage, jamais par catégorie.
- `reference/new-work.md` § « Commit the world » : la stratégie de couleur se
  choisit **avant** les couleurs. Choix retenu : **Restrained** pour les
  surfaces de travail (neutres + une couleur d'action), **Committed** pour le
  bandeau d'état, qui se gorge de la couleur de son niveau quand le niveau
  l'exige.
- `impeccable concept-seed --scope direction --mode persuade` : obligatoire
  avant toute ligne de code sur un monde de remplacement. Graine **`22c7b0c6`**,
  **index assigné : 4**. Le tirage impose de construire le 4ᵉ candidat de ma
  propre liste classée par résonance, précisément pour casser l'ornière du
  premier. Les six adversaires tirés du catalogue sont pesés au §3.

### 1.3 MCP Magic UI

Le serveur n'est pas monté comme outil dans cette session ; je l'ai interrogé
directement en JSON-RPC sur stdio (`npx -y @magicuidesign/mcp@latest`,
`Magic UI MCP 1.0.4`). **78 composants** listés et parcourus.

La grande majorité est exactement l'esthétique interdite : `aurora-text`,
`shimmer-button`, `border-beam`, `shine-border`, `meteors`, `particles`,
`sparkles-text`, `neon-gradient-card`, `animated-gradient-text`,
`retro-grid`, `warp-background`, `rainbow-button`, `magic-card`. Aucun n'est
utilisé.

Trois mécanismes retenus, **tous sur la vitrine, aucun dans l'espace client ni
dans la console** :

| Composant | Ce que j'en garde | Ce que je change |
|---|---|---|
| `number-ticker` | Le ressort qui amène un chiffre à sa valeur : une aiguille d'instrument qui se pose, pas un compteur de marketing. | Réécrit en ~30 lignes de React sur `requestAnimationFrame`. La version Magic UI dépend de `motion` (framer-motion, ~35 ko gzip) pour un ressort ; le projet a un budget de performance et une exigence Green IT. Aucune dépendance ajoutée. |
| `animated-list` | L'arrivée séquentielle d'éléments dans une liste, pour montrer des alertes qui tombent. | Même chose : réécrit sans `motion`, et l'animation **s'arrête** après la dernière alerte au lieu de tourner en boucle. Une boucle infinie est du bruit. |
| `safari` | Le cadre de navigateur autour d'une capture produit. | Le mécanisme existait déjà dans le dépôt (`CaptureProduit`) ; Magic UI a confirmé les proportions de la barre de titre. |

`scroll-progress` a été évalué et **écarté** : le curseur de progression de la
vitrine est déjà porté par le bandeau d'état, en ajouter un second serait un
doublon.

---

## 2. La direction retenue

> **Le produit est un tableau de supervision de réseau, pas un site de
> logiciel.** Le monde est celui d'éCO2mix et du signal Ecowatt : la salle de
> conduite d'une infrastructure française, et le signal public qu'elle publie
> pour des gens qui n'y connaissent rien.

**La thèse.** Ce produit a un problème que presque aucun autre n'a : il doit
dire *la même chose* à un gérant de PME qui n'est pas informaticien et à son
prestataire technique. La plupart des produits résolvent ça avec deux modes
d'affichage bricolés. Le réseau électrique français l'a résolu il y a des
années, et tout le monde en France connaît les deux surfaces sans le savoir :

- **Ecowatt**, c'est le signal public. Une couleur, une phrase, une action.
  « Signal vert : consommation normale. » Un enfant le lit.
- **éCO2mix**, c'est la console de l'exploitant. Des courbes empilées, un
  curseur « maintenant », des filtres, un export CSV, le pas de temps à la
  demi-heure.

Les deux lisent **la même donnée**, à la même seconde. C'est exactement la
règle n°1 de `PRODUCT.md` : deux lecteurs, une vérité. Le profil **Dirigeant**
est Ecowatt. Le profil **Technique** est éCO2mix. Ce n'est plus un réglage
d'affichage, c'est deux surfaces d'un même instrument, et elles ont le droit
de ne pas se ressembler.

**Ce que la direction refuse.** L'arrangement par défaut de la catégorie : le
héros sombre avec un bouclier néon, la mappemonde des menaces, et trois cartes
« fonctionnalités » avec une icône ronde au-dessus. Et son opposé prévisible :
la cybersécurité pastel « pour les humains », avec des illustrations arrondies.

**Le monde.** Un bâti graphite — rail, bandeau, pied de page — et une face
d'instrument claire, réglée, où se lit le contenu. C'est la forme physique
d'un pupitre de conduite : le cadre est sombre, l'afficheur est lumineux. Ce
n'est pas un « mode sombre » : c'est un bâti. La décision vient de la scène
d'usage, comme le plancher de qualité l'exige : le gérant ouvre le produit sur
son téléphone, en plein jour, depuis un email. Le texte long ne peut pas être
sur fond noir. Le bâti, lui, peut.

**Le premier écran de la vitrine.** Pas de promesse : l'instrument, en marche.
Un bandeau d'état pleine largeur affiche le niveau du jour d'un client fictif
et la phrase qui va avec. Dessous, à gauche, une seule ligne de titre et une
seule action. À droite, le panneau de conduite : la jauge d'exposition qui se
pose sur sa valeur, la courbe des quatre-vingt-dix derniers jours avec son
curseur « maintenant », et deux alertes qui tombent puis s'arrêtent. Tout est
réel, tiré du client de démonstration.

**Le chemin du visiteur.** Il comprend en cinq secondes que ça surveille
quelque chose et que ça lui dira quoi faire. L'accueil tient en six actes, un
par idée. Le détail part sur `/fonctionnalites`, `/securite`, `/offres`,
`/faq` — rien n'est supprimé, tout est déplacé (inventaire au §8).

**L'interaction signature.** Le **curseur « maintenant »**. Sur chaque série
temporelle du produit — courbe d'exposition, historique de diagnostic,
évolution des campagnes — une ligne verticale marque l'instant présent, avec
sa valeur en Chivo Mono au-dessus. Sur la vitrine, elle avance une fois au
chargement, puis s'arrête. Dans l'application, elle suit le survol et le
clavier (flèches), et elle est le seul élément qui porte la couleur d'action.

**La portée transversale.** Le bandeau d'état est présent sur les trois
surfaces : la vitrine (celui du client de démonstration), l'espace client
(celui du client), la console (celui de la plateforme — nombre de clients en
alerte). Même composant, même grammaire, trois contenus.

**Le risque assumé.** Un bâti sombre autour d'une face claire peut paraître
lourd si le rail est trop large ou trop bavard. Il est donc réduit à 236 px au
bureau, replié en barre basse au téléphone, et il ne porte aucune décoration.

### Les relèvements

Le tirage impose de peser six mondes adverses et, pour chacun qui perd, de
nommer la discipline qui manque à la direction retenue et de l'y hisser. Quatre
relèvements ont été écrits dans la direction :

- **Relèvement « téléscripteur » (donné par le magazine télétexte).** Chaque
  page a une adresse, et l'adresse est atteignable au clavier depuis n'importe
  où. Le produit gagne une palette de commandes (`Ctrl/⌘ + K`) et, sur chaque
  écran, un fil d'adresse stable qui dit où l'on est.
- **Relèvement « pas entier » (donné par le tableau de destinations de dépôt).**
  Aucune valeur ne glisse : un changement d'état saute d'un cran entier, jamais
  d'une fraction. Le dépassement élastique du premier réglage a été retiré
  après la passe du détecteur (§6, règle 2) ; c'est la discrétisation qui porte
  la discipline, pas le rebond.
- **Relèvement « frange » (donné par le bord de nuage irisé).** La couleur est
  confinée au bandeau d'état et à l'arête de l'élément vivant. Le champ de
  lecture reste achromatique. Aucune grande surface colorée hors du bandeau.
- **Relèvement « âge » (donné par le calendrier de saumure).** Toute
  information porte son âge en clair, partout : « il y a 3 jours », jamais une
  date nue qu'il faut soustraire de tête.

---

## 3. Les pistes écartées

### 3.1 Les deux directions écartées de ma propre liste

**Le bulletin de vigilance Météo-France** (mon candidat n°1, celui que le
tirage refuse justement parce que c'est le premier). Carte à quatre couleurs,
bulletin de suivi horodaté, « vigilance orange jusqu'à 18 h ». Écartée pour
deux raisons : le produit envoie déjà une « météo cyber » quotidienne, donc le
monde serait la lecture littérale du nom — ce que `new-work.md` compte comme
l'ornière — et surtout la vigilance météo ne sait parler qu'à un seul lecteur.
Elle n'a pas de seconde surface pour l'expert. C'est la faiblesse que la
direction retenue n'a pas.

**Le contrôle technique automobile** (candidat n°2). Le procès-verbal, les
défaillances mineures / majeures / critiques, la date de la prochaine visite,
la vignette. Extrêmement lisible pour un gérant de PME, et le vocabulaire est
déjà celui du produit. Écartée parce qu'elle est **ponctuelle** : un contrôle
technique est un événement tous les deux ans. Le produit, lui, surveille en
continu. Le monde aurait menti sur le mécanisme.

### 3.2 Les six adversaires tirés, et leur verdict

Chacun a été fusionné avec les faits du produit avant d'être jugé, sur deux
axes seulement : identification du public, et clarté du produit.

| Adversaire | Verdict | Pourquoi | Ce qui a été gardé |
|---|---|---|---|
| Magazine télétexte (grille 40×24, REVEAL) | **Refusé** | Un gérant de PME en 2026 ne lit pas le télétexte ; la mosaïque de blocs détruit l'exigence « des phrases, zéro jargon ». | L'adressage clavier universel → relèvement « téléscripteur ». |
| Tableau de destinations de dépôt (toile teinte, course arrêtée) | **Refusé** | Magnifique et illisible : l'état d'erreur « demi-légende à cheval sur une couture » n'est compréhensible par personne. | Le changement par cran entier → relèvement « pas entier ». |
| Bord de nuage irisé | **Compétitif** (tient la clarté) | « La couleur confinée aux arêtes, le champ de texte achromatique » est une vraie discipline, mais le monde entier ne peut pas porter une console dense. | La discipline de confinement → relèvement « frange ». |
| Calendrier de saumure | **Refusé** | Aucun rapport avec le public ni le mécanisme. | Le compte de jours en première classe → relèvement « âge ». |
| Générique Saul Bass | **Compétitif** (tient la clarté) | « Une idée par carte pleine page » répond exactement au reproche « la vitrine est trop dense ». Mais un générique est une séquence : il ne sait pas tenir un tableau de 400 lignes. | La structure en actes pleine largeur pour l'accueil de la vitrine. |
| Enseigne néon du désert | **Refusé** | Le néon sur fond de nuit est l'ornière même de la catégorie. | Le plan de fabrication montré à côté du rendu → sur la vitrine, la capture réelle est annotée avec des lignes de rappel, au lieu d'être une image de prestige. |

Aucun adversaire ne gagne les deux axes. La direction assignée est construite,
relevée par les quatre dons ci-dessus.

---

## 4. La typographie

**Archivo Variable** (titres, interface, texte courant) et **Chivo Mono
Variable** (chiffres, mesures, identifiants). Toutes deux sous licence SIL
Open Font License, du même dessinateur (Omnibus-Type), auto-hébergées par
`@fontsource-variable`. **Aucun appel à Google Fonts au moment de l'exécution.**

Pourquoi celles-là :

- Le plancher de qualité d'`impeccable` liste explicitement comme « défauts
  d'entraînement » les faces que tout modèle propose : Fraunces, Playfair,
  Space Grotesk, **IBM Plex**, **DM Sans**, **Plus Jakarta Sans**, Inter en
  display. Les recommandations de `ui-ux-pro-max` tombaient toutes dans cette
  liste. Archivo n'y est pas, et ce n'est pas un hasard : c'est une grotesque
  de labeur dessinée pour la presse et les formulaires, pas pour les pages de
  lancement.
- **Archivo a un axe de largeur (62 % → 125 %)** en plus de la graisse
  (100 → 900), dans **un seul fichier woff2 par sous-ensemble**. C'est ce qui
  donne la voix du monde : les légendes d'instrument sont de l'Archivo
  condensé en capitales, comme la sérigraphie d'un pupitre, et le titre de
  l'accueil est de l'Archivo large et gras. Une seule famille fait le travail
  de trois.
- **Chivo Mono** est la mono de la même fonderie et de la même famille de
  dessin. Elle sert là où ça se mesure : scores, pourcentages, dates,
  compteurs, colonnes de tableau, identifiants tronqués. Jamais ailleurs — la
  mono comme costume « technique » est refusée par le plancher de qualité.
- Bilan de poids : deux familles variables remplacent Fraunces + Inter. Mesuré
  au §9.

Rôles typographiques (classes, `index.css`) :

| Rôle | Face | Réglage |
|---|---|---|
| `.t-hero` | Archivo | `wdth 96`, 800, `clamp(2.25rem, 1.2rem + 4.4vw, 4.25rem)`, `-0.035em`, `text-wrap: balance` |
| `.t-titre` | Archivo | `wdth 100`, 700, `clamp(1.5rem, 1.1rem + 1.6vw, 2.125rem)`, `-0.02em` |
| `.t-sous-titre` | Archivo | `wdth 100`, 650, `1.125rem` |
| `.t-accroche` | Archivo | `wdth 100`, 400, `clamp(1.0625rem, 1rem + .4vw, 1.25rem)`, `1.6`, mesure 62ch |
| `.t-corps` | Archivo | 400, `1rem`, `1.65`, mesure 68ch |
| `.t-legende` | Archivo | **`wdth 70`**, 600, `0.6875rem`, capitales, `+0.09em` — la sérigraphie du pupitre |
| `.t-menu` | Archivo | `wdth 92`, 550, `0.9375rem` |
| `.n-grand` | Chivo Mono | 600, `clamp(2.5rem, 2rem + 2.6vw, 4rem)`, `-0.03em`, `tnum` |
| `.n` | Chivo Mono | 500, hérite, `tnum` `zero` |

`.t-legende` n'est **jamais** placée au-dessus d'un titre de section : c'est
une légende d'instrument (en-tête de colonne, axe, libellé d'état), pas un
sur-titre. Les sur-titres sont supprimés du produit.

---

## 5. Les jetons de couleur

Source unique : `frontend/src/tokens.css`, importé par `index.css`, exposé à
Tailwind v4 par `@theme`. **Aucune couleur en dur dans un composant** — une
règle ESLint et un test Vitest le vérifient.

### 5.1 Le bâti (graphite)

| Jeton | Hex | Usage |
|---|---|---|
| `--bati-900` | `#0E151B` | Pied de page, actes sombres de la vitrine |
| `--bati-800` | `#141D25` | Rail de navigation, bandeau d'état au repos |
| `--bati-700` | `#1E2A34` | Panneaux sur bâti, en-têtes de colonne de la console |
| `--bati-600` | `#2B3A47` | Filets sur bâti |
| `--bati-500` | `#43586A` | Filets accentués, bordure de champ sur bâti |
| `--craie` | `#E9EEF2` | Texte principal sur bâti — 14,8:1 sur `--bati-800` |
| `--craie-douce` | `#A2B3C0` | Texte secondaire sur bâti — 6,9:1. Teinté depuis la teinte du bâti, jamais gris |

### 5.2 La face d'instrument (surface de travail)

| Jeton | Hex | Usage |
|---|---|---|
| `--face` | `#F6F8F9` | Fond de page |
| `--face-haute` | `#FFFFFF` | Panneaux, lignes de tableau |
| `--face-creuse` | `#EDF1F3` | Fond de champ, ligne alternée, en-tête de tableau |
| `--reglure` | `#D8E0E6` | Le filet de 1 px. La structure du produit |
| `--reglure-forte` | `#B9C6CF` | Séparation de bloc |
| `--encre` | `#0E151B` | Texte principal — 16,1:1 sur `--face` |
| `--encre-douce` | `#4A5C69` | Texte secondaire — 7,2:1 sur `--face` |
| `--encre-tenue` | `#6B7C88` | Légendes, unités — 4,6:1 sur `--face`, jamais sous 11 px |

### 5.3 L'échelle de risque — quatre crans, et elle ne sert qu'à ça

Le vocabulaire est celui de la vigilance publique française, qui a quatre
niveaux et que tout le monde sait lire. **Aucune de ces couleurs n'est
utilisée pour autre chose qu'un niveau de risque.** Chaque cran porte aussi
une forme (le glyphe du cran) et un mot : jamais d'information par la couleur
seule.

| Cran | Encre | Fond | Arête | Contraste encre/fond de page |
|---|---|---|---|---|
| `calme` | `#0B6E3F` | `#E6F2EB` | `#8FC4A9` | 5,1:1 |
| `surveille` | `#8A5300` | `#FBF0DC` | `#DDB673` | 5,0:1 |
| `preoccupant` | `#AE3B0B` | `#FCEAE0` | `#E39C79` | 5,2:1 |
| `critique` | `#9E1219` | `#FBE6E7` | `#DE8F93` | 6,6:1 |

Quand le niveau atteint `critique`, le bandeau d'état **se gorge** de sa
couleur : fond `#6E0D12`, texte `--craie`. C'est le seul endroit du produit où
une couleur occupe une grande surface, et c'est voulu — c'est le seul moment
où l'on veut que le gérant lève les yeux.

Séparément, l'échelle **opérationnelle** (`ok` / `attention` / `panne`) d'un
actif surveillé reste distincte : elle décrit un service, pas un risque. Elle
utilise `--encre-douce` + un glyphe, et n'emprunte jamais l'échelle de risque.

### 5.4 L'action — une seule couleur, et elle n'est jamais un état

| Jeton | Hex | Usage |
|---|---|---|
| `--action` | `#1650CF` | Boutons principaux, liens, curseur « maintenant », anneau de focus — 6,9:1 sur blanc |
| `--action-appui` | `#103FA6` | Survol et appui |
| `--action-clair` | `#89B0FF` | Liens et focus **sur bâti** — 7,4:1 sur `--bati-800` |
| `--action-voile` | `#E7EEFC` | Fond de sélection, ligne sélectionnée |

### 5.5 Espacements

Unité 4 px. Échelle : `--e-1` 4 · `--e-2` 8 · `--e-3` 12 · `--e-4` 16 ·
`--e-5` 24 · `--e-6` 32 · `--e-7` 48 · `--e-8` 72 · `--e-9` 112.

Rythme : `--rythme-bloc` 32 px, `--rythme-section` `clamp(56px, 7vw, 104px)`.
Règle du plancher de qualité : **plus d'espace au-dessus d'un titre qu'en
dessous** (`--e-7` au-dessus, `--e-4` en dessous).

Densité : la face d'instrument a deux densités, `compacte` (hauteur de cellule
34 px) et `confortable` (46 px), pilotées par une variable CSS sur le conteneur.
Le profil **Technique** ouvre en `compacte`, le profil **Dirigeant** en
`confortable`.

### 5.6 Rayons et profondeur

Rayon `--r-1` 3 px (chips, champs), `--r-2` 6 px (panneaux, boutons),
`--r-3` 10 px (bandeau, modales). **Rien au-dessus.** Pas d'arrondi généralisé.

La profondeur vient d'un **filet**, pas d'une ombre. Deux ombres seulement
existent, toutes deux avec décalage **et** flou — un halo coloré sans décalage
est une décoration, pas une profondeur :
`--ombre-pose: 0 1px 2px rgb(14 21 27 / .06), 0 2px 8px -2px rgb(14 21 27 / .08)`
et `--ombre-flottante: 0 8px 28px -8px rgb(14 21 27 / .22)` (menus, modales).

---

## 6. Les règles d'animation

1. **Un moment d'auteur par surface, pas une entrée identique sur chaque
   section.** Vitrine : l'instrument s'anime une fois au premier écran.
   Espace client : le curseur « maintenant » avance une fois. Console : rien.
   **Le chiffre animé n'existe QUE sur la vitrine**, et c'est une règle de
   mode, pas une préférence : la vitrine persuade, l'application opère, et sur
   une surface d'opération l'expression n'a jamais le droit de masquer l'état.
   Vérifié en production : une capture pleine hauteur du tableau de bord
   montrait 85 pendant que le bandeau annonçait 100 — le chiffre était encore
   en route. Un écran de travail qui affiche une valeur fausse pendant une
   seconde ment pendant une seconde.
2. **Rien ne glisse : un changement d'état saute d'un cran entier.**
   `--pas: 260ms cubic-bezier(.16, 1, .3, 1)`. La discipline est portée par la
   discrétisation du déplacement — on bouge d'une ligne entière, jamais d'une
   fraction — et non par un dépassement élastique : le détecteur d'`impeccable`
   a relevé le premier réglage (dépassement à 1,15) comme un rebond, et il
   avait raison. Un ressort sur une valeur mesurée se lit comme une
   hésitation.
3. Transitions d'interface : `--vif: 120ms ease-out` (survol, appui),
   `--calme: 220ms cubic-bezier(.22, 1, .36, 1)` (apparition, dépliage).
4. Une sortie est plus rapide qu'une entrée (×0,7).
5. **Aucun contenu ne dépend d'une animation.** L'état final est l'état par
   défaut ; l'animation part de là et y revient.
6. `@media (prefers-reduced-motion: reduce)` : toutes les durées à 0,01 ms, le
   compteur affiche directement sa valeur, la liste d'alertes est rendue
   complète, le curseur « maintenant » est posé à sa place.
7. Jamais d'animation de `width`/`height` ; `transform` et `opacity`, plus
   `clip-path` et `filter` là où ils restent fluides.

---

## 7. Les surfaces du navigateur

Le point que le plancher de qualité signale comme le plus souvent oublié.
Toutes thématisées depuis la palette, dans `tokens.css` :

- `::selection` : fond `--action-voile`, texte `--encre` (et `--action-clair`
  sur bâti) ;
- `caret-color: var(--action)` sur tout champ de saisie ;
- `scrollbar-color: var(--reglure-forte) transparent` + `scrollbar-width: thin`,
  et la variante sur bâti ;
- `accent-color: var(--action)` pour cases à cocher et curseurs natifs ;
- anneau de focus unique : `outline: 2px solid var(--action)`,
  `outline-offset: 2px`, sur `:focus-visible` seulement, avec la variante
  `--action-clair` sur bâti ;
- `text-underline-offset: 0.18em`, `text-decoration-thickness: 1px` sur les
  liens de texte ;
- `font-variant-numeric: tabular-nums` sur toute colonne de chiffres ;
- `color-scheme: light` déclaré, pour que les contrôles natifs ne basculent
  pas en sombre sur la face claire.

---

## 8. Les composants clés

| Composant | Rôle | États livrés |
|---|---|---|
| `BandeauEtat` | Le signal. Niveau + phrase + action unique. Présent sur les trois surfaces. | 4 crans, gorgé en `critique`, chargement, indisponible |
| `Rail` | Navigation permanente sur bâti. Replié en barre basse sous 900 px. | actif, survol, focus, replié, section hors offre (402) |
| `Panneau` | Le bloc d'instrument : tête réglée, corps, pied d'actions. | normal, chargement, vide, erreur, hors offre |
| `Jauge` | Score d'exposition sur 100, avec son cran et son glyphe. | 4 crans + inconnu |
| `Serie` | Série temporelle avec curseur « maintenant » (souris + flèches). | données, données partielles, vide |
| `Tableau` | Le tableau professionnel : tri, filtres, recherche, sélection, pagination, densité. Conservé de la refonte précédente, re-vêtu. | tri, vide, chargement, aucun résultat, sélection |
| `Chip` | État en un mot + glyphe + couleur de cran. | 4 crans de risque, 3 crans opérationnels, neutre |
| `Bouton` | `principal`, `second`, `discret`, `danger`. | repos, survol, appui, focus, occupé, désactivé |
| `Champ` | Libellé visible, aide, erreur au champ. | repos, focus, erreur, désactivé, lecture seule |
| `Adresse` | Le fil qui dit où l'on est (relèvement « téléscripteur »). | — |
| `Palette` | `Ctrl/⌘ + K`, va à n'importe quel écran. | vide, résultats, aucun résultat |
| `Age` | « il y a 3 jours », avec la date exacte en `title` (relèvement « âge »). | — |

Les deux profils, sur le même écran :

| | Dirigeant | Technique |
|---|---|---|
| Densité | confortable (46 px) | compacte (34 px) |
| Tête d'écran | une phrase + la décision à prendre | le compte d'objets + les filtres |
| Indicateurs | 3 au maximum, chiffrés en `.n-grand` | tous, en colonnes triables |
| Tableaux | 5 lignes, les plus urgentes, puis « voir tout » | pagination complète, densité, export |
| Vocabulaire | « ce domaine n'est pas protégé contre l'usurpation » | « SPF absent, DMARC p=none » |
| Série | 90 jours, un seul tracé | 90 jours, tracés superposés, curseur mobile |

---

## 9. Budget

Mesuré avant / après à chaque surface, et reporté dans le rapport final :
poids JS et CSS du lot principal, hauteur des pages de la vitrine, nombre de
requêtes de police. Objectif : ne pas dépasser le poids d'avant la refonte,
les deux familles variables remplaçant Fraunces + Inter.

---

## 10. Contrat de finition

Cette refonte n'est pas finie tant que, pour chaque surface : la passe
`impeccable detect` est passée et ses constats traités, Vitest et Playwright
sont verts, axe-core ne remonte rien en `critical`/`serious`/`moderate`, il n'y
a aucun débordement horizontal à 390 px, aucune erreur console, et les captures
avant/après existent en bureau et en téléphone.
