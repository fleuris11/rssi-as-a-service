# ADR-037 — Un centre de notifications dans l'application

- **Statut** : accepté
- **Date** : 2026-09-15
- **Contexte** : Lot C, point 20. Complète les emails existants (météo,
  alertes temps réel, signaux avant-coureurs) sans les remplacer.

## Contexte

Cinq fonctionnalités livrées dans les versions précédentes attendaient un
moyen de prévenir quelqu'un, et n'en avaient aucun : les demandes de
fonctionnalités, les demandes de référentiels, les comptes désignés, le
rapport de comité, la veille. Côté exploitant, une demande client n'était
visible qu'en ouvrant la console au bon onglet. Le produit envoyait des
emails pour la surveillance, mais rien dans l'application elle-même.

## Décision 1 — Une notification appartient à une personne, pas à un client

`Notification` n'est **pas** un `TenantScopedModel`. Elle porte un
destinataire (`recipient`) et, quand il y en a un, le client concerné
(`tenant`, facultatif).

Deux raisons. Les notifications de l'exploitant ne concernent aucun client en
particulier : les rattacher de force à un tenant n'aurait pas de sens. Et une
personne qui suit plusieurs entreprises doit lire ses notifications dans une
seule cloche, quel que soit le client sélectionné.

La lecture reste cloisonnée, en deux temps (`inbox.visible_for`) :
destinataire d'abord, puis, pour une notification rattachée à un client,
appartenance **actuelle** à ce client. Une personne qui a quitté une
entreprise ne voit plus ce qui la concerne, sans qu'il faille supprimer
quoi que ce soit.

### Alternative écartée : une ligne par client

Dupliquer chaque notification d'exploitant par client, ou exiger une
entreprise sélectionnée pour lire la cloche, aurait forcé l'exploitant — qui
n'est membre d'aucun client — à ne rien voir. C'est précisément le cas que la
consigne signale.

## Décision 2 — Un module d'interface sans dépendance métier

Les autres apps préviennent par `apps.notifications.inbox`, jamais par le
modèle (règle d'architecture n°1). Ce module est distinct de
`notifications/services.py`, qui compose les emails et importe pour cela la
surveillance, le renseignement et l'IA : une app qui voudrait simplement
prévenir un utilisateur aurait importé toute cette chaîne, et la première
dépendance circulaire aurait suivi. `inbox` ne dépend que des membres d'un
client, via `tenants.services`.

## Décision 3 — Idempotence tranchée en base

Une clé `dedupe_key`, unique par destinataire quand elle est renseignée
(contrainte partielle). Les tâches Celery sont relivrées, un double clic
arrive, et une même publication de veille peut être retenue puis intégrée :
la base refuse le doublon, même entre deux workers. Le rapport de comité
utilise `comite:<client>:<mois>`, la veille `veille:<publication>`, le suivi
d'une demande `demande:<id>:<statut>`.

## Décision 4 — Les branchements, et ce qu'ils ne font pas

| Événement | Qui est prévenu | Ce qui est volontairement exclu |
|---|---|---|
| Nouvelle demande d'un client | les administrateurs de la plateforme | le client lui-même |
| Suivi d'une demande | la personne qui l'a déposée | ses collègues |
| Compte désigné déclaré | les administrateurs de la plateforme | l'adresse surveillée (ADR-033) |
| Nouvelles fuites sur des comptes surveillés | les administrateurs actifs du client | l'adresse ; une analyse sans nouveauté |
| Publication de veille retenue ou intégrée | les administrateurs actifs des clients | une suggestion non triée ou écartée |
| Rapport de comité du mois écoulé | les administrateurs actifs des clients | un second envoi le même mois |

Un administrateur désactivé (salarié parti) n'est jamais destinataire.

## Décision 5 — Une cloche sobre

Le compteur est interrogé toutes les minutes, et seulement quand l'onglet est
visible. La liste, plus lourde, n'est chargée qu'à l'ouverture. La console
d'administration, hors du gabarit client, porte sa propre cloche, et une
notification d'exploitant ouvre directement l'onglet concerné
(`?onglet=requests`).

## Conséquences

- Tout nouvel événement métier se branche par `inbox.notify*`, avec sa clé
  d'idempotence et son test « qui ne doit PAS être prévenu ».
- Les notifications ne sont pas encore purgées : à prévoir avec la politique
  de conservation, quand leur volume le justifiera.
- Les emails restent le canal de l'urgence (alerte temps réel). La cloche est
  le canal du suivi.
