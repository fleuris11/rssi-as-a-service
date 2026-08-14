import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import { EntitlementsProvider } from './context/EntitlementsContext'
import PlatformAdminRoute from './components/PlatformAdminRoute'
import ActionPlanPage from './pages/ActionPlanPage'
import AdminBreachsensePage from './pages/AdminBreachsensePage'
import PlatformAdminPage from './pages/admin/PlatformAdminPage'
import AssistantPage from './pages/AssistantPage'
import CompromisesPage from './pages/CompromisesPage'
import DashboardPage from './pages/DashboardPage'
import DiagnosticPage from './pages/DiagnosticPage'
import DocumentsPage from './pages/DocumentsPage'
import ExposurePage from './pages/ExposurePage'
import NotificationPreferencesPage from './pages/NotificationPreferencesPage'
import ResultsPage from './pages/ResultsPage'
import SurveillancePage from './pages/SurveillancePage'
import TwoFactorSettingsPage from './pages/TwoFactorSettingsPage'

// Routes de l'application authentifiée, extraites de App.jsx pour former un
// point de découpe : ce module (et tout ce qu'il importe) n'est téléchargé
// que lorsqu'un visiteur quitte la vitrine pour entrer dans le produit.
// Les chemins restent inchangés — aucune URL existante n'est cassée.
export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<ProtectedRoute />}>
        <Route
          element={
            <EntitlementsProvider>
              <AppLayout />
            </EntitlementsProvider>
          }
        >
          <Route path="/tableau-de-bord" element={<DashboardPage />} />
          <Route path="/diagnostic" element={<DiagnosticPage />} />
          <Route path="/resultats" element={<ResultsPage />} />
          <Route path="/resultats/:assessmentId" element={<ResultsPage />} />
          <Route path="/plan-action" element={<ActionPlanPage />} />
          <Route path="/surveillance" element={<SurveillancePage />} />
          <Route path="/exposition" element={<ExposurePage />} />
          <Route path="/compromissions" element={<CompromisesPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/assistant" element={<AssistantPage />} />
          <Route path="/preferences" element={<NotificationPreferencesPage />} />
          <Route path="/securite" element={<TwoFactorSettingsPage />} />
        </Route>
      </Route>

      {/* Espace d'administration plateforme : hors du layout client, qui
          exige un tenant courant. Un administrateur plateforme n'a aucune
          raison d'etre membre d'une entreprise cliente. */}
      <Route element={<PlatformAdminRoute />}>
        <Route path="/admin/plateforme" element={<PlatformAdminPage />} />
        <Route path="/admin/breachsense" element={<AdminBreachsensePage />} />
      </Route>

      {/* Une URL inconnue renvoie vers la vitrine plutôt que vers le tableau
          de bord : un visiteur non connecté qui se trompe d'adresse doit
          atterrir sur une page qui lui parle, pas sur un écran de connexion. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
