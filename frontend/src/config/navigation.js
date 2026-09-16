import {
  Inbox,
  Newspaper,
  Building2,
  ClipboardCheck,
  Crosshair,
  KanbanSquare,
  LayoutDashboard,
  FileBarChart,
  MessageSquareText,
  Radar,
  ScrollText,
  ShieldAlert,
  UserRoundSearch,
} from 'lucide-react'

// Single source of truth for the sidebar links AND the topbar's page
// title/breadcrumb (AppLayout looks up the current route here instead of
// duplicating titles per page).
// V2-8 (ADR-038) : `fonctionnalite` dit de quelle clé du registre un écran
// dépend, `derivePar` qu'il n'existe QUE par une autre. Composer le périmètre
// d'un client retire les deux — laisser « Plan d'action » à un client sans
// diagnostic afficherait un écran vide qui l'invite à faire un diagnostic
// auquel il n'a pas droit.
export const NAV_ITEMS = [
  { to: '/tableau-de-bord', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/diagnostic', label: 'Diagnostic', icon: ClipboardCheck, fonctionnalite: 'anssi_assessment' },
  { to: '/plan-action', label: 'Plan d’action', icon: KanbanSquare, derivePar: 'anssi_assessment' },
  // Lot C : `technical` marque un écran PUREMENT technique. En profil
  // dirigeant, il reste accessible mais descend dans une section « Détails
  // techniques » : c'est la consigne « accessibles mais pas mis en avant ».
  // Surveillance montre des contrôles HTTP, TLS et DNS ; Compromissions est
  // la liste exhaustive dont Exposition donne déjà la lecture priorisée.
  { to: '/surveillance', label: 'Surveillance', icon: Radar, technical: true },
  // Phase 8B : « Exposition » est la vue principale du volet menace (le
  // médecin), « Compromissions » reste la liste exhaustive des fuites
  // avérées (la chemise de résultats) — d'où cet ordre.
  { to: '/exposition', label: 'Exposition', icon: Crosshair },
  { to: '/compromissions', label: 'Compromissions', icon: ShieldAlert, technical: true },
  // V2-6 : des comptes que le client DÉSIGNE, distincts de ses actifs. Le
  // lien est dans la navigation principale et non rangé sous « Exposition » :
  // ce sont deux périmètres différents, et les confondre dans le menu
  // reviendrait à les confondre tout court.
  {
    to: '/comptes-surveilles',
    label: 'Comptes surveillés',
    icon: UserRoundSearch,
    fonctionnalite: 'watched_accounts',
  },
  // V2-3 : la page qu'on ouvre pour PRÉPARER un comité, distincte du
  // tableau de bord qu'on ouvre pour savoir où on en est aujourd'hui.
  { to: '/rapports', label: 'Rapports', icon: FileBarChart },
  { to: '/documents', label: 'Documents', icon: ScrollText },
  // B5.18 : la veille reglementaire vue du client. Lecture seule, et
  // seulement ce qui a ete juge pertinent.
  { to: '/veille', label: 'Veille', icon: Newspaper },
  { to: '/assistant', label: 'Assistant', icon: MessageSquareText, fonctionnalite: 'assistant' },
  // Lot B : la page existait, etait routee, et n'etait dans AUCUN menu.
  // Le seul lien y menant etait enfoui dans le panneau « hors offre » —
  // un client qui avait depose une demande n'avait aucun moyen de la
  // retrouver. Une demande sans retour est pire que pas de bouton.
  { to: '/mes-demandes', label: 'Mes demandes', icon: Inbox },
]

// Pages reachable but not in the primary nav (contextual links only) —
// still need a topbar title.
const SECONDARY_TITLES = {
  '/resultats': 'Résultats',
  '/notifications': 'Notifications',
  '/preferences': 'Préférences',
  '/securite': 'Sécurité',
  '/admin/breachsense': 'Administration — Renseignement sur la menace',
  '/admin/plateforme': 'Administration de la plateforme',
}

// Liens réservés aux administrateurs plateforme (is_staff), affichés dans une
// section distincte de la barre latérale : l'administration n'est pas un
// espace client mieux doté, c'est un espace séparé.
export const STAFF_NAV_ITEMS = [
  { to: '/admin/plateforme', label: 'Plateforme', icon: Building2 },
  { to: '/admin/breachsense', label: 'Licence CTI', icon: Radar },
]

/**
 * Les clés RETIRÉES à ce client par une composition (V2-8, ADR-038).
 *
 * Deux absences qui ne se traitent pas pareil : hors offre (`source: 'plan'`)
 * reste visible et désactivé — c'est un levier commercial ; retirée pour ce
 * client (`source: 'override'`) disparaît — on ne montre pas à quelqu'un ce
 * qu'on vient de lui retirer.
 */
export function fonctionnalitesRetirees(features = []) {
  return new Set(
    features.filter((f) => !f.included && f.source === 'override').map((f) => f.key)
  )
}

function estVisible(item, retirees) {
  if (item.fonctionnalite && retirees.has(item.fonctionnalite)) return false
  return !(item.derivePar && retirees.has(item.derivePar))
}

/**
 * La navigation telle qu'un profil la lit, pour un périmètre donné.
 *
 * Le profil ne retire aucun lien : en profil dirigeant, les écrans techniques
 * changent seulement de place. La composition, elle, en retire.
 */
export function navigationPourProfil(isTechnical, retirees = new Set()) {
  const visibles = NAV_ITEMS.filter((item) => estVisible(item, retirees))
  if (isTechnical) return { principale: visibles, techniques: [] }
  return {
    principale: visibles.filter((item) => !item.technical),
    techniques: visibles.filter((item) => item.technical),
  }
}

export function pageTitleFor(pathname) {
  const navMatch = NAV_ITEMS.find((item) => pathname.startsWith(item.to))
  if (navMatch) return navMatch.label
  const secondaryMatch = Object.entries(SECONDARY_TITLES).find(([path]) => pathname.startsWith(path))
  return secondaryMatch?.[1] ?? ''
}
