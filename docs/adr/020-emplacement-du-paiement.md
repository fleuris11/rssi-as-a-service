# 020 — Emplacement du paiement (et pourquoi il n'est pas encore là)

- **Statut** : Adopté ; l'emplacement est en place, le prestataire ne l'est pas
- **Date** : 2026-08-14

## Contexte

La Phase 10 rend le produit commercialisable : offres, abonnements, essai,
quotas. Il manque le paiement. La tentation est d'installer un SDK de
prestataire tout de suite — c'est rapide et cela donne l'impression d'avoir
fini.

Trois raisons de ne pas le faire maintenant :

1. **Aucune entité juridique n'est encore renseignée.** Les mentions légales
   sont des trames à compléter (`docs/legal/README.md`). Ouvrir un compte
   prestataire suppose une société, un RIB, une adresse — rien de tout cela
   n'existe dans le projet à ce jour.
2. **Le prestataire n'est pas arrêté.** Le choix dépend de la structure
   juridique, des commissions, du régime de TVA et de la localisation des
   données (un prestataire est un sous-traitant à déclarer). S'engager
   maintenant, c'est choisir sans les informations qui font le choix.
3. **Une dépendance installée est un engagement.** Un SDK importé finit par
   fuiter dans les modèles, les vues et les migrations. Le retirer coûte plus
   cher que de l'avoir attendu.

## Options étudiées

**A. Intégrer un prestataire immédiatement (Stripe ou équivalent).**
Rejeté pour les trois raisons ci-dessus.

**B. Ne rien prévoir, et refondre le modèle le jour venu.**
Rejeté : le cycle de vie d'abonnement est écrit maintenant. Y greffer plus tard
la notion de client externe, de référence d'abonnement distante et de webhook
imposerait de rouvrir des migrations sur des données de production.

**C. Poser l'emplacement sans le prestataire** — retenu.

## Décision

### Les paiements existants sont manuels et complets

`Payment` enregistre un encaissement réel : montant, devise, date de réception,
référence (virement, chèque), note et acteur. Un reçu PDF est généré par le
même moteur que les documents produits par l'assistant. Un abonnement peut donc
être vendu, encaissé et justifié **sans aucun prestataire** — c'est le mode de
fonctionnement prévu pour les premiers clients.

### Trois champs, aujourd'hui inutilisés, tiennent la place

Sur `Subscription` :

- `billing_provider` — vaut `"manual"` par défaut ;
- `external_customer_ref` — identifiant du client chez le prestataire ;
- `external_subscription_ref` — identifiant de l'abonnement chez le
  prestataire.

Ils sont vides et le code ne les lit nulle part. Leur seule fonction est
d'éviter une migration structurante le jour de l'intégration : on écrira alors
un adaptateur qui remplit ces champs et réagit aux webhooks, sans toucher au
cycle de vie ni aux gardes de capacité.

### Le cycle de vie reste la source de vérité

Le paiement ne pilote pas l'état : c'est `Subscription.status` qui décide de ce
qui est permis, et chaque transition laisse un `SubscriptionEvent` daté et
attribué. Un futur webhook déclenchera donc `activate()` ou `suspend()` — les
mêmes fonctions que le back-office — et passera par les mêmes gardes. Un
paiement encaissé ne pourra jamais activer un abonnement que la capacité de la
plateforme ne permet pas d'honorer (ADR-019).

## Conséquences

**Ce que cela apporte.** Aucune dépendance de paiement dans
`requirements.txt`. Le produit est vendable dès maintenant en facturation
manuelle. L'intégration future est un adaptateur, pas une refonte.

**Ce que cela coûte.** L'encaissement est saisi à la main : viable pour les
premiers clients, pas au-delà de quelques dizaines. Il n'y a ni relance
automatique, ni gestion d'échec de paiement, ni prorata de changement d'offre
en cours de période — ces règles seront à écrire avec le prestataire, car leur
sémantique dépend de lui.

**Condition de réouverture.** Cet ADR sera repris quand l'entité juridique
existera et que le prestataire sera choisi. La décision à documenter alors :
qui, de la plateforme ou du prestataire, fait autorité sur l'état d'un
abonnement en cas de désaccord. La réponse par défaut retenue ici est **la
plateforme**, parce qu'elle est la seule à connaître la capacité disponible.
