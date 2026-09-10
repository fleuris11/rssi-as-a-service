"""Les documents, composés à partir des données de la plateforme.

**Composés, et non rédigés par l'IA.** La décision est prise dans ADR-032 et
elle tient en une phrase : un document qu'une PME doit réécrire entièrement ne
sert à rien. Un modèle écrit une fois, correctement, et rempli avec les
véritables actifs, le véritable score et les véritables échéances du client est
plus utile — et surtout reproductible — qu'une rédaction qui change à chaque
génération. La charte informatique reste rédigée par l'IA : c'est le seul
document dont le texte doit vraiment s'adapter au contexte particulier de
l'entreprise, et elle existait déjà ainsi.

Trois règles suivies partout ici :

1. **on n'invente rien.** Ce que la plateforme ne sait pas est écrit
   ``[à compléter]``, jamais deviné. Un plan de continuité qui annonce un
   délai de reprise que personne n'a décidé est pire qu'une case vide ;
2. **on dit d'où vient chaque chiffre.** Un document présenté à un assureur ou
   à un donneur d'ordre doit pouvoir être justifié ligne à ligne ;
3. **on écrit pour un dirigeant de PME.** Pas de jargon sans traduction, pas de
   renvoi à une norme que le lecteur n'a pas.
"""

from datetime import date

from .context import A_COMPLETER

EFFORT_FR = {"low": "faible", "medium": "moyen", "high": "élevé"}
#: Les états de possession d'un actif (ADR-026), en français. Le document est
#: lu par un dirigeant : « declared » n'y a pas sa place.
POSSESSION_FR = {
    "proven": "prouvée",
    "declared": "déclarée sur l'honneur",
    "to_review": "à régulariser",
}
IMPACT_FR = {"low": "faible", "medium": "moyen", "high": "fort"}


# --- Petits outils de mise en forme -----------------------------------------


def _jour(valeur) -> str:
    if valeur is None:
        return "—"
    return valeur.strftime("%d/%m/%Y")


def _ou(valeur, defaut: str = A_COMPLETER) -> str:
    """La valeur si elle est renseignée, la marque « à compléter » sinon."""
    if valeur in (None, "", 0):
        return defaut
    return str(valeur)


def _tableau(entetes: list[str], lignes: list[list[str]], *, a_remplir: bool = False) -> str:
    """Un tableau Markdown.

    ``a_remplir`` distingue deux usages qui n'ont pas la même règle pour
    une cellule vide. Dans un tableau de RESTITUTION, une cellule vide
    reçoit un tiret : sans lui la colonne s'effondre et le tableau devient
    illisible une fois exporté. Dans un tableau À REMPLIR par le client, ce
    tiret donnerait un formulaire qui a l'air déjà rempli — de rien. On
    laisse alors la case vide.
    """
    vide = "" if a_remplir else "—"
    rendu = ["| " + " | ".join(entetes) + " |"]
    rendu.append("|" + "|".join(["---"] * len(entetes)) + "|")
    for ligne in lignes:
        cellules = [
            str(cellule).replace("|", "/") if cellule not in (None, "") else vide
            for cellule in ligne
        ]
        rendu.append("| " + " | ".join(cellules) + " |")
    return "\n".join(rendu)


def _entete(titre: str, ctx: dict, document) -> str:
    """L'en-tête commun : qui, quoi, quelle version, à quelle date.

    La ligne de version n'est pas décorative : c'est elle qui permet à un
    dirigeant de savoir laquelle des trois copies qui traînent dans ses
    courriels est la bonne.
    """
    entreprise = ctx["entreprise"]
    return "\n".join(
        [
            f"# {titre}",
            "",
            f"**{entreprise['raison_sociale']}**",
            "",
            _tableau(
                ["", ""],
                [
                    ["Version", f"v{document.version}"],
                    ["Date d'édition", _jour(date.today())],
                    ["Rédigé par", "RSSI as a Service, à partir des données de la plateforme"],
                    ["Validé par", A_COMPLETER],
                    ["Date de validation", A_COMPLETER],
                    ["Prochaine revue", A_COMPLETER],
                ],
            ),
            "",
        ]
    )


def _pied(sources: list[str]) -> str:
    """Ce qui a été rempli automatiquement, et ce qui reste à la charge du
    lecteur. Un document qui ne dit pas d'où il vient se relit mal six mois
    plus tard."""
    lignes = [
        "",
        "---",
        "",
        "## D'où vient ce document",
        "",
        "Il a été composé automatiquement à partir des informations que vous avez "
        "saisies sur la plateforme RSSI as a Service :",
        "",
    ]
    lignes += [f"- {source}" for source in sources]
    lignes += [
        "",
        f"Les passages marqués {A_COMPLETER} n'ont pas pu être remplis : la plateforme "
        "ne les connaît pas. Ils demandent une décision de votre part — les laisser en "
        "l'état reviendrait à publier un document qui affirme ce que personne n'a décidé.",
        "",
        "Ce document est une base de travail, pas un avis juridique. Faites-le relire "
        "avant de l'opposer à un tiers (assureur, donneur d'ordre, autorité).",
    ]
    return "\n".join(lignes)


def _rappel_diagnostic(maturite: dict) -> str:
    """Le bandeau qu'on met en tête d'un document quand aucun diagnostic n'a
    été terminé : le document reste utile, mais il est générique et il faut
    que ce soit dit AVANT que le lecteur s'en aperçoive."""
    if maturite["evalue"]:
        return ""
    return (
        "> **Ce document n'a pas encore été personnalisé.** Aucun diagnostic de maturité "
        "n'a été terminé sur la plateforme : les sections qui devraient refléter votre "
        "situation réelle sont restées génériques. Terminez votre diagnostic, puis "
        "régénérez ce document — il se remplira tout seul.\n"
    )


def _liste_actifs(actifs: list[dict]) -> str:
    if not actifs:
        return (
            f"Aucun actif n'est déclaré sur la plateforme. {A_COMPLETER} : listez ici vos "
            "sites web, noms de domaine, messagerie, outils métier et matériels."
        )
    return _tableau(
        ["Type", "Actif", "Sous surveillance", "Possession"],
        [
            [
                actif["type"],
                actif["valeur"],
                "oui" if actif["actif"] else "non",
                POSSESSION_FR.get(actif["possession"], actif["possession"]),
            ]
            for actif in actifs
        ],
    )


# --- 1. Politique de sécurité du système d'information ----------------------


POLITIQUE_DOMAINES = {
    # Le texte d'engagement écrit une fois, par domaine du guide d'hygiène.
    # Il est repris tel quel ; ce qui change d'un client à l'autre, c'est
    # l'état constaté et la liste des écarts qui suit.
    "Sensibiliser et former": "Toute personne qui utilise nos outils informatiques est "
    "sensibilisée aux risques courants (courriels piégés, mots de passe, clés USB) au moment "
    "de son arrivée, puis au moins une fois par an.",
    "Connaître le système d'information": "Nous tenons à jour la liste de nos outils, de nos "
    "prestataires et de nos accès. Aucun service nouveau n'est mis en production sans être "
    "inscrit à cet inventaire.",
    "Authentifier et contrôler les accès": "Chaque personne dispose d'un compte nominatif. "
    "Les comptes partagés sont proscrits. Les accès d'une personne qui quitte l'entreprise "
    "sont fermés le jour de son départ.",
    "Sécuriser les postes": "Les postes de travail sont tenus à jour, protégés par un antivirus "
    "et verrouillés automatiquement en cas d'absence.",
    "Sécuriser le réseau": "Les accès distants passent par un canal chiffré. Le réseau "
    "sans-fil destiné aux visiteurs est séparé du réseau de l'entreprise.",
    "Sécuriser l'administration": "Les comptes d'administration sont distincts des comptes "
    "courants et ne servent qu'aux opérations qui les exigent.",
    "Gérer le nomadisme": "Les matériels emportés à l'extérieur sont chiffrés. En déplacement, "
    "aucun réseau public n'est utilisé sans protection.",
    "Maintenir le système d'information à jour": "Les mises à jour de sécurité sont appliquées "
    "sans délai déraisonnable, et au plus tard sous un mois.",
    "Superviser, auditer, réagir": "Nous surveillons en continu la disponibilité et la "
    "configuration de nos actifs exposés, et nous traitons les alertes selon la procédure de "
    "gestion des incidents.",
    "Pour aller plus loin": "Nous réexaminons chaque année les mesures avancées que notre "
    "taille et notre activité justifient.",
}


def politique_de_securite(tenant, ctx: dict, document) -> str:
    entreprise = ctx["entreprise"]
    maturite = ctx["maturite"]
    plan = ctx["plan_action"]

    parties = [_entete("Politique de sécurité du système d'information", ctx, document)]
    rappel = _rappel_diagnostic(maturite)
    if rappel:
        parties.append(rappel)

    parties.append(
        "\n".join(
            [
                "## 1. Objet et périmètre",
                "",
                f"Cette politique définit les règles de sécurité informatique applicables au sein "
                f"de **{entreprise['raison_sociale']}**"
                + (
                    f", entreprise du secteur {entreprise['secteur']}"
                    if entreprise["secteur"]
                    else ""
                )
                + (
                    f", qui compte {entreprise['effectif']} personnes."
                    if entreprise["effectif"]
                    else "."
                ),
                "",
                "Elle s'applique à l'ensemble des personnes qui utilisent les moyens informatiques "
                "de l'entreprise : salariés, dirigeants, stagiaires, intérimaires et prestataires.",
                "",
                "Elle couvre les actifs suivants, déclarés sur la plateforme :",
                "",
                _liste_actifs(ctx["actifs"]),
                "",
                "Cet inventaire est celui des actifs **exposés sur internet** que nous "
                f"surveillons. {A_COMPLETER} : complétez-le avec vos outils internes (serveurs, "
                "logiciels métier, sauvegardes, matériels).",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 2. Organisation et responsabilités",
                "",
                _tableau(
                    ["Rôle", "Qui", "Ce qu'il fait"],
                    [
                        [
                            "Direction",
                            _ou(entreprise.get("contact_email")),
                            "Valide cette politique, arbitre les moyens, est informée des "
                            "incidents graves.",
                        ],
                        [
                            "Référent sécurité",
                            A_COMPLETER,
                            "Tient à jour cette politique et le plan d'action, suit les alertes.",
                        ],
                        [
                            "Prestataire informatique",
                            A_COMPLETER,
                            "Met en œuvre les mesures techniques, applique les mises à jour.",
                        ],
                        [
                            "Chaque utilisateur",
                            "l'ensemble du personnel",
                            "Respecte la charte informatique et signale tout incident.",
                        ],
                    ],
                ),
                "",
                "Il n'est pas nécessaire de recruter : dans une entreprise de cette taille, le "
                "référent sécurité est le plus souvent le dirigeant lui-même ou la personne qui "
                "gère déjà l'informatique. Ce qui compte est que la responsabilité soit nommée.",
            ]
        )
    )

    # 3. Engagements par domaine — le cœur personnalisé.
    engagements = ["## 3. Nos engagements, domaine par domaine", ""]
    if maturite["evalue"]:
        engagements.append(
            f"L'état constaté vient du diagnostic « {maturite['referentiel']} » terminé le "
            f"{_jour(maturite['date'])} : **{maturite['score_global']}/100** sur "
            f"{maturite['mesures_examinees']} mesures examinées."
        )
        engagements.append("")
        scores_par_domaine = {d["domain_name"]: d["score"] for d in maturite["par_domaine"]}
        ecarts_par_domaine: dict[str, list] = {}
        for ecart in maturite["ecarts"]:
            ecarts_par_domaine.setdefault(ecart["domaine"], []).append(ecart)
        domaines = list(scores_par_domaine) or list(POLITIQUE_DOMAINES)
    else:
        scores_par_domaine, ecarts_par_domaine = {}, {}
        domaines = list(POLITIQUE_DOMAINES)

    for domaine in domaines:
        engagements.append(f"### {domaine}")
        engagements.append("")
        engagement = POLITIQUE_DOMAINES.get(
            domaine,
            "Nous appliquons les mesures de ce domaine et nous les réexaminons chaque année.",
        )
        engagements.append(f"**Ce que nous nous engageons à faire.** {engagement}")
        engagements.append("")
        score = scores_par_domaine.get(domaine)
        if score is not None:
            engagements.append(f"**Où nous en sommes.** {score}/100 au dernier diagnostic.")
            engagements.append("")
        ecarts = ecarts_par_domaine.get(domaine, [])
        if ecarts:
            engagements.append("**Ce qu'il nous reste à mettre en place :**")
            engagements.append("")
            for ecart in ecarts:
                etat = "partiellement en place" if ecart["partiel"] else "pas en place"
                engagements.append(f"- {ecart['intitule']} — *{etat}*")
            engagements.append("")

    parties.append("\n".join(engagements))

    parties.append(
        "\n".join(
            [
                "## 4. Règles applicables à tous",
                "",
                "Les règles d'usage quotidien (matériel, mots de passe, messagerie, internet, "
                "télétravail) sont détaillées dans la **charte informatique**, annexée à cette "
                "politique et portée à la connaissance de chaque utilisateur.",
                "",
                "Les manquements répétés à ces règles exposent leur auteur aux sanctions prévues "
                "au règlement intérieur.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 5. Gestion des incidents",
                "",
                "Tout incident de sécurité — courriel suspect ouvert, matériel perdu, site "
                "indisponible, compte compromis — est signalé sans délai selon la **procédure de "
                "gestion des incidents**, et consigné au **registre des incidents**.",
                "",
                "La plateforme surveille en continu nos actifs exposés et signale les alertes. "
                "Elle ne voit ni notre réseau interne, ni nos postes de travail : ces incidents-là "
                "remontent par les utilisateurs.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 6. Continuité d'activité",
                "",
                "Les dispositions permettant de poursuivre l'activité en cas de sinistre "
                "informatique sont décrites dans le **plan de continuité simplifié** : "
                "sauvegardes, délais de reprise visés, contacts d'urgence.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 7. Prestataires et sous-traitants",
                "",
                "Tout prestataire ayant accès à nos données ou à nos systèmes :",
                "",
                "- est identifié dans notre inventaire ;",
                "- accède par un compte nominatif, retiré à la fin de la prestation ;",
                "- s'engage contractuellement sur la confidentialité et, s'il traite des données "
                "personnelles pour notre compte, sur les obligations du RGPD ;",
                "- nous informe sans délai de tout incident nous concernant.",
            ]
        )
    )

    suivi = ["## 8. Suivi et révision", ""]
    suivi.append(
        "Cette politique est réexaminée au moins une fois par an, et à chaque changement "
        "important (nouvel outil, nouveau site, incident majeur)."
    )
    suivi.append("")
    if plan:
        suivi.append(
            f"**{len(plan)} action(s)** sont ouvertes à ce jour pour combler les écarts "
            "identifiés. Les plus prioritaires :"
        )
        suivi.append("")
        suivi.append(
            _tableau(
                ["Action", "Domaine", "Échéance", "Responsable"],
                [
                    [
                        ligne["mesure"],
                        ligne["domaine"],
                        _jour(ligne["echeance"]),
                        _ou(ligne["responsable"], "—"),
                    ]
                    for ligne in plan[:10]
                ],
            )
        )
        if len(plan) > 10:
            suivi.append("")
            suivi.append(
                f"*(et {len(plan) - 10} autre(s) — voir le plan d'action sur la plateforme)*"
            )
    else:
        suivi.append(
            "Aucune action n'est ouverte à ce jour. Le plan d'action se remplit tout seul à "
            "la clôture d'un diagnostic."
        )
    parties.append("\n".join(suivi))

    parties.append(
        _pied(
            [
                "la fiche de votre entreprise (raison sociale, secteur, effectif, contact) ;",
                "vos actifs déclarés et leur état de possession ;",
                "les résultats de votre dernier diagnostic de maturité ;",
                "votre plan d'action et ses échéances.",
            ]
        )
    )
    return "\n\n".join(parties)


# --- 2. Procédure de gestion des incidents ----------------------------------


def procedure_incidents(tenant, ctx: dict, document) -> str:
    entreprise = ctx["entreprise"]

    parties = [_entete("Procédure de gestion des incidents de sécurité", ctx, document)]

    parties.append(
        "\n".join(
            [
                "## 1. À quoi sert cette procédure",
                "",
                "Un incident de sécurité se règle mal dans l'improvisation. Cette procédure dit "
                "**qui prévenir, dans quel ordre, et quoi faire dans la première heure**. Elle "
                "tient sur quelques pages, et la fiche réflexe de la dernière section est faite "
                "pour être imprimée et affichée.",
                "",
                "### Qu'est-ce qu'un incident ?",
                "",
                "Tout événement qui met en cause la confidentialité, l'intégrité ou la "
                "disponibilité de nos données et de nos outils. Concrètement, chez nous :",
                "",
                "- un courriel piégé a été ouvert, une pièce jointe exécutée ;",
                "- un mot de passe a été saisi sur un faux site ;",
                "- un ordinateur, un téléphone ou une clé USB a été perdu ou volé ;",
                "- des fichiers sont devenus illisibles, une demande de rançon s'affiche ;",
                "- notre site web est indisponible ou affiche autre chose que d'habitude ;",
                "- un compte de l'entreprise a été retrouvé dans une fuite de données ;",
                "- un virement a été demandé par un dirigeant… qui n'a rien demandé.",
                "",
                "**Dans le doute, on signale.** Une fausse alerte coûte cinq minutes ; un "
                "incident tu pendant trois jours coûte beaucoup plus.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 2. Qui prévenir",
                "",
                _tableau(
                    ["Ordre", "Qui", "Coordonnées", "Dans quels cas"],
                    [
                        [
                            "1",
                            "Référent sécurité interne",
                            A_COMPLETER,
                            "Tous les cas, immédiatement.",
                        ],
                        [
                            "2",
                            "Direction",
                            _ou(entreprise.get("contact_email")),
                            "Dès qu'il y a un doute sur des données, de l'argent ou l'activité.",
                        ],
                        [
                            "3",
                            "Prestataire informatique",
                            A_COMPLETER,
                            "Dès qu'une action technique est nécessaire.",
                        ],
                        [
                            "4",
                            "Assureur (cyber ou multirisque)",
                            A_COMPLETER,
                            "Sinistre potentiel — souvent un délai contractuel de 48 à 72 h.",
                        ],
                    ],
                ),
                "",
                "Ces coordonnées doivent rester joignables **même si l'informatique est à "
                "l'arrêt** : gardez-en une copie papier.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 3. Les six étapes",
                "",
                "**1. Détecter et signaler.** Celui qui constate prévient le référent sécurité, "
                "par téléphone si la messagerie est en cause. Il note l'heure et ce qu'il a vu.",
                "",
                "**2. Qualifier.** Le référent détermine la gravité (section 4), ce qui est "
                "touché, et si des données personnelles sont concernées.",
                "",
                "**3. Contenir.** Empêcher que cela s'étende : débrancher le poste du réseau "
                "(*sans l'éteindre*), changer les mots de passe concernés, suspendre le compte "
                "compromis, bloquer un virement en cours auprès de la banque.",
                "",
                "**4. Éradiquer.** Supprimer la cause : nettoyage ou réinstallation du poste, "
                "fermeture de l'accès utilisé, correction de la faille exploitée.",
                "",
                "**5. Restaurer.** Remettre en service à partir des sauvegardes, puis vérifier "
                "que tout fonctionne avant de rouvrir les accès. Voir le plan de continuité.",
                "",
                "**6. Capitaliser.** Renseigner le registre des incidents, et décider d'au moins "
                "**une** mesure pour que cela ne se reproduise pas. Sans cette étape, le même "
                "incident revient.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 4. Échelle de gravité",
                "",
                _tableau(
                    ["Niveau", "Exemples", "Réaction attendue", "Qui décide"],
                    [
                        [
                            "Faible",
                            "Courriel suspect signalé mais non ouvert ; alerte de configuration.",
                            "Traitement sous 5 jours ouvrés.",
                            "Référent sécurité",
                        ],
                        [
                            "Moyen",
                            "Poste infecté isolé ; compte compromis sans données sensibles ; site "
                            "indisponible quelques heures.",
                            "Traitement le jour même.",
                            "Référent + direction informée",
                        ],
                        [
                            "Élevé",
                            "Rançongiciel ; vol de données ; fraude au virement ; arrêt prolongé "
                            "de l'activité.",
                            "Cellule de crise immédiate, activité prioritaire.",
                            "Direction",
                        ],
                    ],
                ),
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 5. Obligations légales et démarches",
                "",
                "**Données personnelles (RGPD).** Si l'incident touche des données personnelles "
                "(clients, salariés, prospects), l'entreprise dispose de **72 heures à compter de "
                "la prise de connaissance** pour notifier la CNIL, sauf si le risque pour les "
                "personnes est improbable. Cette analyse — et sa conclusion, même négative — se "
                "consigne au registre des incidents. Notification : `notifications.cnil.fr`.",
                "",
                "**Information des personnes concernées.** Si le risque pour elles est élevé, "
                "elles doivent être prévenues directement, en langage clair.",
                "",
                "**Plainte.** Un dépôt de plainte est possible et souvent demandé par l'assureur. "
                "Commissariat, gendarmerie, ou en ligne selon les cas.",
                "",
                "**Assistance gratuite.** `cybermalveillance.gouv.fr` oriente les TPE/PME et met "
                "en relation avec des prestataires référencés.",
                "",
                "**Assurance.** Vérifiez le délai de déclaration prévu à votre contrat : il est "
                "souvent plus court que vous ne le pensez.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 6. Ce que la plateforme détecte, et ce qu'elle ne voit pas",
                "",
                "**Ce qu'elle détecte seule**, et qui arrive dans vos alertes :",
                "",
                "- indisponibilité d'un site déclaré (confirmée par plusieurs contrôles) ;",
                "- certificat de sécurité expiré ou proche de l'expiration ;",
                "- en-têtes de sécurité et configuration de messagerie incomplets ;",
                "- comptes de l'entreprise retrouvés dans des fuites de données.",
                "",
                "**Ce qu'elle ne voit pas**, et qui ne remontera que par vos utilisateurs :",
                "",
                "- tout ce qui se passe sur vos postes de travail et votre réseau interne ;",
                "- un rançongiciel, une clé USB perdue, une erreur de manipulation ;",
                "- une fraude au virement ou une usurpation d'identité par téléphone.",
                "",
                "C'est la raison pour laquelle le signalement humain reste la première étape de "
                "cette procédure.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 7. Fiche réflexe — à imprimer",
                "",
                "**DANS LES DIX PREMIÈRES MINUTES**",
                "",
                "1. Débrancher le câble réseau / couper le Wi-Fi du poste concerné.",
                "2. **Ne pas éteindre le poste** : on perdrait les traces nécessaires à l'analyse.",
                "3. Ne rien supprimer, ne rien « nettoyer » soi-même.",
                "4. Appeler le référent sécurité, puis la direction.",
                "5. Noter l'heure, ce qui a été vu, ce qui a été fait.",
                "",
                "**CE QU'IL NE FAUT PAS FAIRE**",
                "",
                "- Payer une rançon : rien ne garantit la restitution, et cela finance la suite.",
                "- Répondre au courriel suspect ou rappeler le numéro qu'il indique.",
                "- Attendre de « voir si ça se règle tout seul ».",
                "- Prévenir clients ou partenaires avant d'avoir qualifié l'incident.",
                "",
                f"**Contacts** — Référent : {A_COMPLETER} · Direction : "
                f"{_ou(entreprise.get('contact_phone'), A_COMPLETER)} · "
                f"Prestataire : {A_COMPLETER}",
            ]
        )
    )

    parties.append(
        _pied(
            [
                "la fiche de votre entreprise (contacts de direction) ;",
                "les types d'alertes que la plateforme sait produire pour vos actifs.",
            ]
        )
    )
    return "\n\n".join(parties)


# --- 3. Registre des incidents ----------------------------------------------


def registre_incidents(tenant, ctx: dict, document) -> str:
    evenements = ctx["evenements"]

    parties = [_entete("Registre des incidents de sécurité", ctx, document)]

    parties.append(
        "\n".join(
            [
                "## À quoi sert ce registre",
                "",
                "Il consigne les incidents de sécurité survenus dans l'entreprise, ce qui a été "
                "fait et quand. Deux raisons de le tenir :",
                "",
                "- **une obligation** : l'article 33.5 du RGPD impose de documenter *toute* "
                "violation de données personnelles, y compris celles qui n'ont pas été notifiées "
                "à la CNIL — c'est la trace de l'analyse qui est exigée, pas seulement celle de "
                "la notification ;",
                "- **un usage** : c'est le premier document que demandent un assureur, un "
                "donneur d'ordre ou un auditeur, et c'est celui qui permet de voir qu'un même "
                "incident revient.",
                "",
                "Ce registre se conserve au moins cinq ans.",
            ]
        )
    )

    detectes = ["## 1. Événements détectés par la plateforme", ""]
    if evenements:
        detectes.append(
            f"{len(evenements)} événement(s) au {_jour(date.today())}. Ces lignes sont remplies "
            "automatiquement ; les colonnes « Mesures prises » et « Données personnelles » "
            "demandent votre analyse."
        )
        detectes.append("")
        detectes.append(
            _tableau(
                [
                    "Détecté le",
                    "Source",
                    "Nature",
                    "Actif concerné",
                    "Gravité",
                    "Statut",
                    "Clos le",
                    "Données personnelles ?",
                    "Mesures prises",
                ],
                [
                    [
                        _jour(evenement["detecte_le"]),
                        evenement["source"],
                        evenement["nature"],
                        evenement["actif"],
                        evenement["gravite"],
                        evenement["statut"],
                        _jour(evenement["clos_le"]),
                        "à analyser" if evenement["donnees_personnelles"] else "non",
                        "",
                    ]
                    for evenement in evenements
                ],
            )
        )
        detectes.append("")
        detectes.append(
            "> Les comptes retrouvés dans des fuites sont signalés « à analyser » : une adresse "
            "professionnelle est une donnée personnelle, et il faut décider si la fuite constitue "
            "une violation à documenter — voire à notifier. Les identifiants eux-mêmes ne sont "
            "pas reproduits ici : ce document circule, ils restent sur la plateforme."
        )
    else:
        detectes.append(
            "Aucun événement détecté à ce jour. C'est une bonne nouvelle, et cela ne veut pas "
            "dire qu'il ne s'est rien passé : la plateforme ne voit ni vos postes de travail, "
            "ni votre réseau interne. Les incidents constatés en interne s'ajoutent à la main "
            "dans le tableau ci-dessous."
        )
    parties.append("\n".join(detectes))

    parties.append(
        "\n".join(
            [
                "## 2. Incidents constatés en interne",
                "",
                "À remplir à la main. Une ligne par incident, y compris ceux qui se sont révélés "
                "sans conséquence : c'est la trace de l'analyse qui compte.",
                "",
                _tableau(
                    [
                        "N°",
                        "Date et heure",
                        "Découvert par",
                        "Nature",
                        "Systèmes / données touchés",
                        "Gravité",
                        "Données personnelles ?",
                        "CNIL notifiée ?",
                        "Mesures prises",
                        "Clos le",
                    ],
                    [[str(n), "", "", "", "", "", "", "", "", ""] for n in range(1, 6)],
                    a_remplir=True,
                ),
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 3. Comment remplir les colonnes délicates",
                "",
                "**Gravité** — faible / moyenne / élevée, selon l'échelle de la procédure de "
                "gestion des incidents.",
                "",
                "**Données personnelles ?** — Y a-t-il eu accès, perte, altération ou divulgation "
                "de données concernant des personnes identifiables (clients, salariés, "
                "prospects) ? Si oui, l'incident est une *violation de données* au sens du RGPD "
                "et cette ligne doit être documentée même si vous ne notifiez pas.",
                "",
                "**CNIL notifiée ?** — oui (avec la date et le numéro de notification), ou non "
                "**avec le motif** : « risque improbable pour les personnes parce que… ». Un "
                "« non » sans motif est ce qu'un contrôle relèvera.",
                "",
                "**Mesures prises** — ce qui a été fait pour arrêter l'incident, *et* ce qui a "
                "été changé pour qu'il ne revienne pas.",
            ]
        )
    )

    parties.append(
        _pied(
            [
                "les alertes ouvertes sur vos actifs surveillés ;",
                "les fuites de données concernant vos domaines (sans les identifiants eux-mêmes).",
            ]
        )
    )
    return "\n\n".join(parties)


# --- 4. Plan de continuité simplifié ----------------------------------------


def plan_de_continuite(tenant, ctx: dict, document) -> str:
    entreprise = ctx["entreprise"]
    actifs = ctx["actifs"]

    parties = [_entete("Plan de continuité d'activité (version simplifiée)", ctx, document)]

    parties.append(
        "\n".join(
            [
                "## 1. Objet",
                "",
                "Ce plan répond à une seule question : **comment continue-t-on à travailler si "
                "l'informatique s'arrête ?** Il est volontairement court. Un plan de trente pages "
                "que personne ne relit ne sert à rien le jour où il faut l'appliquer.",
                "",
                "Il est à relire une fois par an et après tout incident significatif.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 2. Ce qui doit continuer en priorité",
                "",
                f"{A_COMPLETER} — listez ici vos 3 à 5 activités essentielles, celles dont "
                "l'arrêt coûte immédiatement de l'argent ou de la confiance (par exemple : prendre "
                "les commandes, facturer, payer les salaires, répondre aux clients).",
                "",
                _tableau(
                    [
                        "Activité essentielle",
                        "Ce qu'il lui faut pour fonctionner",
                        "Arrêt tolérable",
                    ],
                    [["", "", ""] for _ in range(4)],
                    a_remplir=True,
                ),
                "",
                "**Les actifs que nous surveillons** et qui soutiennent ces activités :",
                "",
                _liste_actifs(actifs),
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 3. Scénarios et réactions",
                "",
                "### Scénario A — Notre site web ou notre service en ligne est indisponible",
                "",
                "*Dans l'heure* : vérifier s'il s'agit d'une panne de l'hébergeur (page d'état, "
                "support). Prévenir le prestataire. Publier un message sur un autre canal "
                "(téléphone, réseaux sociaux) si des clients sont concernés.",
                "",
                "*Dans la journée* : si la panne dure, activer le mode dégradé — prise de commande "
                "par téléphone ou par courriel.",
                "",
                "### Scénario B — Rançongiciel : nos fichiers sont chiffrés",
                "",
                "*Immédiatement* : isoler les postes touchés du réseau **sans les éteindre**. "
                "Couper l'accès aux sauvegardes pour ne pas les contaminer. Appeler le prestataire "
                "et l'assureur. **Ne pas payer.**",
                "",
                "*Ensuite* : reconstruire à partir des sauvegardes, sur des machines saines. "
                "Déposer plainte. Analyser l'origine avant de rouvrir les accès.",
                "",
                "### Scénario C — Perte des locaux ou du matériel (incendie, dégât des eaux, vol)",
                "",
                f"*Immédiatement* : {A_COMPLETER} — indiquez le lieu de repli (autre site, "
                "domicile, espace de travail partagé) et les moyens de reprise (ordinateurs de "
                "secours, accès distants).",
                "",
                "*Condition de réussite* : que les données soient accessibles depuis ailleurs. "
                "C'est ce que garantit la sauvegarde hors site (section 4).",
                "",
                "### Scénario D — Un prestataire clé est indisponible",
                "",
                f"{A_COMPLETER} — pour chacun de vos prestataires critiques (informatique, "
                "hébergeur, comptabilité, banque), notez qui appeler à défaut et quelle solution "
                "de repli existe.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 4. Sauvegardes",
                "",
                "Sans sauvegarde vérifiée, aucun plan de continuité ne tient. La règle **3-2-1** :",
                "",
                "- **3** copies de vos données ;",
                "- sur **2** supports différents ;",
                "- dont **1** hors des locaux, déconnectée du réseau (un rançongiciel chiffre "
                "aussi les sauvegardes qu'il peut atteindre).",
                "",
                _tableau(
                    ["Quoi", "Réponse"],
                    [
                        ["Ce qui est sauvegardé", A_COMPLETER],
                        ["Où", A_COMPLETER],
                        ["À quelle fréquence", A_COMPLETER],
                        ["Qui vérifie que la sauvegarde a bien tourné", A_COMPLETER],
                        ["Date de la dernière **restauration testée**", A_COMPLETER],
                    ],
                ),
                "",
                "> Une sauvegarde jamais restaurée n'est pas une sauvegarde : c'est une "
                "hypothèse. Testez une restauration au moins une fois par an, et notez la date "
                "ci-dessus.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 5. Délais visés",
                "",
                "Deux chiffres à décider, en français simple :",
                "",
                "- **Combien de temps pouvons-nous rester à l'arrêt ?** (délai de reprise)",
                "- **Combien de travail pouvons-nous nous permettre de perdre ?** (par exemple "
                "« une journée de saisie », ce qui impose une sauvegarde quotidienne)",
                "",
                _tableau(
                    ["Activité", "Arrêt maximal acceptable", "Perte de données acceptable"],
                    [["", "", ""] for _ in range(4)],
                    a_remplir=True,
                ),
                "",
                "Ces deux réponses commandent tout le reste : la fréquence des sauvegardes, le "
                "besoin ou non d'un matériel de secours, le niveau de service à exiger du "
                "prestataire.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 6. Contacts d'urgence",
                "",
                _tableau(
                    ["Rôle", "Nom", "Téléphone", "À contacter pour"],
                    [
                        [
                            "Direction",
                            A_COMPLETER,
                            _ou(entreprise.get("contact_phone")),
                            "Décision d'activer ce plan",
                        ],
                        ["Référent sécurité", A_COMPLETER, A_COMPLETER, "Coordination"],
                        ["Prestataire informatique", A_COMPLETER, A_COMPLETER, "Remise en service"],
                        ["Hébergeur", A_COMPLETER, A_COMPLETER, "Site et messagerie"],
                        ["Assureur", A_COMPLETER, A_COMPLETER, "Déclaration de sinistre"],
                        ["Banque", A_COMPLETER, A_COMPLETER, "Blocage d'un virement frauduleux"],
                    ],
                ),
                "",
                "**Gardez une copie papier de cette page.** Le jour où vous en aurez besoin, "
                "elle ne sera peut-être pas accessible sur un écran.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## 7. Test annuel",
                "",
                "Une fois par an, consacrez une heure à jouer un scénario « sur table » : on "
                "annonce la panne, chacun dit ce qu'il ferait, on note ce qui manque. C'est court, "
                "et c'est ce qui transforme ce document en réflexe.",
                "",
                _tableau(
                    ["Date du test", "Scénario joué", "Ce qui a manqué", "Corrigé le"],
                    [["", "", "", ""] for _ in range(3)],
                    a_remplir=True,
                ),
            ]
        )
    )

    parties.append(
        _pied(
            [
                "la fiche de votre entreprise ;",
                "vos actifs déclarés et surveillés.",
            ]
        )
    )
    return "\n\n".join(parties)


# --- 5. Fiche de sensibilisation --------------------------------------------


def fiche_sensibilisation(tenant, ctx: dict, document) -> str:
    entreprise = ctx["entreprise"]
    maturite = ctx["maturite"]
    evenements = ctx["evenements"]

    parties = [_entete("Sécurité informatique : l'essentiel en une page", ctx, document)]

    parties.append(
        "\n".join(
            [
                "## Pourquoi cette fiche vous concerne",
                "",
                f"La sécurité informatique de **{entreprise['raison_sociale']}** ne repose pas "
                "sur un logiciel : elle repose sur ce que chacun fait au quotidien. La quasi-"
                "totalité des attaques qui touchent les entreprises de notre taille commencent "
                "par un geste banal — un courriel ouvert, un mot de passe réutilisé.",
                "",
                "Cinq minutes de lecture. Rien de technique.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## Les cinq réflexes",
                "",
                "**1. Un mot de passe long, et différent partout.** Une phrase que vous êtes seul "
                "à connaître vaut mieux qu'un mot compliqué. Le même mot de passe partout, c'est "
                "une seule fuite pour tout perdre.",
                "",
                "**2. La double authentification, dès qu'elle est proposée.** Messagerie, banque, "
                "outils métier : un code reçu en plus du mot de passe bloque l'immense majorité "
                "des tentatives.",
                "",
                "**3. Vérifier avant de cliquer.** Un lien inattendu, une pièce jointe non "
                "annoncée, une urgence inhabituelle : on s'arrête. En cas de doute, on appelle "
                "l'expéditeur sur son numéro habituel — jamais celui indiqué dans le message.",
                "",
                "**4. Les mises à jour, sans les repousser.** « Rappeler plus tard » trois "
                "semaines de suite laisse ouverte une porte que l'éditeur a déjà refermée.",
                "",
                "**5. Signaler, même en cas de doute.** Personne n'est puni pour avoir signalé "
                "une erreur. Ce qui coûte cher, c'est le silence.",
            ]
        )
    )

    parties.append(
        "\n".join(
            [
                "## Reconnaître un courriel piégé",
                "",
                "- Il crée une **urgence** : facture impayée, compte bloqué, dernier "
                "avertissement.",
                "- Il demande une **action inhabituelle** : virement, changement de RIB, saisie "
                "de mot de passe.",
                "- L'**adresse de l'expéditeur** ressemble à une adresse connue… à une lettre "
                "près.",
                "- Le lien ne mène pas où il prétend : posez le curseur dessus sans cliquer, "
                "l'adresse réelle s'affiche.",
                "- Le ton ou la langue détonnent par rapport aux échanges habituels.",
                "",
                "**Le cas le plus coûteux pour une PME** : un message qui semble venir du "
                "dirigeant et demande un virement urgent et confidentiel. La règle est simple et "
                "sans exception : **aucun virement inhabituel sans un appel de vérification** sur "
                "un numéro déjà connu.",
            ]
        )
    )

    chez_nous = ["## Ce qu'on observe chez nous", ""]
    if maturite["evalue"]:
        chez_nous.append(
            f"Notre dernier diagnostic ({_jour(maturite['date'])}) nous situe à "
            f"**{maturite['score_global']}/100**."
        )
        # Les écarts à fort impact et faible effort : ceux sur lesquels un
        # utilisateur peut réellement agir dans sa semaine.
        prioritaires = [
            ecart
            for ecart in maturite["ecarts"]
            if ecart["impact"] == "high" and ecart["effort"] in ("low", "medium")
        ][:3]
        if prioritaires:
            chez_nous.append("")
            chez_nous.append("Nos trois points d'attention du moment :")
            chez_nous.append("")
            for ecart in prioritaires:
                chez_nous.append(f"- {ecart['enonce']}")
    else:
        chez_nous.append(
            "Notre diagnostic de maturité n'est pas encore terminé : cette section se remplira "
            "avec nos points d'attention réels dès qu'il le sera."
        )

    fuites = [e for e in evenements if e["source"] == "Renseignement sur la menace"]
    if fuites:
        chez_nous.append("")
        chez_nous.append(
            f"**{len(fuites)} compte(s)** liés à nos domaines ont été retrouvés dans des fuites de "
            "données publiques. Aucun nom n'est cité ici. Si le vôtre en fait partie, vous en "
            "serez informé individuellement — et la seule action utile est de changer le mot de "
            "passe concerné **partout où vous l'avez réutilisé**."
        )
    parties.append("\n".join(chez_nous))

    parties.append(
        "\n".join(
            [
                "## En cas de doute, ou d'erreur",
                "",
                "Vous avez cliqué, saisi un mot de passe, ou vous n'êtes pas sûr :",
                "",
                "1. **Débranchez le réseau** (câble ou Wi-Fi), sans éteindre l'ordinateur.",
                f"2. **Prévenez** : {A_COMPLETER} (référent sécurité) — "
                f"{_ou(entreprise.get('contact_email'))} (direction).",
                "3. **Ne supprimez rien** : les traces servent à comprendre ce qui s'est passé.",
                "",
                "Signaler tôt transforme un incident grave en incident sans suite.",
            ]
        )
    )

    parties.append(
        _pied(
            [
                "la fiche de votre entreprise ;",
                "les points faibles issus de votre dernier diagnostic ;",
                "le nombre de comptes de vos domaines retrouvés dans des fuites (sans les nommer).",
            ]
        )
    )
    return "\n\n".join(parties)


# --- 6. Rapport de comité de sécurité ---------------------------------------


def rapport_comite(tenant, ctx: dict, document) -> str:
    """Le rapport de comité, archivé comme document versionné.

    Il ne recalcule rien : il reprend exactement ce que produit
    ``apps.reporting`` (V2-3, ADR-028), déjà déterministe et déjà testé. Deux
    calculs du même chiffre finiraient par diverger, et le jour où le PDF de
    la page et le document archivé ne diraient pas la même chose, aucun des
    deux ne serait défendable.
    """
    from apps.reporting import periods
    from apps.reporting import services as reporting_services

    # Le trimestre, période par défaut d'un comité de sécurité. La page de
    # restitution laisse choisir ; ici on ARCHIVE, et un document archivé doit
    # couvrir une période nommée que le lecteur retrouvera sur la page.
    periode = periods.resolve(periods.PRESET_QUARTER)
    donnees = reporting_services.build_report(tenant, periode)

    exposition = donnees["exposure"]
    maturite = donnees["maturity"]
    plan = donnees["action_plan"]
    surveillance = donnees["monitoring"]

    parties = [_entete("Rapport de comité de sécurité", ctx, document)]
    parties.append(
        f"**Période couverte : {donnees['period']['label']}** "
        f"(du {_jour(donnees['period']['start'])} au {_jour(donnees['period']['end'])})"
    )

    faits = ["## 1. Ce qu'il faut retenir", ""]
    if donnees["highlights"]:
        faits += [f"- **{fait['title']}** — {fait['detail']}" for fait in donnees["highlights"]]
    else:
        faits.append("- Aucun fait marquant sur la période.")
    parties.append("\n".join(faits))

    parties.append(
        "\n".join(
            [
                "## 2. Les chiffres",
                "",
                _tableau(
                    ["Indicateur", "Valeur", "Ce que cela veut dire"],
                    [
                        [
                            "Maturité",
                            _ou(maturite["score"], "non évaluée"),
                            "Ce que l'entreprise a mis en place, sur 100.",
                        ],
                        [
                            "Exposition",
                            _ou(exposition["exposure_score"], "—"),
                            "Ce qui circule à propos de l'entreprise. Plus bas est mieux.",
                        ],
                        [
                            "Fuites ouvertes",
                            exposition["open_total"],
                            "Comptes exposés non encore traités.",
                        ],
                        [
                            "Actions ouvertes",
                            plan["open"],
                            f"dont {plan['overdue']} en retard.",
                        ],
                        [
                            "Actions terminées sur la période",
                            plan["completed_in_period"],
                            "Ce qui a effectivement avancé.",
                        ],
                        [
                            "Disponibilité",
                            _ou(surveillance["uptime_percentage"], "—"),
                            "Part du temps où les sites surveillés ont répondu.",
                        ],
                    ],
                ),
                "",
                "> Maturité et exposition ne se moyennent pas : elles mesurent deux choses sans "
                "rapport, l'organisation d'un côté, ce qui circule de l'autre.",
            ]
        )
    )

    reste = ["## 3. Ce qui reste à faire", ""]
    if donnees["remaining"]:
        reste += [f"- **{ligne['title']}** — {ligne['detail']}" for ligne in donnees["remaining"]]
    else:
        reste.append("- Rien de bloquant n'a été identifié sur la période.")
    parties.append("\n".join(reste))

    parties.append(
        "\n".join(
            [
                "## 4. Décisions du comité",
                "",
                f"{A_COMPLETER} — consignez ici les décisions prises en séance, leur porteur et "
                "leur échéance. C'est la partie du rapport qu'aucune plateforme ne peut écrire à "
                "votre place, et c'est celle qu'on relit au comité suivant.",
                "",
                _tableau(
                    ["Décision", "Porteur", "Échéance"],
                    [["", "", ""] for _ in range(4)],
                    a_remplir=True,
                ),
            ]
        )
    )

    parties.append(
        _pied(
            [
                "les indicateurs de la période, calculés par la plateforme (ADR-028) ;",
                "votre plan d'action, vos alertes de surveillance et vos fuites détectées.",
            ]
        )
    )
    return "\n\n".join(parties)
