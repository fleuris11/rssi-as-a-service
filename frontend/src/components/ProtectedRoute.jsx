import { Loader2 } from 'lucide-react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute() {
  const { isAuthenticated, loading, currentTenantId } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <Loader2 className="size-6 animate-spin text-brand-600" aria-hidden="true" />
        <span className="sr-only">Chargement…</span>
      </div>
    )
  }
  if (!isAuthenticated) {
    return <Navigate to="/connexion" replace />
  }
  if (!currentTenantId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-6 text-center">
        <p className="text-ink-600">Aucune entreprise associée à votre compte.</p>
      </div>
    )
  }
  return <Outlet />
}
