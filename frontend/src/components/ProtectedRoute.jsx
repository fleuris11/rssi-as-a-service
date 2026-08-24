import { Loader2 } from 'lucide-react'
import { Link, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute() {
  const { isAuthenticated, loading, currentTenantId, user } = useAuth()

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
    // Un administrateur plateforme n'est membre d'aucune entreprise cliente
    // (ADR-014) : ce n'est pas une anomalie de son compte, c'est sa nature.
    // On l'envoie donc dans SA console plutôt que de le laisser devant un
    // écran vide qui laisse croire à un compte cassé.
    if (user?.is_staff) {
      return <Navigate to="/admin/plateforme" replace />
    }

    // Un utilisateur ordinaire sans entreprise, en revanche, a bien un
    // problème : son invitation n'a pas abouti, ou on l'a retiré de son
    // entreprise. Le lui dire, et lui donner une sortie.
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-canvas px-6 text-center">
        <p className="text-ink-800">Aucune entreprise n’est associée à votre compte.</p>
        <p className="max-w-md text-sm text-ink-600">
          Votre accès a peut-être été retiré, ou votre invitation n’a jamais été finalisée.
          Rapprochez-vous de l’administrateur qui vous a ouvert cet accès.
        </p>
        <Link to="/connexion" className="text-sm font-medium text-brand-700 underline">
          Se connecter avec un autre compte
        </Link>
      </div>
    )
  }

  return <Outlet />
}
