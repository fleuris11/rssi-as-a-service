# 014 — Cycle de vie des secrets de fuite (données ultra-sensibles Breachsense)

- **Statut** : Adopté. Décision initiale en Phase 7, révisée en Phase 7 (mise à
  jour du masquage), révisée sur le fond en Phase 8 (chiffrement réversible),
  complétée en Phase 8C (purge, rotation de clé). Ce document décrit **l'état
  final** ; l'historique des revirements est conservé en fin de document.
- **Dernière révision** : 2026-08-11

## Contexte

Les endpoints Breachsense (`/stealer`, `/combo`, `/creds`, `/sessions`,
`/nhi`, `/darkweb`, `/docs`) renvoient, par nature, des **secrets en clair** :
mots de passe, tokens d'authentification, cookies de session, numéros de carte.
Ce sont les données les plus sensibles que la plateforme manipule.

Deux particularités les distinguent de tout ce que la plateforme traitait
jusque-là :

1. **Ces secrets appartiennent à des tiers**, pas à la plateforme. Le mot de
   passe compromis est celui de la personne dont le compte a fuité — pas un
   secret applicatif comme une clé d'API ou un secret TOTP.
2. **Leur valeur pour le client est réelle mais bornée dans le temps.** Un
   dirigeant a besoin de savoir *qu'*un mot de passe a fuité, et parfois de
   savoir *lequel* (pour vérifier une réutilisation) — mais cette valeur
   s'éteint une fois le mot de passe changé.

## Décision — le cycle de vie, de bout en bout

### 1. Ingestion : masquage puis chiffrement

Le secret ne survit jamais en clair au-delà de la mémoire du processus qui
l'ingère.

- **Masquage du payload** (`providers/breachsense/normalizer.mask_payload`),
  avant toute écriture, par deux mécanismes complémentaires :
  - **correspondance exacte de nom de champ** (`EXACT_SECRET_FIELDS`) pour les
    champs du schéma réel dont le nom est trop abrégé pour une sous-chaîne
    fiable : `val` (cookie de session), `ccn`/`ccx` (carte bancaire), `cwa`
    (wallet crypto) ;
  - **sous-chaînes génériques** (`SECRET_KEY_MARKERS` : `password`, `pass`,
    `pwd`, `secret`, `token`, `credential`, `api_key`/`apikey`, `auth`),
    appliquées récursivement sur tout l'arbre — ceinture de sécurité pour un
    champ non prévu, jamais le mécanisme principal pour un endpoint connu.
  Le payload persisté (`BreachFinding.raw_data`) est le payload **déjà
  masqué**, jamais l'original.
- **`secret_masked`** : forme tronquée non réversible (`••••••23`), l'affichage
  par défaut.
- **`secret_encrypted`** : le secret représentatif, chiffré (Fernet), et
  **`has_secret`** : vrai uniquement si un blob déchiffrable existe réellement.

### 2. Conservation : chiffré au repos, clé hors base

- Clé **dédiée** `BREACH_SECRET_ENCRYPTION_KEY`, distincte de
  `TOTP_ENCRYPTION_KEY` et `AI_PSEUDONYMIZATION_KEY` : compromettre l'une ne
  compromet pas les autres.
- La clé vit exclusivement en variable d'environnement — **une compromission
  de la seule base de données ne suffit pas à déchiffrer**.
- Aucun secret ne transite par un `logger.*` ni vers un outil de suivi
  d'erreurs. Le « scrubbing » est structurel : la donnée n'existe en clair que
  dans la réponse HTTP de révélation, jamais dans un flux de journalisation.
- **Le secret n'est jamais transmis à l'IA**, ni en clair, ni chiffré, ni même
  sous sa forme masquée (voir ADR-005 et le contexte de synthèse d'exposition).

### 3. Révélation : conditions cumulatives

`POST /api/v1/threat-intelligence/findings/{id}/reveal/` déchiffre **en
mémoire** et renvoie la valeur une fois, avec `Cache-Control: no-store`. Quatre
conditions, toutes nécessaires :

1. **Rôle** : administrateur du tenant, ou utilisateur plateforme (`is_staff`)
   — mais uniquement pour un tenant dont il est **déjà membre**. Il n'existe
   aucun mécanisme d'emprunt d'identité inter-tenant : un administrateur
   plateforme sans adhésion ne peut révéler aucun finding. Limite de portée
   assumée, pas un oubli.
2. **Ré-authentification fraîche (step-up)** : mot de passe du compte ou code
   TOTP, fourni à **chaque** appel — jamais une élévation mise en cache. Un
   jeton d'accès volé seul ne suffit donc pas.
3. **Étanchéité tenant stricte** : `services.get_finding` filtre sur
   `request.tenant`, comme tout le module.
4. **Rate limiting dédié** : 5/min par utilisateur, 10/min par IP —
   volontairement bien en-deçà d'un usage humain normal, pour limiter
   l'extraction massive même via un compte admin compromis.

**Traçabilité intégrale** : chaque tentative — accordée ou refusée, et pour
chaque motif de refus — est journalisée dans `SecretRevealAudit` (qui, quel
finding, quel tenant, horodatage, IP, user-agent), **jamais** le secret. Le
contrôle de rôle est vérifié manuellement dans la vue, précisément pour que le
refus « rôle insuffisant » soit tracé lui aussi — le court-circuit habituel de
DRF ne l'aurait pas permis.

**À quoi sert vraiment la révélation** (Phase 8C) : à trancher une hypothèse de
réutilisation (ADR-017), pas à satisfaire une curiosité. Quand une corrélation
est détectée sur un finding dont le mot de passe est disponible, l'action
recommandée propose explicitement de le révéler pour comparer, en rappelant que
l'accès est tracé.

### 4. Purge : le secret expire, la fuite reste

Au-delà de `BREACH_SECRET_RETENTION_DAYS` (90 par défaut, compté depuis la
détection), une tâche Celery Beat quotidienne efface `secret_encrypted`,
repasse `has_secret` à `False` et horodate `secret_purged_at`.

**On purge le secret, jamais la fuite.** Supprimer le `BreachFinding` ferait
perdre l'historique de conformité (« cette fuite a été traitée le … »), qui est
précisément ce qu'un tenant doit pouvoir présenter. L'interface affiche « mot de
passe effacé le … conformément à la politique de conservation » plutôt que de
laisser croire qu'il n'y en a jamais eu.

La tâche est naturellement idempotente (le filtre porte sur `has_secret=True`)
et chaque exécution est tracée dans `SecretPurgeRun` (volume, horodatage, jamais
de secret), consultable au back-office plateforme.

**Rétentions distinctes, décidées explicitement :**

| Donnée | Rétention | Pourquoi |
|---|---|---|
| Secret chiffré | 90 j | Sa valeur s'éteint une fois le mot de passe changé. |
| `SecretRevealAudit` | 365 j | Piste d'audit de sécurité : sa valeur est justement de **survivre** à la donnée qu'elle protège. Ne contient aucun secret. |
| `BreachFinding` | Non purgé | Historique de conformité (voir ci-dessus). |
| Cassettes de test (ADR-015) | Non purgées | Elles ne contiennent **aucun secret** : la commande d'enregistrement les masque avant écriture. Rien à purger — les soumettre à une rétention laisserait croire qu'elles en contiennent. |

**La politique est lisible par le client** dans le produit (page Exposition),
pas seulement dans un contrat : c'est ce qui rend la promesse crédible.

### 5. Rotation de la clé

`BREACH_SECRET_ENCRYPTION_KEYS` est une liste **ordonnée** (MultiFernet) : la
première clé chiffre, toutes déchiffrent. Rotation sans coupure :

1. générer une nouvelle clé Fernet ;
2. la placer **en tête** de la liste, l'ancienne restant derrière ;
3. lancer `python manage.py rotate_breach_secret_key` (idempotente, sûre à
   interrompre — chaque secret est traité individuellement) ;
4. retirer l'ancienne clé.

Un secret qu'**aucune** clé configurée n'ouvre est signalé et **laissé
intact** : l'effacer détruirait une donnée qu'une clé retrouvée plus tard
pourrait encore lire.

Le réglage historique `BREACH_SECRET_ENCRYPTION_KEY` (clé unique) reste accepté
en repli, pour qu'un déploiement existant continue de fonctionner sans
changement de configuration.

## Autres décisions conservées

- **Minimisation de l'identifiant** : si l'identifiant est l'email
  professionnel d'un membre du tenant, il est stocké en clair
  (`identifier_plain`) — le tenant le connaît déjà et doit pouvoir agir dessus.
  Sinon (tiers : client, partenaire), seule une forme masquée est conservée
  (`identifier_masked`), la plateforme n'ayant pas de base légale pour
  conserver en clair l'identité de personnes non-utilisatrices du service.
- **Base légale RGPD** : exécution du contrat pour les données concernant le
  tenant et ses membres (l'actif a été déclaré et sa surveillance sollicitée) ;
  intérêt légitime strictement minimisé pour les données de tiers apparaissant
  incidemment.
- **Test de propriété obligatoire** (`test_no_secret_persistence.py`) : pour
  chaque endpoint porteur de secret, un secret connu est injecté dans le
  pipeline réel, puis la ligne créée est interrogée **en SQL brut** (pas via
  l'ORM, pour ne pas pouvoir être trompé par une propriété Python) — colonne
  chiffrée comprise, encodée en hex. La propriété vérifiée est que le clair
  n'apparaît dans **aucune** colonne : garantie par le chiffrement, pas par
  l'absence de la donnée.

## Conséquences

- Un correctif futur qui ajouterait un champ à `BreachFinding` doit repasser
  par le test de propriété avant merge.
- Le back-office plateforme n'affiche que des agrégats (quota, pool, journal
  d'usage, journal des révélations, exécutions de purge) — jamais le détail
  d'un `BreachFinding` d'un tenant.
- **Risque résiduel accepté** : une base compromise **et** une clé compromise
  exposent des secrets tiers. Mesures compensatoires : clé hors base, rotation
  possible sans coupure, rétention courte qui borne le volume exposé.
- **Risque résiduel accepté** : un compte administrateur compromis (mot de
  passe **et** second facteur) peut révéler des secrets. Mesures
  compensatoires : rate limiting strict, traçabilité intégrale permettant la
  détection a posteriori, ré-authentification fraîche à chaque appel.

---

## Historique des révisions

Conservé pour la traçabilité des décisions (exigence de certification) — l'état
courant est décrit ci-dessus, ce qui suit explique **comment on y est arrivé**.

### Phase 7 — décision initiale : non-persistance stricte

La version initiale **rejetait** le chiffrement réversible (option A d'alors) au
motif qu'une base de secrets tiers déchiffrables serait une surface de risque
disproportionnée « sans bénéfice produit clair — le dirigeant n'a pas besoin de
*voir* le mot de passe fuité ». Le secret était masqué et jeté ; seuls
`secret_masked` et un booléen `secret_seen` étaient conservés.

### Phase 7 (addendum) — correction du mapping de masquage

Après réception du schéma réel des endpoints, les sous-chaînes `cookie`,
`session` et `hash` ont été retirées : `cookie` masquait à tort
`cookie_name`/`cookie_path` (métadonnées, seul `val` est un secret) et `hash`
masquait à tort `file_hash` (empreinte du fichier fuité) et l'indicateur 0/1
`hash` de `/creds`. À l'inverse, `val`, `ccn`, `ccx` et `cwa` n'étaient couverts
par **aucune** règle — un vrai gap de sécurité, corrigé par correspondance
exacte de nom de champ.

### Phase 8 — revirement : chiffrement réversible

Le postulat « le dirigeant n'a pas besoin de voir le mot de passe » s'est révélé
faux à l'usage : il en a besoin pour vérifier une réutilisation ailleurs avant
de le faire changer partout, ou pour le transmettre à un prestataire de
remédiation. L'option A initialement rejetée a donc été reprise, **assortie des
mesures compensatoires** que la version initiale n'avait pas envisagées (step-up,
audit intégral, rate limiting dédié). `secret_seen` a été remplacé par
`has_secret` — les deux notions ayant cessé de coïncider : « un secret était
présent à l'ingestion » n'est pas « un secret chiffré est disponible ». La
migration ne reporte donc **pas** l'ancienne valeur : les findings antérieurs
ont `has_secret=False`.

### Phase 8C — complétion du cycle de vie

Le chiffrement réversible laissait deux questions ouvertes, traitées ici : les
secrets s'accumulaient indéfiniment (→ purge planifiée, §4) et la clé n'était
pas rotable sans coupure (→ MultiFernet, §5). La révélation a par ailleurs
trouvé sa justification produit avec la corrélation de réutilisation (ADR-017).
