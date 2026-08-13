import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import LandingPage from './marketing/pages/LandingPage'

// Le code de l'application est chargé À LA DEMANDE : un visiteur qui arrive
// sur la vitrine ne doit pas télécharger le tableau de bord, le kanban et les
// graphiques qu'il ne verra peut-être jamais. La vitrine, elle, est importée
// normalement — c'est la première page, la charger en différé ajouterait un
// aller-retour réseau avant le premier pixel.
const DemoRequestPage = lazy(() => import('./marketing/pages/DemoRequestPage'))
const LegalPage = lazy(() => import('./marketing/pages/LegalPage'))
const AppRoutes = lazy(() => import('./AppRoutes'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))

function RouteFallback() {
  // Volontairement discret : un écran de chargement voyant sur une transition
  // de quelques dizaines de millisecondes est plus dérangeant que rien.
  return <div className="min-h-screen bg-surface" aria-busy="true" />
}

function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Vitrine publique */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/demonstration" element={<DemoRequestPage />} />
        <Route path="/mentions-legales" element={<LegalPage page="legal" />} />
        <Route path="/confidentialite" element={<LegalPage page="privacy" />} />
        <Route path="/contact" element={<LegalPage page="contact" />} />

        {/* Authentification */}
        <Route path="/connexion" element={<LoginPage />} />
        <Route path="/inscription" element={<RegisterPage />} />

        {/* Application */}
        <Route path="/*" element={<AppRoutes />} />
      </Routes>
    </Suspense>
  )
}

export default App
