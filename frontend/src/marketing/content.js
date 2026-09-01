/**
 * Contenu du site vitrine, centralisé.
 *
 * Un seul fichier plutôt que du texte dispersé dans les composants, pour deux
 * raisons : la relecture éditoriale se fait d'un coup d'œil, et l'ajout d'une
 * langue plus tard consistera à dupliquer cet objet plutôt qu'à parcourir
 * l'arborescence. L'i18n n'est PAS implémentée ici (aucune dépendance
 * ajoutée) : la structure y est simplement prête.
 *
 * RÈGLE DE RÉDACTION : chaque affirmation de ce fichier doit correspondre à
 * une fonctionnalité qui existe réellement dans le code. Les formulations ont
 * été vérifiées une par une contre l'implémentation :
 *   - neuf sources de renseignement, pas dix (la dixième valeur de
 *     l'énumération, « webhook », est un canal de livraison, pas une source —
 *     voir providers/breachsense/client.py:QUERY_ENDPOINTS) ;
 *   - la révélation exige une NOUVELLE vérification d'identité (mot de passe
 *     OU code à usage unique), ce qui n'est pas la même chose que « sous
 *     double authentification » : la 2FA est proposée, pas imposée ;
 *   - la vérification DNS porte sur SPF et DMARC ; DKIM est hors périmètre
 *     (son sélecteur n'est pas découvrable) ;
 *   - le produit détecte et alerte, il ne bloque rien ;
 *   - l'envoi immédiat couvre les échecs de surveillance et les signaux
 *     avant-coureurs ; une fuite AVÉRÉE ouvre une alerte dans l'interface et
 *     part dans la météo du lendemain, pas dans un email immédiat
 *     (`ingest_raw_findings` n'en déclenche aucun) — d'où la formulation de
 *     NOTIFICATIONS, qui ne promet pas « l'email dans la minute » ;
 *   - les emails partent aux ADMINISTRATEURS de l'espace, pas à toute
 *     l'équipe (`notifications.services.list_recipient_emails`) ;
 *   - « jusqu'à N analyses par mois » est un plafond, pas une périodicité :
 *     aucune tâche périodique de scan n'existe (`config/celery.py`).
 *
 * La grille tarifaire, elle, n'est plus écrite ici : elle vient de l'API
 * (`/api/v1/billing/plans/`), et le bloc PRICING n'en est que le repli.
 */

export const SITE = {
  name: 'RSSI as a Service',
  tagline: 'Surveillance des fuites de données et de la conformité pour les PME',
  contactEmail: 'contact@rssiasservice.online',
}

export const NAV = [
  { label: 'Le produit', href: '#produit' },
  { label: 'Diagnostic', href: '#diagnostic' },
  { label: 'Alertes', href: '#alertes' },
  { label: 'Fonctionnement', href: '#fonctionnement' },
  { label: 'Sécurité', href: '#securite' },
  { label: 'Tarifs', href: '#tarifs' },
  { label: 'Questions', href: '#questions' },
]

export const HERO = {
  title: 'Vous saurez que vos identifiants ont fuité avant vos clients.',
  subtitle:
    "Nous surveillons en continu neuf sources de renseignement sur les fuites de données, et nous vous prévenons en langage clair, avec l'action à mener.",
  primaryCta: 'Demander une démonstration',
  secondaryCta: 'Se connecter',
  note: 'Aucune installation. Aucun agent à déployer sur vos postes.',
}

export const PROBLEM = {
  title: 'Ce qui se passe pendant que vous travaillez',
  items: [
    {
      title: 'Les identifiants de vos équipes circulent',
      body: "Mots de passe, jetons d'accès et cookies de session récupérés lors de fuites chez des tiers s'échangent sur des marchés parallèles, parfois des années après.",
    },
    {
      title: 'Personne ne surveille cela chez vous',
      body: "Votre prestataire informatique maintient votre parc. Surveiller ce qui se dit et se vend à l'extérieur de l'entreprise est un autre métier, et un travail quotidien.",
    },
    {
      title: "On l'apprend le plus souvent par l'incident",
      body: "Une facture réglée sur un mauvais compte, une boîte email consultée par un tiers : le signal d'alerte arrive quand le dommage est déjà là.",
    },
  ],
}

export const DIFFERENTIATORS = {
  title: 'Quatre choses que nous faisons différemment',
  items: [
    {
      id: 'signaux',
      eyebrow: 'Signaux avant-coureurs',
      title: 'Détecter ce qui se prépare, pas seulement ce qui a fui',
      body: "Le dépôt d'un nom de domaine ressemblant au vôtre est le préparatif classique d'un faux email demandant un virement. Nous repérons ces signaux, ainsi que les mentions de votre entreprise sur des espaces fréquentés par des attaquants, et nous vous les présentons séparément des fuites avérées.",
      detail: "Un signal n'est pas un incident : le ton et l'action recommandée sont différents.",
    },
    {
      id: 'traduction',
      eyebrow: 'Traduction en langage de direction',
      title: 'Chaque alerte dit ce que cela signifie et quoi faire',
      body: "Pas de terme technique laissé sans explication. Chaque élément détecté s'accompagne d'une phrase compréhensible et d'une action concrète.",
      example: {
        label: 'Exemple réel affiché dans le produit',
        meaning:
          "Un cookie de session a été volé : c'est le jeton que votre navigateur garde après une connexion réussie, pour ne pas redemander le mot de passe à chaque page. Avec ce jeton, un attaquant entre dans le compte sans avoir besoin du mot de passe ni du code de double authentification.",
        action:
          "Déconnectez toutes les sessions actives de ce compte, puis changez le mot de passe.",
      },
    },
    {
      id: 'reutilisation',
      eyebrow: 'Réutilisation possible de mots de passe',
      title: 'Relier une fuite externe à vos accès professionnels',
      body: "Quand une adresse professionnelle de votre entreprise apparaît dans la fuite d'un service qui n'est pas le vôtre, ou quand le même identifiant revient dans plusieurs fuites, nous le signalons comme une hypothèse à vérifier.",
      detail:
        "Nous ne testons aucun identifiant nulle part : nous écrivons donc « réutilisation possible », jamais « confirmée ». Pour lever le doute, un administrateur peut consulter la valeur exacte du mot de passe fuité, après une nouvelle vérification de son identité. Chaque consultation est tracée.",
    },
    {
      // Vérifié contre ai_assistant/prompts.py et services.py : l'assistant
      // répond À PARTIR du contexte du client (scores, écarts, alertes,
      // compromissions ouvertes), et non d'une culture générale ; le prompt
      // lui impose de renvoyer vers un professionnel qualifié sur le droit et
      // la réponse à incident. La pseudonymisation est un pipeline obligatoire
      // (ADR-005), pas une option : c'est pour cela qu'elle est ici.
      id: 'assistant',
      eyebrow: 'Assistant',
      title: 'Poser une question sur VOTRE situation, pas sur la sécurité en général',
      body: "« Que dois-je faire en premier ? », « Ce compte est-il vraiment un risque ? » : l'assistant répond à partir de vos propres données — votre score, vos écarts, vos alertes ouvertes, les fuites qui vous concernent. Les réponses sont courtes, en français courant, et se terminent par ce qu'il y a à faire.",
      detail:
        "Il vous renvoie vers un professionnel qualifié dès qu'une question sort de son périmètre : le droit, un contentieux, un incident en cours. Et avant chaque envoi, les noms, adresses et domaines sont remplacés par des identifiants neutres, puis rétablis à la réception — le service d'intelligence artificielle ne voit jamais le nom de votre entreprise.",
    },
  ],
}

/**
 * Ce qui arrive dans la boîte email, sans ouvrir le produit.
 *
 * Vérifié ligne à ligne contre `apps/notifications` avant rédaction, et deux
 * formulations ont dû être corrigées à cette occasion :
 *
 *  1. Le canal est l'EMAIL, uniquement. Pas de SMS, pas de messagerie
 *     d'équipe, pas d'astreinte : `EmailLog.Kind` ne connaît que trois envois
 *     (météo, alerte temps réel, signal avant-coureur) et tous passent par
 *     `EmailMultiAlternatives`.
 *  2. L'envoi immédiat couvre les ÉCHECS DE SURVEILLANCE
 *     (`monitoring/tasks.py` → `send_realtime_alert_email`) et les SIGNAUX
 *     avant-coureurs reçus par webhook (`_notify_pre_incident_signals`).
 *     Une fuite avérée, elle, ouvre une alerte dans l'interface et part dans
 *     la météo du lendemain matin : `ingest_raw_findings` ne déclenche aucun
 *     email immédiat. On écrit donc « le lendemain matin », pas « en temps
 *     réel » — voir docs/journal.md, écart relevé le 01/09/2026.
 *
 * Les destinataires sont les ADMINISTRATEURS de l'espace
 * (`list_recipient_emails` filtre sur `Membership.Role.ADMIN`), pas tous les
 * utilisateurs : c'est écrit tel quel plus bas.
 */
export const NOTIFICATIONS = {
  title: 'Ce que vous recevez sans vous connecter',
  subtitle:
    "Un dirigeant n'ouvre pas un outil de sécurité tous les matins. Il ouvre ses emails. Le produit est fait pour venir à vous, pas pour attendre votre visite.",
  items: [
    {
      title: 'La météo cyber, chaque matin',
      body: "Un email quotidien, à l'heure que vous choisissez : l'état de vos actifs, les alertes encore ouvertes et ce qui a bougé depuis la veille. Il part tous les jours, y compris quand tout va bien — savoir que rien n'a changé fait partie de l'information.",
      detail: "Une seule météo par jour et par espace, même si l'envoi est relancé.",
    },
    {
      title: "Une alerte dès qu'un contrôle échoue",
      body: "Site injoignable, certificat qui approche de l'expiration, configuration email affaiblie : l'email part sans attendre la météo du lendemain. Une panne passagère ne déclenche rien — un site n'est déclaré indisponible qu'après trois échecs consécutifs.",
    },
    {
      title: 'Un signal quand votre exposition publique change',
      body: "Le dépôt d'un nom de domaine ressemblant au vôtre, ou une mention de votre entreprise sur un espace fréquenté par des attaquants, vous est signalé au moment où il apparaît. Le message est volontairement plus calme que celui d'une alerte : rien n'a fuité, quelque chose se prépare peut-être.",
    },
    {
      title: 'Vous réglez ce que vous recevez',
      body: "L'heure de la météo, sa désactivation, celle des alertes immédiates : tout se change depuis vos préférences. Ces emails partent aux administrateurs de l'espace, pas à toute votre équipe.",
    },
  ],
}

/**
 * Le diagnostic, présenté comme le produit d'entrée qu'il est.
 *
 * Chiffres vérifiés : `load_anssi_referential` charge 10 domaines et
 * 42 mesures (« Guide d'hygiène informatique », ANSSI). Le plan d'action est
 * généré depuis le diagnostic (`actions.services.generate_action_plan`), et la
 * charte comme l'export PDF existent bien (`ai_assistant/urls.py` :
 * `documents/`, `documents/<id>/export/pdf/`).
 *
 * NE PAS ÉCRIRE que le diagnostic « met en conformité » : la FAQ répond déjà
 * l'inverse, et c'est la bonne réponse.
 */
export const DIAGNOSTIC = {
  title: 'Savoir par où commencer',
  subtitle:
    "La question d'une PME n'est presque jamais « que se passe-t-il ? », c'est « par quoi je commence ? ». Le diagnostic répond à celle-là.",
  steps: [
    {
      title: 'Un questionnaire sur un référentiel public',
      body: "Les 42 mesures du guide d'hygiène informatique de l'ANSSI, réparties en 10 domaines. Un référentiel public et reconnu, que vous pouvez consulter par vous-même — nous n'inventons pas notre propre grille de notation.",
    },
    {
      title: 'Un score, et le détail de son calcul',
      body: "Une note globale et une note par domaine, avec les mesures qui les composent. Vous voyez où vous êtes solide et où vous ne l'êtes pas, sans avoir à interpréter un graphique.",
    },
    {
      title: 'Un plan d’action priorisé',
      body: "Le diagnostic produit directement les actions à mener, classées par priorité, que vous suivez dans un tableau : à faire, en cours, fait. Le but est qu'une PME sans équipe sécurité sache quoi faire lundi matin.",
    },
    {
      title: 'Les documents qui vont avec',
      body: "Une charte informatique adaptée à votre entreprise, rédigée à partir de ce que vous avez déclaré, à relire et à valider avant diffusion. Vos documents validés s'exportent en PDF, prêts à circuler.",
    },
  ],
  note: "Le diagnostic vous aide à progresser ; il ne vous certifie pas. Ce que vous mettez réellement en œuvre reste votre décision.",
}

export const HOW_IT_WORKS = {
  title: 'Comment cela fonctionne',
  subtitle: "Quatre étapes. Rien à installer, rien à configurer sur vos postes.",
  steps: [
    {
      number: 1,
      title: 'Vous déclarez vos actifs',
      body: "Vos noms de domaine, sites et domaines de messagerie. Vous confirmez que vous en êtes propriétaire — nous n'analysons rien que vous n'ayez déclaré.",
    },
    {
      number: 2,
      title: 'Nous interrogeons neuf sources',
      body: "Logs de logiciels voleurs d'identifiants, listes de couples adresse/mot de passe, identifiants exposés, sessions compromises, clés techniques, mentions sur des espaces malveillants, documents fuités, surface d'exposition publique, veille.",
    },
    {
      number: 3,
      title: 'Vous recevez une alerte compréhensible',
      body: "Par email et dans votre espace : ce qui a été trouvé, ce que cela signifie, et l'action à mener. Pas de tableau de bord à déchiffrer.",
    },
    {
      number: 4,
      title: 'Vous suivez votre exposition dans le temps',
      body: "Un score par actif, calculé selon des règles fixes et dont le détail est affiché. Traiter une alerte le fait baisser.",
    },
  ],
}

export const TRUST = {
  title: 'Vos données, et ce que nous en faisons',
  subtitle:
    "Vous nous confiez des informations sur vos vulnérabilités. Voici comment elles sont traitées.",
  items: [
    {
      title: 'Cloisonnement entre clients',
      body: "Chaque espace client est isolé. L'isolation est appliquée à trois niveaux indépendants, et par défaut aucune donnée n'est renvoyée si le contexte client n'est pas résolu — le système échoue en refusant, pas en montrant.",
    },
    {
      title: 'Mots de passe fuités chiffrés',
      body: "Un mot de passe retrouvé dans une fuite est chiffré dès sa réception et n'est jamais lisible par défaut : l'interface n'affiche qu'une forme masquée.",
    },
    {
      title: 'Consultation encadrée et tracée',
      body: "En consulter la valeur exacte exige d'être administrateur de l'espace et de re-prouver son identité à ce moment précis, par mot de passe ou code à usage unique. Chaque tentative, acceptée ou refusée, est enregistrée avec son auteur, sa date et son adresse.",
    },
    {
      title: 'Effacement automatique',
      body: "Les valeurs de mots de passe sont effacées automatiquement au bout de 90 jours. L'historique de la fuite est conservé, la valeur récupérable disparaît.",
    },
    {
      title: 'Pseudonymisation avant analyse externe',
      body: "Le produit utilise un service d'intelligence artificielle pour rédiger des synthèses. Les noms, adresses email et noms de domaine sont remplacés par des identifiants neutres avant l'envoi, puis rétablis à la réception. Aucun mot de passe n'est jamais transmis, même chiffré.",
    },
    {
      title: 'Authentification renforcée disponible',
      body: "La double authentification par application mobile peut être activée sur chaque compte, avec des codes de récupération à usage unique. Les accès sensibles sont journalisés.",
    },
  ],
}

// Montants INDICATIFS, centralisés pour être modifiables en un seul endroit.
// La tarification n'est pas arrêtée : ces valeurs servent à situer un ordre de
// grandeur en démonstration, pas à engager.
//
// CE BLOC EST UN REPLI, PAS LA SOURCE. La grille affichée vient de
// `GET /api/v1/billing/plans/` (catalogue publié, ADR-019) : modifier une
// offre depuis l'administration doit se voir sans redéploiement. Ces objets ne
// servent que si l'API ne répond pas — une grille vide serait pire qu'une
// grille légèrement datée, et c'est la première chose qu'un prospect regarde.
//
// DEUX RÈGLES, tenues par un test :
//  1. la forme est CELLE DE L'API (`billing.serializers.PublicPlanSerializer`),
//     pas une forme maison. Le repli avait sa propre forme (`id`, `price`,
//     `pitch`, puces en texte libre), le composant devait la traduire, et
//     c'est dans cette traduction que la divergence est passée inaperçue :
//     il annonçait Essentiel/Standard/Étendu à 49/149/349 quand la base porte
//     Veille/Pilotage/Souverain à 89/249/sur devis ;
//  2. codes, noms, prix et quotas recopient la base
//     (`billing/migrations/0002_initial_plans.py`).
//     `billing/tests/test_vitrine_plan_consistency.py` échoue si l'un des
//     deux bouge sans l'autre.
//
// Les quotas ne sont PAS écrits à la main dans les puces : `quotaLines()` les
// dérive des champs de l'offre. Un nombre recopié à la main est exactement ce
// qui avait produit « 30 actifs surveillés » — alors que le pool de
// surveillance continue de TOUTE la plateforme est de 15 (ADR-013).
export const PRICING = {
  title: 'Offres',
  subtitle:
    "Montants indicatifs, hors taxes, par mois. La tarification définitive est établie au moment du devis.",
  disclaimer:
    "Ces montants sont donnés à titre indicatif pour situer un ordre de grandeur. Ils ne constituent pas une offre commerciale.",
  currency: '€',
  quoteLabel: 'Sur devis',
  plans: [
    {
      code: 'veille',
      name: 'Veille',
      tagline: 'Savoir ce qui circule sur votre entreprise.',
      price_monthly: 89,
      is_quote_only: false,
      is_highlighted: false,
      monitored_assets: 1,
      monthly_scans: 20,
      max_users: 3,
      features: [{ key: 'realtime_monitoring', label: 'Surveillance en temps réel' }],
    },
    {
      code: 'pilotage',
      name: 'Pilotage',
      tagline: 'Comprendre, prioriser et agir.',
      price_monthly: 249,
      is_quote_only: false,
      is_highlighted: true,
      monitored_assets: 3,
      monthly_scans: 60,
      max_users: 10,
      features: [
        { key: 'assistant', label: 'Assistant conversationnel' },
        { key: 'exposure_synthesis', label: "Synthèse d'exposition" },
        { key: 'pdf_export', label: 'Export PDF des documents' },
        { key: 'reuse_correlation', label: 'Corrélation de réutilisation' },
        { key: 'secret_reveal', label: 'Révélation de mot de passe' },
        { key: 'anssi_assessment', label: 'Diagnostic de maturité' },
        { key: 'charter_generation', label: 'Génération de charte informatique' },
        { key: 'realtime_monitoring', label: 'Surveillance en temps réel' },
      ],
    },
    {
      code: 'souverain',
      name: 'Souverain',
      tagline: 'Sur mesure, pour les structures aux contraintes particulières.',
      price_monthly: 0,
      is_quote_only: true,
      is_highlighted: false,
      monitored_assets: 5,
      monthly_scans: 120,
      max_users: 0, // 0 = illimité (Plan.UNLIMITED)
      features: [
        { key: 'assistant', label: 'Assistant conversationnel' },
        { key: 'exposure_synthesis', label: "Synthèse d'exposition" },
        { key: 'pdf_export', label: 'Export PDF des documents' },
        { key: 'reuse_correlation', label: 'Corrélation de réutilisation' },
        { key: 'secret_reveal', label: 'Révélation de mot de passe' },
        { key: 'anssi_assessment', label: 'Diagnostic de maturité' },
        { key: 'charter_generation', label: 'Génération de charte informatique' },
        { key: 'realtime_monitoring', label: 'Surveillance en temps réel' },
      ],
    },
  ],
}

/**
 * Les trois quotas d'une offre, rendus en puces à partir de ses champs —
 * jamais recopiés à la main, que l'offre vienne de l'API ou du repli.
 *
 * Chaque formulation est tenue au cordeau, et pour une raison :
 *
 * — « actif en surveillance continue », pas « actifs surveillés ». Le nombre
 *   compte les emplacements de la licence, pris sur un pool de 15 PARTAGÉ par
 *   toute la plateforme (ADR-013). La garde de capacité
 *   (`billing/capacity.py`) refuse toute activation qui ferait dépasser ce
 *   pool : le chiffre affiché est donc un engagement que la plateforme sait
 *   honorer. Un actif peut par ailleurs être déclaré et vérifié
 *   (disponibilité, certificat, en-têtes, SPF/DMARC) sans occuper
 *   d'emplacement — d'où une formule qui nomme la ressource rare au lieu de
 *   laisser croire à un plafond du nombre d'actifs.
 *
 * — « Jusqu'à N analyses par mois », pas « analyse hebdomadaire ». Le champ
 *   est un PLAFOND mensuel, pas une périodicité : aucune tâche périodique de
 *   scan n'existe (`config/celery.py`). Une analyse part à la déclaration
 *   d'un actif, puis à la demande.
 */
export function quotaLines(plan) {
  const assets = Number(plan.monitored_assets) || 0
  const scans = Number(plan.monthly_scans) || 0
  const users = Number(plan.max_users) || 0

  const lines = []
  if (assets) {
    lines.push(`${assets} actif${assets > 1 ? 's' : ''} en surveillance continue`)
  }
  if (scans) {
    lines.push(`Jusqu'à ${scans} analyses de fuites par mois`)
  }
  // 0 = illimité (Plan.UNLIMITED) : le zéro ne s'affiche jamais tel quel.
  lines.push(users ? `${users} utilisateur${users > 1 ? 's' : ''}` : 'Utilisateurs illimités')
  return lines
}

export const FAQ = {
  title: 'Questions fréquentes',
  items: [
    {
      question: 'Où sont hébergées nos données ?',
      answer:
        "Sur une infrastructure située dans l'Union européenne, opérée par nos soins. Les données de chaque client sont cloisonnées et ne sont accessibles qu'aux personnes que vous avez invitées dans votre espace.",
    },
    {
      question: "Qu'est-ce qui est transmis à des services tiers ?",
      answer:
        "Deux flux sortent de la plateforme. Vers notre fournisseur de renseignement sur les fuites : uniquement les noms de domaine que vous avez déclarés, pour interroger ses bases. Vers un service d'intelligence artificielle, pour rédiger les synthèses : un contexte pseudonymisé, où noms, adresses et domaines sont remplacés par des identifiants neutres. Aucun mot de passe n'est transmis à quiconque, sous aucune forme.",
    },
    {
      question: 'Combien de temps conservez-vous les mots de passe retrouvés ?',
      answer:
        "90 jours, puis la valeur est effacée automatiquement. L'historique de la fuite (quel compte, quand, quelle source) est conservé au-delà, sans la valeur. Pendant ces 90 jours, le mot de passe est chiffré et n'est lisible qu'après une vérification d'identité, tracée.",
    },
    {
      question: "En quoi est-ce différent de ce que fait déjà mon prestataire informatique ?",
      answer:
        "Votre prestataire administre votre parc : postes, réseau, sauvegardes. Nous regardons ce qui se passe à l'extérieur — ce qui a fuité, ce qui circule, ce qui se prépare contre vous. Les deux sont complémentaires : nous transmettons d'ailleurs des actions concrètes que votre prestataire peut exécuter.",
    },
    {
      question: 'Faut-il installer quelque chose ?',
      answer:
        "Non. Aucun agent, aucun logiciel, aucune modification de votre réseau. Vous déclarez vos noms de domaine dans l'interface, et la surveillance se fait depuis l'extérieur, comme le ferait un attaquant qui vous observe.",
    },
    {
      question: 'Que se passe-t-il si vous détectez une fuite pendant la nuit ?',
      answer:
        "L'alerte est enregistrée et l'email part immédiatement : vous la trouvez à votre réveil. Nous ne proposons pas d'astreinte téléphonique, et nous n'intervenons pas sur vos systèmes — le produit détecte et vous informe, l'action reste entre vos mains ou celles de votre prestataire.",
    },
    {
      question: 'Est-ce que cela nous met en conformité ?',
      answer:
        "Cela vous y aide, cela ne vous en garantit pas. Le diagnostic s'appuie sur un référentiel reconnu de 42 mesures et produit un plan d'action priorisé ; la surveillance et la traçabilité des accès constituent des éléments de preuve utiles. La conformité reste une démarche d'entreprise, qui dépend de ce que vous mettez réellement en œuvre.",
    },
    {
      question: 'Bloquez-vous les attaques ?',
      answer:
        "Non, et nous préférons le dire clairement. Nous ne sommes ni un antivirus, ni un pare-feu. Nous détectons, nous expliquons et nous alertons. Aucun de nos accès ne permet d'agir sur vos systèmes.",
    },
  ],
}

export const FINAL_CTA = {
  title: 'Voir le produit sur vos propres domaines',
  body: "Une démonstration dure une vingtaine de minutes, en partage d'écran. Nous vous montrons l'interface réelle et répondons à vos questions.",
  cta: 'Demander une démonstration',
}

export const DEMO_FORM = {
  title: 'Demander une démonstration',
  subtitle:
    "Nous vous recontactons sous un jour ouvré pour convenir d'un créneau. Une vingtaine de minutes, en partage d'écran, sans installation.",
  fields: {
    fullName: 'Nom et prénom',
    company: 'Société',
    role: 'Fonction',
    email: 'Email professionnel',
    companySize: 'Taille de la société',
    preferredSlot: 'Créneau souhaité',
    message: 'Votre message',
  },
  messagePlaceholder: 'Ce que vous aimeriez voir en priorité (facultatif)',
  submit: 'Envoyer ma demande',
  submitting: 'Envoi en cours…',
  successTitle: 'Votre demande est bien enregistrée',
  successBody:
    "Nous vous recontactons sous un jour ouvré à l'adresse indiquée. Vous recevez d'ici quelques minutes un email de confirmation.",
  privacyNote:
    "Ces informations servent uniquement à vous recontacter. Elles ne sont ni revendues ni utilisées à d'autres fins.",
}

export const COMPANY_SIZES = [
  { value: '1-9', label: '1 à 9 personnes' },
  { value: '10-49', label: '10 à 49 personnes' },
  { value: '50-249', label: '50 à 249 personnes' },
  { value: '250+', label: '250 personnes et plus' },
]

export const SLOTS = [
  { value: 'morning', label: 'Plutôt le matin' },
  { value: 'afternoon', label: "Plutôt l'après-midi" },
  { value: 'any', label: 'Peu importe' },
]

export const FOOTER = {
  description:
    "Surveillance des fuites de données et accompagnement à la conformité pour les PME.",
  columns: [
    {
      title: 'Produit',
      links: [
        { label: 'Diagnostic et plan d’action', href: '/#diagnostic' },
        { label: 'Alertes et météo cyber', href: '/#alertes' },
        { label: 'Fonctionnement', href: '/#fonctionnement' },
        { label: 'Sécurité et données', href: '/#securite' },
        { label: 'Tarifs', href: '/#tarifs' },
        { label: 'Questions fréquentes', href: '/#questions' },
      ],
    },
    {
      title: 'Société',
      links: [
        { label: 'Contact', href: '/contact' },
        { label: 'Sécurité et données', href: '/securite-donnees' },
        { label: 'Mentions légales', href: '/mentions-legales' },
        { label: 'Confidentialité', href: '/confidentialite' },
        { label: 'Conditions générales', href: '/conditions-generales' },
      ],
    },
  ],
  legalNote: 'Le produit détecte et alerte. Il n’intervient pas sur vos systèmes.',
}
