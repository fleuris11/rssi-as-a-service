import { Loader2 } from 'lucide-react'
import { LogOut, ShieldEllipsis } from 'lucide-react'
import { Link, Navigate, NavLink, Outlet } from 'react-router-dom'
import { STAFF_NAV_ITEMS } from '../config/navigation'
import { useAuth } from '../context/AuthContext'

/**
 * Espace d'administration plateforme — **distinct de l'espace client**.
 *
 * Ne passe volontairement pas par ``ProtectedRoute`` : celui-ci exige un
 * tenant courant, ce qui est juste pour l'espace client mais faux ici. Un
 * administrateur plateforme n'a aucune raison d'être membre d'une entreprise
 * cliente — et, d'après ADR-014, ne devrait justement pas l'être pour les
 * clients dont il n'a pas à consulter les données. Le monter sous le layout
 * client rendait l'administration inaccessible à un compte purement
 * administrateur, ce qui est exactement le cas d'usage visé.
 */
export default function PlatformAdminRoute() {
  const { isAuthenticated, loading, user, logout } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <Loader2 className="size-6 animate-spin text-brand-600" aria-hidden="true" />
        <span className="sr-only">Chargement…</span>
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/connexion" replace />
  if (!user?.is_staff) return <Navigate to="/tableau-de-bord" replace />

  return (
    <div className="min-h-screen bg-canvas">
      {/* En-tête sombre et libellé explicite : on doit voir d'un coup d'œil
          qu'on n'est pas dans l'espace d'un client. */}
      <header className="border-b border-brand-800 bg-brand-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-5 py-3">
          <span className="flex items-center gap-2 text-white">
            <ShieldEllipsis className="size-5" aria-hidden="true" />
            <span className="font-display text-sm font-semibold">Administration plateforme</span>
          </span>

          <nav aria-label="Administration" className="flex flex-wrap gap-1">
            {STAFF_NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `transition-smooth rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-white ${
                    isActive
                      ? 'bg-brand-800 text-white'
                      : 'text-brand-200 hover:bg-brand-800/60 hover:text-white'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <Link
              to="/tableau-de-bord"
              className="transition-smooth rounded-md px-3 py-1.5 text-sm text-brand-200 hover:text-white focus-visible:outline-2 focus-visible:outline-white"
            >
              Espace client
            </Link>
            <button
              type="button"
              onClick={logout}
              className="transition-smooth flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-brand-200 hover:text-white focus-visible:outline-2 focus-visible:outline-white"
            >
              <LogOut className="size-4" aria-hidden="true" />
              Déconnexion
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8">
        <Outlet />
      </main>
    </div>
  )
}
