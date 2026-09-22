import { LogOut, ShieldCheck, ShieldEllipsis, SlidersHorizontal } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { fonctionnalitesRetirees, navigationPourProfil, STAFF_NAV_ITEMS } from '../config/navigation'
import { useAuth } from '../context/AuthContext'
import { useOptionalEntitlements } from '../context/EntitlementsContext'
import { useDisplayProfile } from '../context/useDisplayProfile'

const linkBase =
  'transition-smooth t-menu relative flex items-center gap-3 rounded-sm py-2 pl-3 pr-2 outline-offset-2'

/**
 * L'entrée active porte un FILET plein à gauche, pas un fond teinté.
 *
 * Le fond teinté avait deux défauts : sur le bâti il se distinguait mal du
 * survol, et il occupait une surface colorée dans un produit où la couleur ne
 * dit que le risque. Le filet marque la position sans rien peindre — c'est la
 * grammaire d'un pupitre, où l'index repère une voie.
 */
function linkClass({ isActive }, collapsed) {
  const etat = isActive
    ? 'bg-bati-700 text-craie before:absolute before:inset-y-1 before:left-0 before:w-0.5 before:rounded-full before:bg-action-claire'
    : 'text-craie-douce hover:bg-bati-700/60 hover:text-craie'
  return `${linkBase} ${etat} ${collapsed ? 'justify-center pl-2 pr-2' : ''}`
}

/**
 * Rendered both as the fixed desktop/tablet sidebar (icon-only at the `md`
 * breakpoint, full at `lg`+ — see AppLayout) and, unmodified, inside the
 * mobile drawer — same markup, the drawer just controls visibility/overlay.
 */
export default function Sidebar({ collapsed = false, onNavigate }) {
  const { currentTenant, logout, user } = useAuth()
  const { isTechnical } = useDisplayProfile()
  // V2-8 (ADR-038) : ce qui a été RETIRÉ à ce client sort du menu. Ce qui est
  // seulement hors offre y reste, désactivé, comme avant.
  const droits = useOptionalEntitlements()
  const { principale, techniques } = navigationPourProfil(
    isTechnical,
    fonctionnalitesRetirees(droits?.features)
  )

  return (
    <div className="sur-bati flex h-full flex-col bg-bati-900">
      <div
        className={`flex items-center gap-2.5 border-b border-bati-700 px-4 py-4 ${
          collapsed ? 'justify-center px-0' : ''
        }`}
      >
        <span
          aria-hidden="true"
          className="grid size-8 shrink-0 place-items-center rounded-sm bg-craie text-bati-900"
        >
          <span
            className="text-[0.6875rem] font-semibold uppercase leading-none"
            style={{ fontVariationSettings: "'wdth' 70" }}
          >
            net
          </span>
        </span>
        {!collapsed && (
          <span
            className="font-display text-sm font-semibold text-craie"
            style={{ fontVariationSettings: "'wdth' 92" }}
          >
            RSSI as a Service
          </span>
        )}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {principale.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={(state) => linkClass(state, collapsed)}
            title={collapsed ? item.label : undefined}
          >
            <item.icon className="size-5 shrink-0" aria-hidden="true" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}

        {/* Lot C : en profil dirigeant, les écrans purement techniques restent
            à un clic, sous leur propre intitulé — accessibles, pas mis en
            avant. En profil technique, cette section est vide : ils sont à
            leur place dans la liste principale. */}
        {techniques.length > 0 && (
          <div role="group" aria-label="Détails techniques">
            <p
              className={`t-legende mt-6 px-3 pb-1.5 text-craie-douce ${
                collapsed ? 'text-center' : ''
              }`}
            >
              {collapsed ? '···' : 'Détails techniques'}
            </p>
            {techniques.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavigate}
                className={(state) => linkClass(state, collapsed)}
                title={collapsed ? item.label : undefined}
              >
                <item.icon className="size-5 shrink-0" aria-hidden="true" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </div>
        )}

        {/* Section distincte pour l'administration plateforme : elle ne
            s'affiche que pour un utilisateur is_staff, et la séparation
            visuelle rappelle qu'on quitte l'espace client. */}
        {user?.is_staff && (
          <>
            <p
              className={`t-legende mt-6 px-3 pb-1.5 text-action-claire ${
                collapsed ? 'text-center' : ''
              }`}
            >
              {collapsed ? '···' : 'Plateforme'}
            </p>
            {STAFF_NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavigate}
                className={(state) => linkClass(state, collapsed)}
                title={collapsed ? item.label : undefined}
              >
                <item.icon className="size-5 shrink-0" aria-hidden="true" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </>
        )}
      </nav>

      <div className="space-y-1 border-t border-bati-600 px-3 py-3">
        {!collapsed && currentTenant && (
          <div className="mb-2 px-3 py-1.5">
            <p className="t-legende text-craie-douce">Espace</p>
            <p className="mt-0.5 truncate text-sm font-medium text-craie">
              {currentTenant.tenant_name}
            </p>
          </div>
        )}
        <NavLink
          to="/preferences"
          onClick={onNavigate}
          className={(state) => linkClass(state, collapsed)}
          title={collapsed ? 'Préférences' : undefined}
        >
          <SlidersHorizontal className="size-5 shrink-0" aria-hidden="true" />
          {!collapsed && <span>Préférences</span>}
        </NavLink>
        <NavLink
          to="/securite"
          onClick={onNavigate}
          className={(state) => linkClass(state, collapsed)}
          title={collapsed ? 'Sécurité' : undefined}
        >
          <ShieldCheck className="size-5 shrink-0" aria-hidden="true" />
          {!collapsed && <span>Sécurité</span>}
        </NavLink>
        {user?.is_staff && (
          <NavLink
            to="/admin/renseignement"
            onClick={onNavigate}
            className={(state) => linkClass(state, collapsed)}
            title={collapsed ? 'Renseignement' : undefined}
          >
            <ShieldEllipsis className="size-5 shrink-0" aria-hidden="true" />
            {!collapsed && <span>Renseignement</span>}
          </NavLink>
        )}
        <button
          type="button"
          onClick={logout}
          title={collapsed ? 'Déconnexion' : undefined}
          className={`${linkBase} w-full text-craie-douce hover:bg-bati-700/60 hover:text-craie ${collapsed ? 'justify-center' : ''}`}
        >
          <LogOut className="size-5 shrink-0" aria-hidden="true" />
          {!collapsed && <span>Déconnexion</span>}
        </button>
      </div>
    </div>
  )
}
