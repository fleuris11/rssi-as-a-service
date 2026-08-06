import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import ActionPlanPage from './pages/ActionPlanPage'
import AssistantPage from './pages/AssistantPage'
import DashboardPage from './pages/DashboardPage'
import DiagnosticPage from './pages/DiagnosticPage'
import DocumentsPage from './pages/DocumentsPage'
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
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/assistant" element={<AssistantPage />} />
          <Route path="/preferences" element={<NotificationPreferencesPage />} />
          <Route path="/securite" element={<TwoFactorSettingsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/tableau-de-bord" replace />} />
    </Routes>
  )
}

export default App
