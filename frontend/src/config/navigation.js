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
export const NAV_ITEMS = [
  { to: '/tableau-de-bord', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/diagnostic', label: 'Diagnostic', icon: ClipboardCheck },
  { to: '/plan-action', label: 'Plan d’action', icon: KanbanSquare },
  { to: '/surveillance', label: 'Surveillance', icon: Radar },
  // Phase 8B : « Exposition » est la vue principale du volet menace (le
  // médecin), « Compromissions » reste la liste exhaustive des fuites
  // avérées (la chemise de résultats) — d'où cet ordre.
  { to: '/exposition', label: 'Exposition', icon: Crosshair },
  { to: '/compromissions', label: 'Compromissions', icon: ShieldAlert },
  // V2-6 : des comptes que le client DÉSIGNE, distincts de ses actifs. Le
  // lien est dans la navigation principale et non rangé sous « Exposition » :
  // ce sont deux périmètres différents, et les confondre dans le menu
  // reviendrait à les confondre tout court.
  { to: '/comptes-surveilles', label: 'Comptes surveillés', icon: UserRoundSearch },
  // V2-3 : la page qu'on ouvre pour PRÉPARER un comité, distincte du
  // tableau de bord qu'on ouvre pour savoir où on en est aujourd'hui.
  { to: '/rapports', label: 'Rapports', icon: FileBarChart },
  { to: '/documents', label: 'Documents', icon: ScrollText },
  // B5.18 : la veille reglementaire vue du client. Lecture seule, et
  // seulement ce qui a ete juge pertinent.
  { to: '/veille', label: 'Veille', icon: Newspaper },
  { to: '/assistant', label: 'Assistant', icon: MessageSquareText },
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

export function pageTitleFor(pathname) {
  const navMatch = NAV_ITEMS.find((item) => pathname.startsWith(item.to))
  if (navMatch) return navMatch.label
  const secondaryMatch = Object.entries(SECONDARY_TITLES).find(([path]) => pathname.startsWith(path))
  return secondaryMatch?.[1] ?? ''
}
