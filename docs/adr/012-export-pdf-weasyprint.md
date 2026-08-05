# ADR 012 — Export PDF de la charte informatique via WeasyPrint

- **Statut** : Adopté
- **Date** : 2026-08-05
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Phase 4 a livré la génération IA de la charte informatique avec export Markdown
(`GeneratedDocumentExportView`), mais l'export PDF restait un reste-à-faire explicite (cadrage §7,
US-4.1) : les tenants attendent un document qu'ils peuvent transmettre tel quel (impression,
signature, diffusion interne), pas un fichier `.md` brut. Cette mission (Phase 5) demandait
d'implémenter l'export PDF si l'intégration Docker restait raisonnable, ou de documenter
l'alternative choisie sinon.

## Options étudiées

1. **Rendu PDF côté client** (bibliothèque JS dans le navigateur, ex. `jsPDF`,
   `react-to-print` + impression navigateur). Écarté : rendu dépendant du moteur du navigateur de
   l'utilisateur (mise en page non garantie identique d'un poste à l'autre), et échapperait au
   pipeline de génération documentaire déjà en place côté backend (versioning, horodatage de
   validation, cohérence avec l'export Markdown existant).
2. **Service tiers de conversion HTML→PDF** (API SaaS externe). Écarté : envoi du contenu de la
   charte (potentiellement sensible pour le tenant, même si techniquement pas soumis aux mêmes
   règles que le pipeline IA puisqu'il ne s'agit plus de données pseudonymisées à ce stade — le
   contenu est déjà réhydraté) à un service tiers supplémentaire, sans bénéfice sur la maîtrise du
   rendu ; contraire à la sobriété d'architecture du projet (un service de plus à opérer/payer).
3. **WeasyPrint** (bibliothèque Python HTML/CSS → PDF, rendu serveur) intégrée directement dans le
   pipeline `apps.ai_assistant.services`.

## Décision

`render_document_pdf()` (`backend/apps/ai_assistant/services.py`) convertit le markdown validé en
HTML minimal (`markdown` avec les extensions `extra`/`sane_lists`) puis délègue le rendu PDF à
WeasyPrint, avec une feuille de style dédiée (`_PDF_STYLESHEET`, mise en page A4, typographie
sobre). L'export est exposé via `GeneratedDocumentExportPdfView`
(`GET /api/v1/ai/documents/<id>/export/pdf/`), protégée par les mêmes permissions/quota IA que le
reste du module (`IsTenantMember`, `IsAIEnabled`, `TenantAIRateThrottle`) bien qu'aucun appel IA ne
soit déclenché par cette route — la cohérence de permission avec le reste du module de documents
prime sur une distinction fine qui n'apporterait rien ici.

L'intégration Docker s'est révélée raisonnable une fois la bonne liste de paquets système identifiée :
WeasyPrint nécessite Pango/Cairo/GDK-Pixbuf au niveau système, absents de l'image `python:3.12-slim`
par défaut. `backend/Dockerfile` installe `libpango-1.0-0`, `libpangocairo-1.0-0`,
`libgdk-pixbuf-2.0-0`, `libcairo2`, `libffi8`, `shared-mime-info` et `fonts-liberation` avant
l'installation des dépendances Python ; `.github/workflows/ci.yml` installe le même jeu de paquets
pour que les tests d'export PDF s'exécutent en CI. Ces tests (`TestRenderDocumentPdf`,
`test_export_pdf_returns_a_pdf_attachment`) ne peuvent pas s'exécuter sur une machine de
développement Windows sans ces bibliothèques système ; ils sont vérifiés via l'image Docker et la CI
plutôt que localement — limitation documentée plutôt que contournée silencieusement.

## Conséquences

**Positives**
- Rendu serveur déterministe : le PDF produit ne dépend ni du navigateur ni du poste de
  l'utilisateur, cohérent avec le fait que le document est déjà versionné et validé côté serveur.
- Aucun service tiers supplémentaire : le contenu de la charte ne quitte jamais l'infrastructure du
  projet pour être converti.
- Réutilise le contenu markdown déjà stocké (`GeneratedDocument.content_markdown`) — pas de
  duplication de source entre l'export `.md` et l'export `.pdf`.

**Négatives / points de vigilance**
- Dépendance système supplémentaire (Pango/Cairo/GDK-Pixbuf) à maintenir dans `backend/Dockerfile`
  et `.github/workflows/ci.yml` en parallèle ; un changement de base image Python (comme le
  renommage `libgdk-pixbuf2.0-0` → `libgdk-pixbuf-2.0-0` rencontré lors du passage à Debian
  "trixie") peut casser le build sans lien évident avec le code applicatif.
- Impossible de développer/tester l'export PDF sur un poste Windows sans Docker — un développeur
  futur devra le savoir avant de perdre du temps à chercher pourquoi `pytest` échoue localement sur
  ces deux tests précis.
- WeasyPrint est une dépendance Python supplémentaire dans le chemin de rendu ; toute vulnérabilité
  qui y serait découverte suit le même processus que le reste de la chaîne d'approvisionnement
  (ADR-008 : `pip-audit` en CI).
