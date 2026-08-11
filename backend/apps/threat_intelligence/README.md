# `threat_intelligence` — renseignement sur la menace (Breachsense)

Voir `docs/adr/013` (intégration, abstraction provider), `docs/adr/014`
(traitement des secrets de fuite : chiffrement réversible + révélation
ré-authentifiée) et `docs/adr/015` (modes live/replay/null).

## Modes de fonctionnement (`BREACHSENSE_MODE`)

| Mode | Ce que ça fait | Quand |
|---|---|---|
| `live` | Appels réels à l'API Breachsense. **Consomme le quota partagé** (1000 requêtes/mois pour toute la plateforme). | Production, enregistrement d'une cassette, smoke test manuel. |
| `replay` | Sert les cassettes de `tests/fixtures/breachsense/`. **Aucun appel réseau.** | Développement, CI, démonstration client. |
| `null` | `NullProvider` : aucune donnée, aucun appel. | Environnement sans licence ni cassette. |
| `auto` *(défaut)* | `replay` si des cassettes existent, sinon `null`. **Jamais `live`.** | Défaut volontaire. |

Le défaut ne bascule **jamais** en `live`, même lorsqu'une licence est
configurée : disposer d'une licence est une capacité, pas une instruction de
la dépenser. Passer en `live` doit rester un acte explicite.

## Enregistrer une cassette

Une cassette est la réponse réelle de l'API pour un domaine donné, **déjà
masquée** : l'ADR-014 s'applique aux fixtures comme à la base — une cassette
ne contient jamais de secret en clair, et peut donc être committée.

```bash
# Depuis backend/ — consomme réellement du quota, d'où le flag obligatoire.
python manage.py record_breachsense_cassette \
    --domain exemple-client.fr \
    --confirm-live-call
```

Le fichier est écrit dans `apps/threat_intelligence/tests/fixtures/breachsense/<domaine>.json` :

```json
{
  "domain": "exemple-client.fr",
  "recorded_at": "2026-08-10T09:00:00+00:00",
  "requests_consumed": 9,
  "secrets_masked": true,
  "endpoints": { "stealer": [ { "usr": "...", "pwd": "••••••23" } ] }
}
```

Ensuite, `BREACHSENSE_MODE=replay` (ou le défaut `auto`) rejoue ces données
sans aucun appel réseau, à travers le pipeline d'ingestion réel
(normalisation, dédoublonnage, alerte).

> `record_breachsense_cassette` est la **seule** commande du dépôt qui appelle
> délibérément l'API réelle. Elle instancie `BreachsenseProvider` directement,
> sans passer par `get_provider()`, précisément parce que son rôle est de
> contourner le mode configuré.

## Tenant de démonstration

```bash
python manage.py seed_demo_tenant           # idempotent, rejouable
python manage.py seed_demo_tenant --reset   # repart d'un état propre
```

Crée « Demo — Cabinet Comptable Durand » (slug `demo-cabinet-durand`) avec des
utilisateurs, des actifs et un jeu de fuites couvrant tous les
`source_endpoint`. Les identifiants de connexion et le mot de passe de démo
sont affichés en fin d'exécution.

Garde-fous :
- refuse de tourner avec `DEBUG=False` sans `--allow-production` ;
- le préfixe de nom « Demo — » et le slug réservé rendent ces données
  impossibles à confondre avec un tenant réel ;
- les « mots de passe » seedés sont manifestement factices (`Hiver2024!durand`)
  mais crédibles à l'écran — jamais un secret réel.

Les fuites sont créées via `services.ingest_raw_findings`, donc à travers le
pipeline réel : masquage, chiffrement du secret, dédoublonnage et ouverture
d'alerte sont ceux de la production, pas une insertion directe en base.

## Cycle de vie des secrets de fuite (ADR-014)

`chiffré à l'ingestion` → `révélable sous conditions` → `purgé à échéance` → `clé rotable`

### Purge automatique

Une tâche Celery Beat quotidienne (3 h 30) efface les secrets au-delà du délai
de rétention. **Elle purge le secret, pas la fuite** : métadonnées, statut et
historique de traitement restent, seule la valeur récupérable disparaît.

| Réglage | Défaut | Portée |
|---|---|---|
| `BREACH_SECRET_RETENTION_DAYS` | 90 | Secret chiffré d'un `BreachFinding` |
| `BREACH_REVEAL_AUDIT_RETENTION_DAYS` | 365 | Journal des révélations |

Le journal des révélations est volontairement conservé **plus longtemps** que
les secrets : c'est une piste d'audit de sécurité, sa valeur est de survivre à
la donnée qu'elle protège. Les cassettes de test ne sont pas concernées : elles
ne contiennent aucun secret (masqués à l'enregistrement).

Exécution manuelle si besoin :

```bash
python manage.py shell -c "from apps.threat_intelligence import services; print(services.purge_expired_secrets())"
```

Les exécutions sont tracées (`SecretPurgeRun`) et visibles au back-office
plateforme — la politique ne vaut que si l'on peut constater qu'elle tourne.

### Rotation de la clé de chiffrement

`BREACH_SECRET_ENCRYPTION_KEYS` est une liste **ordonnée** : la première clé
chiffre, toutes déchiffrent (MultiFernet). La rotation se fait donc **sans
coupure ni fenêtre de maintenance**.

```bash
# 1. Générer une nouvelle clé
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. La placer EN TÊTE, l'ancienne derrière (.env) :
#    BREACH_SECRET_ENCRYPTION_KEYS=<nouvelle>,<ancienne>
#    puis redémarrer web/worker/beat.
#    À ce stade : la nouvelle chiffre, l'ancienne déchiffre encore l'existant.

# 3. Re-chiffrer l'existant (idempotent, sûr à interrompre)
python manage.py rotate_breach_secret_key --dry-run   # compte sans écrire
python manage.py rotate_breach_secret_key

# 4. Retirer l'ancienne clé :
#    BREACH_SECRET_ENCRYPTION_KEYS=<nouvelle>
```

Ne pas sauter l'étape 3 : retirer l'ancienne clé avant d'avoir re-chiffré rend
illisibles tous les secrets encore chiffrés avec elle.

Un secret qu'aucune clé configurée n'ouvre est **signalé et laissé intact** (la
commande ne l'efface pas) : une clé retrouvée plus tard peut encore le lire.

Le réglage historique `BREACH_SECRET_ENCRYPTION_KEY` (clé unique) reste accepté
en repli — un déploiement existant continue de fonctionner sans changement.
