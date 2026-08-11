import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import StaffRoute from './components/StaffRoute'
import ActionPlanPage from './pages/ActionPlanPage'
import AdminBreachsensePage from './pages/AdminBreachsensePage'
import AssistantPage from './pages/AssistantPage'
import CompromisesPage from './pages/CompromisesPage'
import DashboardPage from './pages/DashboardPage'
import DiagnosticPage from './pages/DiagnosticPage'
import DocumentsPage from './pages/DocumentsPage'
import ExposurePage from './pages/ExposurePage'
import LoginPage from './pages/LoginPage'
import NotificationPreferencesPage from './pages/NotificationPreferencesPage'
import RegisterPage from './pages/RegisterPage'
import ResultsPage from './pages/ResultsPage'
import SurveillancePage from './pages/SurveillancePage'
import TwoFactorSettingsPage from './pages/TwoFactorSettingsPage'

function App() {
  return (
    <Routes>
      <Route path="/connexion" element={<LoginPage />} />
      <Route path="/inscription" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
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
          <Route element={<StaffRoute />}>
            <Route path="/admin/breachsense" element={<AdminBreachsensePage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/tableau-de-bord" replace />} />
    </Routes>
  )
}

export default App
