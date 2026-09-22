# Product

<!-- impeccable:product-schema 1 -->

> Ce fichier a été écrit sans entretien : l'utilisateur a explicitement demandé
> d'enchaîner sans poser de questions. Tous les faits proviennent du dépôt
> (`docs/cadrage_rssi_as_a_service.md`, `CLAUDE.md`, le code, les migrations) ou
> du brief écrit. Les déductions sont signalées par **[déduit]**.

## Platform

web

## Users

Deux publics, dans le même produit, sur les mêmes données.

- **Le dirigeant de TPE/PME française** (10 à 250 salariés) : gérant, DAF,
  responsable administratif. Il n'est pas informaticien, n'a pas de RSSI, et
  n'ouvre le produit que quelques minutes par semaine — souvent parce qu'il a
  reçu un email. Sa question est « est-ce que je dois faire quelque chose
  aujourd'hui, et quoi ». Le jargon le fait décrocher.
- **Le prestataire informatique ou le référent technique** : infogéreur,
  informaticien interne, parfois le neveu doué. Il veut les données brutes,
  les filtres, le détail d'un enregistrement DNS, la date exacte d'une fuite.

Le produit sert aussi **l'exploitant de la plateforme** (une console
d'administration séparée) : gestion des clients, des offres, des demandes
d'accès, des campagnes.

## Product Purpose

Donner à une PME sans expertise cyber une vision continue de son exposition et
une liste courte de choses à faire, sans rien installer chez elle.

Quatre mécanismes réellement implémentés :

1. **Diagnostic de maturité** sur le référentiel ANSSI d'hygiène informatique
   (42 mesures), scoring, restitution, et génération d'un plan d'action en
   kanban.
2. **Surveillance continue passive** des actifs déclarés : disponibilité,
   certificats TLS, en-têtes de sécurité HTTP, SPF/DKIM/DMARC. Aucun agent,
   aucun scan intrusif, uniquement ce qui est public.
3. **Renseignement sur les fuites de données** concernant les domaines et
   comptes déclarés, avec révélation de secret tracée et chiffrée.
4. **Formation des salariés** : parcours courts par lien nominatif, quiz,
   attestation de suivi, campagnes et relances.

Autour : météo cyber quotidienne par email, veille réglementaire, génération
documentaire assistée par IA, comptes désignés (dirigeants exposés), rapports
de comité.

Le succès, c'est qu'un dirigeant qui ouvre l'outil comprenne en moins d'une
minute s'il doit agir, et que son prestataire trouve en moins d'une minute de
quoi il s'agit techniquement.

## Positioning

Ce que la plupart des produits voisins ne font pas :

- **Le même fait est dit deux fois, pour deux lecteurs.** Un profil d'affichage
  Dirigeant et un profil Technique changent la restitution, pas les données.
- **Le produit propose, il ne décide jamais.** La veille réglementaire suggère
  une mesure, elle ne la modifie pas. Une campagne de formation qui atteint ses
  seuils propose de renseigner une mesure ANSSI — c'est une proposition, jamais
  une validation silencieuse. Cette règle est codée, pas déclarative.
- **La sobriété est une contrainte d'architecture** : modèle IA court par
  défaut, cache des réponses stables, quotas de jetons par client, périodicités
  de vérification raisonnées.
- **Le cloisonnement échoue fermé** : le manager par défaut des modèles métier
  ne rend rien hors contexte client, plutôt que de rendre tout.

## Operating Context

- Le dirigeant arrive le plus souvent depuis un **email** (météo quotidienne,
  alerte, relance de formation), sur **téléphone**, entre deux tâches.
- Le prestataire arrive depuis un **poste de bureau**, souvent avec plusieurs
  onglets, et veut trier et exporter.
- Le salarié en formation n'a **pas de compte** : il suit un lien nominatif,
  sur son téléphone, moins de dix minutes.
- L'exploitant travaille dans la console, en usage dense, plusieurs clients à
  la suite.
- Interface, documentation utilisateur et libellés : **en français**. Code et
  identifiants en anglais.

## Capabilities and Constraints

- Django 5 + DRF, monolithe modulaire ; React 18 + Vite + Tailwind ;
  PostgreSQL 16 en schéma partagé multi-client ; Redis ; Celery.
- **Le backend ne bouge pas dans cette refonte.** Gardes 402 (fonctionnalité
  hors offre), cloisonnement, révélation de secret, droits par rôle et
  journalisation d'audit restent intacts.
- Une fonctionnalité hors offre répond **402 Payment Required**, jamais 403 :
  l'écran doit donc savoir afficher « hors de votre offre » sans ressembler à
  une erreur ni à un refus de droits.
- **Aucun service payant ni appel externe au moment de l'exécution** : polices
  et bibliothèques auto-hébergées, synthèse vocale par le navigateur.
- Le nom du fournisseur de renseignement sur les fuites **ne doit apparaître
  nulle part** dans ce qui est livré au navigateur : ni texte, ni route, ni
  nom de fichier, ni capture.
- Rôles : Administrateur, Contributeur, Lecteur. Offres : essai, Veille,
  Pilotage, Souveraine — les quotas portent sur l'engagement, pas l'usage réel.
- Accessibilité : **WCAG AA** est une exigence de la certification RNCP38822
  visée par le projet, pas un confort.

## Brand Commitments

- Nom : **RSSI as a Service**. Domaine : rssiasservice.online.
- Monogramme « net » existant, à conserver ; pas de logo pixelisé.
- Ton : sobre, factuel, jamais alarmiste, jamais commercial. Le produit n'a
  qu'un client réel : **aucun chiffre commercial, aucun témoignage, aucun
  logo de référence ne peut être affiché** — ils n'existent pas.
- Vocabulaire imposé : « attestation de suivi », jamais « certification » ni
  « habilitation ».
- Pas d'emoji, pas d'icône purement décorative. **[déduit du brief]**

## Evidence on Hand

Réel et utilisable :

- Le référentiel ANSSI, 42 mesures, en base.
- Un client de démonstration fictif complet (`seed_demo_tenant`), le seul
  autorisé pour les captures : Cabinet Comptable Durand.
- Des captures réelles du produit dans `frontend/public/screenshots/`.
- Des faits vérifiables dans le code : 42 mesures, rétention des secrets de
  fuite à 90 jours, hébergement en France.

Absences que rien ne doit combler par invention : **aucun témoignage client,
aucun chiffre d'affaires, aucun nombre d'utilisateurs, aucun logo de
référence, aucun benchmark.** Le produit compte un seul client réel, et ses
données ne peuvent apparaître nulle part.

## Product Principles

1. **Deux lecteurs, une vérité.** Le dirigeant et le technicien voient la même
   donnée dans deux langues ; jamais deux chiffres différents.
2. **Proposer, ne jamais décider à la place.** Toute automatisation qui
   toucherait un jugement passe par une proposition explicite.
3. **Dire le risque, pas la peur.** Le niveau de risque est une information,
   pas un argument de vente.
4. **Échouer fermé.** Hors contexte, on ne montre rien plutôt que tout.
5. **Sobre par construction.** Le choix le moins coûteux est le choix par
   défaut, côté IA comme côté page.

## Accessibility & Inclusion

WCAG 2.1 AA sur l'ensemble du front : contraste 4,5:1 sur le texte courant,
focus visible au clavier, navigation complète sans souris, `prefers-reduced-motion`
respecté, aucun débordement horizontal au téléphone, aucune information portée
par la couleur seule. Vérifié automatiquement par axe-core dans la CI.
