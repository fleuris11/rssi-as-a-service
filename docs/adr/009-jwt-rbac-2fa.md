# ADR 009 — JWT courts + refresh rotation, RBAC 3 rôles, 2FA TOTP

- **Statut** : Adopté
- **Date** : 2026-08-05
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Le frontend est une SPA React découplée du backend Django/DRF, consommant une API REST
(`/api/v1/`). L'authentification doit donc être stateless côté serveur (pas de session Django
classique côté SPA), tout en offrant une révocation raisonnable en cas de compromission de jeton, une
séparation des permissions entre rôles au sein d'un même tenant (un administrateur, un contributeur et
un lecteur n'ont pas les mêmes droits sur le diagnostic, le plan d'action ou les actifs surveillés), et
un niveau d'authentification renforcé cohérent avec le positionnement du produit : un outil de
cybersécurité qui n'appliquerait pas à son propre accès les mesures qu'il recommande à ses utilisateurs
(2FA) manquerait d'exemplarité — un risque de crédibilité produit autant qu'un risque technique.

## Options étudiées

1. **Sessions serveur** (cookies de session Django classiques). Écarté : couple fortement le frontend
   au domaine du backend (cookies same-site), complique le découplage SPA/API voulu dès le départ, et
   n'apporte pas d'avantage de sécurité décisif face à des jetons courts avec rotation.
2. **OAuth externe seul** (délégation complète à un fournisseur d'identité tiers – Google, Microsoft).
   Écarté comme unique mécanisme : dépendance à un tiers pour l'accès à un produit de cybersécurité
   destiné à des TPE/PME qui n'ont pas forcément d'identité fédérée d'entreprise ; envisageable en
   complément futur, pas comme fondation.
3. **JWT courts + rotation des refresh tokens, RBAC à 3 rôles, 2FA TOTP.**

## Décision

**JWT** (`djangorestframework-simplejwt`, `backend/config/settings.py:SIMPLE_JWT`) : access token de
15 minutes, refresh token de 7 jours avec `ROTATE_REFRESH_TOKENS=True` et
`BLACKLIST_AFTER_ROTATION=True` — chaque rafraîchissement invalide l'ancien refresh token, limitant la
fenêtre d'exploitation d'un jeton volé. Le rafraîchissement (`/api/v1/auth/token/refresh/`) est
lui-même throttlé (`apps/accounts/throttling.py:AuthRateThrottle`, `docs/security_review.md`
catégorie A07).

**RBAC** : trois rôles par tenant (`apps.tenants.models.Membership.Role` — `admin`, `contributor`,
`reader`), portés par la relation `Membership` plutôt que par l'utilisateur lui-même (un utilisateur
peut avoir des rôles différents selon le tenant). Les permissions DRF (`apps/tenants/permissions.py` :
`IsTenantMember`, `IsTenantAdmin`, `IsTenantMemberReadOnlyForReader`) sont posées explicitement sur
chaque vue — jamais de vue sans classe de permission déclarée.

**2FA TOTP** (US-1.3, `apps/accounts/services.py`, `apps/accounts/models.py:TwoFactorCredential` /
`RecoveryCode`) : enrôlement par QR code (`pyotp` + `qrcode`), secret chiffré au repos avec une clé
Fernet dédiée (`TOTP_ENCRYPTION_KEY`, distincte de `AI_PSEUDONYMIZATION_KEY` — ADR-005 — pour qu'une
compromission de l'une ne compromette pas l'autre), codes de récupération à usage unique hashés,
vérification au login via un jeton de challenge opaque (`secrets.token_urlsafe`, TTL 5 minutes,
usage unique — jamais un JWT, pour ne pas donner l'illusion d'un accès déjà authentifié) et
désactivation nécessitant la confirmation du mot de passe.

## Conséquences

**Positives**
- L'API reste stateless côté serveur pour l'accès courant (le blacklist de refresh tokens est la seule
  trace de session côté serveur), ce qui garde le découplage SPA/API simple.
- La rotation des refresh tokens limite la durée de vie utile d'un jeton compromis à un seul cycle de
  rafraîchissement plutôt qu'à 7 jours pleins.
- Le RBAC porté par `Membership` plutôt que par l'utilisateur permet nativement le cas d'un
  consultant/expert-comptable membre de plusieurs tenants avec des rôles différents, sans modèle
  supplémentaire.
- La 2FA n'est pas un gadget documentaire : elle s'accompagne d'un verrouillage progressif par
  compte+IP et de messages d'erreur non énumérants (`docs/security_review.md` catégorie A07),
  cohérents avec l'exemplarité attendue d'un produit cyber.

**Négatives / points de vigilance**
- Un access token compromis reste valide jusqu'à 15 minutes sans mécanisme de révocation immédiate
  côté serveur (les JWT ne sont pas des sessions) — accepté comme compromis standard JWT, mitigé par
  la courte durée de vie plutôt qu'éliminé.
- La 2FA est optionnelle à l'activation (US-1.3 ne l'impose pas par défaut à tous les tenants) : un
  compte qui ne l'active pas ne bénéficie pas de la protection renforcée — à réévaluer si un jour une
  politique d'entreprise (tenant) doit pouvoir l'imposer à ses membres (hors périmètre actuel).
