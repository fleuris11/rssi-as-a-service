# Format d'import d'un référentiel

Ce document décrit **le contrat stable** d'import d'un référentiel de
conformité dans RSSI as a Service. Il s'adresse à l'exploitant de la
plateforme et au consultant qui prépare le fichier d'un client.

Décisions correspondantes : [ADR-029](adr/029-referentiels-multiples-et-attribution.md).

---

## 1. Droits d'usage — à lire avant tout

**Le produit fournit la structure d'accueil. Il ne fournit pas le contenu des
référentiels sous droits.**

| Référentiel | Statut | Qui l'importe |
|---|---|---|
| Guide d'hygiène informatique de l'ANSSI (42 mesures) | Licence Ouverte / Etalab v1 — **embarqué dans le dépôt** (`backend/data/anssi_hygiene.json`) | déjà chargé au démarrage |
| ISO/IEC 27001 — Annexe A | **sous droits** (ISO / AFNOR) | l'exploitant ou le client, détenteur de la licence |
| NIST CSF 2.0 | domaine public américain, mais vérifier les conditions de la version utilisée | l'exploitant |
| CIS Controls | **sous droits** (Center for Internet Security), usage soumis à leurs conditions | l'exploitant ou le client |
| Référentiel interne d'un client | propriété du client | le client, ou nous pour son compte |

Le dépôt Git **ne doit contenir aucun contenu sous droits** : ni intitulés, ni
énoncés, ni fichiers d'import. Un tel fichier vit sur le serveur ou dans le
coffre du client, jamais dans le dépôt.

Chaque référentiel importé déclare :

- `kind` — `open` (libre de droits), `licensed` (soumis à droits), `custom`
  (propre à un client) ;
- `licence_notice` — la mention affichée avec le référentiel, dans le produit.
  C'est la seule trace, pour celui qui le consulte six mois plus tard, de ce
  qu'on a le droit d'en faire. Exemple :
  `Reproduit sous licence ISO n°XXXXX — usage interne au client, diffusion interdite.`

Un référentiel `custom` porte en plus un `owner_tenant` : il n'apparaît au
catalogue d'aucun autre client, et ne peut être attribué qu'à lui.

---

## 2. Deux formats, un seul comportement

| Format | Quand l'utiliser | Métadonnées |
|---|---|---|
| **JSON** | forme de référence ; un référentiel qu'on maintient dans le temps | dans le fichier |
| **CSV / tableur** | le cas le plus courant : le client fournit un tableur | en options de la commande |

Les deux passent par la même validation et la même écriture. Un fichier refusé
n'écrit **rien** : la validation est complète avant la première insertion.

---

## 3. Format JSON

```json
{
  "slug": "iso-27001-annexe-a",
  "name": "ISO/IEC 27001:2022 — Annexe A",
  "version": "2022",
  "publisher": "ISO/IEC",
  "kind": "licensed",
  "licence_notice": "Reproduit sous licence n°XXXXX — usage interne.",
  "source_url": "https://www.iso.org/standard/27001",
  "description": "Les contrôles de l'annexe A, reformulés en langage clair.",
  "domains": [
    {
      "code": "controles-organisationnels",
      "name": "Contrôles organisationnels",
      "order": 1,
      "description": "",
      "measures": [
        {
          "code": "A.5.1",
          "number": null,
          "title": "Politiques de sécurité de l'information",
          "statement": "Avez-vous une politique de sécurité écrite, approuvée par la direction, et connue des équipes ?",
          "level": "",
          "weight": 1.0,
          "effort": "medium",
          "impact": "high"
        }
      ]
    }
  ]
}
```

### Champs du référentiel

| Champ | Obligatoire | Rôle |
|---|---|---|
| `slug` | **oui** | identifiant technique, unique sur la plateforme ; sert d'URL |
| `name` | **oui** | nom affiché |
| `version` | **oui** | version du référentiel (`2022`, `2.0`, `v1`) |
| `publisher` | non | organisme émetteur |
| `kind` | non (défaut `open`) | `open` / `licensed` / `custom` — voir §1 |
| `licence_notice` | non | mention de droits affichée avec le référentiel |
| `source_url` | non | lien vers la publication d'origine |
| `description` | non | présentation en une ou deux phrases |
| `domains` | **oui** | au moins un domaine |

### Champs d'un domaine

| Champ | Obligatoire | Rôle |
|---|---|---|
| `code` | **oui** | identifiant du domaine, unique dans le référentiel |
| `name` | non (défaut : le code) | nom affiché |
| `order` | non (défaut : rang dans le fichier) | ordre de passage du questionnaire |
| `description` | non | contexte affiché en tête de domaine |
| `measures` | **oui** | au moins une mesure |

### Champs d'une mesure

| Champ | Obligatoire | Rôle |
|---|---|---|
| `code` | **oui** | identifiant tel qu'il figure dans le référentiel : `1`, `A.5.1`, `PR.AA-01`. **Unique dans le référentiel**, libre ailleurs |
| `title` | **oui** | l'intitulé **officiel**, reproduit fidèlement. Jamais reformulé, jamais surchargeable côté client |
| `statement` | **oui** | l'énoncé en langage clair — la question que lit un dirigeant. C'est ce qui s'affiche dans le questionnaire |
| `number` | non | numérotation officielle quand il y en a une (ANSSI : 1-42). Entier, sans contrainte d'unicité |
| `level` | non | libellé de niveau si le référentiel en a un (`standard`, `renforce`, …). Texte libre, purement informatif |
| `weight` | non (défaut `1.0`) | **poids dans le score**. Strictement positif. Voir §5 |
| `effort` | non (défaut `medium`) | `low` / `medium` / `high` — estimation produit, sert à prioriser le plan d'action |
| `impact` | non (défaut `medium`) | `low` / `medium` / `high` — idem |
| `effort_impact_disclaimer` | non (défaut `true`) | dit que effort/impact sont un jugement produit et non une donnée du référentiel |

### Forme héritée (fichier ANSSI)

Le fichier `backend/data/anssi_hygiene.json` sépare la donnée officielle
(`official`) de la couche produit (`simplified`, `product_rating`), parce qu'il
est vérifié ligne à ligne contre le PDF source
(`docs/verification_referentiel_anssi.md`). Cette forme reste **acceptée** par
l'importateur — la convertir pour faire plaisir à un nouveau format aurait
invalidé cette vérification sans rien apporter.

---

## 4. Format tableur (CSV)

Une ligne par mesure, encodage UTF-8, séparateur virgule. Gabarit :
[`backend/data/modeles/referentiel-modele.csv`](../backend/data/modeles/referentiel-modele.csv).

| Colonne | Obligatoire | Correspond à |
|---|---|---|
| `domaine_code` | **oui** | `domains[].code` |
| `domaine_nom` | non | `domains[].name` |
| `domaine_ordre` | non | `domains[].order` |
| `mesure_code` | **oui** | `code` |
| `mesure_numero` | non | `number` |
| `intitule_officiel` | **oui** | `title` |
| `enonce_clair` | **oui** | `statement` |
| `niveau` | non | `level` |
| `poids` | non | `weight` |
| `effort` | non | `effort` |
| `impact` | non | `impact` |

Les lignes d'un même `domaine_code` sont regroupées automatiquement ; l'ordre
des lignes fixe l'ordre des mesures dans le questionnaire.

Un tableur ne portant pas d'en-tête structuré, les métadonnées du référentiel
se passent en options de la commande (`--slug`, `--name`, `--ref-version`, …) :
les répéter sur chaque ligne inviterait à les contredire.

---

## 5. Le poids, et ce qu'il fait au score

Le score de maturité est une moyenne pondérée sur les mesures **auxquelles il a
été répondu** (« non applicable » et sans réponse sont exclus du dénominateur) :

```
score = 100 × Σ (valeur × poids) / Σ poids
       valeur : oui = 1 · partiellement = 0,5 · non = 0
```

- Sans `weight`, toutes les mesures comptent pareil (`1.0`). C'est le bon choix
  pour un référentiel qui ne hiérarchise pas ses exigences.
- L'import ANSSI pose `1.0` pour les mesures « standard » et `0.5` pour les
  « renforcé », ce qui reproduit **exactement** le calcul d'avant V2-4.

---

## 6. Commandes

```bash
# JSON
python manage.py import_referential --file /chemin/iso27001.json

# Tableur, avec les métadonnées en options
python manage.py import_referential --file /chemin/iso27001.csv \
    --slug iso-27001-annexe-a \
    --name "ISO/IEC 27001:2022 — Annexe A" \
    --ref-version 2022 \
    --publisher "ISO/IEC" \
    --kind licensed \
    --licence-notice "Reproduit sous licence n°XXXXX — usage interne."

# Valider un fichier sans rien écrire
python manage.py import_referential --file /chemin/ref.json --dry-run

# Importer sans rendre le référentiel attribuable tout de suite
python manage.py import_referential --file /chemin/ref.json --inactive
```

`--ref-version` et non `--version` : Django réserve `--version` pour afficher
la sienne.

Options de métadonnées en JSON : elles **surchargent** le fichier. C'est ce qui
permet d'importer une structure livrée avec le produit en y ajoutant sa propre
mention de licence.

### Réimport et mise à jour

L'import est **idempotent** : rejouer le même fichier ne crée rien et ne casse
aucune réponse déjà enregistrée. Un réimport met à jour intitulés, énoncés,
poids, effort et impact des mesures existantes (repérées par leur `code`).

Une mesure présente en base mais **absente** du nouveau fichier est
**conservée**, et la commande le signale. Elle n'est jamais supprimée : une
réponse de client peut la référencer, et une mise à jour de référentiel n'a pas
à effacer un diagnostic. La retirer réellement demande une décision explicite,
prise en connaissance des évaluations concernées.

---

## 7. Après l'import

1. **Attribuer** le référentiel aux clients concernés : console
   d'administration → onglet *Référentiels* → « Attribuer à un client ».
   Sans attribution, personne ne le voit.
2. Un client peut **demander** un référentiel depuis son espace ; la demande
   arrive dans le même onglet, avec qui, quand et pourquoi.
3. Retirer un référentiel à un client est **réversible et non destructeur** :
   il ne peut plus l'évaluer, il continue de consulter ce qu'il a produit.

### Composer un questionnaire plus court

Un sous-ensemble (10, 20, 30 mesures) s'enregistre comme modèle réutilisable et
se choisit au démarrage d'un diagnostic. Le score et le plan d'action ne
portent alors que sur ces mesures.

```
POST /api/v1/assessments/subsets/
{
  "referential": "anssi-hygiene-informatique",
  "slug": "anssi-essentielles",
  "name": "ANSSI — les 10 essentielles",
  "measure_codes": ["1", "2", "5", "8", "10", "12", "16", "21", "26", "34"]
}
```

L'ordre des codes est l'ordre de passage. Un code inconnu fait échouer la
création : un sous-ensemble amputé d'une mesure qu'on croyait dedans donnerait
un score faux sans jamais le dire.

### Reformuler une mesure pour un client

```
PUT    /api/v1/assessments/measures/<id>/override/   {"plain_language": "…", "context_note": "…"}
DELETE /api/v1/assessments/measures/<id>/override/
```

La reformulation vit **à côté** du référentiel : l'énoncé d'origine est intact,
les autres clients ne voient rien, et le retrait le fait réapparaître.
L'intitulé officiel, lui, n'est pas surchargeable — c'est la citation du
référentiel.
