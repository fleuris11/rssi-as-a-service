"""Ce qu'un CLIENT a le droit de lire quand quelque chose échoue.

Le produit avait un seul jeu de messages, écrit pour l'exploitant, et les
servait tels quels aux clients. Un dirigeant de PME qui lançait une analyse
pouvait lire, dans son espace :

    « Breachsense a répondu 400 : Request missing the appropriate parameters »
    « Le pool Breachsense de 15 actifs monitorés est complet. »
    « Le budget d'analyses de la plateforme pour ce mois est atteint (87/1000) »
    « L'URL publique du webhook Breachsense n'est pas configurée sur cet
      environnement »

Chacune de ces phrases donne au client quelque chose qui ne le regarde pas :

- **le nom du fournisseur.** C'est un secret commercial. Un client qui le
  connaît peut aller voir le tarif, et le rapport entre ce qu'il paie et ce
  que coûte la donnée devient une conversation qu'on n'a pas choisi d'avoir.
- **l'état de la plateforme.** « 87/1000 » et « pool de 15 » disent la taille
  du parc et la consommation des AUTRES clients. C'est une fuite entre
  locataires, dans un produit dont l'argument est le cloisonnement.
- **la configuration interne.** « le webhook n'est pas configuré sur cet
  environnement » avoue un défaut d'exploitation à la personne qui paie pour
  ne pas s'en occuper.
- **la mécanique de l'erreur.** Un code HTTP et un message d'API en anglais
  ne sont pas actionnables : ils inquiètent sans rien permettre.

RÈGLE. Un message destiné au client dit trois choses, et rien d'autre : ce
qui n'a pas pu être fait, si c'est temporaire, et ce qu'il peut faire. Le
détail technique part dans les journaux, où l'exploitant le trouvera.

Ces constantes sont vérifiées par
``tests/test_client_facing_messages.py``, qui échoue si l'une d'elles
laisse réapparaître le vocabulaire interne.
"""

# --- Analyse (scan) ---------------------------------------------------------

SCAN_FAILED = (
    "L'analyse n'a pas pu aboutir. Nos équipes en sont informées, et vous "
    "pouvez la relancer dans quelques minutes. Les résultats déjà présents "
    "dans votre espace restent valables."
)

SCAN_TEMPORARILY_UNAVAILABLE = (
    "L'analyse est momentanément indisponible. Réessayez d'ici quelques "
    "minutes ; si cela persiste, contactez-nous."
)

SCAN_COOLDOWN = (
    "Une analyse a déjà été lancée récemment pour votre entreprise. "
    "Une nouvelle analyse sera possible dans quelques heures — les fuites "
    "détectées entre-temps vous parviennent sans attendre."
)

SCAN_QUOTA_REACHED = (
    "Vous avez atteint le nombre d'analyses inclus dans votre offre pour ce "
    "mois. Le compteur repart au début du mois prochain ; contactez-nous si "
    "vous avez besoin d'en lancer davantage d'ici là."
)

# --- Surveillance continue --------------------------------------------------

ASSET_ALREADY_MONITORED = "Cet actif est déjà sous surveillance continue."

MONITORING_UNAVAILABLE = (
    "La surveillance continue ne peut pas être activée pour le moment. "
    "Contactez-nous : nous l'activons pour vous."
)

MONITORING_CAPACITY_REACHED = (
    "Vous avez atteint le nombre d'actifs en surveillance continue inclus "
    "dans votre offre. Retirez-en un, ou contactez-nous pour en ajouter."
)

# --- Vocabulaire interdit ---------------------------------------------------
# Vérifié par le test : aucun de ces fragments ne doit apparaître dans un
# message destiné à un client. La liste est volontairement large — mieux vaut
# refuser une formulation innocente que laisser passer un nom de fournisseur.
FORBIDDEN_IN_CLIENT_MESSAGES = (
    "breachsense",
    "anthropic",
    "claude",
    "webhook",
    "endpoint",
    "api",
    "quota partagé",
    "pool",
    "plateforme",  # « le budget de la plateforme » = l'état des autres clients
    "licence",
    "palier",
    "http",
    "traceback",
    "exception",
    "redis",
    "celery",
    "postgres",
)
