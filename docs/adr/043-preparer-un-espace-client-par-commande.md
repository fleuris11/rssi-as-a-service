# ADR-043 — Préparer un espace client par commande versionnée, pas à la main

- **Date** : 27/09/2026
- **Statut** : acceptée
- **Portée** : `apps/training` (bibliothèque de cours), `apps/platform_admin`
  (préparation d'un client, écran d'attribution), `apps/regulatory_watch`
  (résumés de veille)

## Contexte

La plateforme est en production et un premier client réel y a son espace. Deux
constats ont déclenché cette décision.

**Le catalogue de formation était vide.** Un seul cours existait
(`hameconnage`), chargé par la commande de démonstration de F1. Le studio de F2
permet d'en écrire, la mesure de F3 permet d'en suivre l'effet, mais un client
qui ouvre l'écran Formation ne voyait rien à proposer à ses salariés. Un module
sans contenu n'est pas un module : c'est un formulaire.

**L'espace du premier client était à moitié vide**, et la tentation immédiate
était de le remplir en tapant des ordres dans le conteneur de production :
ajouter une adhésion, attribuer des cours, composer trois documents. Vingt
minutes de travail, et aucune trace.

## Options

1. **Taper les ordres en production, une fois.** Le plus rapide. Rien n'est
   relisible avant exécution, rien n'est rejouable, rien n'apparaît dans le
   journal d'audit, et le prochain client demande de recommencer de mémoire.
2. **Des migrations de données.** Versionnées, jouées automatiquement au
   déploiement. Mais le contenu d'un cours se corrige : chaque faute
   d'orthographe demanderait une migration de plus, et une migration ne se
   rejoue pas. Pire, une migration qui écrit dans l'espace d'un client
   l'appliquerait à **tous** les clients, présents et futurs.
3. **Des fixtures Django.** Chargeables à la demande, mais elles écrivent en
   base sans passer par les services : la validation des blocs de contenu, les
   gardes d'offre et les contrôles avant publication seraient contournés.
4. **Un jeu de données de démonstration étendu** (`seed_demo_tenant`). Il
   existe déjà et fait très bien son travail, mais il est **conçu pour un
   client fictif** : il coupe les emails, invente des salariés, pose des
   réponses de diagnostic. Rien de tout cela n'a sa place chez un vrai client.
5. **Des commandes de gestion versionnées, idempotentes, génériques.** Retenu.

## Décision

Trois commandes, et une séparation nette entre le **contenu** et le
**mécanisme**.

### `seed_catalogue_formation`

Charge la bibliothèque de cours. Le contenu vit dans `apps/training/catalogue.py`,
qui est une donnée pure : aucune écriture en base, donc testable sans base. La
commande, elle, est un mécanisme de quarante lignes.

Trois propriétés tenues :

- **idempotente** : un cours déjà chargé n'est pas retouché sans `--reset` ;
- **aucune inscription cassée** : `--reset` vide le *contenu* de la version
  courante, jamais la version — une inscription pointe dessus (ADR-039) ;
- **publiée par le chemin normal** : la publication passe par `studio.publier`,
  qui refuse un cours sans écran ou sans bonne réponse. Une commande n'a pas le
  droit de publier ce que le studio refuserait.

Le contenu est **testé comme du code**. Un cours mal écrit ne casse rien : il se
charge, se publie, et enseigne quelque chose de faux. Aucun test d'intégration
ne l'attrape. `test_catalogue.py` automatise donc une relecture — question sans
bonne réponse, renvoi vers un écran inexistant, choix unique à deux bonnes
réponses, explication trop courte pour former, quiz trop court pour que son
seuil veuille dire quelque chose.

### `preparer_client`

Prépare l'espace d'un client réel : adhésion administrateur, attribution de la
bibliothèque, inscription du compte passé en option, composition des documents
manquants. **Générique** : aucun nom de client, aucune adresse, aucun
identifiant n'est écrit dans le dépôt. Tout arrive par `--tenant` et `--admin`.

Ce qu'elle ne fait **jamais**, et c'est la partie importante de cette décision :

- **aucune analyse d'exposition, aucun scan, aucune recherche de
  compromission.** Ces gestes ont un coût, engagent une licence et désignent des
  personnes : ils restent déclenchés à la main par l'exploitant ;
- **aucun envoi de courriel.** Les inscriptions créées n'émettent pas de lien
  nominatif ; l'exploitant les enverra depuis l'interface quand il le décidera ;
- **aucun diagnostic répondu à la place du client.** Les réponses à un
  référentiel sont un engagement de l'entreprise. Les inventer produirait un
  score faux, donc un plan d'action faux, donc des documents faux — et le
  client les découvrirait en les présentant à son assureur ;
- **aucun apprenant inventé.** Les salariés d'un client réel sont des personnes
  réelles. Seul le compte passé en `--admin` est inscrit, pour qu'il puisse
  parcourir les cours depuis son propre espace ;
- **aucun document rédigé par l'IA.** La charte informatique est le seul
  document rédigé (ADR-032) : elle passe par un job, un quota de jetons et un
  coût. Une commande de préparation ne la déclenche pas ;
- **aucune garde contournée.** Le quota d'utilisateurs de l'offre est vérifié
  comme pour n'importe quelle invitation. Une commande d'exploitation n'a pas
  le droit de passer devant une garde d'offre.

Les documents composés sont laissés en **brouillon** : valider un document, c'est
dire qu'un responsable l'a lu. Personne ne l'a lu.

Chaque exécution laisse une entrée `tenant.prepare` dans le journal d'audit de
la plateforme. Sans elle, l'apparition de données dans l'espace d'un client
serait inexplicable six mois plus tard, y compris pour celui qui a lancé la
commande.

### `resumer_la_veille`

Demande à l'IA un résumé des publications de veille qui n'en ont pas. La console
a déjà un bouton par publication ; au démarrage la file en compte plusieurs
dizaines, et ouvrir chacune pour cliquer n'apporte rien de plus que cette
boucle.

Le geste reste **déclenché à la main** — la collecte ne résume rien d'elle-même,
par sobriété — et **borné** par `--limite`, pour qu'une erreur de manipulation
ne lance pas deux cents appels. Le texte source reste la référence ; le résumé
vient à côté, daté et identifié comme produit par une machine (V2-7 §7).

Elle **ne qualifie rien et ne change aucun statut.** Résumer n'est pas décider.
Retenir ou écarter une publication reste un geste humain posé depuis la console,
avec un relecteur nommé — c'est la règle de la veille depuis V2-7, et une
commande n'a pas à y faire exception au prétexte qu'elle est plus rapide.

### L'écran qui manquait

En écrivant `preparer_client`, un relevé a montré que `attribuer_cours`
n'était appelé **que par des commandes et des tests** : aucune route HTTP ne
proposait un cours à un client. Le studio savait écrire des cours (F2), la
mesure savait en suivre l'effet (F3), et l'attribution n'avait aucun chemin
dans l'interface. Un module dont l'exploitant ne peut rien proposer n'est pas un
module.

Un onglet « Formations » de la console corrige cela, construit comme le pendant
exact de l'onglet « Référentiels » — même structure, mêmes deux colonnes, même
journal d'audit (`COURSE_ASSIGNED`, `COURSE_REVOKED`). Trois choix méritent
d'être notés :

- **un cours écrit PAR un client n'apparaît pas**, et la route le vérifie plutôt
  que l'écran : proposer à un client le travail d'un autre est exactement ce que
  la séparation catalogue/attribution existe pour empêcher ;
- **le nombre de salariés encore inscrits est affiché** sur chaque cours
  proposé. C'est le chiffre qui fait hésiter avant un retrait, et le cacher
  ferait cliquer à l'aveugle ;
- **le retrait ne touche à aucun parcours**, et l'écran le dit à chaque fois.
  Une inscription pointe vers une version, pas vers une attribution : le salarié
  en cours de route termine, et son attestation reste. Ce qui cesse, c'est la
  possibilité d'en inscrire de nouveaux. Sans cette phrase, personne n'oserait
  cliquer.

La commande n'est donc pas remplacée par l'écran : elle sert à **poser** les sept
cours d'un coup, l'écran sert à **ajuster** ensuite. Les deux passent par le même
service.

## Conséquences

**Ce qu'on gagne.** Le deuxième client se prépare en une commande. La
préparation se relit avant d'être lancée, se simule (`--dry-run`), se rejoue
sans rien doubler, et laisse une trace. Le catalogue se corrige par un commit et
un `--reset`, pas par une migration.

**Ce qu'on accepte.** Le contenu des cours est en Python, pas dans une base
éditable : le corriger demande un déploiement. C'est assumé — le studio existe
pour écrire des cours *de client*, la bibliothèque est un produit de
l'exploitant, et un produit se versionne.

**Ce qui reste à la main, et pourquoi c'est bien.** Le diagnostic du client, les
scans d'exposition, l'envoi des liens de formation, la qualification des
publications de veille, la validation des documents. Chacun de ces gestes
engage quelqu'un. Une commande qui les prendrait en charge déplacerait cet
engagement vers un script, c'est-à-dire vers personne.

**Réversibilité.** Les trois commandes n'écrivent que des données. Une
attribution se retire, un document se supprime, un résumé se réécrit, une
adhésion se révoque — tout depuis l'interface. Aucun schéma n'est modifié,
aucune migration n'est introduite.
