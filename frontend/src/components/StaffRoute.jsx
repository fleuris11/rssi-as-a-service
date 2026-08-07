import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// Nested inside ProtectedRoute (already handles auth/loading/tenant
// checks) — this only adds the is_staff gate for platform back-office
// pages. The real security boundary is server-side (IsAdminUser on the
// API — apps.threat_intelligence.views.ThreatIntelligenceAdminStatusView),
// this is purely UX: don't render a page whose data calls will 403 anyway.
export default function StaffRoute() {
  const { user } = useAuth()
  if (!user?.is_staff) {
    return <Navigate to="/tableau-de-bord" replace />
  }
  return <Outlet />
}
