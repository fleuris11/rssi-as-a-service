import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

/**
 * Les trois pièces communes à toutes les pages de la vitrine.
 *
 * Dans leur propre module, et non dans `sections.jsx` : l'accueil n'a besoin
 * que d'elles, et les importer depuis `sections.jsx` tirerait le tableau
 * comparatif des offres et son appel d'API dans le lot principal — 8 ko que
 * personne ne demande tant qu'il reste sur l'accueil. Mesuré : le lot
 * principal est repassé de 316,5 ko à 309,6 ko en déplaçant ces trois
 * fonctions ici.
 */

/**
 * Un acte de la page. Le fond alterne entre la face d'instrument et le bâti :
 * c'est ce qui donne son rythme au défilement, un passage dense méritant un
 * passage calme.
 */
export function Acte({ id, fond = 'face', children, className = '' }) {
  const fonds = {
    face: 'bg-canvas',
    haute: 'bg-surface',
    creuse: 'bg-ink-100',
    bati: 'sur-bati',
  }
  return (
    <section
      id={id}
      className={`${fonds[fond]} ${className}`}
      style={{ paddingBlock: 'var(--rythme-section)' }}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6">{children}</div>
    </section>
  )
}

/** L'action principale. Une seule par page, répétée à l'identique. */
export function Action({ children = 'Demander une démonstration' }) {
  return (
    <Link
      to="/demonstration"
      className="transition-smooth inline-flex items-center gap-2 rounded-md bg-brand-600 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-700"
    >
      {children}
      <ArrowRight className="size-4" aria-hidden="true" />
    </Link>
  )
}

export function TeteDePage({ titre, chapeau }) {
  return (
    <Acte fond="haute">
      <h1 className="t-display max-w-3xl">{titre}</h1>
      {chapeau && <p className="t-lead mt-5">{chapeau}</p>}
    </Acte>
  )
}
