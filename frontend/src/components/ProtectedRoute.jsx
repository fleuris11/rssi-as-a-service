import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute() {
  const { isAuthenticated, loading, currentTenantId } = useAuth()

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Chargement…</div>
  }
  if (!isAuthenticated) {
    return <Navigate to="/connexion" replace />
  }
  if (!currentTenantId) {
    return (
      <div className="p-8 text-center text-slate-600">
        Aucune entreprise associée à votre compte.
      </div>
    )
  }
  return <Outlet />
}
