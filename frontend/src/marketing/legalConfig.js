/**
 * Informations légales de l'éditeur — FICHIER À REMPLIR.
 *
 * Source unique : les pages Mentions légales, Confidentialité, CGV et
 * Sécurité s'alimentent toutes ici. Tant qu'un champ vaut la chaîne vide, les
 * pages concernées affichent un bandeau « à compléter » et la mention
 * manquante apparaît explicitement comme telle.
 *
 * RÈGLE : ne JAMAIS inventer d'information légale. Une raison sociale ou un
 * numéro d'immatriculation plausible mais faux est pire qu'une case vide —
 * il donne l'apparence de la conformité sans la substance, et personne ne
 * pense à le corriger.
 *
 * Les textes juridiques qui s'appuient sur ces valeurs sont des TRAMES à
 * faire valider par un professionnel du droit (voir docs/legal/README.md).
 */

export const LEGAL_ENTITY = {
  companyName: '',
  legalForm: '',
  shareCapital: '',
  registrationNumber: '', // SIREN/SIRET ou équivalent
  vatNumber: '',
  address: '',
  postalCode: '',
  city: '',
  country: '',
  publicationDirector: '',
  contactEmail: 'contact@rssiasservice.online',
  phone: '',
}

export const HOSTING = {
  // Renseigné parce que VÉRIFIABLE, contrairement à l'identité de l'éditeur :
  // le serveur est un VPS OVHcloud, région SBG (Strasbourg). Mentions légales
  // relevées sur le site d'OVH, à revérifier si l'hébergeur change.
  providerName: 'OVH SAS (OVHcloud)',
  providerAddress: '2 rue Kellermann, 59100 Roubaix, France — RCS Lille Métropole 424 761 419',
  // Précis plutôt que vague : le serveur est physiquement à Strasbourg.
  dataLocation: "France (Strasbourg) — Union européenne",
}

/**
 * Sous-traitants ultérieurs. Décrits par leur RÔLE et les données qu'ils
 * reçoivent, ce qui est exact et vérifiable dans le code ; leur identité
 * commerciale reste à compléter par l'éditeur.
 */
export const SUBPROCESSORS = [
  {
    role: 'Fournisseur de renseignement sur les fuites',
    name: 'Breachsense',
    purpose: 'Interrogation des bases de fuites de données',
    dataShared:
      "Les noms de domaine que le client a déclarés. Aucune donnée personnelle de ses collaborateurs, aucun identifiant, aucun mot de passe.",
    location: '',
  },
  {
    role: "Fournisseur de service d'intelligence artificielle",
    name: 'Anthropic',
    purpose: 'Rédaction des synthèses et des documents',
    dataShared:
      "Un contexte pseudonymisé : noms, adresses email et noms de domaine sont remplacés par des identifiants neutres avant l'envoi, puis rétablis à la réception. Aucun mot de passe n'est transmis, sous aucune forme.",
    location: '',
  },
  {
    role: 'Hébergeur',
    name: '',
    purpose: "Hébergement de l'application et de la base de données",
    dataShared: "L'ensemble des données du service, chiffrées au repos pour les plus sensibles.",
    location: "Union européenne",
  },
]

/** Durées de conservation — reflètent la configuration réelle du produit. */
export const RETENTION = [
  {
    data: 'Mots de passe retrouvés dans des fuites',
    duration: '90 jours',
    note: "Effacement automatique. L'historique de la fuite (compte concerné, date, source) est conservé sans la valeur.",
  },
  {
    data: 'Journal des consultations de mots de passe',
    duration: '365 jours',
    note: 'Qui a consulté quoi, quand, depuis quelle adresse. Ne contient jamais le mot de passe.',
  },
  {
    data: 'Résultats de surveillance et alertes',
    duration: "Durée de l'abonnement",
    note: 'Conservés pour permettre le suivi de la progression dans le temps.',
  },
  {
    data: 'Données de compte et de facturation',
    duration: "Durée de la relation contractuelle, puis obligations comptables",
    note: 'À préciser avec le conseil juridique de l’éditeur.',
  },
  {
    data: 'Demandes de démonstration',
    duration: 'Le temps du suivi commercial',
    note: '',
  },
]

/** Mesures de sécurité, décrites factuellement — pas d'auto-certification. */
export const SECURITY_MEASURES = [
  {
    title: 'Cloisonnement entre clients',
    body: "Chaque espace client est isolé à trois niveaux indépendants. Par défaut, aucune donnée n'est renvoyée si le contexte client n'est pas résolu : le système échoue en refusant, pas en montrant.",
  },
  {
    title: 'Chiffrement des données les plus sensibles',
    body: "Les mots de passe retrouvés dans des fuites et les secrets d'authentification à deux facteurs sont chiffrés au repos, chacun avec une clé dédiée. Les clés ne sont jamais stockées en base.",
  },
  {
    title: "Contrôle et traçabilité des accès sensibles",
    body: "Consulter la valeur d'un mot de passe fuité exige d'être administrateur de l'espace et de re-prouver son identité à ce moment précis. Chaque tentative, acceptée ou refusée, est enregistrée avec son auteur, sa date et son adresse.",
  },
  {
    title: 'Pseudonymisation avant tout traitement externe',
    body: "Aucune donnée identifiante n'est transmise en clair à un service d'analyse tiers : noms, adresses et domaines sont remplacés par des identifiants neutres avant l'envoi.",
  },
  {
    title: 'Authentification',
    body: "Jetons de session courts avec rotation, double authentification par application mobile disponible sur chaque compte, verrouillage progressif après échecs répétés, politique de mot de passe d'au moins 12 caractères.",
  },
  {
    title: 'Chaîne de développement',
    body: "Analyse automatisée des dépendances et de l'image applicative à chaque modification du code, revue de sécurité documentée selon le référentiel OWASP Top 10, et suite de tests automatisés couvrant les propriétés de sécurité.",
  },
]

/** Ce que la plateforme ne fait pas — aussi important que ce qu'elle fait. */
export const SECURITY_LIMITS = [
  "Le service détecte et alerte : il n'intervient pas sur les systèmes du client et ne bloque aucune attaque.",
  "Aucun agent n'est installé sur les postes ou le réseau du client ; la surveillance se fait depuis l'extérieur, sur les seuls actifs qu'il a déclarés.",
  "Le service n'atteste d'aucune conformité réglementaire. Il fournit des éléments (diagnostic, plan d'action, traçabilité) qui peuvent y contribuer.",
  "Aucun identifiant n'est testé nulle part : une réutilisation de mot de passe est signalée comme une hypothèse à vérifier, jamais comme un fait établi.",
]

/** Un champ vide signale une mention à compléter. */
export function missingEntityFields() {
  const required = [
    ['companyName', 'Raison sociale'],
    ['legalForm', 'Forme juridique'],
    ['registrationNumber', "Numéro d'immatriculation"],
    ['address', 'Adresse'],
    ['city', 'Ville'],
    ['publicationDirector', 'Directeur de la publication'],
  ]
  return required.filter(([key]) => !LEGAL_ENTITY[key]).map(([, label]) => label)
}

export function missingHostingFields() {
  return [
    ['providerName', "Nom de l'hébergeur"],
    ['providerAddress', "Adresse de l'hébergeur"],
  ]
    .filter(([key]) => !HOSTING[key])
    .map(([, label]) => label)
}

/** Valeur, ou repère explicite si le champ n'est pas renseigné. */
export function orPlaceholder(value) {
  return value || '— à compléter —'
}
