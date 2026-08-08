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
