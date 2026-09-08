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

## 6 bis. Retour à la v1 — procédure de repli

> **À qui s'adresse cette section** : à quelqu'un qui découvre le projet, un
> soir d'incident. Elle se lit de haut en bas et ne suppose aucune
> connaissance préalable de l'architecture. Toutes les commandes ont été
> exécutées le 8 septembre 2026 telles qu'elles sont écrites — sauf celles du
> **cas B**, qui écrasent la production et ont donc été vérifiées sur une base
> jetable (voir « Ce qui a été réellement exécuté », en fin de section).

### 6 bis.1 Le point de retour

La version en exploitation a été figée avant l'ouverture des travaux de V2 :

| | |
|---|---|
| **Tag** | `v1.0-production` (annoté), objet `3c62272` → commit `eecd03a` |
| **Commit** | `eecd03a` — *test(cti): parcourt la chaine complete d'une analyse lancee par l'exploitant* |
| **Mise en production** | 6 septembre 2026, 17h44 UTC — exécution n°14 du workflow « Déploiement production » |
| **Client servi** | CRRH, offre Souverain (premier client réel, créé le 3 septembre 2026) |
| **Tests verts sur ce commit** | CI n°55, ses cinq travaux au vert : 1089 tests backend, 145 tests frontend unitaires, 19 parcours de bout en bout |
| **Branche de correctifs** | `maintenance/v1`, partie de ce tag |
| **Sauvegarde de référence** | `rssi_2026-09-08_03h30.tar.gz` (186 224 octets, 11 905 lignes de SQL), restauration vérifiée |

Le tag et la branche sont sur le dépôt distant. Pour le vérifier depuis
n'importe quel poste, sans avoir cloné le projet :

```bash
git ls-remote --tags https://github.com/fleuris11/rssi-as-a-service.git v1.0-production
# 3c62272...  refs/tags/v1.0-production        <- l'objet du tag annoté
# eecd03a...  refs/tags/v1.0-production^{}     <- le commit qu'il désigne
```

**Pourquoi un tag annoté et pas un tag simple** : le tag annoté porte un
message, un auteur et une date. Il répond tout seul à la question qu'on se
pose à 2 h du matin — *quel est au juste cet état, et pourquoi l'a-t-on
gardé ?* :

```bash
git cat-file -p v1.0-production
```

### 6 bis.2 D'abord : dans quel cas êtes-vous ?

Deux situations, deux procédures. **Cette étape prend trente secondes et
détermine tout le reste** — ne la sautez pas.

La question est : *la V2 a-t-elle migré la base de production ?* Ramener le
code de la v1 sur une base au schéma V2 est le seul scénario où le retour
arrière peut abîmer davantage que l'incident.

```bash
ssh ubuntu@152.228.136.251
cd ~/rssi
git fetch --tags --quiet origin

docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U rssiasservice -d rssiasservice -tAc \
  "SELECT app||'/'||name FROM django_migrations
   WHERE app NOT IN ('admin','auth','contenttypes','sessions','token_blacklist')
   ORDER BY 1;" < /dev/null | sort > /tmp/appliquees.txt

git ls-tree -r --name-only v1.0-production \
  | grep -oE 'apps/[a-z_]+/migrations/[0-9]{4}[a-z0-9_]*' \
  | sed -E 's#apps/([a-z_]+)/migrations/#\1/#' | sort > /tmp/dans_v1.txt

comm -23 /tmp/appliquees.txt /tmp/dans_v1.txt
```

Cette dernière commande liste **les migrations appliquées en base que le code
de la v1 ne connaît pas**.

- **Sortie vide → cas A.** La base est compatible avec la v1. Retour du code
  seul. C'est le cas normal, et c'est celui mesuré le 8 septembre 2026
  (33 migrations appliquées, 33 présentes dans le tag, aucun écart).
- **Sortie non vide → cas B.** Il faut ramener la base avec le code.

> `< /dev/null` sur les appels `docker compose exec -T` n'est pas décoratif :
> sans lui, `exec` hérite de l'entrée standard et **dévore la suite du
> script**. Le symptôme est déroutant — le script s'arrête sans erreur après
> la première commande.

### 6 bis.3 Cas A — retour du code seul (environ 2 minutes)

**Chemin normal. À préférer systématiquement** : c'est le chemin automatisé,
celui qui vérifie la CI, celui qui contrôle le résultat depuis l'extérieur.

1. GitHub → onglet **Actions** → workflow **« Déploiement production »** →
   bouton **Run workflow**.
2. Renseigner :
   - *Use workflow from* : **`main`** — c'est la branche d'où est lue la
     **définition** du workflow, pas la version déployée. La laisser sur
     `main` ;
   - *Commit, branche ou TAG à déployer* : **`v1.0-production`** ;
   - *Motif du déploiement* : par exemple `retour arriere V2 - incident du JJ/MM`.
3. Lancer et attendre.

**Durée mesurée** (exécution n°14 du 06/09/2026, chemin identique) : **50 s au
total**, dont 35 s pour l'étape de déploiement et 9 s pour la vérification
externe. Compter quelques minutes de plus si le cache de construction Docker
du serveur ne contient plus les couches de la v1 — après plusieurs semaines de
V2, c'est probable.

Le workflow s'arrête de lui-même si quelque chose cloche :

- il **refuse de déployer** si la CI n'est pas verte sur le commit visé ;
- il **échoue** si `https://rssiasservice.online/healthz` ne répond pas 200
  dans les 150 secondes qui suivent le redémarrage.

Le résumé d'exécution indique la **ref demandée**, le **commit** et le **tag
exact** — de quoi vérifier d'un coup d'œil qu'on a bien déployé
`v1.0-production` et non `main`.

#### Si le workflow refuse : « La CI n'est pas verte sur … (état : aucune) »

Ce n'est pas un échec de la v1. Les exécutions de workflow finissent par
disparaître avec le temps ; la garde ne trouve alors plus de CI verte sur ce
commit et refuse, par principe.

Le recours existe déjà et ne demande **aucune modification du dépôt** :

1. GitHub → **Actions** → workflow **CI** → **Run workflow** ;
2. dans *Use workflow from*, choisir le **tag `v1.0-production`** (le sélecteur
   liste les tags autant que les branches) ;
3. attendre la CI (**5 min 01 s** mesurées sur l'exécution n°55) ;
4. relancer le déploiement.

> Cette relance manuelle de la CI n'a pas été ajoutée pour ce cas-ci : elle
> existe depuis qu'un push sur `main` n'avait produit aucun run, rendant la
> production inatteignable. Le commentaire en tête de `ci.yml` le raconte.

### 6 bis.4 Cas A bis — GitHub est indisponible

Le repli manuel, à n'utiliser que si le workflow ne peut pas tourner. Il fait
exactement ce que fait le workflow, **sans la vérification de CI ni le
contrôle externe** — que vous ferez donc à la main, à l'étape 6 bis.6.

```bash
ssh ubuntu@152.228.136.251
cd ~/rssi

git log --oneline -1                       # noter la version en place AVANT
git fetch --tags --quiet origin
git checkout --quiet v1.0-production
git log --oneline -1                       # doit afficher eecd03a
chmod +x deploy/*.sh

docker compose -f docker-compose.prod.yml up -d --build
```

`git checkout` sur un tag laisse le dépôt en **HEAD détachée** : c'est normal,
c'est déjà l'état dans lequel le workflow laisse le serveur après chaque
déploiement (`git status -sb` affiche `## HEAD (no branch)`).

`--build` n'est pas optionnel : le frontend est compilé dans l'image Caddy, un
simple redémarrage ne ramènerait pas l'interface de la v1.

### 6 bis.5 Cas B — retour du code **et** de la base

À n'exécuter que si l'étape 6 bis.2 a listé des migrations inconnues de la v1.
**Cette procédure écrase la base de production.** Lisez-la en entier avant de
taper la première commande.

```bash
ssh ubuntu@152.228.136.251
cd ~/rssi

# 1. Arrêter ce qui écrit en base. Postgres et Caddy restent debout : le site
#    doit continuer de répondre quelque chose, et Postgres doit rester
#    accessible pour recevoir la restauration.
docker compose -f docker-compose.prod.yml stop web worker beat

# 2. Sauvegarder l'état ACTUEL avant de l'écraser. C'est le seul filet si le
#    retour arrière se révèle être une erreur de diagnostic.
./deploy/sauvegarde.sh

# 3. Extraire la sauvegarde visée et VÉRIFIER de quoi il s'agit avant tout.
T=$(mktemp -d)
tar xzf ~/sauvegardes/rssi_2026-09-08_03h30.tar.gz -C "$T"
cat "$T/commit.txt"   # doit désigner eecd03a — le code qui tournait alors
cat "$T/date.txt"     # doit désigner la nuit attendue

# 4. Restaurer la base. Le dump est produit avec --clean --if-exists : il
#    efface les objets avant de les recréer. ON_ERROR_STOP=1 arrête à la
#    première erreur plutôt que de laisser une base à moitié restaurée.
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U rssiasservice -d rssiasservice -v ON_ERROR_STOP=1 -q < "$T/base.sql"

# 5. Restaurer les clés de chiffrement — SEULEMENT si elles ont changé depuis
#    la sauvegarde. En cas de doute, restaurez : une base rendue illisible
#    coûte plus cher qu'un réglage de V2 à ressaisir.
cp backend/.env backend/.env.avant-retour   # toujours, avant d'écraser
cp "$T/env" backend/.env
chmod 600 backend/.env

rm -rf "$T"
```

> **`backend/.env` et non `.env`.** À la racine, `.env` est un **lien
> symbolique** vers `backend/.env` (`ls -la .env` le montre). Écrire dans
> `backend/.env` met bien à jour les deux ; remplacer le lien par un fichier
> ferait diverger les deux emplacements à la première rotation de mot de
> passe.

> **Pourquoi le `.env` est dans la sauvegarde.** Les mots de passe fuités sont
> chiffrés en base (ADR-014). Une base restaurée sans sa clé Fernet est en
> partie **définitivement illisible**. La sauvegarde du 08/09 contient bien
> les trois clés attendues — `AI_PSEUDONYMIZATION_KEY`, `TOTP_ENCRYPTION_KEY`,
> `BREACH_SECRET_ENCRYPTION_KEY` — sur 33 variables.

Puis ramener le code : **cas A** (workflow) ou **cas A bis** (SSH). Le service
`migrate` rejouera les migrations de la v1 ; toutes étant déjà appliquées dans
la base restaurée, il n'aura rien à faire.

**Durée** : compter une dizaine de minutes. La restauration elle-même est
rapide — **1 seconde** pour les 1,6 Mo du dump du 08/09, mesuré. Le temps part
dans l'arrêt des services, la sauvegarde de sécurité et les vérifications.

### 6 bis.6 Vérifier que le retour a bien eu lieu

Ne pas s'en tenir au vert du workflow. Trois contrôles, dans cet ordre :

```bash
# 1. Vu d'Internet — la seule mesure qui dit ce qu'un visiteur constate.
curl -s -o /dev/null -w 'healthz : HTTP %{http_code} en %{time_total}s\n' \
     https://rssiasservice.online/healthz
curl -s https://rssiasservice.online/healthz          # {"status": "ok"}

# 2. La version réellement en place sur le serveur.
ssh ubuntu@152.228.136.251 'cd ~/rssi && git log --oneline -1'
#   -> eecd03a test(cti): parcourt la chaine complete ...

# 3. Tous les conteneurs sont debout, et `migrate` est sorti en 0.
ssh ubuntu@152.228.136.251 \
  'cd ~/rssi && docker compose -f docker-compose.prod.yml ps -a \
   --format "table {{.Service}}\t{{.Status}}" < /dev/null'
#   migrate doit afficher « Exited (0) » — pas un autre code.
```

Puis, en cas B seulement, que les données sont bien celles attendues :

```bash
ssh ubuntu@152.228.136.251 'cd ~/rssi && for t in tenants_tenant accounts_user \
  assessments_assessment monitoring_asset django_migrations; do
  printf "%-26s %s\n" "$t" "$(docker compose -f docker-compose.prod.yml exec -T \
  postgres psql -U rssiasservice -d rssiasservice -tAc "SELECT count(*) FROM $t;" \
  < /dev/null)"; done'
```

Relevé sur la sauvegarde du 08/09 (les mêmes valeurs qu'en production ce
jour-là) : 7 entreprises, 10 comptes dont 1 administrateur, 4 diagnostics,
7 actifs surveillés, 65 migrations, 51 tables.

### 6 bis.7 Après le retour

La production tourne à nouveau en v1. **Ne corrigez pas l'incident sur
`main`** — `main` porte désormais la V2, et la fusionner reviendrait à
redéployer ce dont vous venez de sortir.

```bash
git fetch origin
git switch maintenance/v1        # partie de v1.0-production
git switch -c fix/mon-correctif
# ... correction + tests ...
```

Puis PR vers `maintenance/v1`, CI verte, et déploiement de **la branche**
`maintenance/v1` par le workflow (le champ accepte une branche aussi bien
qu'un tag). Reporter ensuite le correctif sur `main` — un `cherry-pick` suffit
tant que les deux branches n'ont pas trop divergé.

### 6 bis.8 Ce que cette procédure ne couvre pas

Trois limites, énoncées pour qu'on ne les découvre pas le jour venu.

1. **Les données créées depuis la sauvegarde sont perdues en cas B.** La
   sauvegarde date de 3 h 30 ; tout ce que le client a saisi depuis disparaît.
   C'est la raison d'être de la sauvegarde de sécurité de l'étape 2 : elle
   permet de repêcher a posteriori ce qui a été écrasé.
2. **Aucune page de maintenance.** Pendant le cas B, le site répond mais
   l'application est arrêtée : le visiteur voit des erreurs, pas un message.
3. **Le retour arrière n'a jamais été exécuté en vraie grandeur.** Ses
   éléments l'ont été séparément (voir ci-dessous), mais la bascule complète
   sur la production, non. La première exécution réelle est à faire **hors
   incident**, à froid, un jour où l'on peut se permettre qu'elle échoue.

### 6 bis.9 Ce qui a été réellement exécuté le 8 septembre 2026

Distinction volontaire : une procédure qui prétend être vérifiée sans l'être
est pire qu'une procédure honnêtement annotée.

| Élément | Vérification |
|---|---|
| Existence du tag et de la branche sur le distant | `git ls-remote` — les deux répondent |
| Le serveur connaît le tag | `git fetch --tags` puis `git tag -l` sur le VPS : `v1.0-production` → `eecd03a` |
| Commande de décision cas A / cas B (6 bis.2) | exécutée sur la production : sortie vide, 33 = 33 |
| Intégrité de la sauvegarde | `gzip -t` OK ; marqueur `PostgreSQL database dump complete` présent (le fichier n'est pas tronqué) |
| Contenu de la sauvegarde | `base.sql` 1 652 678 octets / 11 905 lignes / 51 `CREATE TABLE` / 51 blocs `COPY` ; `env` 1 909 octets, 33 variables, les 3 clés Fernet présentes ; `commit.txt` → `eecd03a` ; `date.txt` → `2026-09-08T03:30:02+00:00` |
| **Restauration réelle** | dump restauré dans une base **jetable** (`verif_restauration_20260908`) avec `ON_ERROR_STOP=1` : **1 s**, 51 tables, effectifs identiques à la production (7 / 10 / 4 / 7 / 65), 1 compte administrateur retrouvé. Base supprimée ensuite ; la production n'a pas été touchée |
| Le workflow accepte un tag | vérifié par lecture et par l'API : `actions/checkout` résout un tag comme une branche, et l'environnement `production` n'impose **aucune** restriction de refs déployables (`deployment_branch_policy: null`) |
| La garde de CI accepterait ce commit | requête à l'API GitHub reproduite à la main sur `eecd03a` : CI n°55, `conclusion: success`, ses 5 travaux verts |
| Durées annoncées | relevées sur les exécutions réelles n°14 (déploiement, 50 s) et n°55 (CI, 5 min 01 s) |
| `/healthz` | 200 en 0,38 s, `{"status": "ok"}` |
| Commandes du **cas B** sur la production | **non exécutées** — elles écrasent la base. Vérifiées sur la base jetable, à un argument près (`-d verif_restauration_20260908` au lieu de `-d rssiasservice`) |

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

## 7 bis. Supervision

Deux niveaux, complémentaires et **aucun suffisant seul**.

### Surveillance interne (`deploy/surveillance.sh`, toutes les 5 minutes)

Contrôle ce que l'extérieur ne peut pas voir :

| Contrôle | Ce qu'il détecte |
|---|---|
| État des six conteneurs | un service arrêté ou en redémarrage permanent |
| `/healthz` vu de la machine | l'application ne répond plus |
| Réponse d'un worker Celery | un worker « running » mais bloqué — cas qu'un contrôle d'état ne voit pas |
| Occupation du disque (seuil 85 %) | un disque plein casse PostgreSQL tardivement et bruyamment |
| Échéance du certificat (seuil 10 jours) | un renouvellement automatique qui aurait échoué |

**Alerte après trois échecs consécutifs, jamais au premier** — même règle
anti-faux positif que les alertes du produit (`CLAUDE.md`). Une seule alerte
par incident, puis un message de retour à la normale : une alerte répétée
toutes les cinq minutes cesse d'être lue.

**Limite assumée** : cette surveillance tourne **sur** le serveur qu'elle
surveille, et son alerte part par le conteneur `web`. Elle ne verra jamais une
panne du serveur lui-même. C'est précisément pourquoi la suivante n'est pas
optionnelle.

**Vérifiée réellement** : arrêt contrôlé du worker Celery, trois contrôles en
échec, alerte émise et acceptée par le serveur SMTP, absence de répétition aux
contrôles suivants, message de retour à la normale après rétablissement.

### Surveillance externe (UptimeRobot)

Interroge `https://rssiasservice.online/healthz` depuis Internet toutes les
5 minutes et alerte par email. C'est la seule qui voie une panne du serveur,
une expiration de domaine ou une rupture réseau.

Offre gratuite : 50 sondes, intervalle de 5 minutes, alertes par email,
3 mois d'historique. **L'inscription demande une action humaine** — la marche
à suivre figure au §11 bis.

---

## 7 ter. Intégration continue

### Ce qui est vérifié à chaque poussée

Cinq travaux (`.github/workflows/ci.yml`) : lint et format du backend,
détection de migrations manquantes, tests unitaires, audit des dépendances
Python ; lint, compilation et audit du frontend ; tests de composants ;
parcours de bout en bout sur la pile Docker complète ; analyse de
vulnérabilités de l'image conteneur.

### La CI est restée rouge deux semaines

Du 11 au 25 août, alors que `CLAUDE.md` interdit de fusionner sur du rouge.
Des commits ont été fusionnés pendant toute cette période.

**Un seul voyant rouge, six causes distinctes**, découvertes en couches
successives : chacune masquait la suivante, et il a fallu corriger les quatre
premières pour seulement *voir* les deux dernières. C'est la leçon principale
de cet épisode — un indicateur binaire ne dit pas combien de problèmes il
recouvre, et le laisser rouge revient à s'interdire de le savoir.

| Cause | Nature |
|---|---|
| `ruff format --check` échouait sur dix fichiers | la vérification locale documentée était `ruff format .`, qui **applique** le format au lieu de **vérifier** qu'il l'est. On pouvait croire avoir vérifié sans l'avoir fait. |
| `npm audit` : vulnérabilité haute dans `nanoid` | dépendance transitive non mise à jour |
| `pip-audit` : Django 5.2.16 vulnérable (PYSEC-2026-3717) | exploitable à distance sans authentification |
| **`TOTP_ENCRYPTION_KEY` absente en intégration continue** | la suite dépendait d'un `backend/.env` présent sur le poste. La fixture qui la simule existait, mais cantonnée à `apps/accounts/tests`. Conséquence secondaire notable : l'assertion « cette clé n'apparaît pas dans la réponse » devenait **toujours fausse**, une chaîne vide étant contenue dans n'importe quelle chaîne — le test censé prouver l'absence de fuite prouvait l'inverse. |

À quoi s'ajoutait une **course aux migrations** : `web`, `worker` et `beat`
partagent le même point d'entrée et appliquaient donc les migrations **tous les
trois en parallèle**, se disputant la création des mêmes tables. Le perdant
s'arrêtait sur `duplicate key value violates unique constraint`. Course, donc
intermittente — et d'autant plus déroutante que le service survivant faisait
croire à un démarrage réussi. Un service `migrate` dédié les applique désormais
une seule fois, les autres attendant qu'il ait terminé.

Puis, une fois ces cinq causes levées, deux autres sont apparues :

| Cause | Nature |
|---|---|
| **Cinq variables de production héritées de l'ambiance** | même mécanisme que `TOTP_ENCRYPTION_KEY`, sur les tests de `config/settings_production.py`. Second défaut au passage : le test « une variable manquante fait échouer le démarrage » plaçait l'import **hors** du bloc qui devait capturer l'exception ; il ne fonctionnait que si son voisin avait réussi et laissé le module en cache. Un test dont le résultat dépend de l'ordre ne prouve rien. |
| **Le tag `aquasecurity/trivy-action@0.28.0` a disparu** | le projet est passé à des tags préfixés `v`. Le job d'analyse d'image a cassé **sans qu'une ligne de ce dépôt ne change**. Il était par ailleurs invisible depuis le 11 août : dépendant du job `backend` qui échouait, il était « ignoré » et non « en échec ». L'action est désormais épinglée au **commit**, pas au tag. |

#### Ce que la panne empêchait de voir

La course aux migrations n'est pas la cause la plus spectaculaire, c'est la
plus coûteuse : elle empêchait la pile de démarrer, donc **aucun parcours de
bout en bout ne s'était exécuté en intégration continue depuis des semaines**.
Trois défauts réels attendaient derrière :

- **le référentiel ANSSI manquait dans tout environnement neuf** — chargé par
  une commande de gestion que rien n'exécutait automatiquement. Le poste de
  développement fonctionnait parce que la commande y avait été passée une fois,
  des mois plus tôt. **Tout nouveau déploiement de production était concerné :
  pas de référentiel, donc pas de diagnostic.** Le service `migrate` s'en
  charge désormais, dans les deux fichiers Compose ;
- **six fonctionnalités vendues ne sont appliquées nulle part** (voir plus
  bas) ;
- trois parcours en échec sur des mesures d'accessibilité prises pendant les
  animations d'apparition.

Le premier est le plus instructif pour un dossier de déploiement : **une étape
manuelle exécutée une fois sur le poste de développement devient invisible.**
Elle ne manque à personne tant qu'aucun environnement n'est reconstruit —
et elle manque à tous le jour où il l'est.

#### Six fonctionnalités vendues, appliquées nulle part

Sur les neuf clés du registre des fonctionnalités
(`backend/apps/billing/features.py`), **trois seulement sont lues quelque
part** : `exposure_synthesis`, `secret_reveal`, `realtime_monitoring`.

`anssi_assessment`, `assistant`, `pdf_export`, `reuse_correlation`,
`charter_generation` et `extended_history` sont déclarées, affichées dans la
grille tarifaire, et gardées par rien.

**Un client « Veille » à 89 € obtient donc l'essentiel de ce qui est vendu
249 € au titre de « Pilotage ».** Ce n'est pas une panne — rien ne casse,
personne ne se plaint. C'est une fuite commerciale, invisible par
construction : aucun test ne peut échouer sur une garde qui n'existe pas.

Le registre **donne l'apparence** d'un contrôle d'accès. Seule la recherche des
points d'usage montre que les deux tiers des clés ne servent à rien.

### Empêcher la récidive

`verifier.sh`, à la racine, reproduit **exactement** ce que la CI contrôle.
Toute étape ajoutée au workflow doit l'être aussi dans ce script.

```bash
./verifier.sh          # tout
./verifier.sh back     # backend seulement
./verifier.sh front    # frontend seulement
```

La branche `main` doit par ailleurs être protégée pour exiger une CI verte
avant fusion — marche à suivre au §11 ter.

### Déploiement

Automatisé mais **déclenché à la main** (`.github/workflows/deploiement.yml`),
décision documentée en **ADR-023**. Le workflow refuse de s'exécuter si la CI
n'est pas verte sur le commit visé, se connecte par une clé SSH **dédiée**,
reconstruit, applique les migrations et vérifie `/healthz` **depuis
l'extérieur**.

#### La clé SSH de déploiement

Paire **ed25519 dédiée**, distincte de la clé d'administration du poste, sans
phrase de passe (un workflow ne peut pas en saisir une). Empreinte publique :

```
SHA256:HjEdWLX+KZqrTe3Mc6aB3Znqb190Sao4jxcUWoHJJLo   deploiement github-actions rssiasservice
```

Elle est installée sur le compte `ubuntu` du serveur avec l'option
**`restrict`** :

```
restrict ssh-ed25519 AAAAC3Nza... deploiement github-actions rssiasservice
```

`restrict` refuse d'un coup la redirection de ports, la redirection d'agent,
X11, l'allocation d'un terminal et le `~/.ssh/rc`. Autrement dit : cette clé
peut **exécuter la commande de déploiement, et rien qui transforme le serveur
en point de rebond**. Vérifié, avec témoin : une redirection `-R` est refusée
avec la clé de déploiement et acceptée avec la clé d'administration ;
l'allocation d'un terminal est refusée (`PTY allocation request failed`).

> **Ce que `restrict` ne fait PAS.** Le compte reste membre du groupe `docker`,
> **équivalent à root** sur l'hôte. Un compte séparé « aux droits strictement
> nécessaires » n'y changerait rien : il faudrait l'y mettre aussi. Et le
> déploiement doit tourner depuis `/home/ubuntu/rssi` — lancer `docker compose`
> depuis un autre chemin créerait un **second** projet Compose, donc une pile
> parallèle avec une base vide. L'isolement réel est apporté par la
> **séparation des clés** (révocable sans couper l'accès de l'exploitant), pas
> par une séparation de comptes qui serait cosmétique ici.

> **`command=` n'a pas été posée**, et c'est un choix, pas un oubli. Le
> workflow envoie un script *ad hoc* sur l'entrée standard (`ssh … bash -s`),
> script qui contient le commit visé. Une commande forcée ignorerait ce script
> et exécuterait un script fixe, incapable de savoir quel commit déployer. La
> poser supposerait de modifier le workflow pour passer le SHA **en argument de
> la commande SSH** et de valider ce SHA côté serveur. C'est le durcissement
> suivant, à faire le jour où d'autres personnes pourront déclencher le
> workflow.

**Révocation.** Retirer la ligne du serveur coupe l'accès immédiatement, sans
toucher à la clé personnelle de l'exploitant :

```bash
ssh ubuntu@152.228.136.251
cp ~/.ssh/authorized_keys ~/.ssh/authorized_keys.avant-revocation
sed -i '/github-actions/d' ~/.ssh/authorized_keys
ssh-keygen -lf ~/.ssh/authorized_keys   # doit ne plus lister HjEdWLX+...
```

> **Filtrer sur `github-actions`, jamais sur `deploiement`.** Le commentaire de
> la clé d'**administration** contient lui aussi le mot « deploiement »
> (`deploiement rssiasservice depuis poste Fleuris`) : un `sed
> '/deploiement/d'` effacerait les deux lignes et vous fermerait la porte du
> serveur. Le mot `github-actions` n'apparaît que sur la clé de déploiement.

Puis supprimer le secret `DEPLOY_SSH_KEY` dans **Settings → Secrets and
variables → Actions** du dépôt. Avant de révoquer, garder une session SSH
d'administration **ouverte** : c'est le filet si la commande se trompe de
ligne.

À faire si le compte GitHub est compromis, si le dépôt change de mainteneur,
ou périodiquement.

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
| **Surveillance externe à activer** | La surveillance interne fonctionne et son alerte a été vérifiée. La sonde externe (UptimeRobot, §11 bis) demande une inscription : sans elle, une panne du serveur lui-même ne déclenche rien. | Élevée |
| **Relecture juridique** | Les CGV sont une trame minimale ; le contrat de sous-traitance (DPA) reste à rédiger (`docs/legal/README.md`). | Élevée |
| **Répétition du retour arrière à froid** | La procédure de repli vers `v1.0-production` (§6 bis) est écrite et ses éléments vérifiés un à un, mais la bascule complète n'a jamais été jouée sur la production. Une procédure de repli jamais exécutée est une hypothèse, pas un filet — même raisonnement que pour une sauvegarde jamais restaurée. À jouer un jour où l'on peut se permettre qu'elle échoue. | Élevée |
| **Protection de la branche `main` à activer** | Marche à suivre au §11 ter. Sans elle, rien n'empêche techniquement de fusionner sur du rouge — ce qui vient de se produire pendant deux semaines. | Élevée |
| **Défauts d'image trouvés par un outil, pas par les tests** | Le Dockerfile n'appliquait aucune mise à jour de sécurité Debian ; c'est Trivy qui l'a signalé, pas la suite de tests. **Deuxième fois** pour cette classe de défaut (la première : la course aux migrations, vue par la CI et non par les tests). Aucun test ne peut voir un paquet système périmé ou une procédure de déploiement fausse — c'est une limite de méthode à assumer, pas un test à écrire. | Moyenne — méthode |
| **Palier de licence CTI** | 15 emplacements partagés, dont 13 engagés par le jeu de démonstration. Deux restent disponibles. | Moyenne |
| **Appels d'API redondants au tableau de bord** | Mesuré : `/auth/me/` appelé **trois fois**, `/assessments/` et `/monitoring/dashboard/` deux fois chacun, au même chargement. Premier rendu à 6,3 s sur un poste lent. Contraire à l'exigence Green IT (budget de performance frontend). | Moyenne |
| **Déploiement continu** | Le déploiement est automatisé mais déclenché à la main, par choix documenté (ADR-023). Trois conditions à réunir avant d'automatiser le déclenchement : CI verte durablement, préproduction, retour arrière automatique. | Faible |

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

# Le référentiel ANSSI est chargé automatiquement par le service `migrate`
# depuis le 25/08 ; la commande ci-dessous ne sert qu'au rattrapage et elle est
# idempotente. Ce n'est PAS une donnée de démonstration : sans référentiel, le
# diagnostic n'existe pas et l'inscription échoue sur « Diagnostic
# indisponible ».
docker compose -f docker-compose.prod.yml exec web \
    python manage.py load_anssi_referential

# Données de démonstration (facultatif, refusé si DEBUG=False sans le drapeau)
docker compose -f docker-compose.prod.yml exec web \
    python manage.py seed_demo_tenant --allow-production
docker compose -f docker-compose.prod.yml exec web \
    python manage.py seed_demo_clients --allow-production
```

Puis faire pointer le domaine (enregistrement `A`) vers l'adresse IP du
serveur. Caddy obtient le certificat seul, dès que le DNS a propagé.

---

## 11 bis. Activer la surveillance externe

Cette étape demande une action humaine : la création d'un compte.

1. Aller sur **uptimerobot.com** → **Register for FREE**
2. Créer le compte avec l'adresse qui doit recevoir les alertes
3. **Add New Monitor**, avec exactement ces valeurs :

| Champ | Valeur |
|---|---|
| Monitor Type | `HTTP(s)` |
| Friendly Name | `RSSI as a Service — production` |
| URL | `https://rssiasservice.online/healthz` |
| Monitoring Interval | `5 minutes` (minimum de l'offre gratuite) |
| Alert Contacts To Notify | cocher l'adresse email |

4. **Create Monitor**

Pourquoi `/healthz` et non la page d'accueil : cette adresse ne répond `200`
que si l'application **et** sa base de données répondent. La page d'accueil,
elle, est un fichier statique servi par Caddy — elle continuerait de s'afficher
alors que l'application serait morte.

**Vérifier l'alerte, une fois créée.** Une alerte qu'on n'a pas vue se
déclencher ne prouve rien :

```bash
ssh ubuntu@152.228.136.251
cd ~/rssi
docker compose -f docker-compose.prod.yml stop caddy   # le site devient injoignable
# attendre l'email (jusqu'a 10 min : detection + confirmation)
docker compose -f docker-compose.prod.yml start caddy  # retablissement
```

À faire à un moment choisi, pas pendant une démonstration.

---

## 11 ter. Protéger la branche `main`

À faire dans l'interface GitHub — l'API ne suffit pas sans droits
d'administration sur le dépôt.

**Settings** → **Branches** → **Add branch protection rule**

| Réglage | Valeur | Raison |
|---|---|---|
| Branch name pattern | `main` | |
| Require status checks to pass before merging | **coché** | c'est le cœur : plus de fusion sur du rouge |
| ↳ Require branches to be up to date before merging | **coché** | une CI verte sur un code obsolète ne prouve rien |
| ↳ Status checks | `backend`, `frontend`, `frontend-unit`, `e2e` | les nommer explicitement ; sans cela, un travail supprimé passe inaperçu |
| Do not allow bypassing the above settings | **coché** | sinon la règle ne s'applique pas à l'administrateur, c'est-à-dire à personne ici |

**Ne pas cocher** « Require a pull request before merging » sur un dépôt à un
seul mainteneur : cela empêcherait de pousser directement sans apporter de
relecture — personne d'autre ne relirait.

Les cases de vérification n'apparaissent dans la liste qu'après **au moins une
exécution** du workflow sur le dépôt. Si la liste est vide, pousser un commit
et revenir.

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
| `docs/adr/023-deploiement-declenche-a-la-main.md` | pourquoi le déploiement n'est pas automatique |
| `docs/legal/README.md` | état des textes juridiques, travail restant |
| `docs/identite-visuelle/README.md` | logos et déclinaisons |
| `docs/journal.md` | journal de bord, phase par phase |
