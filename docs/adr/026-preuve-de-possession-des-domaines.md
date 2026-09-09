# ADR-026 — Preuve de possession avant surveillance continue

- **Statut** : accepté
- **Date** : 2026-09-09
- **Contexte** : corrige la portée d'ADR-010 (« un actif n'est vérifié que s'il
  est déclaré ») et pose une condition supplémentaire sur le mode webhook
  d'ADR-013

## Contexte

ADR-010 pose qu'un actif n'est vérifié que s'il a été **déclaré** par le
tenant. C'était la bonne règle contre le mauvais risque : elle empêche la
plateforme d'aller sonder des domaines au hasard, mais elle ne dit rien de la
légitimité du déclarant.

La production a montré la faille, et elle n'était pas théorique. Le
3 septembre 2026, le premier client réel (CRRH) a déclaré **`ratp.fr`** parmi
ses actifs. Le point est resté ouvert dans le journal depuis, avec la mention
« déclarer n'est pas posséder — à trancher ». Le 4 septembre, un rapprochement
avec le fournisseur a montré que le pool de surveillance contenait aussi
`afinhab.org`, qui n'était même pas un actif déclaré.

Ce qui a été mis en place jusqu'ici — la case `ownership_confirmed`, cochée à
la déclaration — n'était pas une preuve et ne laissait **aucune trace** : ni
qui l'avait cochée, ni quand, ni sur quel actif. Le jour où l'organisation
tierce demande des comptes, un booléen ne répond à aucune des trois questions.

## Ce que le produit fait réellement à un domaine

La question ne se tranche pas en bloc, parce que les deux gestes du produit
n'engagent pas la même chose.

| | Analyse ponctuelle | Surveillance continue |
|---|---|---|
| Durée | un instant | des mois |
| Visibilité | décidée et datée | invisible du dehors |
| Ressource | quelques requêtes du quota | un des 15 emplacements de la licence |
| Effet | un rapport, lu une fois | des alertes qui partent d'elles-mêmes |
| Nature des données | ce que le fournisseur sait déjà | idem, en continu |

Aucun des deux ne « scanne » le domaine d'un tiers : ce sont des lectures de
bases de fuites déjà constituées (ADR-013), pas des sondes intrusives. Le
risque n'est donc pas technique, il est **juridique et réputationnel** :
produire, conserver et notifier un dossier de compromissions sur une
organisation qui n'a rien demandé et ne le sait pas.

C'est cette différence de durée et d'invisibilité qui justifie deux régimes
plutôt qu'un.

## Options

**A. Ne rien changer, s'en remettre aux CGV.**
Rejeté. Une clause contractuelle ne fait pas obstacle à la constitution du
dossier ; elle ne fait que déplacer la responsabilité sur le client une fois
le dommage produit. Et elle ne répond toujours pas à « qui a déclaré ce
domaine, et quand ? ».

**B. Exiger une preuve de possession pour tout — déclaration comprise.**
Rejeté, et c'est l'option la plus tentante. Elle bloquerait l'entrée du
produit : une PME qui découvre la plateforme ne doit pas avoir à ouvrir sa
zone DNS avant d'obtenir son premier résultat. L'effet « waouh » de
l'onboarding (ADR-013 §2) repose précisément sur une analyse déclenchée à la
déclaration d'un actif. Exiger la preuve à cet endroit reviendrait à échanger
un risque juridique contre un produit que personne n'essaie.

**C. Une seule méthode de preuve (DNS TXT).**
Rejeté. C'est la méthode la plus solide, mais elle suppose la main sur la zone
DNS — ce qu'une PME dont le domaine est géré par un prestataire ou un
hébergeur mutualisé n'a pas toujours. Une seule méthode ne supprime pas le
blocage, elle le déplace vers les clients les moins outillés, c'est-à-dire
exactement la cible du produit.

**D. Deux régimes : preuve pour la surveillance continue, déclaration tracée
pour l'analyse ponctuelle.**
Retenu.

## Décision

1. **La surveillance continue exige une preuve de possession vérifiée.** La
   garde (`monitoring.services.ensure_ownership_proven`) est appelée par
   `threat_intelligence.services.register_monitored_asset` **avant toute autre
   vérification** — avant le quota d'offre, avant le pool, avant tout appel
   sortant au fournisseur. Un domaine dont on ne sait pas s'il appartient au
   client ne doit ni consommer un emplacement de la licence, ni faire l'objet
   d'une requête à son sujet.

2. **Trois méthodes au choix du client**, parce qu'aucune n'est disponible
   pour tout le monde :
   - un **enregistrement DNS TXT** `rssi-verification=<jeton>` publié sur le
     domaine ;
   - un **fichier** `/.well-known/rssi-verification.txt` contenant le jeton ;
   - un **email de validation** envoyé à une adresse d'administration du
     domaine, choisie dans une **liste fermée** (`admin`, `administrator`,
     `hostmaster`, `postmaster`, `webmaster`) — les mêmes que celles employées
     par les autorités de certification, et pour la même raison : laisser le
     demandeur saisir l'adresse de son choix reviendrait à lui demander de
     s'écrire à lui-même.

3. **L'analyse ponctuelle reste possible sans preuve**, sur une **déclaration
   sur l'honneur tracée** : `AssetOwnershipAttestation` enregistre l'auteur, la
   date, l'actif, l'adresse IP et le texte exact accepté. Le texte est recopié
   plutôt que référencé — une déclaration doit pouvoir être relue dans les
   termes où elle a été présentée, même après que le formulaire a changé.

4. **Les actifs antérieurs ne sont pas coupés.** Ceux qui ne portent ni preuve
   ni déclaration tracée — c'est-à-dire tous ceux déclarés avant cette
   décision — sont marqués « à vérifier » et listés dans un écran de la
   console (`/api/v1/platform/ownership-review/`). Couper un client pour une
   règle postérieure à son engagement serait le punir de notre propre retard.
   L'état est **dérivé** des tables, jamais stocké : un drapeau aurait dû être
   posé par une migration puis maintenu à jour à chaque preuve validée, soit
   deux occasions de mentir.

5. **L'email de validation dit au tiers comment refuser.** Il nomme
   l'entreprise demandeuse, explique ce qui sera activé, et précise que ne pas
   transmettre le code suffit à tout empêcher. Sans cette porte de sortie, la
   méthode ne serait qu'une formalité de plus — elle ne vaut que parce que le
   destinataire peut dire non.

## Conséquences

- **La surveillance continue devient un geste en deux temps** : prouver, puis
  activer. L'écran nomme l'étape manquante (« Prouver la possession » au lieu
  de « Surveiller ») plutôt que de laisser le client la découvrir en échouant.
- **Les vérifications réseau sont passives**, au sens d'ADR-010 : une requête
  DNS publique et un GET HTTP. Le GET passe par `safe_get`, donc par la
  validation SSRF de chaque saut de redirection — un domaine dont on ne sait
  pas encore s'il appartient au client est exactement la cible qu'il ne faut
  pas suivre les yeux fermés.
- **Le jeton n'est pas un secret au sens d'ADR-014** : il est fait pour être
  publié. Il reste imprévisible (`secrets.token_urlsafe`), sans quoi n'importe
  qui pourrait publier le jeton d'un domaine qu'il ne possède pas.
- **Le refus est traduit à la frontière de l'app.** `OwnershipNotProvenError`
  existe en deux exemplaires — un dans `monitoring`, un dans
  `threat_intelligence` — et le second traduit le premier. Sans cela, l'erreur
  traversait le `except ThreatIntelligenceError` des vues jusqu'en 500 : un
  refus de règle métier présenté au client comme une panne.
- **Le cas `ratp.fr` reste à traiter humainement.** La décision empêche
  désormais d'en activer la surveillance continue, et l'écran de
  régularisation le fait apparaître ; elle ne décide pas à la place de
  l'exploitant ce qu'il faut dire au client.

## Ce que cette décision ne fait pas

- Elle **ne vérifie pas la possession en continu**. Une preuve acquise le
  reste : un domaine qui change de mains ne serait pas détecté. Une
  re-vérification périodique est un durcissement ultérieur, à décider quand le
  volume le justifiera.
- Elle **ne régularise pas l'existant**. Elle le rend visible, et rien de plus.
  Les actifs antérieurs continuent d'être surveillés jusqu'à ce que quelqu'un
  s'en occupe.
- Elle **ne dit rien des deux domaines orphelins** relevés côté fournisseur le
  4 septembre (`afinhab.org`, `crrhuemoa.org` sans `MonitoredAsset`
  correspondant). C'est un problème de rapprochement, distinct, toujours
  ouvert.

## Réversibilité

Le schéma est purement additif (deux tables, aucun champ retiré). Retirer
l'exigence se ferait en supprimant un appel — `ensure_ownership_proven` — sans
migration ni perte de données : les preuves déjà obtenues resteraient
lisibles. C'est volontaire : une décision prise sous la pression d'un incident
doit pouvoir être desserrée sans chantier si elle se révèle trop stricte pour
le marché visé.
