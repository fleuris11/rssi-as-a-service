# ADR-028 — Modèle d'indicateurs de comité

- **Statut** : accepté
- **Date** : 2026-09-09
- **Contexte** : ajoute une restitution périodique par-dessus les mesures
  existantes (ADR-016 score d'exposition, diagnostic ANSSI, plan d'action,
  surveillance) ; s'appuie sur la leçon de performance du 06/09/2026

## Contexte

Le besoin n'est pas « ajouter des graphiques ». Un RSSI prépare un comité
mensuel ou trimestriel, et aujourd'hui il rouvre quatre écrans, recopie des
chiffres dans un tableur, et reconstruit à la main une évolution que le
produit possède déjà. L'objectif est de **supprimer une soirée de travail par
mois**.

Ce que le produit avait : quatre mesures justes, toutes instantanées. Ce qui
manquait : une période, une comparaison, et un document.

## Décision 1 — Quatre familles d'indicateurs, jamais fusionnées

| Famille | Ce qu'elle mesure | Source |
|---|---|---|
| **Exposition** | ce qui circule à propos de l'entreprise | fuites ouvertes, score ADR-016 |
| **Maturité** | ce que l'entreprise a mis en place | diagnostic ANSSI |
| **Plan d'action** | ce qui avance | plan généré à la clôture du diagnostic |
| **Surveillance** | ce qui tient | contrôles, alertes, certificats |

**Aucun score global de sécurité n'est produit.** C'est la décision la plus
structurante de cet ADR, et c'est un refus.

Une moyenne de la maturité et de l'exposition monterait quand l'entreprise
remplit un questionnaire et descendrait quand un fournisseur se fait pirater —
deux variations qu'aucune action commune n'explique. Le chiffre serait
ininterprétable : un dirigeant qui le voit baisser ne saurait pas s'il doit
former ses équipes ou changer des mots de passe. Pire, il rendrait les **deux**
mesures injustifiables, puisqu'aucune des deux ne pourrait plus être défendue
séparément.

Le rapport et l'écran le disent explicitement au lecteur, plutôt que de
compter sur son bon sens : la moyenne se fabriquerait sinon dans le tableur
d'à côté.

## Décision 2 — Le passé se reconstruit, il ne se stocke pas

Chaque indicateur est daté et comparable à la période précédente. Deux façons
d'y arriver :

**A. Une table d'instantanés quotidiens**, alimentée par une tâche planifiée.
Rejeté comme mécanisme principal, pour une raison de calendrier : elle ne
produirait aucun historique avant un mois de fonctionnement, or le besoin est
immédiat — le premier comité a lieu avant. Elle ajouterait aussi une table qui
peut diverger de la réalité (une tâche qui n'a pas tourné laisse un trou
silencieux).

**B. Reconstruire depuis les horodatages existants.** Retenu. Les données
portent déjà leur histoire : `detected_at` et `treated_at` pour une fuite,
`completed_at` et `score_global` pour un diagnostic, `checked_at` pour un
contrôle. « Ouvert au 15 juin » se calcule, il n'a pas à être mémorisé.

Conséquence directe : **l'historique existe dès la mise en service**, sur
toute la profondeur des données.

Deux ajustements ont été nécessaires pour que cette reconstruction soit
juste :

- une fuite **ignorée** ne datait pas sa clôture (seul « traité » le faisait).
  Reconstruire l'état de juin aurait compté comme ouvertes des fuites que le
  client avait fermées ;
- une action du plan n'avait ni **échéance** ni **date de fin**. « En retard »
  ne pouvait pas exister — sans échéance, rien n'est en retard — et
  « terminées ce trimestre » se serait appuyé sur `updated_at`, qui bouge à la
  moindre correction de note.

Ce qui n'est pas reconstructible est dit comme tel : les fuites ignorées
**avant** cette version n'ont pas de date de clôture, et sont comptées comme
closes depuis toujours. Le choix minore le passé plutôt que de gonfler le
présent — entre deux erreurs, celle qui n'inquiète pas à tort.

## Décision 3 — Tout agrégé en base, mesuré avant d'être décidé

CLAUDE.md pose la règle Green IT ; la production a fourni le chiffre. Le
06/09/2026, matérialiser 28 450 instances Django coûtait 3,79 s, et un
`defer()` sur les colonnes larges n'y changeait rien : **le coût est celui des
objets, pas des données**. Un tableau de bord qui interroge plusieurs dates
referait la même faute, multipliée.

Mesures faites sur un jeu reproduisant le volume réel :

| | Avant | Après | |
|---|---|---|---|
| Score d'exposition à une date | 4,56 s (objets Django) | 0,85 s (n-uplets) | **×5,4** |
| Lecture des colonnes du score | 0,92 s (5,0 Mo de secrets chiffrés) | 0,72 s (booléen calculé en base) | ×1,3 |
| Série « ouvertes jour par jour » sur 91 jours | 91 requêtes attendues | **3 requêtes** | |
| Tableau de bord complet, 28 450 fuites | — | **35 requêtes, 1,77 s** | |

Deux enseignements, dont un contre mon hypothèse de départ :

1. le gain vient presque entièrement du **refus de matérialiser des objets**
   (×5,4) ;
2. j'avais supposé que rapatrier la colonne chiffrée dominait le coût. La
   mesure dit ×1,3 : réel, mais secondaire. La première version du banc ne
   contenait d'ailleurs aucun secret et concluait à tort que ce transport ne
   coûtait rien.

La série quotidienne mérite d'être explicitée, parce qu'elle est le piège
naturel de ce genre d'écran : « combien de fuites ouvertes chaque jour ? » se
traduit spontanément par une boucle sur les jours. On fait autrement — une
requête pour les détections par jour, une pour les clôtures par jour, un
compte au début de la période, puis une somme cumulée sur des seaux
quotidiens. **Le nombre de requêtes ne dépend pas du volume**, et c'est
exactement ce que le test vérifie : un budget de temps échouerait selon la
machine, un budget de requêtes décrit une propriété du code.

## Décision 4 — Une app `reporting`, sans modèle

CLAUDE.md fixe la liste des apps. Celle-ci s'y ajoute, et le mérite d'être
justifié.

La restitution de comité traverse le diagnostic, le plan d'action, la
surveillance et le renseignement. La loger dans l'une des quatre aurait été
arbitraire et y aurait fait entrer les trois autres. Elle ne possède **aucun
modèle** : chaque app calcule ses propres indicateurs, sur ses propres tables,
par son `services.py` ; `reporting` compose, ajoute la période et la
comparaison, et rend le document.

C'est ce qui permet de tenir les deux contraintes à la fois : la règle
d'architecture (une app n'atteint jamais les modèles d'une autre) et les
agrégats en base (le SQL est écrit là où vivent les tables).

## Décision 5 — Un document, pas un export de base

Le rapport PDF est écrit **pour une direction**, pas pour un RSSI : la
personne qui le reçoit n'a pas le vocabulaire, n'ouvrira pas le produit, et
décide quand même. Chaque chiffre est donc accompagné de ce qu'il veut dire,
l'évolution est écrite en toutes lettres (un PDF n'a pas d'infobulle : une
flèche verte sans phrase laisse deviner si monter est une bonne nouvelle), et
le document est autonome — aucune image, aucune police téléchargée, il doit
s'ouvrir hors ligne dix ans plus tard.

Les « faits marquants » et le « reste à faire » sont **déterministes** : des
règles, pas une IA. Un document présenté à une direction doit être
reproductible, et chaque phrase justifiable par un chiffre du tableau.

La construction est séparée du rendu (`build_html` / `render_pdf`) : le fond
du rapport est ainsi testable sur toute machine, y compris celles où le moteur
de rendu système (ADR-012) n'est pas installé.

L'export tableur reprend **exactement** les chiffres de l'écran. Si les deux
divergeaient, le RSSI recommencerait à tout recalculer à la main — c'est-à-dire
que cette version n'aurait servi à rien.

## Décision 6 — Deux graphiques, et la question qu'ils posent

La consigne interdisait le graphique décoratif : si la question n'est pas
formulable, le graphique ne se fait pas. Deux ont survécu :

- **compromissions ouvertes, jour par jour** → *est-ce que le stock baisse ?*
  Un chiffre isolé ne peut pas y répondre : 14 fuites ouvertes est une bonne
  nouvelle si on partait de 40, une mauvaise si on partait de 3. Une seule
  courbe, pas de découpage par gravité — trois courbes répondraient à une
  question que personne ne pose en comité et rendraient la première illisible ;
- **exposition par actif** → *sur quel actif agir en premier ?* Rendu en
  barres alignées plutôt qu'en graphique : avec trois à dix actifs, une barre
  n'apporte rien qu'un nombre aligné ne dise déjà.

Écarté : un graphique de la maturité. Avec un à deux diagnostics par an, une
courbe à deux points est une décoration. Le chiffre et l'écart suffisent.

## Conséquences

- Deux colonnes ajoutées à `ActionItem` (`due_date`, `completed_at`), avec un
  remplissage qui **approxime** la date de fin par `updated_at` pour les
  actions déjà faites. C'est une approximation, elle est dite : la vraie date
  n'a jamais été enregistrée, et la seule alternative honnête — laisser vide —
  ferait disparaître du tableau de bord tout le travail accompli avant cette
  version.
- Le score d'exposition existe désormais en deux implémentations : celle du
  fil (avec ses composantes explicables) et celle du tableau de bord (totale,
  sans objets). Un test vérifie qu'elles donnent **exactement** le même
  chiffre — deux calculs qui divergeraient seraient pires que pas de tableau
  de bord, puisque l'écran de détail et le tableau se contrediraient.
- La période est résolue **côté serveur**. Le frontend n'en calcule aucune :
  deux implémentations du même trimestre finiraient par diverger, et l'écart
  se verrait le jour où le PDF ne dirait pas la même chose que la page.

## Ce que cette décision ne fait pas

- Elle **n'introduit aucune table d'instantanés**. Le jour où un indicateur ne
  sera plus reconstructible (une valeur qui n'existe qu'à l'instant où on la
  mesure), il faudra la stocker — et ce sera une décision distincte.
- Elle **ne planifie ni n'envoie** le rapport. Il se produit à la demande. Un
  envoi automatique mensuel est une évidence de produit, mais il suppose de
  décider à qui, à quelle date, et ce qu'on fait quand la période est vide.
- Elle **ne compare pas à d'autres entreprises**. Un « vous êtes dans la
  moyenne de votre secteur » supposerait un référentiel qui n'existe pas, et
  publierait indirectement la situation des autres clients.
