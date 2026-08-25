"""Bascule des essais en cours vers l'offre d'essai dédiée (ADR-024).

## Pourquoi ce module existe

La migration 0003 **crée** l'offre `essai` et fait pointer
`BILLING_DEFAULT_TRIAL_PLAN_CODE` dessus. Cela ne vaut que pour les
inscriptions **futures** : les essais déjà ouverts restent sur l'offre du
catalogue qui les portait, c'est-à-dire, en pratique, « Veille ».

Tant qu'aucune garde de fonctionnalité n'est posée, cela ne se voit pas — tout
le monde a tout. Le jour où les six gardes manquantes tomberont, ces essais-là
perdraient d'un coup le diagnostic, l'assistant, l'export PDF, la corrélation
et la génération de charte : un prospect en cours d'essai verrait le produit
se vider sans avoir rien fait. C'est exactement la panne qu'ADR-024 dit
d'éviter, et que la migration 0003 seule ne suffit pas à éviter.

## Pourquoi une fonction, et pas du code dans la migration

Trois appelants, une seule règle :

- la migration 0004, qui l'applique au déploiement, sur les modèles
  historiques ;
- la commande ``basculer_essais``, qui permet de la rejouer et de la vérifier
  sur un environnement réel ;
- les tests, qui l'exercent sur les modèles courants.

Une règle recopiée dans la migration serait intestable autrement qu'en
rejouant tout l'historique des migrations.

## Idempotence

Une migration ne s'exécute qu'une fois ; l'idempotence ne s'observe donc que
si la règle est rejouable. Elle l'est : la sélection porte sur « essais qui ne
sont PAS déjà sur l'offre d'essai ». Une seconde passe ne trouve plus rien et
ne récrit rien — c'est ce que vérifient les tests.

## Deux écarts assumés par rapport à ``services.change_plan``

1. **Les surcharges sont conservées.** ``change_plan`` les efface, à raison :
   elles appartenaient à la négociation de l'ancienne offre. Ici il ne s'agit
   pas d'une renégociation commerciale mais de la **correction d'un défaut de
   configuration** : personne n'a renégocié quoi que ce soit. Effacer un
   ``override_features`` posé à la main retirerait à un client quelque chose
   qu'un exploitant lui avait délibérément accordé — soit précisément ce que
   cette bascule existe pour empêcher.

2. **Aucun contrôle de capacité plateforme n'est nécessaire**, parce que la
   bascule ne peut pas augmenter l'engagement : elle est **refusée** si
   l'offre d'essai réclame plus d'emplacements que l'offre quittée. Voir
   ``_refus_de_capacite``.
"""

from dataclasses import dataclass, field

# Repli seulement : le code réellement visé est celui que les inscriptions
# utilisent (``BILLING_DEFAULT_TRIAL_PLAN_CODE``). Viser une constante en dur
# alors que le réglage pointe ailleurs ferait diverger les essais déjà ouverts
# des essais à venir — l'incohérence même qu'on corrige.
CODE_ESSAI_PAR_DEFAUT = "essai"

RAISON = "Bascule vers l'offre d'essai dédiée (ADR-024)."


@dataclass
class Bascule:
    """Un essai déplacé. Porte de quoi écrire une ligne de journal lisible."""

    tenant: str
    offre_avant: str
    offre_apres: str
    emplacements_avant: int
    emplacements_apres: int

    @property
    def perd_des_emplacements(self) -> bool:
        return self.emplacements_apres < self.emplacements_avant


@dataclass
class Rapport:
    """Ce que la bascule a fait, et ce qu'elle n'a pas fait — les deux comptent.

    Un rapport qui ne listerait que les succès laisserait croire à une
    exécution complète là où l'offre d'essai peut être absente, ou une bascule
    refusée pour cause de capacité.
    """

    basculees: list[Bascule] = field(default_factory=list)
    ignorees: list[str] = field(default_factory=list)
    refusees: list[str] = field(default_factory=list)
    empechement: str = ""

    @property
    def a_agi(self) -> bool:
        return bool(self.basculees)

    def lignes(self) -> list[str]:
        """Rendu texte, utilisé tel quel par la migration et par la commande.

        Volontairement bavard sur le cas « rien à faire » : un silence ne
        distingue pas « aucun essai à basculer » de « le code n'a pas tourné ».
        """
        if self.empechement:
            return [f"Bascule des essais NON EFFECTUÉE : {self.empechement}"]

        lignes = []
        if not self.basculees:
            lignes.append("Bascule des essais : aucun essai à basculer.")
        else:
            lignes.append(f"Bascule des essais : {len(self.basculees)} abonnement(s) déplacé(s).")
            for bascule in self.basculees:
                ligne = f"  - {bascule.tenant} : {bascule.offre_avant} -> {bascule.offre_apres}"
                if bascule.perd_des_emplacements:
                    # Signalé parce que le client peut se retrouver au-dessus
                    # de son nouveau quota. Ses actifs continuent d'être
                    # surveillés — la garde de quota refuse d'en AJOUTER, elle
                    # ne supprime rien (on ne retire pas un service en cours).
                    ligne += (
                        f" (emplacements {bascule.emplacements_avant} -> "
                        f"{bascule.emplacements_apres} : vérifier les actifs déjà déclarés)"
                    )
                lignes.append(ligne)

        for motif in self.refusees:
            lignes.append(f"  ! refusé — {motif}")
        for motif in self.ignorees:
            lignes.append(f"  . ignoré — {motif}")
        return lignes


def _refus_de_capacite(offre_source, offre_essai) -> str:
    """Garde de sûreté sur la ressource rare (ADR-013/019).

    L'offre d'essai est modifiable depuis la console sans redéploiement : rien
    n'empêche quelqu'un d'y porter les emplacements à 3. La bascule
    deviendrait alors une opération qui **augmente** l'engagement plateforme,
    en masse et sans que personne ne l'ait demandé.

    On ne tente pas de compter le pool ici : à ce stade (migration), refuser
    d'augmenter est plus sûr que d'arbitrer. Un refus laisse l'essai là où il
    est, c'est-à-dire dans l'état d'avant — jamais une perte.
    """
    if offre_essai.monitored_assets > offre_source.monitored_assets:
        return (
            f"{offre_source.code} -> {offre_essai.code} augmenterait l'engagement "
            f"({offre_source.monitored_assets} -> {offre_essai.monitored_assets} "
            "emplacements). Bascule refusée : l'offre d'essai ne doit pas coûter plus "
            "cher en ressource rare que l'offre quittée."
        )
    return ""


def basculer_essais(Plan, Subscription, SubscriptionEvent, *, code_essai: str) -> Rapport:
    """Déplace vers l'offre d'essai les abonnements en essai qui n'y sont pas.

    Les modèles sont passés en paramètre pour que la migration puisse fournir
    ses modèles historiques — une migration qui importerait
    ``apps.billing.models`` casserait au premier changement de schéma
    ultérieur.
    """
    rapport = Rapport()

    offre_essai = Plan.objects.filter(code=code_essai).first()
    if offre_essai is None:
        # Jamais une exception : une migration qui tombe empêche tout le
        # déploiement, pour un défaut de catalogue qui ne casse rien en soi.
        rapport.empechement = (
            f"aucune offre de code {code_essai!r}. Les essais en cours restent sur "
            "leur offre actuelle."
        )
        return rapport

    candidats = (
        Subscription.objects.filter(status="trial")
        .exclude(plan_id=offre_essai.id)
        .select_related("plan", "tenant")
    )

    for abonnement in candidats:
        offre_source = abonnement.plan

        if offre_source.status == "internal":
            # Une offre interne a été attribuée à la main : partenaire, tarif
            # négocié, compte de démonstration. Défaire une décision
            # d'exploitant serait pire que le défaut qu'on corrige.
            rapport.ignorees.append(
                f"{abonnement.tenant.name} : offre interne {offre_source.code!r}, "
                "attribuée délibérément"
            )
            continue

        refus = _refus_de_capacite(offre_source, offre_essai)
        if refus:
            rapport.refusees.append(f"{abonnement.tenant.name} : {refus}")
            continue

        abonnement.plan = offre_essai
        # Surcharges volontairement NON effacées — voir l'en-tête du module.
        abonnement.save(update_fields=["plan", "updated_at"])

        SubscriptionEvent.objects.create(
            subscription=abonnement,
            from_status=abonnement.status,
            to_status=abonnement.status,
            from_plan=offre_source.name,
            to_plan=offre_essai.name,
            reason=RAISON[:255],
            actor=None,
        )

        rapport.basculees.append(
            Bascule(
                tenant=abonnement.tenant.name,
                offre_avant=offre_source.code,
                offre_apres=offre_essai.code,
                emplacements_avant=offre_source.monitored_assets,
                emplacements_apres=offre_essai.monitored_assets,
            )
        )

    return rapport
