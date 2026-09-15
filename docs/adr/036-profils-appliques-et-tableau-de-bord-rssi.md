# ADR-036 — Des profils qui changent la restitution, un tableau de bord qui prépare le comité

- **Statut** : accepté
- **Date** : 2026-09-15
- **Contexte** : Lot C, parties C1 et C2. Prolonge ADR-031 (profil d'affichage)
  et ADR-028 (indicateurs de comité) sans revenir sur leurs décisions.

## Contexte

Deux constats de la revue du lot C :

1. **L'interrupteur Dirigeant / Technique ne changeait rien.** ADR-031 avait
   posé les bonnes règles — le serveur ignore le profil, rien n'est retiré —
   mais les primitives n'étaient appliquées qu'à deux écrans. Partout
   ailleurs, basculer ne produisait aucune différence visible. Mesuré : trois
   primitives, deux usages dans tout le frontend.
2. **Le tableau de bord ne préparait rien.** Un score, deux alertes, des
   raccourcis. L'API de restitution de la V2-3 savait déjà résoudre une
   période et la comparer à la précédente, mais seule la page « Rapports »
   s'en servait, et avec une seule courbe.

## Décision 1 — Toujours aucune réponse d'API qui dépende du profil

Rien ne change sur ce point, et c'est délibéré : le test qui compare les
charges utiles des deux profils reste la garantie « un même fait reste le même
fait ». Tout ce qui suit est de la PRÉSENTATION.

Un seul ajout serveur, qui ne dépend pas du profil : l'alerte de surveillance
expose sa signification et l'action attendue (`meaning`,
`recommended_action`), depuis la même source que l'email d'alerte. Sans ce
texte, une alerte ne pouvait pas « mener avec son impact » en profil
dirigeant — elle n'en avait pas.

## Décision 2 — Quatre primitives de plus, pas des conditions dispersées

`ProfileDate` (date lisible / horodatage à la seconde avec fuseau),
`TechnicalValue` (identifiant, code source : visible en technique, masqué —
jamais retiré — en dirigeant), `ScoreReading` (« 92 sur 100 — votre niveau
est solide », seuils lus dans la même table que la jauge) et `AlertReading`
(ordre de lecture : impact → action → constat replié, ou l'inverse).

Appliquées à la surveillance, aux compromissions, à l'exposition, aux
résultats, au plan d'action, à la veille et aux comptes surveillés.

**Replié ne veut plus dire retiré.** Le détail d'une fuite sortait du DOM tant
qu'on ne cliquait pas ; un test l'épinglait même (`not.toBeInTheDocument`).
C'était contraire à ADR-031 : il est désormais masqué, et l'attente du test a
été corrigée en le disant.

Un test par écran représentatif vérifie les deux moitiés de la consigne : le
texte VISIBLE diffère entre les deux profils, et le texte PRÉSENT (visible ou
non) contient les mêmes faits.

## Décision 3 — Les écrans techniques changent de place, ils ne disparaissent pas

En profil dirigeant, « Surveillance » et « Compromissions » descendent dans une
section « Détails techniques » du menu. Exposition reste en tête : c'est la
lecture priorisée des mêmes fuites. Un test vérifie que l'ensemble des
destinations est identique dans les deux profils.

## Décision 4 — Le tableau de bord lit l'API de restitution, et chaque courbe a sa question

Le tableau de bord ne recalcule rien. Période résolue par le serveur,
comparaison par défaut, sens des évolutions décidé une fois (ADR-028). Cinq
indicateurs, chacun avec sa valeur, sa tendance et le lien vers son écran.
Quatre courbes, chacune sous la question à laquelle elle répond — le composant
refuse de s'afficher sans question — et avec sa lecture écrite en toutes
lettres.

Une courbe n'est pas dessinée quand elle n'aurait rien à montrer : un seul
diagnostic sur la période donne une phrase, pas un point isolé.

## Décision 5 — La courbe du score : une requête par point, choisie sur mesure

Le score d'exposition ne s'agrège pas en SQL (fraîcheur à la date du point).
Deux implémentations ont été écrites et mesurées sur 28 450 fuites :

| Chemin | Requêtes | Temps (meilleur de 3) |
|---|---|---|
| `exposure_score_at` à chaque point | 13 | **0,33 s** |
| Une requête, état reconstruit en mémoire | 1 | 1,21 s |

La première mesure donnait déjà ce sens, mais sur un jeu biaisé (toutes les
fuites détectées « maintenant », chemin rapide passé en second sur un cache
chaud). Elle a été refaite avec des détections et des traitements répartis
sur six mois et des passages alternés (`test_performance_courbes.py`) avant
de conclure. **Retenu : une requête par point.** Le nombre reste FIXE —
treize — et ne dépend ni du volume ni de la durée.

Conséquence : le budget de requêtes du tableau de bord complet passe de 40 à
56. Ce qui est garanti n'a pas changé : il ne dépend pas du volume.

## Conséquences

- Un écran qui ajoute un champ technique doit passer par une primitive, sinon
  l'interrupteur recommence à ne rien faire.
- `CardHeader` ignorait la propriété `subtitle` : les questions des courbes de
  la page Rapports n'avaient jamais été affichées. Corrigé à part.
- Reste à faire : le rendu en navigateur réel des deux profils sur mobile.
