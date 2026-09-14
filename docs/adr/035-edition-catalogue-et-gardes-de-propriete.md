# ADR-035 — Éditer le catalogue sans le réécrire : propriété, compositions, import client

- **Statut** : accepté
- **Date** : 2026-09-15
- **Contexte** : lot B. Prolonge [ADR-029](029-referentiels-multiples-et-attribution.md)
  (référentiels multiples et attribution) et [ADR-030](030-consolidation-multi-referentiels.md)
  (consolidation).

## Contexte

La V2-4 avait livré les modèles de référentiels, de compositions et de
reformulations, et une partie de l'API. L'exploitant ne pouvait pourtant ni
importer un référentiel, ni en créer un, ni composer un questionnaire court,
ni reformuler un énoncé pour un client sans une commande Django ; le client ne
pouvait pas importer le sien. Constaté en production : un produit invisible.

En écrivant ces écrans, deux défauts sont apparus, et ils commandent les
décisions ci-dessous plus que l'ergonomie :

1. **`import_referential` identifiait le référentiel par son slug et le mettait
   à jour.** Un import portant l'identifiant du référentiel ANSSI en aurait
   remplacé le questionnaire — pour tous les clients.
2. **`create_subset` faisait de même pour les compositions.** L'API client
   existante permettait déjà à un client de composer avec l'identifiant d'un
   modèle de plateforme, et donc d'en réécrire les mesures pour tous les
   autres.

Aucun test ne le voyait : ils vérifiaient qu'on pouvait créer et mettre à jour,
jamais **qui** mettait à jour **quoi**.

## Décision 1 — La propriété est une garde, pas une convention

Un référentiel ou une composition a un propriétaire : la plateforme
(`owner_tenant` nul) ou un client. **Un import ou une composition ne remplace
jamais un objet d'un autre propriétaire.** La garde vit dans les services
(`import_referential`, `create_subset`), c'est-à-dire sous toutes les vues
— console, client, commandes — et non dans l'une d'elles.

### Options écartées

- **Contrôler dans chaque vue** : c'est précisément ce qui avait manqué ; la
  vue client de composition existait depuis la V2-4 sans ce contrôle.
- **Rendre les slugs uniques par propriétaire** (contrainte en base) : aurait
  demandé une migration de contrainte sur des tables en production, pour un
  bénéfice identique à une garde de service, et aurait laissé ouverte la
  question « à qui est `anssi-hygiene-informatique` ».

## Décision 2 — L'identifiant d'un référentiel importé par un client est imposé

Le client ne choisit pas l'identifiant : il est préfixé par celui de son
entreprise (`<client>-<nom>`), et **celui du fichier est ignoré avant toute
analyse**. Le référentiel est `custom`, appartient au client, lui est attribué
à la confirmation, et n'apparaît dans le catalogue d'aucun autre client.

Deux gardes plutôt qu'une : le préfixe évite les collisions ordinaires, la
garde de propriété (décision 1) tient même si le préfixe venait à être
contourné. Le message d'une collision ne nomme jamais le propriétaire : ce
serait apprendre à un client l'existence d'un autre.

## Décision 3 — Attribuer « un sous-ensemble » à un client, c'est composer pour lui

La consigne demandait d'attribuer « un ou plusieurs référentiels, ou
sous-ensembles ». **Aucun second mécanisme d'attribution n'est créé.** Une
composition sans propriétaire est un modèle de plateforme, proposé à tout
client à qui le référentiel est attribué ; une composition écrite *pour* un
client ne se propose qu'à lui. Composer pour un client exige que le
référentiel lui soit déjà attribué.

### Option écartée

Une table `SubsetAssignment` parallèle à `ReferentialAssignment` : deux
attributions à maintenir en cohérence (retirer le référentiel mais garder la
composition ?), pour exprimer ce que `owner_tenant` exprime déjà.

## Décision 4 — Aucun import en un seul geste

Console comme client : on **analyse** (toutes les erreurs, avec leur ligne),
on montre l'**aperçu** — y compris « ce référentiel existe déjà et sera mis à
jour pour tous ses clients » —, puis on **confirme**. Rien n'est écrit tant
qu'il reste une erreur, et l'écriture est atomique.

## Décision 5 — Un domaine d'autres apps ne se lit que par ses services

Le correctif du compteur « Clients : 0 » avait importé
`ReferentialAssignment` dans la console, en violation de la règle 1 de
CLAUDE.md. Le compte passe désormais par
`assessments.services.count_active_assignments`, et un test interdit
l'import du modèle dans la console.

## Conséquences

- Les deux défauts d'intégrité sont fermés et épinglés par des tests qui
  rougissent quand on retire la garde.
- Un exploitant qui veut **réellement** remplacer le référentiel d'un client
  ne peut pas le faire par un import de console : c'est voulu. Le chemin est
  de demander au client de réimporter, ou d'agir en base de façon tracée.
- Les compositions héritent des règles de retrait d'ADR-029 : retirer le
  référentiel à un client ne supprime ni ses compositions ni ses évaluations.
- **Dette** : la reformulation et la composition ne sont pas encore
  historisées (qui a changé quel énoncé, quand) au-delà du journal
  d'administration.
