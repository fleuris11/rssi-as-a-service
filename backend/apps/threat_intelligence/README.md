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
