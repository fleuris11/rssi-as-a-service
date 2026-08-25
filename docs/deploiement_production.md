# Mise en production — RSSI as a Service

> Document de référence pour le dossier de certification RNCP38822 (Blocs 2, 3, 4)
> et pour toute reprise du déploiement.
>
> **Date de mise en production** : 24 août 2026
> **URL** : https://rssiasservice.online
> **Rédigé à partir de mesures réelles**, pas d'estimations : chaque chiffre de
> ce document a été relevé sur le serveur en exploitation.

---

## 1. Contexte et contraintes

Trois contraintes ont structuré toutes les décisions :

| Contrainte | Conséquence |
|---|---|
| **Budget très limité** | Le coût récurrent devait rester sous ~5 €/mois |
| **Domaine déjà acquis** chez LWS (`rssiasservice.online`, expire le 26/12/2026) | Il fallait le conserver, pas le racheter ni le transférer |
| **Double finalité** : produit réel + support de certification | La traçabilité des décisions compte autant que le résultat |

Une quatrième contrainte, technique celle-là : l'application est un **monolithe
modulaire Django + Celery + PostgreSQL + Redis, orchestré par Docker Compose**
(ADR-007). Elle exige donc un accès **root** et un moteur Docker — ce qu'aucun
hébergement mutualisé ne fournit.

---

## 2. Le choix de l'hébergement

### 2.1 Pourquoi l'offre existante ne pouvait pas convenir

Le compte LWS existant portait une **formule « domaine »** avec 1 Go d'espace
web. Toutes les fonctions de son panneau apparaissaient grisées, ce qui a
d'abord laissé penser à un simple déblocage à obtenir.

En réalité, **même débloquée, cette formule n'aurait jamais pu héberger le
produit** : c'est de l'hébergement mutualisé PHP/MySQL. Ni Docker, ni accès
root, ni Python, ni PostgreSQL, ni processus de fond (Celery). Le produit ne
correspondait pas à l'offre, indépendamment de son état d'activation.

### 2.2 Serveur dédié écarté

La page consultée à l'origine (`lws.fr/serveur_dedie_linux.php`) porte le nom
« serveur dédié » mais commercialise en réalité des **VPS**. Un véritable
serveur dédié aurait représenté cinq à dix fois le besoin réel, pour une
application dont la consommation mesurée est inférieure à 1 Go de mémoire.

### 2.3 Dimensionnement par la mesure

Plutôt que d'estimer, la consommation a été **mesurée conteneur par conteneur**
sur l'environnement de développement, puis vérifiée en production.

Consommation relevée en production (`docker stats`, au repos) :

| Conteneur | Mémoire |
|---|---|
| Django / Gunicorn (`web`) | 212 Mo |
| Celery worker | 200 Mo |
| Celery beat | 108 Mo |
| PostgreSQL 16 | 54 Mo |
| Caddy | 19 Mo |
| Redis | 5 Mo |
| **Total conteneurs** | **~598 Mo** |
| **Total système** (avec OS et moteur Docker) | **962 Mo sur 3,7 Go** |

Occupation disque : **5,5 Go sur 39 Go**, images Docker comprises.

Conclusion du dimensionnement : **2 vCPU, 4 Go de RAM, 40 Go de disque**. Une
marge de trois fois la consommation au repos, suffisante pour absorber les
pics (génération PDF, appels IA, analyse CTI).

### 2.4 Comparaison des offres

Relevé le 24 août 2026, à configuration identique (2 vCPU / 4 Go) :

| Offre | Disque | Prix TTC/mois | Sur un an |
|---|---|---|---|
| **OVH VPS-1** *(retenu)* | 40 Go NVMe | **4,57 €** | **~55 €** |
| LWS VPS S | 80 Go | ~12 € | ~144 € |
| LWS VPS M | 120 Go | 4,99 € **le premier mois**, puis 24 € | ~240 € |

L'offre LWS à 4,99 € affichait le prix le plus bas mais s'avérait la plus
chère à l'année : la mention en note de bas de page précisait *« prix réduit
pendant le premier mois […] puis 19,99 € les mois suivants »*.

**Décision : OVH VPS-1.** Même machine que le VPS S de LWS pour **89 € de
moins par an**. Les 40 Go de moins sont sans effet : les images Docker du
projet pèsent 1,1 Go au total.

**Argument secondaire, non négligeable pour ce projet** : OVH est un hébergeur
français, et le serveur retenu est physiquement à **Strasbourg (région SBG)**.
Cela alimente directement deux exigences du produit — la politique de
confidentialité doit nommer l'hébergeur et localiser les données, et le
catalogue commercial comporte une offre nommée « Souverain ».

---

## 3. Architecture retenue

### 3.1 Séparation domaine / serveur

Le point le plus souvent mal compris, et pourtant central :

```
  rssiasservice.online              152.228.136.251
  ┌────────────────────┐            ┌────────────────────┐
  │  DOMAINE (LWS)     │            │  SERVEUR (OVH)     │
  │                    │            │                    │
  │  • enregistrement  │  DNS : A   │  • l'application   │
  │  • zone DNS        │ ─────────► │  • la base         │
  │  • boîtes email    │            │  • les traitements │
  └────────────────────┘            └────────────────────┘
         inchangé                          nouveau
```

Le domaine **reste chez LWS**. Seul un enregistrement DNS de type `A` a été
modifié pour pointer vers l'adresse IP du VPS. Aucun transfert, aucun rachat,
aucune interruption du service de messagerie.

**Zone DNS après modification** (les lignes en gras ont été modifiées) :

| Type | Nom | Valeur | Rôle |
|---|---|---|---|
| **A** | **@** | **152.228.136.251** | **le site → le VPS** |
| CNAME | www | `@` | suit automatiquement |
| A | mail | 83.229.19.96 | messagerie, **inchangée** |
| MX | @ | `10 mail.rssiasservice.online.` | messagerie, **inchangée** |
| CNAME | imap / pop / smtp | `mail.rssiasservice.online.` | messagerie, **inchangée** |

Les serveurs de noms (`ns21` à `ns24.lwsdns.com`) n'ont **pas** été touchés :
la gestion DNS reste chez LWS. Modifier les NS aurait cassé la messagerie.

### 3.2 Comment le backend et le frontend cohabitent sur le VPS

Le frontend React n'est **pas** servi par un serveur séparé, et n'appelle pas
l'API sur un autre domaine. Les deux sont derrière **un seul point d'entrée**
— Caddy — ce qui supprime toute question de CORS et de certificat croisé.

```
Internet
   │  HTTPS 443  (HTTP 80 → redirection 308)
   ▼
┌──────────────────────────────────────────────────┐
│  CADDY  (image construite depuis deploy/)        │
│  • certificat Let's Encrypt automatique          │
│  • en-têtes de sécurité (HSTS, CSP, …)           │
│                                                  │
│  /api/*  /admin/*  /healthz  /static/*           │
│        └────────► reverse proxy ──► web:8000     │
│                                                  │
│  tout le reste                                   │
│        └────────► fichiers statiques /srv        │
│                   (build React, repli index.html)│
└──────────────────────────────────────────────────┘
                        │
   ┌────────────────────┼────────────────────┐
   ▼                    ▼                    ▼
┌────────┐        ┌──────────┐         ┌──────────┐
│  web   │        │  worker  │         │   beat   │
│gunicorn│        │  Celery  │         │ Celery   │
└────┬───┘        └────┬─────┘         └────┬─────┘
     └─────────────────┼────────────────────┘
              ┌────────┴────────┐
              ▼                 ▼
        ┌──────────┐      ┌─────────┐
        │PostgreSQL│      │  Redis  │
        │  (volume)│      │         │
        └──────────┘      └─────────┘
```

**Points structurants :**

- **Une seule image Caddy contient le frontend compilé.** `deploy/Dockerfile.caddy`
  construit en deux étapes : Node compile la SPA React, puis le résultat est
  copié dans l'image Caddy. Il n'y a donc pas de serveur Node en production.
- **Le frontend appelle l'API sur la même origine.** À la compilation,
  `VITE_API_URL` vaut la chaîne vide, ce qui fait pointer les appels vers
  l'origine courante. C'est Caddy qui les route vers Django.
- **PostgreSQL et Redis ne sont pas exposés à l'hôte.** Aucun `ports:` dans le
  fichier de production : ils ne sont joignables que depuis le réseau interne
  des conteneurs. Le pare-feu n'ouvre que 22, 80 et 443.
- **Trois processus applicatifs distincts** : Gunicorn pour les requêtes HTTP,
  un worker Celery pour les traitements longs (analyses, IA, emails), un
  ordonnanceur pour les tâches périodiques. Aucun appel réseau lent ne se
  produit dans le cycle requête/réponse (règle du cadrage).
- **Persistance par volumes Docker nommés** : `rssi_postgres_data` (la base),
  `rssi_caddy_data` (les certificats), `rssi_caddy_config`. Détruire les
  conteneurs ne détruit pas les données.

---

## 4. Déroulé du déploiement

Chaque étape a été **vérifiée**, pas supposée réussie. Les vérifications
figurent en regard.

### Étape 1 — Commande du VPS

Ubuntu 22.04 LTS, sans panneau d'administration préinstallé (Plesk ou cPanel
auraient consommé de la mémoire sans usage ici), aucune option payante.

### Étape 2 — Accès et durcissement

| Action | Vérification effectuée |
|---|---|
| Génération d'une paire de clés ed25519 sur le poste | empreinte relevée, clé privée restreinte au seul compte utilisateur (ACL Windows) |
| Installation de la clé publique sur le serveur | connexion par clé testée |
| Mise à jour complète du système | — |
| Pare-feu UFW : 22, 80, 443 uniquement, tout le reste refusé | règles listées |
| **Désactivation de l'authentification par mot de passe** | **testée dans les deux sens** : la clé passe, le mot de passe est refusé |
| Interdiction de la connexion `root` | — |
| Mises à jour de sécurité automatiques | service actif |
| fail2ban (bannissement après 4 échecs) | actif — **5 tentatives déjà interceptées** dans l'heure suivant la mise en service |

> **Point à retenir pour le mémoire** : le durcissement a été fait **avant**
> de déployer quoi que ce soit. Une IP publique est balayée par des robots dans
> les minutes qui suivent son activation — fail2ban en a apporté la preuve.

La désactivation du mot de passe a été précédée d'une **vérification que la clé
était bien en place**. Couper l'authentification par mot de passe sans ce
contrôle est le moyen classique de se condamner l'accès à son propre serveur.

### Étape 3 — Docker

Dépôt officiel Docker (la version des dépôts Ubuntu n'inclut pas Compose v2).
Résultat : Docker 29.7.2, Compose v5.5.0, utilisables sans `sudo`.

*Vérification* : exécution d'un conteneur de test.

### Étape 4 — Récupération du code

Clonage depuis GitHub (dépôt public), commit vérifié après clonage.

### Étape 5 — Secrets de production

**Générés sur le serveur**, jamais transmis par un canal quelconque :

- clé secrète Django (50 caractères)
- mot de passe PostgreSQL (32 caractères)
- **trois clés Fernet distinctes** : pseudonymisation IA, secrets 2FA, mots de
  passe fuités (ADR-005 / 009 / 014)

*Vérifications* : présence, longueur, **distinction effective des trois clés**
(une collision annulerait silencieusement la séparation des usages),
permissions `600`, et confirmation que le fichier est ignoré par git.

> **Conséquence à documenter** : une compromission du poste de développement
> ne donne aucun accès aux données de production. En contrepartie, la perte de
> ces clés rendrait les mots de passe fuités chiffrés **définitivement
> illisibles** — d'où la stratégie de sauvegarde décrite au §6.

### Étape 6 — Construction et migrations

Quatre images construites (`web`, `worker`, `beat`, `caddy`).
Migrations appliquées au démarrage par l'`entrypoint`.

*Vérification* : lecture des journaux, puis appel de l'API **depuis l'intérieur
du conteneur** avant toute exposition publique.

### Étape 7 — DNS

Modification de l'enregistrement `A` dans le panneau LWS.

*Vérification* : propagation contrôlée sur **trois résolveurs publics
indépendants** (Google, Cloudflare, Quad9), et confirmation que les
enregistrements de messagerie étaient intacts.

### Étape 8 — HTTPS

Démarrage de Caddy, obtention automatique des certificats Let's Encrypt pour
le domaine et son sous-domaine `www`.

*Vérifications, depuis l'extérieur* :

| Contrôle | Résultat |
|---|---|
| Vitrine, connexion, pages légales | HTTP 200 |
| API et `/healthz` | HTTP 200 |
| HTTP → HTTPS | 308 |
| Certificat | Let's Encrypt, valide jusqu'au 22/11/2026 |
| En-têtes de sécurité | HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy |
| En-tête `Server` | masqué |

### Étape 9 — Compte administrateur

Créé **sans mot de passe**, avec émission d'un lien d'invitation à usage unique
et durée limitée (72 h). L'exploitant définit lui-même son mot de passe.

> Ce n'est pas un détail de confort : c'est le mécanisme d'invitation
> développé en phase 11, et son premier usage réel a servi de test en
> conditions de production.

---

## 5. Configuration post-déploiement

### 5.1 Clés d'API

Saisies **en frappe masquée** via `deploy/configurer-secret.sh`, jamais passées
en argument de ligne de commande — un argument est visible dans `ps` par tout
utilisateur de la machine et persiste dans l'historique du shell.

*Vérification de la clé IA* : un **appel réel à l'API Anthropic** a été
effectué (8 jetons en entrée, 1 en sortie). Vérifier la seule présence d'une
clé ne prouve rien.

### 5.2 Messagerie

Serveur SMTP de LWS, port 587 avec STARTTLS. Trois obstacles ont été
rencontrés et sont documentés au §7.

*Vérification* : envoi réel d'un message **et** contrôle que le flux
d'invitation bascule effectivement de « lien à copier » à « email envoyé ».

### 5.3 Réglages d'exploitation

Onze réglages sont modifiables **depuis la console d'administration**, sans
accès au serveur ni redémarrage : plafonds de licence, durée et offre d'essai,
durées de conservation, seuils d'alerte, ouverture des inscriptions, message
de maintenance, durée de corbeille, et **source du renseignement CTI**.

Chaque réglage vit en base avec **repli sur la variable d'environnement** tant
qu'il n'a jamais été modifié : la plateforme démarre donc sans aucune ligne en
base.

**Les secrets ne sont pas dans ce mécanisme** et n'y seront pas : une clé de
chiffrement en base serait exposée par la moindre sauvegarde et la moindre
injection SQL. La console n'affiche que leur présence et leur validité.

---

## 6. Sauvegarde

### Ce qui est sauvegardé

`deploy/sauvegarde.sh`, exécuté **chaque nuit à 3 h 30** :

1. un export complet de la base PostgreSQL ;
2. **le fichier `.env`, qui porte les clés de chiffrement** ;
3. le commit déployé au moment de la sauvegarde ;
4. l'horodatage.

Le deuxième point est celui qu'on oublie. Les mots de passe fuités sont
chiffrés en base (ADR-014) : **une base restaurée sans sa clé serait en partie
illisible**. C'est une erreur qui ne se découvre que le jour où l'on restaure.

Le troisième permet de savoir quelle version de l'application tournait —
restaurer une base sur un code plus ancien casse les migrations.

### Garde-fous

- Le script **refuse de produire une archive** si l'export fait moins de
  50 lignes : une sauvegarde vide qui écrase les précédentes est pire que pas
  de sauvegarde.
- Rotation à 14 jours.
- Archive en permissions `600` — elle contient des secrets.

### Restauration vérifiée

**Une sauvegarde jamais restaurée n'est pas une sauvegarde.** La restauration
a été testée dans une **base jetable**, sans jamais toucher la production :
51 tables, le compte administrateur et les trois offres retrouvés, puis base
de test supprimée.

### Copie hors serveur

Une copie est rapatriée sur le poste de l'exploitant, dans un dossier
restreint à son seul compte.

> **Décision documentée** : cette copie a d'abord été placée dans OneDrive,
> puis déplacée hors du dossier synchronisé. L'archive contient les clés de
> chiffrement en clair ; les confier à un tiers sans chiffrement préalable
> n'était pas un choix acceptable par défaut.

**Limite assumée à ce jour** : la copie hors serveur est manuelle. Une
sauvegarde réellement externalisée et automatique reste à mettre en place.

---

## 7. Défauts découverts en conditions réelles

Cette section a une valeur particulière pour le mémoire : **aucun de ces
défauts n'avait été révélé par la suite de tests**, pourtant verte
(910 tests backend, 102 frontend, 15 parcours de bout en bout).

| # | Défaut | Conséquence évitée |
|---|---|---|
| 1 | **La production pouvait basculer en mode `live` par omission.** `settings_production.py` posait en commentaire qu'« un `.env` incomplet ne doit pas basculer silencieusement en live », puis définissait `default="live"` — le code contredisait son propre commentaire. | Un déploiement oubliant une ligne de configuration aurait consommé le quota réel de la licence CTI (1000 requêtes/mois pour toute la plateforme) **sans décision de personne**. |
| 2 | **La procédure de déploiement documentée ne fonctionnait pas.** Compose interpole les variables depuis un `.env` situé à la racine du dépôt, alors que le projet ne fournissait que `backend/.env`. | Mot de passe PostgreSQL vide, échec au démarrage, message d'erreur ne désignant pas la cause. |
| 3 | **Le client de démonstration le plus riche n'avait aucun abonnement.** Les gardes de droits traitent « aucun abonnement » comme un abonnement non opérationnel. | **Toute démonstration se serait arrêtée au premier bouton.** |
| 4 | **Aucune sauvegarde n'existait**, et rien ne prévoyait de sauvegarder les clés de chiffrement. | Perte définitive des mots de passe fuités en cas d'incident. |
| 5 | **L'offre d'essai par défaut était la plus coûteuse en ressource rare** (3 emplacements sur 15). | La plateforme n'autorisait que **cinq essais gratuits au total** — et zéro une fois le jeu de démonstration chargé. |
| 6 | **Après connexion, un administrateur plateforme atterrissait sur l'espace client**, dont il n'est membre d'aucune entreprise par construction. | Écran vide affichant « Aucune entreprise associée à votre compte », sans lien vers la console : **le produit paraissait cassé alors que tout fonctionnait**. |

À quoi s'ajoutent trois obstacles rencontrés sur la configuration de la
messagerie, tous imputables aux scripts de déploiement et tous corrigés dans
le dépôt : un alias SMTP au lieu du nom réel du serveur (le certificat TLS est
émis pour la machine, pas pour l'alias du domaine) ; des fins de ligne Windows
rendant un script inexécutable sous Linux ; et des scripts enregistrés dans
git sans bit d'exécution, perdant ce droit à chaque `git pull`.

> **Enseignement à exploiter dans le mémoire** : une suite de tests verte
> valide le comportement du logiciel, pas la viabilité de son déploiement ni
> la cohérence de son paramétrage. Les six défauts ci-dessus relèvent tous de
> la configuration, de la procédure ou des données d'exploitation — trois
> domaines qu'aucun test unitaire ne couvre par construction.

---

## 8. Traçabilité

Sept commits documentent cette mise en production :

| Commit | Date | Objet |
|---|---|---|
| `773ecbb` | 24/08 | la procédure de déploiement documentée ne fonctionnait pas |
| `1a3f9f4` | 24/08 | sauvegarde quotidienne vérifiée + outil de saisie des secrets |
| `ab90d17` | 25/08 | la production ne peut plus basculer en live par omission |
| `a96081b` | 25/08 | configuration email vérifiée par un envoi réel |
| `8dd7070` | 25/08 | le script email visait un alias, pas le vrai serveur SMTP |
| `6b1bc24` | 25/08 | logo officiel, favicon et image de partage |
| `e363656` | 25/08 | les scripts sont enregistrés comme exécutables |

---

## 9. Coût d'exploitation

| Poste | Coût |
|---|---|
| VPS OVH VPS-1 | 4,57 € TTC/mois |
| Domaine LWS | déjà acquis, ~12 €/an |
| Certificat TLS | gratuit (Let's Encrypt) |
| **Total récurrent** | **~5 € par mois** |

Coûts variables non inclus : appels à l'API Anthropic (facturés à l'usage,
modèle économe par défaut selon le cadrage Green IT) et licence Breachsense.

---

## 10. Ce qui reste à faire

| Point | Nature | Criticité |
|---|---|---|
| **Identité légale de l'éditeur** | `frontend/src/marketing/legalConfig.js` attend la raison sociale, l'immatriculation et l'adresse. Les pages affichent un bandeau « à compléter » tant qu'elles manquent. | **Bloquant avant toute commercialisation** |
| **Structure juridique** | Sans entité, aucun encaissement n'est possible. Le produit est prêt, le cadre ne l'est pas. | **Bloquant** |
| **Sauvegarde externalisée automatique** | La copie hors serveur est manuelle. | Élevée |
| **Relecture juridique** | Les CGV sont une trame minimale ; le contrat de sous-traitance (DPA) reste à rédiger (`docs/legal/README.md`). | Élevée |
| **Palier de licence CTI** | 15 emplacements partagés, dont 13 engagés par le jeu de démonstration. Deux restent disponibles. | Moyenne |
| **Supervision** | Aucune alerte en cas d'arrêt du service. La console montre l'état, encore faut-il l'ouvrir. | Moyenne |
| **Intégration continue vers la production** | Le déploiement est manuel (`git pull` + reconstruction). | Faible |

---

## 11. Reproduire ce déploiement

Sur un serveur Ubuntu 22.04 neuf, avec Docker installé :

```bash
git clone https://github.com/fleuris11/rssi-as-a-service.git ~/rssi
cd ~/rssi

# Compose lit les variables depuis un .env situé À CÔTÉ du fichier compose.
# Un lien plutôt qu'une copie : deux fichiers divergeraient à la première
# rotation de mot de passe.
cp backend/.env.example backend/.env
ln -s backend/.env .env

# Renseigner backend/.env : clés générées sur la machine, jamais reprises
# d'un autre environnement. BREACHSENSE_MODE doit être explicite.

docker compose -f docker-compose.prod.yml up -d --build

# Données de démonstration (facultatif, refusé si DEBUG=False sans le drapeau)
docker compose -f docker-compose.prod.yml exec web \
    python manage.py load_anssi_referential
docker compose -f docker-compose.prod.yml exec web \
    python manage.py seed_demo_tenant --allow-production
docker compose -f docker-compose.prod.yml exec web \
    python manage.py seed_demo_clients --allow-production
```

Puis faire pointer le domaine (enregistrement `A`) vers l'adresse IP du
serveur. Caddy obtient le certificat seul, dès que le DNS a propagé.

---

## Annexe — Documents liés

| Document | Contenu |
|---|---|
| `docs/adr/007-docker-compose-vps-caddy.md` | choix de l'architecture de déploiement |
| `docs/adr/013-integration-breachsense-cti.md` | plafonds de la licence CTI, ressource partagée |
| `docs/adr/014-secret-chiffre-revelation-tracee.md` | chiffrement réversible des secrets, séparation des clés |
| `docs/adr/015-modes-cti-cassettes-rejouables.md` | modes du fournisseur de renseignement |
| `docs/adr/021-propagation-des-modifications-d-offre.md` | propagation des modifications d'offre |
| `docs/adr/022-droits-des-administrateurs-plateforme.md` | modèle de droits des administrateurs |
| `docs/legal/README.md` | état des textes juridiques, travail restant |
| `docs/identite-visuelle/README.md` | logos et déclinaisons |
| `docs/journal.md` | journal de bord, phase par phase |
