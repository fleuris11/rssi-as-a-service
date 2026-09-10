# ADR-033 — Surveiller des comptes désignés, y compris ceux d'autrui

- **Statut** : accepté
- **Date** : 2026-09-10
- **Contexte** : V2-6, partie A. S'appuie sur le socle CTI
  ([ADR-013](013-integration-breachsense-cti.md)), s'écarte délibérément du
  traitement des secrets d'[ADR-014](014-secret-handling-breach-data.md), et
  prolonge la règle « actif déclaré uniquement » d'[ADR-010](010-verifications-passives-actifs-declares.md)
  à un objet qui n'est pas un actif.
- **⚠️ À faire valider par un juriste** avant mise en production : voir §7.

## Contexte

Jusqu'ici, la plateforme ne surveillait que des **domaines** appartenant au
client — un actif déclaré, dont il atteste la possession (ADR-026). Le besoin
V2-6 est différent : une entreprise veut faire surveiller **des comptes
précis**. L'adresse de sa directrice générale, celle d'un client important, un
compte technique sensible.

Ces comptes ne sont pas ses actifs. Certains ne lui appartiennent même pas.

## Le vrai sujet : ce n'est pas une question technique

Faire surveiller `directrice@exemple.fr`, c'est chercher si cette personne
apparaît dans des fuites de données. **C'est un traitement de données
personnelles de cette personne**, au sens du RGPD, et le responsable de ce
traitement est le client — pas nous : nous agissons sur ses instructions,
comme sous-traitant.

Trois façons de mal traiter ce problème, toutes tentantes :

1. **l'ignorer** et livrer un champ de saisie. C'est ce qui se fait, et c'est
   ce qui expose le client sans qu'il le sache ;
2. **s'en protéger par une clause noyée dans les CGU**. Juridiquement
   fragile — un consentement à un traitement dont on ne parle pas au moment où
   il a lieu — et surtout inutile au client : il ne saura toujours pas qu'il
   doit informer la personne concernée ;
3. **vérifier nous-mêmes la légitimité**. Impossible : nous n'avons ni le
   contrat de travail, ni le contrat client, ni l'accord de la personne. Le
   prétendre reviendrait à endosser une responsabilité qu'on ne peut pas tenir.

## Décision 1 — Faire déclarer, figer la déclaration, la conserver

Au moment d'ajouter un compte — pas dans un écran d'après, pas dans les
conditions générales — le client déclare :

| Champ | Ce qu'il porte |
|---|---|
| `legal_basis` | à quel titre il surveille ce compte |
| `purpose` | **pourquoi**, en texte libre, obligatoire |
| `declaration_text` | le texte exact qu'il a accepté |
| `declaration_version` | la version de ce texte |
| `declared_by` / `declared_at` | qui, et quand |

Les cinq répondent à la consigne V2-6 point 4 (« qui, quand, quel compte,
quelle finalité déclarée ») et sont **figés à la création**.

`declaration_text` conserve le texte **intégral**, et non un renvoi à la
version courante. Le jour où l'on reformulera cet engagement, ce qu'a
réellement accepté ce client-là ne doit pas changer rétroactivement : c'est la
différence entre une trace et une affirmation.

`purpose` est **obligatoire**, contrairement au « pourquoi » d'une demande
d'accès (V2-4) qui est facultatif. La différence est entière : là on demandait
une fonctionnalité, ici on déclare traiter les données d'un tiers. Une finalité
vide rendrait la déclaration ininterprétable le jour où quelqu'un la relit — y
compris la personne concernée.

### Les bases légales, formulées pour un dirigeant de PME

| Valeur | Ce que le client lit | Rattachement (art. 6 RGPD) |
|---|---|---|
| `own` | « C'est mon propre compte » | 6.1.a / non concerné |
| `company` | « Compte professionnel fourni par mon entreprise » | 6.1.f, intérêt légitime de l'employeur à protéger son SI |
| `consent` | « La personne concernée m'a donné son accord » | 6.1.a |
| `contract` | « Prévu au contrat qui me lie à cette personne » | 6.1.b |
| `other` | « Autre situation, que je précise » | à documenter par le client |

Le rattachement à l'article 6 est fait **ici**, pas dans la liste déroulante :
un dirigeant de PME ne choisit pas entre « 6.1.b » et « 6.1.f », il sait dire
si c'est son salarié ou son client.

Le produit **ne vérifie pas** le fondement invoqué et ne prétend pas le faire.
La déclaration ne transfère pas la responsabilité au client — elle était déjà
la sienne. Elle la lui **rend visible au moment où il l'engage**, et nous
laisse la trace de ce qu'il a déclaré.

## Décision 2 — Le retrait n'est jamais gardé par l'offre

Arrêter de traiter les données d'un tiers ne doit dépendre d'aucun abonnement.
Deux conséquences dans le code, et deux tests :

- `DELETE` sur un compte n'est pas derrière `ensure_feature` ;
- la **liste** ne l'est pas non plus — on ne peut pas retirer ce qu'on ne voit
  plus.

Un client qui perd la fonctionnalité ne peut plus déclarer ni analyser. Il peut
toujours voir et arrêter.

## Décision 3 — Le retrait est logique, jamais une suppression

`removed_at` / `removed_by` plutôt qu'un `DELETE`. Supprimer la ligne
emporterait la déclaration avec elle — et avec elle la preuve de la date à
laquelle la surveillance a cessé. C'est exactement ce qu'on veut pouvoir
montrer si la personne concernée le demande.

Re-déclarer un compte retiré crée une **nouvelle** déclaration, avec sa propre
date et sa propre finalité. Ce n'est pas la même décision.

## Décision 4 — Une table séparée, pas un `asset` nullable

`WatchedAccountFinding` est distinct de `BreachFinding`. L'alternative — rendre
`BreachFinding.asset` nullable et ajouter un `watched_account` — aurait été
moins de code et bien pire :

1. **la séparation demandée (consigne point 3) serait devenue un filtre** que
   chaque requête existante devrait penser à poser. Le score d'exposition
   (ADR-016), le fil d'exposition, les indicateurs de comité (ADR-028) et le
   registre des incidents (ADR-032) interrogent `BreachFinding` : ils ignorent
   ces lignes **sans qu'on ait eu à les modifier**. Quatre tests le vérifient ;
2. **aucune alerte de surveillance n'est ouverte.** Une alerte se pose sur un
   `monitoring.Asset`, et il n'y en a pas ici ;
3. huit points d'appel existants auraient dû apprendre à gérer un `asset` nul.

Ce n'est pas de la duplication : c'est une entité différente qui partage une
forme. Elle a un cycle de vie propre, un régime juridique propre, et ne doit
jamais se mélanger aux fuites sur actifs.

## Décision 5 — Aucun secret conservé, même chiffré

C'est un **écart assumé** avec ADR-014, qui chiffre le secret d'une fuite
(`secret_encrypted`) pour permettre sa révélation tracée après
ré-authentification.

Ici, non. Révéler le mot de passe du compte d'un tiers à quelqu'un d'autre que
lui est une tout autre affaire que révéler celui d'un compte de l'entreprise.
Et l'action utile est rigoureusement la même sans le secret : « ce compte est
exposé, faites-le changer, activez la double authentification ».

Il n'y a donc **pas de colonne à révéler**, pas de chemin de révélation, et
rien à purger. `has_secret` dit qu'un mot de passe a circulé — ce qui change la
gravité et l'urgence — et c'est tout.

## Décision 6 — Deux quotas distincts, et un budget qui ne se mélange pas

`Plan.watched_accounts` (combien de comptes déclarables — un **stock**) et
`Plan.monthly_watched_account_scans` (combien d'analyses par mois — un
**flux**). Vendre l'un sans l'autre donnerait soit un carnet d'adresses qu'on
ne peut pas interroger, soit des analyses sans rien à analyser.

Piège évité, et il aurait été silencieux : `monthly_scans_used` comptait
**toutes** les lignes de `BreachIntelligenceUsage` du tenant. Sans précaution,
une analyse de comptes désignés aurait vidé le quota d'analyses d'actifs du
client, qui n'aurait pas compris pourquoi. Les usages VIP portent donc
l'endpoint `watched_account`, exclu du compteur général et compté dans le sien.

Le budget de requêtes de la **plateforme** (ADR-013), lui, est bien commun aux
deux : c'est la même licence qui paie. `ensure_scan_budget_available` est
appelé dans les deux cas.

## Décision 7 — Le contrat de sous-traitance doit être complété

**Ce point n'est pas résolu par cette version et demande un juriste.**

Le contrat qui nous lie au client doit comporter une clause dédiée couvrant ce
traitement spécifique. Ce qu'elle doit dire, à notre lecture — et cette lecture
n'a pas valeur d'avis juridique :

- le client est **responsable de traitement**, nous sommes **sous-traitant**
  au sens de l'article 28 du RGPD, agissant sur ses seules instructions
  documentées ;
- les catégories de données traitées : adresses de messagerie, et données de
  fuites les concernant (indicateur d'exposition d'un mot de passe, jamais sa
  valeur) ;
- les catégories de personnes concernées : dirigeants, collaborateurs,
  contacts clients et partenaires du responsable de traitement ;
- il appartient au client d'**informer les personnes concernées** et de
  pouvoir justifier de la base légale ;
- durée de conservation, et sort des données au retrait d'un compte ou à la
  fin du contrat ;
- notre obligation d'assistance en cas d'exercice des droits (accès,
  effacement, opposition) par une personne concernée.

Le texte affiché dans le produit (`DECLARATION_TEXT`) dit déjà l'essentiel au
client. Il ne remplace pas la clause contractuelle : il la rappelle au moment
utile.

À traiter également avec le juriste, et non tranché ici : le sort d'une demande
d'effacement adressée directement à nous par une personne concernée qui n'est
pas notre client.

## Conséquences

Un client peut désormais faire surveiller les comptes qui comptent pour lui,
indépendamment de ses domaines, et déclencher l'analyse quand il le décide.
Les résultats vivent dans leur propre espace, comptés séparément — l'écran le
dit en toutes lettres : *« ce ne sont pas vos actifs, ce sont des comptes que
vous surveillez »*.

**Ce qui reste ouvert.** Aucune notification n'est envoyée quand un compte
désigné apparaît dans une fuite : le client le voit en revenant sur l'écran.
C'est une dette assumée pour cette version — et la même que le rapport de
comité (V2-3) et les demandes d'accès (V2-4), qui ne s'envoient pas non plus.
Aucune surveillance continue par webhook non plus : le pool de la licence
(quinze emplacements, ADR-013) est déjà contraint, et l'ouvrir aux comptes
désignés demanderait de décider quelle rareté prime. L'analyse est donc **à la
demande**, ce que la consigne demandait.
