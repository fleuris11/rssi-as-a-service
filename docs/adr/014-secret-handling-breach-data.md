# 014 — Traitement des données ultra-sensibles renvoyées par Breachsense

## Contexte

Les endpoints Breachsense (`/stealer`, `/combo`, `/creds`, `/sessions`, `/nhi`, `/darkweb`,
`/docs`) renvoient, par nature, des **secrets en clair** : mots de passe, tokens
d'authentification, cookies de session, parfois des identifiants complets. Ce sont les données
les plus sensibles que la plateforme manipule à ce jour — bien au-delà des données de diagnostic
ANSSI ou des résultats de checks de surveillance (Phase 3), qui ne contiennent jamais de secret.

Le cadrage (§6 Sécurité, §7 RGPD) pose déjà les principes de minimisation et de non-persistance
de secrets ailleurs sur la plateforme (mots de passe utilisateurs hashés, clés API chiffrées),
mais aucun flux existant n'ingère de secret appartenant à un **tiers** (le mot de passe compromis
appartient à la personne dont le compte a fuité, pas à la plateforme). Ce flux appelle des règles
dédiées.

## Options étudiées

**A. Stocker les secrets chiffrés (Fernet, comme la table de pseudonymisation IA ou le secret
TOTP), déchiffrables pour affichage à la demande.**
Rejeté. Même chiffrés, ces secrets constituent une base de données de mots de passe/tokens
tiers en clair potentiel — une surface de risque disproportionnée en cas de compromission de la
clé de chiffrement, sans bénéfice produit clair (le dirigeant n'a pas besoin de *voir* le mot de
passe fuité, seulement de savoir *qu'un* mot de passe a fuité, pour le faire changer).

**B. Ne jamais persister le secret ; ne conserver qu'un indicateur masqué + un booléen.**
Retenu.

**C. Ne rien indiquer du tout sur la nature du secret (juste « une fuite existe »).**
Rejeté : moins utile pour le dirigeant (« un mot de passe se terminant par 23 » aide à
identifier *lequel* compte est concerné parmi plusieurs, sans exposer le secret réel).

## Décision

1. **Non-persistance stricte** : le secret en clair renvoyé par Breachsense (champ `password`,
   `token`, `cookie`, `secret`, ou toute variante) n'est **jamais** écrit en base, ni journalisé
   (aucun `logger.*` ne doit recevoir la valeur brute), ni transmis à Sentry (scrubbing — voir
   `docs/security_review.md`). Il ne transite que dans la mémoire du processus Celery le temps
   de la normalisation, puis est immédiatement remplacé.

2. **Masquage au moment de la normalisation, avant toute écriture** :
   `threat_intelligence.providers.breachsense.normalizer` masque chaque valeur reconnue comme
   secrète, par **deux mécanismes complémentaires** :
   - **Correspondance exacte de nom de champ** (`EXACT_SECRET_FIELDS`), pour les champs du schéma
     réel Breachsense (palier Essentials — obtenu du fournisseur *après* la rédaction initiale de
     cet ADR, voir « Mise à jour » ci-dessous) dont le nom est trop abrégé/cryptique pour être fiable
     via une sous-chaîne générique : `val` (valeur du cookie de session, endpoint `/sessions`), `ccn`/
     `ccx` (numéro/données de carte bancaire, `/stealer`), `cwa` (wallet crypto, `/stealer`).
   - **Sous-chaînes génériques** (`SECRET_KEY_MARKERS` : `password`, `pass`, `pwd`, `secret`,
     `token`, `credential`, `api_key`/`apikey`, `auth`), appliquées récursivement sur tout le
     payload, pas seulement les clés de premier niveau — ceinture de sécurité pour un champ non
     prévu par le mapping exact (schéma non encore documenté, endpoint futur), pas le mécanisme
     principal pour les endpoints déjà connus.
   Calcule dans tous les cas :
   - `secret_masked` : forme tronquée non réversible (ex. `••••••23`, les 2 derniers
     caractères seulement, jamais assez pour reconstituer le secret) ;
   - `secret_seen` : booléen, vrai si un secret était présent dans la charge d'origine — le
     dirigeant voit « un mot de passe a été exposé » sans que la valeur n'ait jamais existé en
     base.
   Le payload brut persisté (`BreachFinding.raw_data`, JSON) est le payload **déjà masqué** —
   jamais le payload d'origine.

   **Mise à jour (même phase, après réception du schéma réel des endpoints)** : la version
   initiale de cet ADR listait aussi `cookie`, `session` et `hash` comme sous-chaînes génériques.
   Elles ont été retirées après réception du schéma exact des réponses Breachsense : `cookie`
   aurait masqué à tort `cookie_name`/`cookie_path` (métadonnées structurelles de l'endpoint
   `/sessions`, pas des secrets — seul le champ `val` en est un) et `hash` aurait masqué à tort
   `file_hash` (empreinte du fichier fuité, endpoint `/docs`) et le champ `hash` de `/creds`
   (indicateur 0/1 « haché ou déchiffré », pas un secret lui-même). Le mapping exact par endpoint
   (`ENDPOINT_SCHEMAS` dans `normalizer.py`) pilote désormais aussi l'extraction de l'identifiant
   et de la date de fuite (les noms de champs réels — `usr`, `eml`, `user_name`, `inf`, `fnd`,
   `found`, `leak_date`... — diffèrent significativement d'un endpoint à l'autre et ne
   correspondaient à aucune des clés génériques devinées initialement) ; l'ancienne heuristique
   générique reste en repli pour tout endpoint non couvert par le mapping exact (dérive de schéma,
   nouvel endpoint), jamais comme mécanisme principal pour un endpoint déjà documenté.

3. **Test de propriété obligatoire** (CLAUDE.md §Tests, cadrage §9) : un test dédié
   (`test_no_secret_persistence.py`) génère des payloads simulés contenant des secrets connus
   pour chaque endpoint, exécute le pipeline d'ingestion complet (normalisation + création de
   `BreachFinding`), puis vérifie par une requête SQL brute sur la table que **aucune** valeur
   du secret d'origine n'apparaît dans une colonne texte/JSON de la ligne créée. Ce test
   protège contre toute régression future qui ajouterait un champ oubliant le masquage.

4. **Minimisation de l'identifiant exposé** (email, identifiant de compte) :
   - si l'identifiant concerné est l'email professionnel d'un membre du tenant (comparaison
     avec `tenants_services.list_members`), il est stocké **en clair**
     (`BreachFinding.identifier_plain`) : c'est une donnée que le tenant connaît déjà et doit
     pouvoir agir dessus directement (faire changer le mot de passe de ce compte) ;
   - sinon (l'identifiant appartient à un tiers — client final, partenaire — dont l'adresse a
     fuité en lien avec un actif du tenant), seule une forme masquée est conservée
     (`identifier_masked`, ex. `jo••••@ex••••.fr`) — minimisation RGPD : la plateforme n'a pas
     de base légale pour conserver en clair l'identité de personnes tierces non-utilisatrices
     du service.

5. **Durée de rétention** : les `BreachFinding` suivent la même politique que les résultats de
   check bruts (cadrage §7) — conservés 90 jours à l'état brut, sauf action explicite du tenant
   (traité/ignoré, qui prolonge la rétention à des fins d'audit de conformité — un
   `BreachFinding` traité fait partie de l'historique de mise en conformité, comme une action du
   plan d'action). La purge automatique des findings non traités de plus de 90 jours est notée
   comme reste-à-faire (tâche Celery Beat, cf. `docs/journal.md`) — hors périmètre immédiat de
   cette phase, qui livre le flux d'ingestion et l'affichage, pas encore la purge planifiée.

6. **Base légale RGPD** : exécution du contrat (le tenant a explicitement déclaré l'actif et
   demandé sa surveillance) pour les données concernant le tenant lui-même et ses membres ;
   intérêt légitime, strictement minimisé (identifiant masqué uniquement), pour les données
   concernant des tiers dont l'identifiant apparaît incidemment dans une fuite liée à un actif
   du tenant.

## Conséquences

- Aucune fonctionnalité de la plateforme ne permet — ni ne permettra sans une nouvelle décision
  ADR explicite — d'afficher un secret en clair à un utilisateur. C'est une contrainte
  délibérée, pas un oubli : elle doit être respectée par toute évolution future de ce module.
- Le back-office plateforme (§9 du prompt Phase 7) n'affiche que des agrégats (quota, occupation
  des slots, journal d'usage) — jamais le détail d'un `BreachFinding` d'un tenant, qui reste
  strictement scopé à ce tenant.
- Un correctif de sécurité futur qui ajouterait un champ à `BreachFinding` doit repasser par le
  test de propriété (point 3) avant merge — CI bloquante si un secret fuite dans une colonne.

## Mise à jour (phase ultérieure) — chiffrement réversible et révélation privilégiée

### Contexte du revirement

La Décision d'origine (point « Conséquences » ci-dessus) posait une contrainte volontairement
absolue : jamais aucun affichage en clair, sans exception. À l'usage, le dirigeant d'un tenant a
un besoin métier légitime que cette contrainte ne couvre pas : **retrouver la valeur exacte d'un
mot de passe compromis** (pas seulement savoir qu'il a fuité) — par exemple pour vérifier s'il est
réutilisé ailleurs (gestionnaire de mots de passe, autre service) avant de le faire changer partout,
ou pour le communiquer à un prestataire IT chargé de la remédiation. L'option A de la section
« Options étudiées » (chiffrement réversible) avait été rejetée par prudence ; ce point du
cadrage est révisé ici, pas silencieusement contourné — d'où cette mise à jour explicite plutôt
qu'un nouvel ADR séparé (même sujet, même modèle, décision qui en amende directement une
précédente).

### Décision (remplace le point 1 « non-persistance stricte » et le 1er item de « Conséquences »)

1. **Chiffrement réversible au lieu de la non-persistance** : le secret représentatif détecté par
   `normalizer.mask_payload` (la même valeur qui produisait déjà `secret_masked`) est désormais
   **conservé chiffré** (`BreachFinding.secret_encrypted`, `BinaryField`, Fernet) plutôt que
   simplement remplacé en mémoire. Clé dédiée `BREACH_SECRET_ENCRYPTION_KEY` (variable d'env,
   jamais commitée), distincte de `TOTP_ENCRYPTION_KEY` et `AI_PSEUDONYMIZATION_KEY` — même
   principe de séparation des clés Fernet que le reste de la plateforme (compromettre l'une ne
   doit pas compromettre les autres). `secret_masked` (affichage par défaut) et le nouveau booléen
   `has_secret` (remplace `secret_seen` — voir « Migration » ci-dessous) sont inchangés dans leur
   rôle : c'est uniquement l'irréversibilité qui est levée, pas le masquage par défaut.
2. Le point 2 (masquage à la normalisation) et le point 3 (test de propriété) restent en vigueur
   **tels quels** pour tout ce qui n'est pas le secret représentatif chiffré : le payload persisté
   dans `raw_data` reste le payload masqué, jamais le brut ; le test de propriété est étendu (pas
   remplacé) pour couvrir aussi `secret_encrypted` — la propriété vérifiée devient « le texte en
   clair du secret n'apparaît dans aucune colonne, y compris la colonne chiffrée », ce qui est
   garanti par les propriétés de Fernet (chiffrement authentifié, sortie indistinguable de
   aléatoire) plutôt que par l'absence de la donnée.
3. **Migration de données** : les `BreachFinding` déjà en base au moment de cette mise à jour n'ont,
   par construction, aucun secret chiffré disponible (ils n'ont jamais existé qu'à l'état masqué/
   jeté) — `has_secret` vaut `False` pour ces lignes, **jamais** reporté depuis l'ancien
   `secret_seen` (qui indiquait « un secret était présent dans la charge d'origine », pas « un
   secret chiffré est disponible » — les deux ont cessé de coïncider avec ce changement). Une
   tentative de révélation sur un finding antérieur à cette mise à jour échoue proprement (404,
   « aucun secret chiffré disponible »), tracée comme tout autre refus.

### Révélation : conditions cumulatives et mesures compensatoires

Le risque explicitement accepté par ce revirement — concentrer des secrets tiers déchiffrables
dans la base, plutôt que de ne jamais les y faire transiter — est compensé par un accès aussi
étroit et tracé que possible, pas par la confiance dans le seul chiffrement au repos :

1. **Rôle** : administrateur du tenant concerné (`Membership.Role.ADMIN`), ou utilisateur
   plateforme (`is_staff`) — mais uniquement pour un tenant dont ce dernier est **déjà membre**
   (aucun mécanisme d'emprunt d'identité inter-tenant n'existe dans cette plateforme ;
   `request.tenant`/`request.membership` ne se résolvent que via une adhésion réelle —
   `TenantScopingMiddleware`). Un administrateur plateforme sans aucune adhésion à un tenant ne
   peut donc révéler aucun de ses findings via cet endpoint — une limite de portée assumée plutôt
   qu'un mécanisme de bascule de tenant construit spécialement pour ce cas, hors périmètre de
   cette mise à jour.
2. **Ré-authentification fraîche (step-up)** : mot de passe du compte OU code TOTP à 6 chiffres,
   fourni à **chaque** appel de révélation — jamais une session ou un jeton d'élévation mis en
   cache côté serveur. Un jeton d'accès volé seul (sans le mot de passe ni le second facteur) ne
   suffit donc pas à révéler un secret.
3. **Étanchéité tenant stricte** : `services.get_finding` reste filtré par `request.tenant`,
   comme tout le reste de ce module — un admin ne peut réussir la révélation que sur un finding de
   son propre tenant, testé explicitement (`test_admin_cannot_reveal_another_tenants_finding`).
4. **Traçabilité intégrale** : chaque tentative — accordée ou refusée, quelle qu'en soit la raison
   (rôle insuffisant, ré-authentification invalide, finding hors périmètre, aucun secret
   disponible) — est journalisée dans `SecretRevealAudit` (qui, quel finding, quel tenant,
   horodatage, IP, user-agent), **jamais** le secret lui-même. Consultable par l'admin du tenant
   (ses propres tentatives) et par l'admin plateforme (vue agrégée toutes entreprises).
5. **Rate limiting strict** : throttle DRF dédié, par utilisateur (`5/min`) et par IP (`10/min`),
   volontairement bien en-deçà d'un usage humain normal — limite l'extraction massive même via un
   compte admin compromis (un attaquant qui changerait de compte reste bloqué par l'IP, un
   attaquant multi-IP reste bloqué par le compte).
6. **Non-mise en cache de la réponse** : `Cache-Control: no-store` sur la réponse de révélation —
   ni un proxy intermédiaire ni le navigateur ne doivent pouvoir la rejouer.

### Arbitrage risque / bénéfice

- **Bénéfice** : un dirigeant peut désormais agir avec l'information complète (vérifier une
  réutilisation de mot de passe, transmettre la valeur exacte à un prestataire de remédiation) —
  un besoin réel qu'un simple indicateur « un secret a fuité » ne couvre pas.
- **Risque accepté** : une base compromise expose désormais des secrets tiers potentiellement
  déchiffrables (si la clé `BREACH_SECRET_ENCRYPTION_KEY`, hors base, l'est aussi). Mesure
  compensatoire : la clé vit exclusivement en variable d'environnement, jamais en base ni dans le
  dépôt — une compromission de la seule base de données ne suffit pas à déchiffrer.
- **Risque accepté** : un compte admin compromis (identifiants **et** second facteur) pourrait
  révéler des secrets. Mesures compensatoires : rate limiting strict, traçabilité intégrale
  (détection a posteriori), ré-authentification fraîche à chaque révélation (le vol du seul jeton
  d'accès JWT ne suffit pas).
- Le point 1 des « Conséquences » d'origine (« aucune fonctionnalité ne permet d'afficher un
  secret en clair ») est donc explicitement révisé par cette mise à jour ; le reste des
  Conséquences (back-office plateforme limité aux agrégats — désormais complété par le journal de
  révélations agrégé, cf. point 4 ci-dessus — et test de propriété obligatoire pour tout nouveau
  champ) reste en vigueur.
