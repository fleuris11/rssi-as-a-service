# ADR-022 — Modèle de droits des administrateurs plateforme

- **Statut** : accepté
- **Date** : 2026-08-15
- **Phase** : 11 (console d'administration complète)

## Contexte

Jusqu'à la phase 11, l'accès à l'administration reposait sur le seul booléen
`is_staff` de Django : on l'a, on peut tout faire — suspendre un client,
modifier le catalogue, changer les plafonds de licence.

La phase 11 ouvre la console à un usage quotidien et à d'autres personnes que
le fondateur. Un collaborateur qui prospecte a besoin de voir les clients
pour les rappeler et de tenir ses affaires à jour ; il n'a aucune raison de
pouvoir résilier un abonnement ou changer un prix.

## Options

### A. Garder `is_staff` seul

Rien à construire. Mais le premier collaborateur reçoit les pleins pouvoirs,
et le seul recours contre une erreur est la confiance.

### B. Permissions Django natives (`Permission`, `Group`)

Le mécanisme existe et est éprouvé. En contrepartie, il faut administrer une
matrice de permissions par modèle, exposer un écran pour la gérer, et
répondre à des questions qui ne se posent pas ici (« peut-il ajouter un
`SubscriptionEvent` mais pas le modifier ? »). Le vocabulaire des permissions
Django est celui des tables, pas celui du métier.

### C. Deux niveaux métier (retenue)

Un modèle `PlatformAdminProfile` porte un `level` :

- **complet** : tout, y compris la configuration de la plateforme et la
  gestion des autres administrateurs ;
- **commercial** : lecture de tous les écrans, plus la gestion des prospects
  (créer, annoter, faire avancer, planifier une relance).

### D. Trois niveaux (lecture seule / commercial / complet)

Plus fin. Mais un niveau « lecture seule » sans écriture d'aucune sorte ne
correspondait à aucun besoin identifié : la personne à qui l'on ouvre la
console est celle qui travaille les affaires.

## Décision

**Option C**, avec deux règles de sûreté.

Le nombre de rôles est délibérément petit et **métier** : ce sont deux
métiers réels, pas une matrice à composer. Le jour où un troisième apparaît
(support technique, comptabilité), il s'ajoutera comme un troisième niveau —
la structure le permet sans refonte.

### Règles de sûreté

1. **On ne se retire pas soi-même**, ni ses propres droits, ni son niveau.
   C'est le moyen le plus simple de se retrouver enfermé dehors.
2. **Le dernier administrateur complet ne peut être ni retiré ni rétrogradé.**
   Sans lui, plus personne ne peut promouvoir qui que ce soit : la console
   devient inaccessible, et seul un accès au serveur permet d'en sortir —
   exactement ce que cette phase élimine.

### Compatibilité

Un compte `is_staff` **sans profil** est traité comme **complet**. C'est le
cas du fondateur et de tous les comptes antérieurs à cette phase : le
déploiement de la migration ne doit retirer les droits de personne.

## Conséquences

- `IsPlatformAdmin` garde l'entrée de la console, quel que soit le niveau.
- `IsFullPlatformAdmin` ouvre la lecture aux deux niveaux et réserve
  l'écriture au niveau complet. C'est la classe par défaut de toutes les vues
  d'administration, **y compris celles de la phase 10** : une garde qui
  dépend du chemin emprunté n'est pas une garde. Ce recâblage a corrigé un
  trou réel — un commercial pouvait modifier le catalogue par les anciennes
  vues.
- Les vues de gestion des prospects surchargent explicitement leur permission
  en `IsPlatformAdmin` : c'est le seul domaine d'écriture ouvert au niveau
  commercial.
- Côté interface, les actions hors niveau seront **désactivées, jamais
  masquées**, comme les fonctionnalités hors offre côté client : on montre ce
  qui existe et à qui le demander.
- `is_superuser` n'est pas utilisé pour ces décisions. Il reste ce qu'il est
  dans Django : un contournement de dernier recours, pas un rôle produit.
