# Vérification du référentiel ANSSI — Guide d'hygiène informatique

- **Date de vérification** : 2026-08-04
- **Fichier vérifié** : `backend/data/anssi_hygiene.json`
- **Source officielle** : ANSSI, *Guide d'hygiène informatique — Renforcer la sécurité de son
  système d'information en 42 mesures*, version 2.0, septembre 2017 (première édition : janvier
  2013)
- **URL officielle** : https://cyber.gouv.fr/publications/guide-dhygiene-informatique
- **PDF téléchargé** : https://messervices.cyber.gouv.fr/documents-guides/guide_hygiene_informatique_anssi.pdf
- **Copie locale (traçabilité)** : `docs/sources/anssi_guide_hygiene_informatique.pdf`
- **Licence** : Licence Ouverte / Open Licence (Etalab, version 1)

## Méthode

Le PDF officiel a été téléchargé directement depuis `messervices.cyber.gouv.fr` (confirmé PDF valide :
en-tête `%PDF-1.4`, 72 pages, métadonnées de création `2017-09-01`, cohérentes avec la mention
« Version 2.0 - Septembre 2017 » imprimée en dernière page du document). Le texte a été extrait
mesure par mesure et comparé à `backend/data/anssi_hygiene.json` tel que produit lors de la session
Phase 2 précédente.

La source la plus fiable pour la numérotation, l'intitulé exact et le rattachement par domaine
s'est révélée être l'annexe **« Outil de suivi »** du guide (pages 62 à 67 du PDF) : un tableau
récapitulatif des 42 mesures, classées par chapitre, dans l'ordre officiel. Cette annexe a servi de
référence canonique, recoupée avec le corps du texte (une mesure par page environ) pour confirmer
chaque intitulé et déterminer, mesure par mesure, si elle est présentée avec un palier
« standard » seul ou un palier « standard » et un complément « renforcé ».

## Constat : le JSON de la session précédente était largement fabriqué

Le référentiel produit lors de la session Phase 2 n'avait **pas** été construit à partir du texte
réel du guide, mais reconstitué de mémoire. La comparaison mesure par mesure révèle des écarts
importants et systématiques :

| Catégorie d'écart | Nombre de mesures concernées |
|---|---|
| Mesures inventées, absentes du guide officiel | 9 (anciens H8, H27, H36, H37, H39, H40, H41, H42, + une confusion sur H35) |
| Mesures officielles totalement absentes de l'ancien JSON | 8 (n° 23, 24, 25, 26, 31, 39, 40, 41, 42 — voir détail ; certaines citées ci-dessus se recoupent avec des mesures mal placées) |
| Mesures correctement identifiées mais rattachées au mauvais domaine | 3 (référent SSI, chiffrement du matériel nomade, et une mesure de chiffrement confondue avec une autre) |
| Mesures avec un intitulé/une description substantiellement déformés | 4 (gestion centralisée, chiffrement, supervision, gestion des incidents) |
| Numérotation | Système de code interne (« H1 »–« H42 ») sans rapport avec la numérotation officielle 1–42 |
| Domaine « Pour aller plus loin » | **6 mesures inventées** en lieu et place des **2 mesures officielles réelles** (analyse de risques formelle ; produits et services qualifiés ANSSI) |
| Domaine « Sécuriser le réseau » | 4 des 8 mesures officielles manquaient entièrement |
| Classification standard/renforcé | ~22 mesures classées « renforcé » sur la base d'un jugement produit non vérifié, alors que **seules 3 mesures (n° 38, 41, 42) sont présentées sans palier standard** dans le guide réel |

En clair : la structure en 10 domaines et l'ordre des chapitres (Sensibiliser et former →
… → Pour aller plus loin) étaient corrects — c'est la seule partie fiable de la version précédente
— mais le contenu précis de chaque mesure (numéro, intitulé, rattachement, niveau) ne l'était pas.
Le référentiel a donc été **entièrement reconstruit** à partir du texte source plutôt que corrigé
mesure par mesure.

## Écarts corrigés, par domaine

### I — Sensibiliser et former (mesures 1-3)
Conforme dès la version précédente (contenu, numéros relatifs, domaine).

### II — Connaître le système d'information (mesures 4-7, pas 5)
- Mesure inventée supprimée : « Identifier explicitement les personnes responsables de chaque
  système d'information » n'existe pas dans le guide. Le domaine compte 4 mesures officielles, pas
  5.

### III — Authentifier et contrôler les accès (mesures 8-13)
Contenu conforme (décalage de numérotation uniquement, dû à la mesure fictive du domaine II).

### IV — Sécuriser les postes (mesures 14-18)
- Mesure 16 : l'ancien intitulé produit (« maintenir à jour les logiciels ») décrivait en fait la
  mesure 34 (politique de mise à jour). L'intitulé officiel de la mesure 16 est « Utiliser un outil
  de gestion centralisée **afin d'homogénéiser les politiques de sécurité** » — un outil de gestion
  centralisée des postes en général, pas spécifiquement des mises à jour.
- Mesure 18 : l'ancien contenu (« chiffrer les données sensibles, en particulier sur les postes
  nomades et supports amovibles ») correspond en réalité à la mesure officielle **31** (domaine
  « Gérer le nomadisme »). La véritable mesure 18 est « Chiffrer les données sensibles **transmises
  par voie Internet** » (données en transit, email/Cloud — sujet différent).

### V — Sécuriser le réseau (mesures 19-26, pas 20-23)
- 4 mesures officielles étaient absentes du référentiel précédent : **23** (cloisonner les services
  visibles depuis Internet du reste du SI), **24** (protéger sa messagerie professionnelle),
  **25** (sécuriser les interconnexions réseau avec les partenaires), **26** (contrôler et protéger
  l'accès aux salles serveurs et locaux techniques). Le domaine compte 8 mesures officielles, pas 4.

### VI — Sécuriser l'administration (mesures 27-29, pas 24-27)
- Mesure inventée supprimée : « Gérer le cycle de vie des comptes et des accès des administrateurs »
  n'est pas une mesure officielle distincte. Le domaine compte 3 mesures officielles, pas 4.

### VII — Gérer le nomadisme (mesures 30-33, pas 28-30)
- Mesure officielle **31** (« Chiffrer les données sensibles, en particulier sur le matériel
  potentiellement perdable ») était absente de ce domaine — elle avait été mal rattachée au domaine
  « Sécuriser les postes » sous un intitulé approximatif (voir IV ci-dessus).
- Ancienne mesure « chiffrer les flux réseau de bout en bout, en priorité les Wi-Fi » reformulée
  fidèlement en mesure officielle **32** : « Sécuriser la connexion réseau des postes utilisés en
  situation de nomadisme » (VPN pour la connexion à distance, pas un énoncé général sur le
  chiffrement des flux).

### VIII — Maintenir le système d'information à jour (mesures 34-35)
Conforme dès la version précédente.

### IX — Superviser, auditer, réagir (mesures 36-40, pas 33-36)
- Mesure inventée supprimée : « Prendre en compte l'obtention d'informations publiques sur des
  vulnérabilités » n'est pas une mesure officielle distincte (le sujet CERT-FR est mentionné en
  encart de la mesure 34, pas comme mesure à part).
- Mesure officielle **38** (« Procéder à des contrôles et audits de sécurité réguliers puis
  appliquer les actions correctives associées ») était absente, remplacée par une mesure
  approximative sur la « supervision des systèmes ».
- Mesure officielle **39** (« Désigner un référent en sécurité des systèmes d'information ») était
  présente mais **rattachée au mauvais domaine** (« Pour aller plus loin » au lieu de
  « Superviser, auditer, réagir »).
- Mesure officielle **40** (« Définir une procédure de gestion des incidents de sécurité ») était
  absente, remplacée par une mesure inventée sur la « gestion de crise informatique » qui n'existe
  pas sous cette forme dans le guide.

### X — Pour aller plus loin (mesures 41-42, pas 37-42)
Le domaine ne compte que **2 mesures officielles** : « Mener une analyse de risques formelle »
(41) et « Privilégier l'usage de produits et de services qualifiés par l'ANSSI » (42). Les
6 mesures précédemment attribuées à ce domaine (plan de continuité d'activité, référent SSI, PSSI,
gestion de crise, implication de la direction, charte informatique) **n'existent pas comme mesures
numérotées du guide** — certains de ces thèmes sont évoqués dans le corps du texte ou la
bibliographie (ex. la charte informatique est suggérée en complément « renforcé » de la mesure 2 ;
« Désigner un référent SSI » est bien une mesure officielle, mais c'est la mesure 39, dans le
domaine IX — voir ci-dessus), mais aucun n'est une mesure officielle du domaine X.

## Classification standard/renforcé — méthode et résultat

Le guide distingue, texte à l'appui, un palier « standard » (l'attendu de base) d'un palier
« renforcé » (optionnel, pour aller plus loin) — mais **pas mesure par mesure comme un choix
binaire** : la majorité des 42 mesures présentent un contenu « standard » avec, pour un sous-
ensemble d'entre elles, un paragraphe additionnel « renforcé » qui vient compléter — et non
remplacer — le socle standard. Seules **trois mesures (38, 41, 42)** sont présentées **sans aucun
contenu standard**, directement au niveau renforcé : les audits de sécurité réguliers, l'analyse de
risques formelle et le recours à des produits/prestataires qualifiés ANSSI.

Le champ `official.level` du référentiel reflète cette réalité : `"renforce"` uniquement pour les
mesures 38, 41 et 42 (aucun palier standard attendu par l'ANSSI elle-même) ; `"standard"` pour les
39 autres, y compris celles qui comportent par ailleurs un complément renforcé optionnel dans le
texte source. **Cette simplification a une conséquence assumée** : le référentiel ne capture pas,
mesure par mesure, l'existence d'un tel complément renforcé (mesures 2, 6, 7, 8, 12, 13, 14, 15, 17,
22, 24, 25, 27, 28, 30, 32, 33, 36, 37 en ont un d'après la lecture du texte) — le diagnostic
RSSI as a Service pose une seule question par mesure, au niveau de l'attendu de base. C'est un choix
produit délibéré (documenté ici, pas une omission silencieuse), cohérent avec `LEVEL_WEIGHTS` dans
`assessments/services.py` qui pondère `standard` à 1.0 et `renforce` à 0.5 dans le calcul du score.

## Restructuration du schéma JSON

Chaque mesure sépare désormais explicitement trois couches, comme demandé :

- **`official`** (`number`, `title`, `domain`, `level`) : reproduit fidèlement le PDF source. Toute
  correction future de cette couche doit être justifiée par une citation du texte source.
- **`simplified`** (`question`) : la reformulation en langage dirigeant — couche produit
  RSSI as a Service, pas une traduction officielle de l'ANSSI.
- **`product_rating`** (`effort`, `impact`, `disclaimer: true`) : un jugement produit sur l'effort
  de mise en œuvre et l'impact pour une TPE/PME, **non issu du guide** (le guide ne note pas ses
  mesures selon ces critères). Le champ `disclaimer` est toujours `true` aujourd'hui et sert de
  garde-fou explicite : `apps.assessments.models.Measure.effort_impact_disclaimer` porte cette
  information jusqu'à l'API, pour qu'elle reste visible et ne soit jamais confondue avec une
  donnée ANSSI côté produit.

Un bloc `meta` a été ajouté au niveau racine du JSON (source, URL officielle, URL du PDF, copie
locale, version, date de publication, licence, date de vérification, référence de ce rapport).

## Modèle de données

Le champ `Measure.code` (identifiant interne type `"H1"`) a été remplacé par `Measure.number`
(entier, unique, 1 à 42 — la numérotation officielle elle-même). Migration
`assessments/0002_remove_measure_code_measure_effort_impact_disclaimer_and_more.py` (voir le
commentaire en tête de fichier : le défaut à vide n'est sûr que sur une table `measure` vide, ce qui
est le cas de tout environnement réel à ce stade — aucune donnée de production n'existe encore pour
ce référentiel).

## Tests

`apps/assessments/tests/test_referential_integrity.py` (nouveau) vérifie automatiquement, à partir
du JSON et de l'état chargé en base : exactement 42 mesures, numéros uniques et continus de 1 à 42,
10 domaines, présence des trois couches et de leurs champs obligatoires sur chaque mesure,
cohérence `official.domain` ↔ domaine parent, valeurs de `level`/`effort`/`impact` dans l'ensemble
attendu, présence et complétude du bloc `meta` (y compris l'existence du PDF référencé par
`meta.local_copy`), et un test de non-régression dédié verrouillant l'ensemble `{38, 41, 42}` comme
seules mesures sans palier standard.

`apps/assessments/tests/test_management_commands.py` complète avec un test de rejet : si
`official.domain` d'une mesure ne correspond pas au domaine qui la contient dans le JSON, la
commande `load_anssi_referential` lève désormais une erreur explicite plutôt que de charger une
donnée incohérente silencieusement.

## Limites de cette vérification

- Le texte a été extrait du PDF avec `pypdf` (extraction texte brute, pas d'OCR d'image) ; les
  intitulés officiels ont été recoupés avec l'annexe « Outil de suivi » (rendu texte le plus propre
  du document) et vérifiés individuellement contre le corps du texte de chaque mesure.
- La classification standard/renforcé mesure par mesure repose sur une lecture attentive mais
  manuelle du texte extrait (recherche des balises « / STANDARD » et « / RENFORCÉ » et de leur
  contexte) ; en cas de doute sur une mesure précise, se reporter au PDF source
  (`docs/sources/anssi_guide_hygiene_informatique.pdf`), qui fait foi.
- `simplified.question` et `product_rating.*` restent un jugement produit non validé par un expert
  métier externe — voir `docs/journal.md`, session Phase 2, section « reste à faire ».
