# ADR-034 — Veille réglementaire : suggérer, jamais modifier

- **Statut** : accepté
- **Date** : 2026-09-10
- **Contexte** : V2-7. Alimente le catalogue de référentiels d'[ADR-029](029-referentiels-multiples-et-attribution.md),
  réutilise la protection SSRF d'[ADR-010](010-verifications-passives-actifs-declares.md)
  et le pipeline IA d'[ADR-005](005-pseudonymisation-avant-appel-ia.md).

## Contexte

Le paysage réglementaire bouge : NIS 2, DORA, règlement sur l'intelligence
artificielle, recommandations nationales. Un produit qui vend un diagnostic de
maturité doit savoir que ses référentiels vieillissent.

La tentation, à ce stade, est de « scanner le net » et de laisser une IA
décider de ce qui compte. C'est le contraire de ce qu'on construit ici.

## Décision 1 — Sources primaires uniquement, et la liste est motivée

Une veille utile suit **l'organisme qui publie le texte**, jamais celui qui le
commente. Les blogs, agrégateurs et sites de presse spécialisée sont exclus par
principe : le risque de remonter une information déformée est trop élevé pour
un produit dont l'argument est la rigueur — et **une exigence inventée coûte
plus cher au client qu'une exigence manquée**.

Les adresses et les formats ont été **vérifiés le 2026-09-10**, pas supposés.
Trois surprises, toutes documentées dans `sources.py` :

| Source | Format | Constat de la vérification |
|---|---|---|
| **ANSSI** — publications | page | Aucun flux. `cyber.gouv.fr/publications/feed` répond 404, la page n'expose aucun `link rel=alternate`. Dégradé en détection de changement. |
| **CNIL** — actualités | RSS 2.0 | Flux valide, publications quotidiennes. Mêle sanctions et doctrine : la qualification est faite à la lecture. |
| **NIST CSRC** — projets ouverts à commentaire | Atom | Flux valide. Prend les textes **avant** publication définitive — l'exigence de demain, avec le temps de s'y préparer. |
| **EUR-Lex** — actes | RSS 2.0 | Le flux fonctionne et **est inutilisable non filtré** : 120 entrées le jour du test, essentiellement des décharges budgétaires. Livré inactif, à brancher sur un flux de recherche ciblée. |
| **ENISA** — publications | page | Les adresses de flux annoncées répondent 404, la page qui les recense répond 403. Dégradé en détection de changement plutôt que d'inscrire une adresse morte. |

**Écartée alors qu'elle fonctionne : le CERT-FR.** Son flux est valide (40
avis le jour du test) mais il publie des avis de vulnérabilité — « Multiples
vulnérabilités dans les produits Ivanti ». C'est opérationnel, pas normatif :
aucun de ces avis ne deviendra une mesure de référentiel, et la file en serait
noyée au point que plus personne ne la lirait. Une liste de sources sans ses
exclusions se relit mal — on ne sait pas si un manque est un oubli ou une
décision.

Les sources vivent **en base**, pas en dur : l'exploitant en ajoute, en corrige
et en désactive depuis la console, sans redéploiement. La migration ne fait
que poser le point de départ, et ne réécrit jamais une source existante.

## Décision 2 — Ce que la veille produit est une suggestion

Une collecte crée des `WatchUpdate`. **Elle n'écrit jamais dans
`assessments`.** Le seul chemin qui ajoute une mesure à un référentiel est
`services.integrate_as_measure`, et il exige quatre choses :

1. un **relecteur nommé** — sans lui, un changement d'état n'est pas une
   décision, c'est un effet de bord ;
2. un **référentiel cible**, choisi ;
3. un **domaine existant** de ce référentiel ;
4. un **contenu saisi** : ni l'intitulé ni l'énoncé ne sont repris de la
   publication. Une exigence rédigée par copie d'un titre de communiqué est
   illisible pour un dirigeant, et fausse le score.

Le statut `integrated` n'est pas une case qu'on coche : c'est la conséquence
d'une intégration réelle. L'API de tri ne l'expose pas, et le service le
refuse.

Six tests attaquent cette règle par les chemins où elle pourrait céder — la
collecte, le tri, l'intégration sans relecteur, l'intégration à contenu vide,
le statut posé à la main, et l'API. C'est la vérification que la fiche V2-7
demandait explicitement.

### Pourquoi une app séparée

`regulatory_watch` plutôt qu'un module d'`assessments`. La séparation **est**
la garantie : un module rangé dans l'app des référentiels aurait eu la main sur
leurs modèles. Ici, la veille passe par `assessments.services.add_measure`
comme n'importe quelle autre app — et cette fonction est la seule porte.

## Décision 3 — La traçabilité vit des deux côtés, en texte d'un côté

`Measure.source_url` et `Measure.source_reference` portent la provenance **en
texte**, sur la mesure elle-même. `WatchUpdate.integrated_measures` porte le
lien structuré, dans l'autre sens.

Deux champs de texte plutôt qu'une clé étrangère d'`assessments` vers la
veille : ils survivent au retrait de cette app, à un export de référentiel, à
une copie. Le lien structuré, lui, va de la périphérie vers le cœur — jamais
l'inverse.

« On ne livre pas ce qu'on ne peut pas sourcer » est déjà la règle de ce projet
(ADR-029 §5, `docs/verification_referentiel_anssi.md`). Une mesure ajoutée par
la veille et dont on aurait perdu la source serait précisément ce qu'on refuse
depuis le début.

## Décision 4 — Une page sans flux dit ce qu'elle sait, et rien de plus

Pour l'ANSSI et l'ENISA, faute de flux, on relève l'empreinte du texte de la
page. On sait alors **que** quelque chose a changé, pas **quoi** — et la file
l'écrit tel quel plutôt que de laisser croire à une publication identifiée.

Deux précautions, apprises en écrivant le code :

- le balisage et les espaces sont normalisés avant l'empreinte, sinon un
  identifiant de session ou un espace en trop ferait « changer » la page à
  chaque passage, et la file se remplirait de fausses nouveautés jusqu'à ce
  que plus personne ne la lise ;
- **le premier passage ne signale rien** : il relève l'empreinte. Annoncer
  « cette page a changé » alors qu'on ne l'a jamais lue serait faux, et
  remplirait la file au déploiement.

## Décision 5 — L'IA résume, elle ne conclut pas

Le résumé est **facultatif et déclenché à la main**, jamais à la collecte : on
ne paie pas un résumé pour une publication que personne n'ouvrira (sobriété,
exigence transversale).

Le prompt interdit explicitement de conclure — le modèle ne dit jamais si la
publication doit être intégrée, ni ce qu'il faudrait faire — et interdit
d'ajouter le moindre fait absent du texte. **Le texte source est conservé et
reste la référence** : le résumé vient à côté, daté, identifié comme produit
par une machine, et l'écran le présente comme « à vérifier contre le texte
source ».

Point technique : c'est le seul appel IA de la plateforme **sans tenant**. Le
texte est public, donc il n'y a rien à pseudonymiser (ADR-005 protège des
données de client, il n'y en a pas ici) et aucun quota client à décompter.
L'usage est enregistré sur la suggestion elle-même plutôt que dans
`AIUsageLog`, qui est scopé par tenant : y ranger un appel de plateforme
l'attribuerait à un client qui ne l'a pas demandé. L'appel reste dans
`ai_assistant.services` — la règle de CLAUDE.md est « aucun appel direct
ailleurs dans le code », pas « aucun appel sans tenant ».

## Décision 6 — Hebdomadaire, et la promesse est écrite

Un passage par semaine, le lundi matin. Les autorités publient à la journée,
pas à la minute ; promettre du temps réel serait mentir, et coûterait cinq
requêtes HTTP toutes les heures pour rien.

La promesse commerciale est une **constante du code**, servie par l'API et
affichée dans la console :

> « Nous suivons les publications officielles des autorités et organismes de
> normalisation, et nous vous signalons ce qui change. Cette veille n'est ni
> exhaustive ni instantanée : elle couvre les sources listées ci-dessous, au
> rythme de leurs publications. »

Un test épingle cette phrase et interdit les deux mots qu'on ne tiendrait
pas — « exhaustive » employé comme promesse, et « temps réel ». Une formule
honnête est déjà plus que ce que font la plupart des concurrents ; une formule
fausse se retourne au premier client qui découvre une exigence ailleurs.

## Conséquences

La console gagne un onglet « Veille » : la file, l'état des sources, et le
formulaire d'intégration. **Console uniquement** — la veille alimente le
catalogue partagé, et une suggestion non triée n'a rien à faire sous les yeux
d'un client. Lecture ouverte aux deux niveaux d'administrateur, décisions
réservées au niveau complet : trier la veille, c'est décider de ce que le
produit exigera de ses clients demain.

**L'état des sources est remonté aussi visiblement que les suggestions.** Une
source qui échoue en silence est pire qu'une source absente : on croit
surveiller. Une source jamais configurée (EUR-Lex) est distinguée d'une source
en panne — sinon elle serait comptée comme un incident pendant des mois.

**Ce qui reste ouvert.** Aucune notification : l'exploitant voit la file en
ouvrant la console. Aucune détection de ce qui a changé *dans* une page — nous
signalons le changement, pas le diff. Et la liste de sources est un point de
départ : elle devra vivre, notamment pour brancher le flux EUR-Lex ciblé, qui
est livré inactif faute de pouvoir choisir la requête à la place de
l'exploitant.
