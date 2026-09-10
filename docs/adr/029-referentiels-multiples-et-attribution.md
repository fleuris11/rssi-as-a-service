# ADR-029 — Plusieurs référentiels, attribués par client

- **Statut** : accepté
- **Date** : 2026-09-09
- **Contexte** : V2-4. Reprend le modèle de diagnostic posé en phase 2
  (Referential / Domain / Measure) et lève l'hypothèse d'un référentiel unique.
  Complété par [ADR-030](030-consolidation-multi-referentiels.md) pour la règle
  de consolidation.

## Contexte

Le modèle portait déjà trois entités qui *ressemblaient* à un catalogue —
`Referential`, `Domain`, `Measure`. En les relisant, quatre hypothèses ANSSI
étaient en réalité gravées dans le schéma et dans le code :

1. **`Measure.number` était un entier unique sur toute la base.** L'ANSSI
   numérote ses mesures de 1 à 42 ; ISO 27001 les nomme `A.5.1`, le NIST CSF
   `PR.AA-01`. Ni l'un ni l'autre n'entre dans un `PositiveSmallIntegerField`,
   et l'unicité globale interdisait même à deux référentiels d'avoir chacun
   une mesure n°1.
2. **Le poids d'une mesure dans le score vivait dans le code**, sous la forme
   d'une table `{standard: 1.0, renforcé: 0.5}` — les deux niveaux du guide
   d'hygiène. Un référentiel sans niveaux n'avait pas de place.
3. **`get_active_referential()` renvoyait « le » référentiel actif**, le même
   pour tous les clients. Il n'existait aucune notion de « ce client a droit à
   ceci ».
4. **« L'évaluation en cours » était unique par client**, pas par référentiel.

Rien de tout cela n'était un défaut à l'époque : il y avait un référentiel.
C'était une hypothèse juste, devenue fausse.

## Décision 1 — Le code d'une mesure est une chaîne, unique par référentiel

`Measure.code` (chaîne, 40 caractères) devient l'identifiant : `1` pour
l'ANSSI, `A.5.1` pour ISO, `PR.AA-01` pour le NIST. Une contrainte d'unicité
porte sur `(referential, code)`.

Django ne sait pas poser une contrainte d'unicité qui traverse une relation
(`domain__referential`). Le référentiel est donc **dénormalisé sur la mesure**,
posé et vérifié par l'importateur. C'est une redondance assumée : elle achète
la seule garantie qui compte ici — deux mesures du même référentiel ne peuvent
pas porter le même code.

`Measure.number` est **conservé**, devenu nullable et non unique. Il porte la
numérotation officielle quand le référentiel en a une, et le rapport de
vérification du référentiel ANSSI (`docs/verification_referentiel_anssi.md`)
épingle précisément ces entiers-là. Le supprimer aurait invalidé une
vérification faite ligne à ligne contre le PDF source, pour économiser une
colonne.

## Décision 2 — Le poids est une donnée du référentiel, pas du code

`Measure.weight` (flottant, défaut 1.0) remplace la table de niveaux dans le
calcul du score. `Measure.level` devient un libellé libre, éventuellement vide.

L'import ANSSI pose 1.0 pour « standard » et 0.5 pour « renforcé » : **le score
d'un diagnostic ANSSI est, au dixième près, celui d'avant V2-4**. C'est vérifié
par un test qui recalcule le score attendu à partir des poids
(`test_le_score_anssi_est_celui_d_avant_v2_4`) et par la commande
`check_referential_migration` sur les diagnostics déjà terminés.

Un référentiel qui ne hiérarchise pas ses exigences laisse le poids à 1.0 :
toutes ses mesures comptent pareil, ce qui est exactement ce qu'il dit.

## Décision 3 — Attribution par client, retrait logique

`ReferentialAssignment(tenant, referential, granted_at, revoked_at, …)` : un
client ne voit que ce qui lui est attribué depuis la console.

Deux gardes, et elles ne sont pas symétriques :

| | Attribution active requise ? |
|---|---|
| Démarrer, répondre, terminer un diagnostic | **oui** |
| Lire un diagnostic, ses scores, son plan d'action | **non** |

Le retrait est une date, jamais une suppression. Un client qui perd l'accès à
un référentiel garde en lecture tout ce qu'il a produit dessus — score, détail
par domaine, plan d'action. C'est le point 7 de la fiche V2-4, et c'est la même
règle que pour les offres (ADR-019) et les preuves de possession (ADR-026) :
**on ne prend jamais en otage des données déjà produites.** Une évaluation en
cours au moment du retrait reste consultable ; elle n'est plus remplissable, et
l'API le dit avec un message qui distingue les deux.

### Alternative écartée : filtrer par l'offre

On aurait pu rattacher les référentiels aux offres (`Plan.features`), comme le
reste. Rejeté : un référentiel n'est pas une fonctionnalité du produit mais un
**contenu**, dont les droits d'usage se négocient client par client (voir
décision 5). Deux clients de la même offre peuvent légitimement n'avoir pas les
mêmes référentiels. La garde d'offre existante (`anssi_assessment`) reste et
s'ajoute à celle-ci : l'une dit « votre offre comprend le diagnostic »,
l'autre « voici les référentiels sur lesquels vous pouvez vous évaluer ».

## Décision 4 — Sous-ensembles et surcharges vivent à côté, jamais à la place

**Sous-ensemble** (`MeasureSubset` + `SubsetMeasure`) : une composition de 10,
20 ou 30 mesures tirées d'un référentiel complet, enregistrée comme modèle
réutilisable. `owner_tenant` nul = modèle de plateforme proposable à tous ;
renseigné = composition écrite pour un client. L'évaluation porte le
sous-ensemble choisi (`Assessment.subset`), et c'est LUI qui définit le
périmètre du questionnaire, de la progression, du score et du plan d'action —
un seul point d'entrée, `services.get_assessment_measures`, pour que ces quatre
choses ne puissent pas diverger.

**Surcharge d'énoncé** (`MeasureStatementOverride`) : une reformulation pour un
client. Elle est appliquée **en mémoire, à la lecture**, sur un attribut privé
(`_override_statement`) et jamais dans `Measure.plain_language` — une instance
dont on aurait écrasé le champ pourrait être sauvegardée par mégarde et
corrompre le référentiel pour tous les autres clients. `Measure.statement` lit
l'un ou l'autre ; l'API expose les deux, pour qu'on sache toujours ce qui a été
remplacé.

Ce qui n'est **pas** surchargeable : l'intitulé officiel. C'est la citation du
référentiel. Le réécrire ferait dire à l'ANSSI ou à l'ISO ce qu'ils ne disent
pas. Un client qui veut préciser son contexte ajoute une note, affichée sous
l'énoncé.

## Décision 5 — Le produit fournit la structure, pas le contenu sous droits

`Referential.kind` prend trois valeurs :

| `kind` | Ce que ça veut dire | Exemple |
|---|---|---|
| `open` | libre de droits, **embarqué dans le dépôt** | ANSSI (Licence Ouverte / Etalab) |
| `licensed` | soumis à droits, **importé par le détenteur de la licence** | ISO 27001, NIST CSF, CIS Controls |
| `custom` | écrit pour ou par un client | référentiel interne |

Le dépôt n'embarque que l'ANSSI. Le contenu d'ISO 27001 et des CIS Controls ne
peut pas être redistribué ; le produit livre la **structure d'accueil** — le
modèle, le format d'import documenté, un gabarit de tableur — et l'exploitant
ou le client importe ce qu'il a le droit d'utiliser, en déclarant sa mention de
licence (`licence_notice`), affichée avec le référentiel.

Format et procédure : [`docs/format_import_referentiel.md`](../format_import_referentiel.md).

## Décision 6 — La demande d'accès est un mécanisme générique

Un client peut demander depuis son espace un référentiel qu'il n'a pas ; la
demande arrive dans la console avec qui, quand et pourquoi.

Ce mécanisme vit dans une **app séparée** (`apps/access_requests`) et ne
connaît pas les référentiels : `AccessRequest` porte un `subject_type` et un
`subject_key`, et un registre déclaré en code (`subjects.py`, même partage que
`billing/features.py`) dit pour chaque type comment le décrire, comment savoir
s'il est déjà détenu, et ce qu'« accorder » veut dire.

Deux sujets sont enregistrés aujourd'hui : `referential` (accorder attribue) et
`feature` (accorder **n'attribue rien** — changer l'offre d'un client est un
acte commercial avec des conséquences de facturation, pas la conséquence
silencieuse d'un clic ; la console dit ce qui reste à faire). V2-6 en ajoutera
d'autres sans toucher au modèle.

Un `ReferentialRequest` aurait été à réécrire au premier autre usage, et un
second modèle presque identique serait apparu à côté.

## Conséquences

**Ce qui devient possible.** Charger ISO 27001, le NIST CSF, les CIS Controls
ou le référentiel interne d'un client. Composer un questionnaire court pour une
TPE qui ne tiendrait pas 42 mesures. Reformuler une mesure pour un secteur
particulier. Mener deux diagnostics de front. Répondre à une demande d'accès
en un clic.

**Ce qui change pour l'existant.** Rien de visible pour un client qui n'a que
l'ANSSI : même questionnaire, même score, même plan. La migration
`0003_referentiels_multiples` rétro-crée les attributions pour tous les clients
existants — sans quoi tous auraient perdu leur diagnostic au déploiement. Elle
suit un schéma expand/contract sur `code` et `referential`, ne supprime aucune
colonne et aucune ligne. Elle a été **répétée sur une copie de base réelle**,
et `manage.py check_referential_migration` vérifie après coup qu'aucune réponse
n'est perdue, qu'aucun diagnostic en cours n'est devenu irremplissable, et
qu'aucun score déjà figé n'est démenti par le nouveau calcul.

**Ce qu'on n'a pas fait, et qu'il faudra peut-être faire.** Aucune table de
correspondance entre référentiels : rien ne dit que la mesure 10 de l'ANSSI et
`A.5.15` d'ISO parlent de la même chose. Conséquence directe sur la
consolidation, traitée dans [ADR-030](030-consolidation-multi-referentiels.md).
Aucune interface de composition de sous-ensemble côté console non plus : la
composition passe par l'API et par les modèles de plateforme.
