# ADR 010 — Vérifications passives uniquement sur actifs déclarés

- **Statut** : Adopté
- **Date** : 2026-08-05
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Le module de surveillance (`apps.monitoring`) vérifie en continu la posture cyber d'actifs
appartenant aux tenants (disponibilité HTTP, certificat SSL, en-têtes de sécurité, configuration
SPF/DKIM/DMARC — cadrage §7, CLAUDE.md règle 4) pour produire la « météo cyber » quotidienne. Un outil
qui interroge des domaines/URL tiers depuis un serveur qu'il contrôle touche immédiatement à des
questions légales (accès non autorisé à un système informatique, Article 323-1 du Code pénal
français) et éthiques (un service SaaS qui scannerait activement des cibles sans mandat explicite
s'exposerait, et exposerait ses utilisateurs, à des poursuites — même dans une intention défensive).
Le produit doit rester utilisable sans contrat de pentest ni mandat d'intrusion pour chaque actif
surveillé, tout en évitant les faux positifs qui décrédibiliseraient la « météo cyber ».

## Options étudiées

1. **Scans actifs de vulnérabilités** (scan de ports, fuzzing, tests d'intrusion automatisés type
   Nmap/Nessus/OpenVAS contre les actifs déclarés). Écarté : nécessiterait un mandat explicite et
   documenté par actif avant tout scan (cadre légal du test d'intrusion), une charge opérationnelle et
   juridique incompatible avec un produit SaaS en libre inscription pour TPE/PME ; risque réputationnel
   et juridique disproportionné par rapport à la valeur ajoutée pour la cible.
2. **Vérifications passives uniquement**, limitées à des requêtes qu'un navigateur ou un client DNS
   grand public effectuerait normalement en consultant le site (GET HTTP, lecture du certificat TLS
   côté client, requêtes DNS publiques), sur des actifs explicitement déclarés et dont la propriété est
   attestée par le tenant.

## Décision

Chaque check (`apps/monitoring/checks/`) se limite à des opérations passives : une requête HTTP GET
standard (`http_client.py`), la lecture du certificat présenté lors d'une connexion TLS normale
(`ssl_certificate.py`), l'inspection des en-têtes de réponse HTTP déjà publics, et des requêtes DNS
publiques (`email_dns.py` pour SPF/DKIM/DMARC) — jamais de scan de port, de tentative d'exploitation,
ni de requête qui ne serait pas envoyée par un client légitime consultant le service normalement.

Deux garde-fous structurels appliquent cette décision au niveau du code, pas seulement de la
documentation :

1. **Actif déclaré uniquement** : `apps.monitoring.models.Asset` exige `ownership_confirmed=True`
   (attestation de propriété, US-5.1) à la création, contrôlée par le serializer ; aucun check ne peut
   s'exécuter sur une cible qui n'a pas été explicitement déclarée par le tenant qui prétend en être
   propriétaire.
2. **Anti-SSRF** (`apps/monitoring/checks/ssrf.py`) : toute résolution DNS est validée contre les
   plages d'IP privées/loopback/link-local/réservées/multicast avant l'ouverture de toute connexion —
   y compris à chaque redirection HTTP suivie (une validation qui ne s'appliquerait qu'à l'URL de
   départ laisserait un attaquant rediriger un check vers un service interne via un 302). Ce garde-fou
   sert doublement : il empêche qu'un actif « déclaré » comme un site public serve en réalité de
   prétexte pour sonder le réseau interne de l'hébergeur du produit.

Pour limiter les faux positifs (confiance dans la « météo cyber », cadrage §9) : une alerte DOWN n'est
ouverte qu'après `CONSECUTIVE_FAILURES_FOR_DOWN` échecs consécutifs (`services._evaluate_down_alert`),
jamais sur un seul échec transitoire.

Cette limitation (pas de scan actif) est documentée explicitement dans les CGU du produit, pour que les
tenants comprennent le périmètre réel de la surveillance qu'ils souscrivent.

## Conséquences

**Positives**
- Aucun mandat de test d'intrusion à collecter ni à gérer par actif : le produit reste utilisable en
  libre inscription, cohérent avec le modèle SaaS visé.
- Les garde-fous (attestation de propriété, anti-SSRF, confirmation par échecs consécutifs) sont dans
  le code et testés (`apps/monitoring/tests/test_ssrf.py`), pas seulement dans une politique — vérifiable
  par la CI à chaque changement.
- Positionnement produit clair et défendable : la « météo cyber » est un indicateur de posture externe
  observable, pas un audit de sécurité — attente correctement calibrée côté utilisateur.

**Négatives / points de vigilance**
- La couverture est nécessairement plus limitée qu'un scan actif : des vulnérabilités non visibles de
  l'extérieur par une requête passive (mauvaise configuration interne, port ouvert non lié à HTTP/TLS,
  etc.) ne sont pas détectées — limite assumée et à rappeler dans toute communication produit pour ne
  pas créer un faux sentiment de couverture complète.
- La détection SPF/DKIM/DMARC dépend de la disponibilité et de la cohérence des résolveurs DNS publics
  interrogés ; une panne DNS tierce peut produire un faux avertissement, mitigé par le seuil de
  confirmation avant alerte (mais ce seuil ne s'applique aujourd'hui explicitement qu'au check
  `HTTP_UPTIME` — à étendre aux autres types de check si des faux positifs DNS sont observés en
  production).
