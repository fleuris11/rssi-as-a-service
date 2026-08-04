import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const linkClass = ({ isActive }) =>
  `rounded-md px-3 py-2 text-sm font-medium ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
  }`

export default function NavBar() {
  const { currentTenant, logout } = useAuth()

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="text-lg font-semibold text-slate-900">RSSI as a Service</span>
          <nav className="flex gap-1">
            <NavLink to="/diagnostic" className={linkClass}>
              Diagnostic
            </NavLink>
            <NavLink to="/resultats" className={linkClass}>
              Résultats
            </NavLink>
            <NavLink to="/plan-action" className={linkClass}>
              Plan d’action
            </NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-600">
          {currentTenant && <span>{currentTenant.tenant_name}</span>}
          <button type="button" onClick={logout} className="text-slate-500 hover:text-slate-900">
            Déconnexion
          </button>
        </div>
      </div>
    </header>
  )
}
