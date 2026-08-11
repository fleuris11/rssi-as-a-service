# 016 — Score d'exposition déterministe et explicable

- **Statut** : Adopté ; implémenté en Phase 8B
- **Date** : 2026-08-11

## Contexte

La Phase 8B introduit le « fil d'exposition » : les actifs d'un tenant classés
par niveau d'exposition, plutôt qu'une liste plate de fuites. Ce classement
suppose un **score par actif**.

Ce score n'est pas un indicateur interne : il est affiché au dirigeant, il
ordonne ce qu'il voit en premier, et il sera **montré en démonstration
commerciale**. Un prospect qui demande « pourquoi 78 et pas 40 ? » doit
obtenir une réponse exacte, pas une approximation. Un client qui traite une
fuite doit voir le score baisser, et comprendre de combien.

La plateforme dispose par ailleurs d'un pipeline IA (ADR-004/005) : la
tentation de « demander un score à l'IA » existe, et il fallait la trancher
explicitement plutôt que par omission.

## Options étudiées

**A. Score produit par l'IA** (envoyer les fuites au modèle, lui demander une
note sur 100).
Rejeté, pour trois raisons distinctes :
1. **Non-reproductible** : deux appels sur les mêmes données peuvent rendre
   deux notes différentes. Un score qui bouge sans que rien n'ait changé
   détruit la confiance plus sûrement qu'un score imparfait mais stable.
2. **Non-justifiable** : on ne peut pas décomposer « pourquoi 78 » ; au mieux
   on demande au modèle de s'expliquer, ce qui produit une justification
   *plausible*, pas la cause réelle du chiffre.
3. **Coût et disponibilité** : le score serait indisponible quand l'IA l'est
   (quota épuisé, panne fournisseur, IA désactivée par le tenant via
   US-4.3) — or c'est l'ossature de la page principale, elle doit s'afficher
   toujours.

**B. Score déterministe, calculé côté serveur, dont les composantes sont
restituées avec le total.**
Retenu.

**C. Pas de score du tout, seulement un tri par sévérité maximale.**
Rejeté : ne distingue pas un actif portant une fuite critique isolée d'un
actif en portant cinq, et ne permet aucune progression visible quand le
dirigeant traite des fuites.

## Décision

1. **Calcul entièrement déterministe** (`apps/threat_intelligence/exposure.py`),
   sans aucun appel IA. La synthèse IA de la Phase 8B (tâche 4) est une
   **lecture** de l'exposition, jamais sa **mesure** — la distinction est
   nette dans le code : deux modules, deux chemins, aucune dépendance.

2. **Quatre facteurs**, dans cet ordre d'importance :
   - **Sévérité** (poids de base) : critique 40, élevée 22, attention 8. Les
     écarts sont volontairement larges pour qu'une fuite critique pèse
     structurellement plus que plusieurs fuites mineures.
   - **Fraîcheur** (multiplicateur) : < 1 mois ×1,0 ; < 3 mois ×0,85 ;
     < 1 an ×0,6 ; au-delà ×0,35. Une fuite de 2019 n'appelle pas la même
     urgence qu'une fuite de la semaine dernière — le mot de passe a
     généralement déjà changé. Calculé sur la date de fuite quand le
     fournisseur la donne, sinon sur la date de détection (jamais rien : une
     fuite sans date échapperait sinon à tout amortissement).
   - **Secret réellement récupérable** (+10) : un finding dont le secret est
     déchiffrable (ADR-014) est immédiatement exploitable. Le drapeau
     `has_secret` seul ne suffit pas — les findings antérieurs au
     chiffrement le portent sans blob déchiffrable et ne doivent pas
     bénéficier du bonus.
   - **Statut** : seules les fuites **ouvertes** entrent dans le calcul.
     Traiter une fuite fait donc baisser le score — c'est ce qui rend le
     geste gratifiant, et c'est testé explicitement.

3. **Contributions décroissantes et plafond à 100** : les fuites d'un même
   actif sont triées par poids décroissant, puis la n-ième contribue
   `poids × 0,6^(n-1)`. Sans cet amortissement, dix fuites anciennes et
   mineures dépasseraient une fuite critique fraîche — l'inverse de ce que
   le dirigeant doit lire. Le tri par poids **décroissant** (et non l'ordre
   d'arrivée) garantit en outre que traiter la fuite la plus grave ne fait
   jamais *remonter* la contribution d'une autre.

4. **Restitution obligatoire des composantes** : `compute_exposure_score`
   renvoie toujours, avec le total, une ligne par fuite indiquant les points
   apportés et **pourquoi** (« gravité critique, fuite moins d'un mois, mot
   de passe récupérable, 3e fuite sur cet actif, pondérée à la baisse »).
   L'API les expose, l'interface les affiche sous « Comment ce score est
   calculé ». Un score sans son explication n'est pas livrable.

5. **Seuils de niveau en configuration**, pas en dur
   (`EXPOSURE_LEVEL_THRESHOLDS`) : calme < 20 ≤ à surveiller < 50 ≤
   préoccupant < 75 ≤ critique. Ce sont des curseurs produit, appelés à
   bouger après retours clients sans toucher au calcul.

## Conséquences

- Le score s'affiche toujours, y compris IA désactivée, quota épuisé ou
  fournisseur en panne — c'est l'ossature de la page principale.
- Les valeurs (40/22/8, ×0,6, +10) sont des **choix produit assumés**, pas
  des constantes dérivées d'un modèle de risque formel. Elles sont
  regroupées en tête de module, nommées, et modifiables en un endroit ; les
  tests portent sur les **propriétés** (ordre relatif, bornes, effet du
  traitement) plutôt que sur des valeurs exactes, pour qu'un ajustement de
  barème ne casse pas la suite sans raison.
- Le plafond à 100 signifie qu'un actif très exposé sature : au-delà d'un
  certain point, le classement entre deux actifs « à 100 » se fait au nombre
  de fuites. Accepté — l'action attendue est la même dans les deux cas.
- Un futur besoin de pondération par **type d'actif** (un VPN vaut-il plus
  qu'un site vitrine ?) n'est pas couvert : tous les actifs déclarés sont
  traités à égalité. À rouvrir si les retours clients le demandent, dans un
  ADR complémentaire.
