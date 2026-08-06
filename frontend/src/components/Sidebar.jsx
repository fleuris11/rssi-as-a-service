import { LogOut, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { NAV_ITEMS } from '../config/navigation'
import { useAuth } from '../context/AuthContext'

const linkBase =
  'transition-smooth flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium outline-offset-2 focus-visible:outline-2 focus-visible:outline-white'

function linkClass({ isActive }, collapsed) {
  const state = isActive
    ? 'bg-brand-800 text-white'
    : 'text-brand-200 hover:bg-brand-800/60 hover:text-white'
  return `${linkBase} ${state} ${collapsed ? 'justify-center' : ''}`
}

/**
 * Rendered both as the fixed desktop/tablet sidebar (icon-only at the `md`
 * breakpoint, full at `lg`+ — see AppLayout) and, unmodified, inside the
 * mobile drawer — same markup, the drawer just controls visibility/overlay.
 */
export default function Sidebar({ collapsed = false, onNavigate }) {
  const { currentTenant, logout } = useAuth()

  return (
    <div className="flex h-full flex-col bg-brand-950 text-white">
      <div className={`flex items-center gap-2.5 px-4 py-5 ${collapsed ? 'justify-center px-0' : ''}`}>
        <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent-600 font-display text-sm font-bold text-white">
          R
        </div>
        {!collapsed && (
          <span className="font-display text-base font-semibold tracking-tight text-white">
            RSSI as a Service
          </span>
        )}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {NAV_ITEMS.map((item) => (
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
      </nav>

      <div className="space-y-1 border-t border-brand-800 px-3 py-3">
        {!collapsed && currentTenant && (
          <div className="mb-2 flex items-center gap-2 rounded-md px-3 py-2">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-brand-100">
              {currentTenant.tenant_name.slice(0, 2).toUpperCase()}
            </div>
            <span className="truncate text-sm text-brand-100">{currentTenant.tenant_name}</span>
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
        <button
          type="button"
          onClick={logout}
          title={collapsed ? 'Déconnexion' : undefined}
          className={`${linkBase} w-full text-brand-200 hover:bg-brand-800/60 hover:text-white ${collapsed ? 'justify-center' : ''}`}
        >
          <LogOut className="size-5 shrink-0" aria-hidden="true" />
          {!collapsed && <span>Déconnexion</span>}
        </button>
      </div>
    </div>
  )
}
