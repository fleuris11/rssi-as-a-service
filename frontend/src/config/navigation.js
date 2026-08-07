import {
  ClipboardCheck,
  KanbanSquare,
  LayoutDashboard,
  MessageSquareText,
  Radar,
  ScrollText,
  ShieldAlert,
} from 'lucide-react'

// Single source of truth for the sidebar links AND the topbar's page
// title/breadcrumb (AppLayout looks up the current route here instead of
// duplicating titles per page).
export const NAV_ITEMS = [
  { to: '/tableau-de-bord', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/diagnostic', label: 'Diagnostic', icon: ClipboardCheck },
  { to: '/plan-action', label: 'Plan d’action', icon: KanbanSquare },
  { to: '/surveillance', label: 'Surveillance', icon: Radar },
  { to: '/compromissions', label: 'Compromissions', icon: ShieldAlert },
  { to: '/documents', label: 'Documents', icon: ScrollText },
  { to: '/assistant', label: 'Assistant', icon: MessageSquareText },
]

// Pages reachable but not in the primary nav (contextual links only) —
// still need a topbar title.
const SECONDARY_TITLES = {
  '/resultats': 'Résultats',
  '/preferences': 'Préférences',
  '/securite': 'Sécurité',
  '/admin/breachsense': 'Administration — Renseignement sur la menace',
}

export function pageTitleFor(pathname) {
  const navMatch = NAV_ITEMS.find((item) => pathname.startsWith(item.to))
  if (navMatch) return navMatch.label
  const secondaryMatch = Object.entries(SECONDARY_TITLES).find(([path]) => pathname.startsWith(path))
  return secondaryMatch?.[1] ?? ''
}
