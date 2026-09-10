# ADR-032 — Une bibliothèque documentaire composée, et non rédigée

- **Statut** : accepté
- **Date** : 2026-09-10
- **Contexte** : V2-5, partie B. Étend le modèle `GeneratedDocument` de la
  phase 4 (US-4.1, charte informatique) et s'appuie sur le pipeline IA
  d'[ADR-005](005-pseudonymisation-avant-appel-ia.md), le rendu PDF
  d'[ADR-012](012-export-pdf-weasyprint.md) et les indicateurs de comité
  d'[ADR-028](028-modele-d-indicateurs-de-comite.md).

## Contexte

### Inventaire de l'existant

| Ce qui existait | Où | État |
|---|---|---|
| Charte informatique | `GeneratedDocument`, rédigée par l'IA | versionnée, brouillon/validé, export `.md` et PDF |
| Rapport de comité | `apps.reporting`, composé et déterministe | produit à la demande, **ni stocké ni versionné** |
| Tout le reste | — | n'existait pas |

Un RSSI de PME produit pourtant toujours les mêmes six ou sept documents, et
les refait à chaque client : politique de sécurité, charte, procédure
d'incident, registre des incidents, plan de continuité, fiche de
sensibilisation, rapport de comité.

### Le vrai risque

La consigne le nomme : *« un document qu'il faut réécrire entièrement ne sert
à rien »*. Le piège n'est pas de ne pas produire de documents — c'est d'en
produire sept qui ressemblent à des documents, que le client ouvre une fois et
n'utilise jamais.

## Décision 1 — Composés par défaut, rédigés par l'IA par exception

Six documents sur sept sont **composés** : un modèle écrit une fois,
correctement, rempli avec les véritables actifs, le véritable score, les
véritables écarts et les véritables échéances du client. Seule la charte
informatique reste **rédigée** par l'IA, comme elle l'était déjà.

Trois raisons, dans cet ordre :

1. **Qualité.** Un LLM à qui l'on demande une politique de sécurité produit
   un texte plausible et générique. Un modèle que nous avons écrit, qui cite
   les dix domaines du guide d'hygiène, l'état constaté de chacun et les
   mesures en écart avec leur échéance, est plus précis — et il l'est pour
   tous les clients à la fois, parce qu'on l'améliore une fois.
2. **Reproductibilité.** Deux générations le même jour donnent le même texte.
   C'est ce qui permet de défendre un document devant un assureur ou un
   auditeur, et c'est le même raisonnement qu'ADR-028 pour le rapport de
   comité : *« un document présenté à une direction doit être reproductible »*.
3. **Sobriété** (Green IT, exigence transversale). Sept documents rédigés par
   l'IA à chaque régénération, pour un texte qui varie sans être meilleur,
   consommeraient un quota mensuel entier.

La charte fait exception parce que son contenu doit réellement s'adapter au
contexte de l'entreprise — un artisan et un cabinet de conseil n'ont pas les
mêmes usages à encadrer — et parce qu'elle existait ainsi, testée, avec sa
garde d'offre.

**Conséquence sur la consigne 7 :** « ce qui est généré par IA passe par le
pipeline existant, avec pseudonymisation » reste vrai, et ne concerne qu'un
document. Rien de nouveau n'appelle l'API Anthropic.

## Décision 2 — Trois règles de rédaction, tenues par des tests

- **On n'invente rien.** Ce que la plateforme ne sait pas est écrit
  `[à compléter]`, jamais deviné. Un plan de continuité qui annonce un délai
  de reprise que personne n'a décidé est pire qu'une case vide. Un test exige
  la présence de la marque dans chacun des six documents : chacun porte au
  moins une décision qui n'appartient qu'au client.
- **On dit d'où vient le document.** Chaque document se termine par la liste
  des données qui l'ont rempli. Testé aussi.
- **Un document générique le dit en tête.** Sans diagnostic terminé, un
  bandeau l'annonce avant que le lecteur ne s'en aperçoive — y compris celui
  qui reçoit le fichier sans avoir vu l'écran.

S'y ajoute un garde-fou de confidentialité : le registre des incidents ne
recopie **aucun identifiant** retrouvé dans une fuite, pas même masqué. Ce
document s'imprime, se transmet, finit en pièce jointe.

## Décision 3 — Le registre part de ce que la plateforme a détecté

Un registre des incidents vide est un tableau vide : personne ne le remplit.
Celui-ci arrive pré-rempli avec les alertes de surveillance ouvertes et les
fuites détectées, chacune avec sa date, son actif et sa gravité, plus une
colonne « données personnelles ? » à analyser — c'est ce qui déclenche
l'obligation de l'article 33 du RGPD.

Ce que nous **n'avons pas** fait : un module de gestion d'incidents avec
saisie manuelle. Il n'était pas demandé, et l'inventer aurait doublé la taille
de cette version. Le document assume la limite et l'écrit : la plateforme ne
voit ni les postes de travail ni le réseau interne, les incidents constatés en
interne s'ajoutent dans un second tableau prévu pour cela.

## Décision 4 — Le rapport de comité est archivé, pas recalculé

Le composeur appelle `apps.reporting.services.build_report` et met le résultat
en forme. Il ne recalcule aucun chiffre.

Deux calculs du même indicateur finiraient par diverger, et le jour où le PDF
de la page de restitution et le document archivé ne diraient pas la même
chose, aucun des deux ne serait défendable. Ce que V2-5 ajoute est le
**versionnement** : le rapport du trimestre devient une pièce datée qu'on
retrouve, plutôt qu'un export volatil.

## Décision 5 — « Éditable » veut dire Word, pas Markdown

L'export `.md` existait et reste : c'est la garantie que le client récupère
son contenu quoi qu'il arrive, et il n'est gardé par aucune offre.

Mais une PME n'édite pas du Markdown. Le format éditable demandé par la
consigne est donc le **`.docx`**, produit par `python-docx` — une dépendance
pure Python, sans bibliothèque système, contrairement à WeasyPrint dont
l'installation impose Pango et Cairo au Dockerfile comme à la CI. L'export
Word fonctionne donc là où le PDF échoue.

Trois formats, deux gardes : `.md` ouvert, `.docx` et PDF sous
`pdf_export` — ce qui est vendu est un **format de rendu**, jamais l'accès aux
données.

## Décision 6 — La garde d'offre descend sur le type, l'interrupteur d'IA aussi

Tant qu'il n'existait qu'un document, garder la vue de création revenait à
garder la charte. Un commentaire du code de la phase 12 l'anticipait :
*« le jour où un second type apparaîtra, la garde devra se déplacer sur le
type demandé »*. C'est fait :

- `charter_generation` ne garde plus que la charte. Retirer cette clé d'une
  offre ne retire plus le registre des incidents, qui n'a rien à voir ;
- `IsAIEnabled` quitte les vues documentaires. Couper l'IA (US-4.3) doit
  désactiver **ce qui appelle l'IA** — pas reprendre au client les documents
  qu'il a produits, ni ceux qu'aucune IA ne rédige. La règle descend dans
  `create_document_job`, pour la seule charte.

C'est un changement de comportement assumé, et il corrige au passage un défaut
qui existait déjà : avant V2-5, un client qui coupait l'IA ne pouvait plus
relire la charte qu'il avait générée la veille.

## Décision 7 — Composé = synchrone

Un document composé ne fait aucun appel réseau, ne coûte rien et prend
quelques dizaines de millisecondes. Il est produit dans la requête et renvoyé
en 201 avec son contenu. Passer par Celery n'apporterait qu'un état
« en cours » que le client devrait interroger pour rien.

La charte garde le chemin asynchrone (202 + job) : elle, appelle une API
externe qui met trente secondes.

## Conséquences

`GeneratedDocument` porte sept types au lieu d'un, plus une colonne `source`
qui dit au lecteur ce qu'on lui promet : un document composé se relit tel
quel, un document rédigé demande une relecture attentive. Les lignes
existantes prennent `source = ai`, ce qu'elles étaient.

**Dette de nommage assumée.** Le modèle et sa machinerie vivent dans
`apps.ai_assistant`, qui contient désormais plus de déterministe que d'IA.
Déplacer le modèle dans une app `documents` aurait demandé de migrer une table
portant, en production, les documents de vrais clients. Le nom est faux, les
données sont intactes ; c'est le bon ordre de priorité.

**Ce qui reste ouvert.** La politique de sécurité s'appuie sur les noms des
domaines du guide d'hygiène ANSSI pour choisir son texte d'engagement : sur un
référentiel importé (V2-4) dont les domaines portent d'autres noms, elle
retombe sur une phrase générique. C'est acceptable et c'est dit ; une table de
correspondance domaine → engagement, alimentable à l'import, serait la suite
naturelle.
