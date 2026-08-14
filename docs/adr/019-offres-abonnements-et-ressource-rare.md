# 019 — Offres, abonnements et gestion de la ressource rare

- **Statut** : Adopté ; implémenté en Phase 10
- **Date** : 2026-08-14

## Contexte

Jusqu'ici la plateforme n'avait pas de notion de client payant : tout tenant
avait accès à tout, et la seule limite était technique. Pour commercialiser, il
fallait trois choses — un catalogue d'offres, un cycle de vie d'abonnement, et
un moyen de dire « non ».

C'est le troisième point qui structure toute la décision. La licence
Breachsense Essentials **plafonne la plateforme entière** à 15 actifs
surveillés en continu et 1000 requêtes d'analyse par mois, **partagés entre
tous les clients**. Ce ne sont pas des quotas par client : ce sont des
ressources rares communes. Vendre un seizième emplacement ne provoque pas une
facture supplémentaire, cela provoque un service qui ne fonctionne pas — pour
le nouveau client comme pour ceux déjà servis.

Un dépassement constaté après coup n'est donc pas un incident de facturation,
c'est un défaut de conception.

## Options étudiées

**A. Quotas déclaratifs, contrôle a posteriori.**
Chaque offre annonce un nombre d'emplacements ; un rapport mensuel signale les
dépassements. Rejeté : au moment où le rapport signale le dépassement, le
service est déjà dégradé et le contrat déjà signé. La seule action possible est
de retirer quelque chose à un client qui l'a payé.

**B. Contrôle au moment de l'usage** (à l'activation d'un actif surveillé).
Séduisant parce que le comptage colle à la consommation réelle. Rejeté : le
refus tombe alors sur le CLIENT, plusieurs semaines après la vente, pour une
capacité que l'exploitant lui a vendue. La faute est commerciale, la sanction
est subie par l'utilisateur final.

**C. Contrôle à l'engagement** — retenu.
La ressource est comptée en **quotas engagés** (somme des quotas des
abonnements en essai ou actifs), pas en actifs effectivement déclarés. Toute
opération qui augmenterait l'engagement — ouvrir un essai, activer, changer
d'offre, convertir un prospect, s'inscrire — passe par une garde qui refuse
**avant toute écriture**.

## Décision

### Le comptage porte sur l'engagement, pas sur l'usage

`apps/billing/capacity.py` additionne les quotas des abonnements en `trial` et
`active`. Un client qui a payé trois emplacements et n'en a déclaré aucun les
occupe quand même : ils lui sont dus. Compter l'usage réel reviendrait à
survendre en s'appuyant sur la lenteur des clients à s'installer, et à leur
refuser le service le jour où ils s'en servent tous.

Les abonnements `suspended`, `cancelled` et `expired` ne comptent pas : leurs
emplacements retournent au pool.

### Le refus est explicite et actionnable

`PlatformCapacityError` porte un message qui dit ce que l'opération
engagerait, quel est le plafond, et **combien il reste** :

> Cette opération engagerait 17 emplacements de surveillance continue pour un
> plafond plateforme de 15. Il en reste 1 disponible(s). Libérez des
> emplacements … ou passez à un palier de licence supérieur avant de poursuivre.

Côté API, ce refus est un **409 Conflict**, pas un 400 ni un 403 : la demande
est légitime et l'appelant a le droit de la formuler, c'est l'état de la
plateforme qui la rend momentanément impossible.

### L'inscription libre est soumise à la même garde

Conséquence trouvée en écrivant les tests, et volontairement conservée : une
inscription publique ouvre un essai, donc engage des emplacements. Elle est
refusée quand le pool est plein. L'alternative — créer le compte sans
abonnement — livrerait un produit dont chaque fonction se bloque, ce qui est
pire qu'un refus franc. `create_tenant_with_owner` est donc atomique et laisse
remonter la seule `PlatformCapacityError`, en absorbant les autres échecs
(catalogue vide, offre par défaut retirée) qui relèvent d'un défaut de
configuration et non d'une limite opposable au client.

### Les fonctionnalités sont déclarées en code, activées en base

Le registre (`apps/billing/features.py`) liste les clés connues, leur libellé
et leur promesse. Les offres n'en activent qu'un sous-ensemble. Deux
comportements volontairement asymétriques :

- **à l'écriture**, une clé inconnue est rejetée : on prévient l'exploitant de
  sa faute de frappe ;
- **à la lecture**, une clé inconnue est ignorée silencieusement : une offre
  mal saisie ne doit jamais faire tomber l'application de ses abonnés.

### Une suspension ne prend pas les données en otage

Un abonnement `suspended` ou `expired` conserve l'**accès en lecture** à tout
l'existant. Seules les opérations qui consomment une ressource — analyse,
surveillance — sont bloquées, avec un **402 Payment Required** qui nomme la
cause. On ne se sert jamais des données d'un client comme d'un levier de
recouvrement.

### Hors offre : désactivé, jamais masqué

`FeatureGate` rend la fonctionnalité visible, grisée, `aria-disabled`, avec le
nom de l'offre qui la débloque. Masquer laisserait croire que le produit ne
sait pas le faire — c'est faux, et cela supprime la seule raison de monter
d'offre. Le composant est un affichage : la garde réelle reste côté serveur, et
les tests vérifient qu'un appel direct à l'API est refusé indépendamment de ce
que montre l'interface.

En cas d'échec de chargement des droits, le frontend est **optimiste** (tout
paraît inclus). Le serveur reste l'autorité ; griser toute l'interface sur un
incident réseau passager transformerait une panne de quelques secondes en
produit visiblement dégradé.

## Conséquences

**Ce que cela apporte.** Le dépassement est structurellement impossible : cinq
tests de refus le vérifient, et la garde a été neutralisée temporairement pour
confirmer qu'ils rougissent bien. L'exploitant voit en permanence l'occupation
du pool et sait, avant de vendre, si une offre donnée tiendrait encore.

**Ce que cela coûte.** La plateforme est petite : 15 emplacements, dont 10 déjà
engagés par le jeu de démonstration. Une inscription libre en consomme trois
(essai sur Pilotage). Le produit est donc, en l'état, capable de refuser une
inscription légitime après cinq nouveaux clients — c'est la réalité de la
licence, pas un défaut du code, mais cela impose de surveiller le pool ou de
monter de palier avant toute campagne d'acquisition.

**Alertes.** Des seuils à 80 % et 95 % préviennent l'exploitant une seule fois
par seuil, par ressource et par mois. Le but est d'anticiper la saturation, pas
de produire un bruit qu'on finit par ignorer.

**Ce qui reste ouvert.** Le paiement lui-même — voir [ADR-020](020-emplacement-du-paiement.md).
