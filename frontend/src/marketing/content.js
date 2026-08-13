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
 *   - le produit détecte et alerte, il ne bloque rien.
 */

export const SITE = {
  name: 'RSSI as a Service',
  tagline: 'Surveillance des fuites de données et de la conformité pour les PME',
  contactEmail: 'contact@rssiasservice.online',
}

export const NAV = [
  { label: 'Le produit', href: '#produit' },
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
  title: 'Trois choses que nous faisons différemment',
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
  ],
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
export const PRICING = {
  title: 'Offres',
  subtitle: "Montants indicatifs, hors taxes, par mois. La tarification définitive est établie au moment du devis.",
  disclaimer:
    "Ces montants sont donnés à titre indicatif pour situer un ordre de grandeur. Ils ne constituent pas une offre commerciale.",
  currency: '€',
  plans: [
    {
      id: 'essentiel',
      name: 'Essentiel',
      price: 49,
      pitch: 'Pour une petite structure avec un domaine et une messagerie.',
      features: [
        '3 actifs surveillés',
        'Diagnostic de maturité et plan d’action',
        'Surveillance disponibilité, certificat, en-têtes, SPF/DMARC',
        'Analyse de fuites mensuelle',
        '2 utilisateurs',
      ],
    },
    {
      id: 'standard',
      name: 'Standard',
      price: 149,
      highlighted: true,
      pitch: 'Pour une PME avec plusieurs sites et une équipe.',
      features: [
        '10 actifs surveillés',
        'Tout ce que comprend Essentiel',
        'Signaux avant-coureurs et corrélation de réutilisation',
        'Analyse de fuites hebdomadaire',
        'Synthèse rédigée et génération documentaire',
        '10 utilisateurs',
      ],
    },
    {
      id: 'etendu',
      name: 'Étendu',
      price: 349,
      pitch: 'Pour une structure multi-sites ou avec des obligations sectorielles.',
      features: [
        '30 actifs surveillés',
        'Tout ce que comprend Standard',
        // Formulation prudente à dessein : la surveillance temps réel repose
        // sur un pool de 15 emplacements PARTAGÉ par toute la plateforme
        // (palier de licence, ADR-013). Promettre « tous vos actifs en temps
        // réel » serait invendable dès le sixième client. Le nombre se
        // convient donc au cas par cas.
        "Surveillance en temps réel (nombre d'actifs convenu ensemble)",
        'Analyse de fuites à la demande',
        'Utilisateurs illimités',
        'Accompagnement à la mise en conformité',
      ],
    },
  ],
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
        { label: 'Mentions légales', href: '/mentions-legales' },
        { label: 'Confidentialité', href: '/confidentialite' },
      ],
    },
  ],
  legalNote: 'Le produit détecte et alerte. Il n’intervient pas sur vos systèmes.',
}
