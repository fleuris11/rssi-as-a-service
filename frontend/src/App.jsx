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
// Les pages secondaires de la vitrine portent le détail que l'accueil ne garde
// plus. Chargées à la demande : un visiteur qui reste sur l'accueil ne
// télécharge pas le tableau comparatif des offres ni la liste des questions.
const FonctionnalitesPage = lazy(() => import('./marketing/pages/FonctionnalitesPage'))
const SecuriteProduitPage = lazy(() => import('./marketing/pages/SecuriteProduitPage'))
const OffresPage = lazy(() => import('./marketing/pages/OffresPage'))
const QuestionsPage = lazy(() => import('./marketing/pages/QuestionsPage'))
const AppRoutes = lazy(() => import('./AppRoutes'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const InvitationPage = lazy(() => import('./pages/InvitationPage'))
const FormationPage = lazy(() => import('./pages/FormationPage'))
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
        <Route path="/fonctionnalites" element={<FonctionnalitesPage />} />
        {/* `/securite-du-produit` et non `/securite` : l'application occupe
            déjà `/securite` (réglages de double authentification), et deux
            pages sur la même adresse est un défaut qui ne se voit qu'une fois
            connecté. */}
        <Route path="/securite-du-produit" element={<SecuriteProduitPage />} />
        <Route path="/offres" element={<OffresPage />} />
        <Route path="/questions" element={<QuestionsPage />} />
        <Route path="/demonstration" element={<DemoRequestPage />} />
        <Route path="/mentions-legales" element={<LegalPage page="legal" />} />
        <Route path="/confidentialite" element={<LegalPage page="privacy" />} />
        <Route path="/conditions-generales" element={<LegalPage page="terms" />} />
        <Route path="/securite-donnees" element={<LegalPage page="security" />} />
        <Route path="/contact" element={<LegalPage page="contact" />} />

        {/* Authentification */}
        <Route path="/connexion" element={<LoginPage />} />
        <Route path="/inscription" element={<RegisterPage />} />
        {/* Lien d'invitation : public par construction, la personne invitée
            n'a pas encore de mot de passe. */}
        <Route path="/invitation/:token" element={<InvitationPage />} />
        {/* Parcours de formation d'un salarié (F1) : public par construction.
            Le salarié n'a pas de compte — c'est le jeton du lien qui
            l'autorise. Déclarée AVANT la route attrape-tout de l'application,
            qui exigerait une session et le renverrait vers la connexion. */}
        <Route path="/formation/:token" element={<FormationPage />} />

        {/* Application */}
        <Route path="/*" element={<AppRoutes />} />
      </Routes>
    </Suspense>
  )
}

export default App
