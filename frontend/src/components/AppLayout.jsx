import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { EtatSurveillanceProvider, useEtatSurveillance } from '../context/EtatSurveillance'
import BandeauEtat from './instrument/BandeauEtat'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

/**
 * La coque de l'application : un bâti graphite à gauche, un bandeau d'état en
 * haut, une face d'instrument claire au milieu.
 *
 * Le bandeau est le même composant que sur la vitrine et la console. C'est ce
 * qui fait qu'on reconnaît l'endroit d'un écran à l'autre, et c'est la seule
 * chose que le dirigeant doit lire s'il ne lit qu'une ligne.
 */

function Bandeau() {
  const { chargement, niveau, phrase, action } = useEtatSurveillance()
  return (
    <BandeauEtat chargement={chargement} niveau={niveau} phrase={phrase} action={action} />
  )
}

export default function AppLayout() {
  const [menuOuvert, setMenuOuvert] = useState(false)

  return (
    <EtatSurveillanceProvider>
      <div className="min-h-screen bg-canvas">
        {/* Tablette (md-lg) : rail d'icônes. Bureau (lg+) : rail complet.
            Téléphone : masqué, remplacé par le tiroir ci-dessous. Deux
            instances sont montées et basculées par `hidden` responsive, ce qui
            retire l'inactive de l'arbre d'accessibilité — pas de lien en
            double pour un lecteur d'écran, le clavier ou Playwright. */}
        <aside className="fixed inset-y-0 left-0 z-20 hidden md:block md:w-20 lg:w-[236px]">
          <div className="h-full lg:hidden">
            <Sidebar collapsed />
          </div>
          <div className="hidden h-full lg:block">
            <Sidebar />
          </div>
        </aside>

        {menuOuvert && (
          <div className="fixed inset-0 z-40 md:hidden">
            <button
              type="button"
              aria-label="Fermer le menu"
              onClick={() => setMenuOuvert(false)}
              className="absolute inset-0 bg-ink-950/60"
            />
            <div className="relative h-full w-72 shadow-elevated">
              <Sidebar onNavigate={() => setMenuOuvert(false)} />
            </div>
          </div>
        )}

        <div className="md:pl-20 lg:pl-[236px]">
          <Topbar onOpenMenu={() => setMenuOuvert(true)} />
          <Bandeau />
          <main className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            <Outlet />
          </main>
        </div>
      </div>
    </EtatSurveillanceProvider>
  )
}
