# ADR 008 — GitHub Actions : lint → tests → build → scan (Trivy) → deploy

- **Statut** : Adopté
- **Date** : 2026-08-05
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Le dépôt est hébergé sur GitHub et le développement est trunk-based (`main` protégée, branches
courtes, PR avec CI verte — CLAUDE.md). Le projet a une double exigence de qualité : ne jamais casser
`main` (produit réel en production) et démontrer une discipline d'intégration continue pour le dossier
de certification Bloc 3. Phase 5 ajoute des exigences supplémentaires à la chaîne : vérification des
dépendances (chaîne d'approvisionnement) et scan de l'image Docker de production, sans quoi le
durcissement sécurité resterait un audit ponctuel plutôt qu'une garantie continue.

## Options étudiées

1. **GitLab CI**. Écarté : le dépôt est déjà sur GitHub, migrer l'hébergement du code pour son CI
   seul n'apporte aucune valeur.
2. **Jenkins** (auto-hébergé). Écarté : ajoute un service supplémentaire à opérer et sécuriser
   uniquement pour l'intégration continue — contraire à la contrainte d'une équipe d'une personne et
   au principe de sobriété (Green IT, CLAUDE.md) qui s'applique aussi à l'infrastructure annexe.
3. **GitHub Actions**, intégré nativement au dépôt existant, sans service tiers à opérer.

## Décision

Le pipeline (`.github/workflows/ci.yml`) est structuré en jobs indépendants qui s'exécutent en
parallèle quand c'est possible, avec un enchaînement logique lint → tests → build → scan :

- **`backend`** : installation des dépendances système WeasyPrint (Pango/Cairo/GDK-Pixbuf — même jeu
  de paquets que `backend/Dockerfile`), lint (`ruff check` + `ruff format --check`), vérification
  qu'aucune migration Django n'est manquante, tests (`pytest --cov=apps`), puis audit des dépendances
  Python (`pip-audit -r requirements.txt --strict`).
- **`frontend`** : lint (`eslint`), build (`npm run build`), puis audit des dépendances npm
  (`npm run audit`, qui exécute `frontend/scripts/check-npm-audit.mjs` — un allowlist explicite pour
  les vulnérabilités à risque accepté documenté, voir `docs/security_review.md` catégorie A06 ; sans
  ce mécanisme, `npm audit` n'offre aucun moyen natif d'accepter un risque documenté sans faire échouer
  la CI indéfiniment).
- **`container-scan`** (dépend de `backend`) : build de l'image `backend/Dockerfile` et scan Trivy
  (`aquasecurity/trivy-action`) avec `severity: HIGH,CRITICAL` et `ignore-unfixed: true` — les
  vulnérabilités sans correctif disponible ne peuvent de toute façon pas être résolues par une action
  côté projet, les inclure ferait échouer la CI sans action possible.

Le déploiement (étape « deploy » du titre de cet ADR, reprise du cadrage §5) n'est pas encore
implémenté dans `ci.yml` : il est prévu en Phase 6 (« Production », cadrage §11) via SSH vers le VPS,
une fois le runbook de déploiement rédigé. Le anticiper dans cet ADR permet de documenter la décision
dès maintenant sans coder une étape qui ne peut pas encore être testée en conditions réelles.

## Conséquences

**Positives**
- Aucun service supplémentaire à opérer : la CI vit dans le même dépôt que le code, gratuite dans les
  limites GitHub Actions pour un dépôt de cette taille.
- La chaîne d'approvisionnement (pip-audit, npm audit, Trivy) est vérifiée à chaque push/PR, pas
  seulement lors d'un audit ponctuel — les régressions de dépendances sont détectées avant merge.
- Les risques acceptés (react-router GHSA-qwww-vcr4-c8h2) sont documentés dans le code
  (`check-npm-audit.mjs`) et dans `docs/security_review.md`, pas seulement dans la tête du
  développeur : traçable et revu à chaque exécution de CI.

**Négatives / points de vigilance**
- L'étape de déploiement automatisé n'existe pas encore : le déploiement reste manuel jusqu'à la
  Phase 6, ce qui est un écart assumé et documenté plutôt qu'un oubli.
- `ignore-unfixed: true` sur le scan Trivy signifie qu'une vulnérabilité HIGH/CRITICAL sans correctif
  disponible ne bloque pas la CI : à réévaluer manuellement de façon périodique (pas seulement lors
  d'un scan automatisé), puisque ces vulnérabilités restent réelles même si elles ne peuvent pas être
  corrigées immédiatement.
