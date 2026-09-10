"""Veille sur l'évolution des référentiels et des exigences (V2-7, ADR-034).

**Rien ici n'est scopé par tenant.** La veille est une activité de
l'exploitant : elle observe des publications publiques et alimente le
catalogue de référentiels, qui est lui-même partagé (ADR-029). Aucun client ne
voit ces tables, et aucune donnée de client n'y entre.

La règle qui commande tout le reste : **ce module produit une SUGGESTION, et
jamais une modification**. Aucune ligne de ces modèles n'écrit dans
``assessments`` ; l'intégration d'une mesure passe par un service séparé, qui
exige un relecteur nommé. Voir ADR-034 §3.
"""

from django.conf import settings
from django.db import models


class WatchSource(models.Model):
    """Une source suivie. **Primaire uniquement** : agence nationale, texte
    européen, organisme de normalisation, autorité sectorielle.

    Les sources secondaires — blogs, agrégateurs, presse spécialisée — sont
    exclues par principe (consigne V2-7 §2, ADR-034 §1). Le risque n'est pas
    théorique : un produit qui vend la rigueur ne peut pas remonter à un
    client une exigence qui n'existe pas, parce qu'un blog l'a mal comprise.
    Rien dans le code n'empêche d'en saisir une — c'est une règle éditoriale,
    tenue par la liste de départ et par l'ADR, pas par une contrainte de base.
    """

    class Format(models.TextChoices):
        RSS = "rss", "Flux RSS"
        ATOM = "atom", "Flux Atom"
        # Pas de flux publié : on relève l'empreinte de la page et on signale
        # qu'elle a changé. Moins précis qu'un flux — on sait QUE ça a bougé,
        # pas QUOI — et c'est dit tel quel dans la file.
        PAGE = "page", "Page sans flux (détection de changement)"

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=200)
    publisher = models.CharField(max_length=200)
    #: La page lisible par un humain — c'est elle qu'on met en lien dans la
    #: file, jamais l'URL technique du flux.
    url = models.URLField()
    #: Vide pour ``PAGE``.
    feed_url = models.URLField(blank=True)
    format = models.CharField(max_length=10, choices=Format.choices)
    #: Rythme ATTENDU, en clair. Sert à juger un silence : une source
    #: hebdomadaire muette depuis deux mois est probablement cassée.
    expected_frequency = models.CharField(max_length=120, blank=True)
    #: Ce qu'on attend de cette source, et ce qu'on n'en attend pas.
    scope_note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    last_polled_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    #: Une source qui échoue en silence est pire qu'une source absente : on
    #: croit surveiller. Le compteur remonte dans la console.
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    #: Empreinte du dernier contenu relevé, pour les sources ``PAGE``.
    content_fingerprint = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["publisher", "name"]

    def __str__(self):
        return f"{self.publisher} — {self.name}"

    @property
    def is_healthy(self) -> bool:
        return self.consecutive_failures == 0


class WatchUpdate(models.Model):
    """Une publication détectée. **Une suggestion, pas une décision.**

    Elle reste dans la file jusqu'à ce qu'un humain la lise et tranche. Tant
    qu'elle est ``NEW``, elle n'a modifié aucun référentiel — et le seul
    chemin qui en modifie un exige un relecteur, un référentiel cible et un
    contenu saisi à la main (``services.integrate_as_measure``).

    ``source_excerpt`` conserve le texte tel que la source l'a publié. C'est
    la référence (consigne V2-7 §7) : un résumé par IA, quand il existe, vient
    À CÔTÉ et ne le remplace jamais.
    """

    class Status(models.TextChoices):
        NEW = "new", "À examiner"
        KEPT = "kept", "Retenue"
        INTEGRATED = "integrated", "Intégrée au référentiel"
        DISMISSED = "dismissed", "Écartée"

    class Kind(models.TextChoices):
        """Qualification posée par l'exploitant à la lecture, jamais deviné
        par la collecte."""

        UNQUALIFIED = "unqualified", "Non qualifiée"
        NEW_REQUIREMENT = "new_requirement", "Nouvelle exigence"
        UPDATE = "update", "Évolution d'une exigence existante"
        INFORMATION = "information", "Information, sans effet sur un référentiel"

    source = models.ForeignKey(WatchSource, on_delete=models.CASCADE, related_name="updates")
    #: Identifiant stable côté source (``guid`` d'un flux) ou, à défaut,
    #: empreinte du couple titre + lien. C'est lui qui empêche de re-signaler
    #: la même publication à chaque passage.
    external_id = models.CharField(max_length=200)
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    published_at = models.DateTimeField(null=True, blank=True)
    source_excerpt = models.TextField(blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.UNQUALIFIED)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    #: Le référentiel auquel l'exploitant rattache cette publication, s'il y
    #: en a un. Nul pour une information générale.
    target_referential = models.ForeignKey(
        "assessments.Referential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    #: Les mesures effectivement créées depuis cette publication. C'est la
    #: moitié « veille » de la traçabilité ; l'autre moitié vit sur la mesure
    #: elle-même (``Measure.source_url`` / ``source_reference``), en texte,
    #: pour survivre même si cette app disparaissait.
    integrated_measures = models.ManyToManyField(
        "assessments.Measure", blank=True, related_name="+"
    )

    #: Résumé par IA — FACULTATIF, déclenché à la main, jamais à la collecte
    #: (sobriété : on ne paie pas un résumé pour une publication que personne
    #: n'ouvrira). Il résume et ne conclut pas (ADR-034 §5).
    ai_summary = models.TextField(blank=True)
    ai_summary_model = models.CharField(max_length=60, blank=True)
    ai_summary_at = models.DateTimeField(null=True, blank=True)
    ai_tokens_input = models.PositiveIntegerField(default=0)
    ai_tokens_output = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-published_at", "-detected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="unique_update_per_source"
            ),
        ]
        indexes = [models.Index(fields=["status", "-detected_at"])]

    def __str__(self):
        return f"{self.source_id} — {self.title[:60]}"

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.NEW, self.Status.KEPT)
