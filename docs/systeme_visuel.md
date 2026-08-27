# Système visuel — RSSI as a Service

> Source unique : `frontend/src/index.css` (bloc `@theme` + utilitaires).
> Ce document explique **pourquoi**. Le code fait foi pour les valeurs.

Direction : moderne et épuré, avec une gravité assumée. Le registre visé est
celui d'un outil professionnel qu'on a plaisir à ouvrir — ni rapport d'audit
austère, ni tableau de bord technique surchargé. Le lecteur type est un
dirigeant de PME, pas un ingénieur sécurité.

---

## La règle qui commande toutes les autres

**La couleur porte le niveau de risque. Elle ne décore pas.**

Si la même teinte sert à un bouton d'action et à une fuite critique, elle ne
signifie plus rien. C'est exactement ce qui était arrivé, et le constat est
mesurable : sur la page Compromissions, **onze boutons ambre pleins** — dix
« Marquer traité » et « Lancer un scan » — voisinaient avec des encadrés
« À faire » ambre, des bandeaux « Réutilisation possible » ambre et des badges
« À traiter » ambre. L'ambre était devenu la texture de fond de la page.

Trois familles, étanches :

| Famille | Ce qu'elle dit | Où |
|---|---|---|
| `risk-*` | une **gravité graduée** | scores, badges de sévérité, bordures de carte |
| `ok` / `warning` / `critical` | un **état opérationnel** binaire ou ternaire | actif joignable ou non, abonnement actif ou expiré, certificat valide |
| `brand` / `ink` | l'**interface** : actions, structure, texte | boutons, navigation, bordures, fonds |

`accent` (l'ambre de la marque) ne porte **ni** action **ni** risque : il reste
la couleur de la signature et du logo.

### Pourquoi l'action est passée en bleu

L'ambre était la couleur de l'action primaire, et sa version foncée
(`accent-700`, #a3660a) est à quelques degrés de `warning-strong` (#8e5e0b).
Deux issues possibles : déplacer le risque hors du spectre chaud, ou déplacer
l'action. Déplacer le risque aurait forcé une échelle de gravité contre-intuitive
(le rouge doit rester le rouge). L'action est donc passée sur le **bleu de
marque**, déjà la couleur de la barre latérale et du logotype — ce qui libère
tout le spectre chaud pour la seule gravité.

Blanc sur `brand-600` : **8,24:1**.

---

## Échelle de gravité — quatre niveaux

Alignée sur les seuils d'ADR-016, qui vivent dans les réglages Django :

```
calme < 20 ≤ à surveiller < 50 ≤ préoccupant < 75 ≤ critique
```

Le serveur renvoyait déjà ces quatre paliers. L'interface n'en connaissait que
trois couleurs et empruntait `accent` pour le quatrième — c'est-à-dire la
couleur des boutons.

| Niveau | Jeton | Texte sur blanc | Texte sur son fond |
|---|---|---|---|
| Calme | `risk-calm` #22775b | 5,44:1 | 4,79:1 |
| À surveiller | `risk-watch` #8a5a08 | 5,92:1 | 5,42:1 |
| Préoccupant | `risk-concern` #a8431c | 6,03:1 | 5,33:1 |
| Critique | `risk-critical` #bc242c | 6,13:1 | 5,44:1 |

Chaque niveau a trois jetons : `-strong` (texte, trait), `-surface` (fond
teinté), `-border` (filet).

**Contrastes calculés, pas estimés.** Un contraste jugé à l'œil est un
contraste faux : c'est axe-core, pas la relecture, qui avait attrapé
`ink-500` en phase 5.

**La couleur n'est jamais seule.** Le niveau est toujours écrit à côté du
chiffre ou du badge. Un daltonien doit lire la même information.

### Le niveau vient du serveur

`ScoreGauge` accepte `level`, la clé renvoyée par l'API, et c'est elle qui
décide de la teinte. Redériver le niveau à partir du score côté client ferait
qu'un ajustement de seuil en base ne se verrait jamais à l'écran. Le calcul
local n'est qu'un repli, pour les scores sans niveau serveur.

---

## Une jauge, deux échelles, le sens toujours écrit

Le défaut le plus grave trouvé au diagnostic n'était pas esthétique :

- maturité ANSSI (tableau de bord, résultats) : **80 est bon**, anneau vert ;
- exposition : **80 est mauvais**, anneau rouge.

Deux anneaux de même forme et de même taille, deux échelles inverses, **et
rien à l'écran pour prévenir**. En démonstration, cela peut faire dire
l'inverse de la réalité à un dirigeant.

`ScoreGauge` remplace les deux composants. Il prend un `scale`
(`exposure` | `maturity`) et affiche, sous le chiffre, la phrase qui lève
l'ambiguïté : « Sur 100 — plus le chiffre est haut, plus le risque est
élevé » / « … meilleure est la maturité ».

---

## Typographie — six rôles

Le défaut n'était pas l'absence de tailles mais leur non-emploi : sur
Exposition et Compromissions, **35 usages sur 38 étaient `text-sm` ou
`text-xs`**, soit 14 ou 12 px. Entre le titre de page et le corps, il n'y
avait rien — donc, dans une carte, le titre d'une fuite, son explication et
l'action à mener pesaient pareil.

Des **rôles** plutôt que des tailles : une page déclare ce qu'un texte *est*,
pas sa dimension. Une taille se choisit au cas par cas et dérive ; un rôle se
relit.

| Rôle | Emploi | Fonte |
|---|---|---|
| `.t-display` | titre de page | Fraunces 30 px |
| `.t-title` | titre de section ou de carte | Fraunces 20 px |
| `.t-lead` | la phrase qu'on lit si on n'en lit qu'une | Inter 17 px |
| `.t-body` | texte courant | Inter 15 px |
| `.t-meta` | métadonnée, second plan | Inter 13 px |
| `.t-eyebrow` | étiquette de section | Inter 11 px, capitales espacées |

**Deux familles, deux fonctions.** *Fraunces* — serif légèrement éditorial —
ne sert qu'aux titres et aux chiffres de tête : un lecteur non technique lit
un titre en serif comme quelque chose de réfléchi, pas de froid. C'est ce qui
empêche l'interface de se lire comme un gabarit d'administration. *Inter*
porte tout le reste : elle est dessinée pour les petites tailles à l'écran, ce
que Fraunces n'est pas.

**Chargement sans saut visuel** : les deux familles sont auto-hébergées
(`@fontsource`), sous-ensemble latin/latin-ext uniquement — l'interface est
en français, inutile d'expédier le cyrillique (exigence Green IT). Aucun appel
à un CDN tiers, donc aucun rendu de repli visible.

---

## Rythme d'espacement — trois valeurs, pas un continuum

L'application utilisait tout l'intervalle de 8 à 24 px. Rien ne distinguait
« dans un bloc » de « entre deux sections » : donc aucun rythme, donc un mur
continu de 3 138 px de haut sur Exposition (6 358 px au téléphone).

| Jeton | Valeur | Ce qu'il sépare |
|---|---|---|
| `--space-tight` | 8 px | des éléments d'un même bloc |
| `--space-block` | 20 px | des blocs d'une même section |
| `--space-section` | 40 px | des sections entre elles |

Utilitaires : `.stack-tight`, `.stack-block`, `.stack-section`. Ils posent la
marge sur `> * + *`, donc rien ne dépasse en haut ni en bas du conteneur et
les piles s'imbriquent sans correction manuelle.

L'écart entre les crans est franc **par choix** : trois valeurs proches ne se
distingueraient pas, et on retomberait sur le continuum.

---

## États interactifs

Tout élément interactif porte les six états : repos, survol, **focus visible**,
actif, désactivé, chargement.

**Un seul anneau de focus**, défini une fois dans `index.css` sur
`:focus-visible` — visible sur fond clair comme sur la barre latérale sombre.
Sur `:focus-visible` et non `:focus` : un anneau au clic souris est du bruit,
son absence au clavier est un défaut d'accessibilité.

`disabled` ne repose jamais sur la seule couleur : l'attribut natif et le
curseur la portent aussi.

---

## Mouvement

Une seule durée (`180 ms`) et une seule courbe, via `.transition-smooth`.
Opt-in plutôt que transition globale : une transition sur tout anime aussi les
recalculs de mise en page.

`prefers-reduced-motion` neutralise transitions et animations.

**Règle absolue, née d'un défaut de la phase 9 :** aucun contenu ne dépend du
déclenchement d'une animation pour être visible. Les apparitions au défilement
avaient produit un texte quasi noir signalé en défaut de contraste par axe —
il était mesuré en plein fondu. Un contenu qui n'apparaît qu'après une
animation est invisible pour qui la désactive, et pour un moteur d'audit.

---

## Ce qu'on n'utilise pas, et pourquoi

- **Dégradés multicolores** : datent immédiatement et brouillent le code
  couleur du risque.
- **Ombres portées lourdes** : deux niveaux d'élévation suffisent
  (`shadow-soft` au repos, `shadow-elevated` pour ce qui flotte). Les deux
  sont teintées du bleu de marque plutôt que noires — une ombre noire sur un
  fond teinté se lit comme une salissure.
- **Coins très arrondis partout** : `--radius-md` par défaut ; le très arrondi
  est réservé aux pastilles.
- **Icônes décoratives** : une icône sans fonction est du bruit. Toute icône
  est `aria-hidden` et double un texte, jamais ne le remplace.
- **Le rouge pour autre chose que le risque réel.**

---

## Portée

Ces jetons sont conçus pour les trois surfaces — espace client, vitrine
publique, console d'administration. Seul l'espace client les applique à ce
stade ; les deux autres suivront sans nouvelle décision.
