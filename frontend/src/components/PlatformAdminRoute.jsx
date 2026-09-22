import { Loader2 } from 'lucide-react'
import { LogOut } from 'lucide-react'
import { Link, Navigate, NavLink, Outlet } from 'react-router-dom'
import { STAFF_NAV_ITEMS } from '../config/navigation'
import { Monogramme } from './AuthLayout'
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
      <header className="sur-bati border-b border-bati-600">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-2.5 sm:px-6">
          <span className="flex items-center gap-2.5">
            {/* Le monogramme dessiné remplace l'image du logo : à 132 px de
                large réduite à 32, elle se voyait matricée sur les écrans à
                forte densité, et c'était la première chose visible de la
                console. */}
            <Monogramme sombre />
            <span
              className="font-display text-sm font-semibold text-craie"
              style={{ fontVariationSettings: "'wdth' 92" }}
            >
              Administration plateforme
            </span>
          </span>

          <nav aria-label="Administration" className="flex flex-wrap gap-1">
            {STAFF_NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `transition-smooth t-menu relative rounded-sm px-3 py-1.5 ${
                    isActive
                      ? 'bg-bati-700 text-craie before:absolute before:inset-x-2 before:bottom-0 before:h-0.5 before:rounded-full before:bg-action-claire'
                      : 'text-craie-douce hover:bg-bati-700/60 hover:text-craie'
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
              className="transition-smooth t-menu rounded-sm px-3 py-1.5 text-craie-douce hover:text-craie"
            >
              Espace client
            </Link>
            <button
              type="button"
              onClick={logout}
              className="transition-smooth t-menu flex items-center gap-2 rounded-sm px-3 py-1.5 text-craie-douce hover:text-craie"
            >
              <LogOut className="size-4" aria-hidden="true" />
              Déconnexion
            </button>
          </div>
        </div>
      </header>

      {/* `data-densite` en compacte : la console sert a traiter des dizaines
          de lignes a la suite, pas a lire trois chiffres. C'est le meme
          reglage que le profil Technique de l'espace client, applique ici par
          defaut. */}
      <main data-densite="compacte" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
