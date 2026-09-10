# ADR-030 — Consolider plusieurs référentiels : la règle

- **Statut** : accepté
- **Date** : 2026-09-09
- **Contexte** : V2-4, suite de [ADR-029](029-referentiels-multiples-et-attribution.md).
  Prolonge le refus posé par [ADR-028](028-modele-d-indicateurs-de-comite.md)
  (pas de score global de sécurité) au cas de deux référentiels.

## Contexte

Un client peut désormais suivre l'ANSSI **et** ISO 27001. La fiche V2-4 demande
un score « par référentiel ET en consolidé », en prévenant : *« consolider deux
référentiels qui ne mesurent pas la même chose demande une règle explicite.
Propose-la et documente-la — ne l'invente pas en silence. »*

Le piège est réel. Les 42 mesures de l'ANSSI et les 93 contrôles de l'annexe A
d'ISO 27001 ne sont ni le même nombre, ni la même granularité, ni le même
propos : le guide d'hygiène est une liste de gestes techniques pour une PME,
l'annexe A est le catalogue de contrôles d'un système de management. Un
diagnostic à 80 % sur l'un et 40 % sur l'autre ne décrit pas une entreprise
« à 60 % ».

## Décision 1 — Le consolidé est la moyenne NON pondérée des scores par référentiel

Chaque référentiel compte pour un, quel que soit son nombre de mesures. On
prend, pour chacun, le score figé de son dernier diagnostic terminé, et on en
fait la moyenne.

**Pourquoi pas une moyenne pondérée par le nombre de mesures** (autrement dit :
verser toutes les mesures dans un même dénominateur). Avec 42 mesures d'un côté
et 93 de l'autre, ISO déciderait de 69 % du chiffre. Personne ne l'aurait
choisi, et rien ne le justifierait : le nombre de contrôles d'un référentiel
dit sa granularité d'écriture, pas son importance.

**Pourquoi pas une déduplication des exigences qui se recouvrent.** Ce serait
plus juste — l'ANSSI et l'ISO demandent tous deux de gérer les mots de passe —
mais nous n'avons aucune table de correspondance entre référentiels, et en
fabriquer une reviendrait à décider nous-mêmes que telle mesure et tel contrôle
sont la même exigence. Ni l'ANSSI ni l'ISO ne l'affirment. Une correspondance
inventée par nous serait invisible dans le chiffre et indéfendable en comité.

**Pourquoi une moyenne tout de même, et pas rien.** Un dirigeant qui suit deux
référentiels a besoin d'une phrase, pas d'un tableau à deux entrées. La moyenne
« un référentiel = une voix » est arbitraire mais **explicable en une phrase**,
ce qui est le seul critère qui tienne devant un comité.

## Décision 2 — Le consolidé ne circule jamais seul

Toute réponse d'API qui porte un consolidé porte aussi :

- `by_referential` : le score de chacun, sa date, son nombre de mesures, et si
  le référentiel est encore attribué ;
- `method` : le nom de la règle (`moyenne_par_referentiel`) ;
- `unscored_referentials` : les référentiels attribués mais **pas encore
  évalués**, qui n'entrent pas dans le calcul. Les taire ferait passer le
  chiffre pour une image complète.

L'écran de résultats affiche le détail au-dessus du consolidé, et la règle en
sous-titre. C'est la même exigence qu'ADR-016 pour le score d'exposition : un
chiffre qui ne dit pas comment il est fabriqué n'est pas défendable.

## Décision 3 — Pas de progression entre deux ensembles différents

L'indicateur de maturité du comité (ADR-028) compare le consolidé courant au
précédent. La comparaison n'est calculée **que si chaque référentiel du
consolidé courant a lui aussi un diagnostic antérieur**. Sinon, `delta` vaut
`null`.

Sans cette règle, un client qui évalue ISO pour la première fois verrait sa
« progression » bouger — vers le haut ou vers le bas selon le résultat — alors
qu'aucune progression n'a eu lieu nulle part. Le chiffre aurait varié parce que
l'ensemble comparé a changé, pas parce que l'entreprise a fait quoi que ce soit.

Pour un client à un seul référentiel — c'est-à-dire tous ceux d'aujourd'hui —
la règle se réduit exactement au comportement d'avant V2-4.

## Décision 4 — Le plan d'action se consolide, lui, sans arbitrage

Un score est une opinion sur un ensemble ; une action est une chose à faire.
Le plan consolidé est donc simplement l'union des actions de tous les
référentiels, chaque ligne portant le sien (`referential_name`), avec un filtre
`?referential=<slug>` pour ne voir qu'un cadre.

Deux référentiels qui demandent la même chose donnent **deux lignes**, côte à
côte. C'est un peu redondant et c'est volontaire : les fusionner demanderait la
table de correspondance qu'on a refusé d'inventer, et masquer l'une des deux
ferait disparaître une exigence d'un référentiel que le client doit tenir. Les
indicateurs de plan portent eux aussi leur `by_referential` : un taux
d'avancement global de 40 % qui recouvre 80 % sur l'ANSSI et 10 % sur ISO ne
dit pas la même chose que 40 % partout.

## Conséquences

Le consolidé est **calculé à la lecture**, jamais stocké : il n'y a rien à
migrer si la règle change, et une règle stockée dans des instantanés serait
impossible à corriger rétroactivement. Les scores par référentiel, eux, restent
les instantanés figés à la clôture (`Assessment.score_global`) — recalculer le
score de juin avec le référentiel de septembre ne donnerait plus le score de
juin.

Si une table de correspondance entre référentiels apparaît un jour, elle
justifiera un nouvel ADR : la règle changerait, et le chiffre affiché à un
client changerait avec elle. Ce n'est pas une modification à faire en silence.
