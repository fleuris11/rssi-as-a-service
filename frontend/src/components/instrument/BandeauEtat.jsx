import { Link } from 'react-router-dom'
import { cranDe } from './crans'

/**
 * LE BANDEAU D'ÉTAT — le signal public.
 *
 * Un cran, une phrase, une seule action. Présent sur les trois surfaces du
 * produit : la vitrine (le client de démonstration), l'espace client (le
 * client), la console (la plateforme). Même composant, même grammaire, trois
 * contenus.
 *
 * Au repos il est posé sur le bâti : sombre, discret, une ligne. Quand le cran
 * atteint « critique », il SE GORGE de sa couleur. C'est le seul endroit du
 * produit où une couleur occupe une grande surface, et c'est voulu : c'est le
 * seul moment où l'on veut que le lecteur lève les yeux.
 *
 * Le glyphe et le mot accompagnent toujours la couleur : le bandeau reste
 * lisible en noir et blanc, et pour quelqu'un qui ne distingue pas le rouge.
 *
 * Rendu dans un `<aside>` nommé : il vit entre l'en-tête et le contenu, donc
 * hors de tout point de repère, et axe-core le relevait à juste titre — un
 * lecteur d'écran qui parcourt les repères sautait par-dessus le signal le
 * plus important de la page.
 */
export default function BandeauEtat({
  score,
  niveau,
  phrase,
  action,
  chargement = false,
  className = '',
}) {
  const cran = cranDe(score, niveau)
  const gorge = cran?.cle === 'critical'

  if (chargement) {
    return (
      <aside aria-label="État de surveillance" className={`sur-bati border-b border-bati-600 ${className}`}>
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2.5 sm:px-6">
          <span className="t-legende text-craie-douce">Relevé en cours…</span>
        </div>
      </aside>
    )
  }

  return (
    <aside
      aria-label="État de surveillance"
      className={`sur-bati border-b ${gorge ? 'border-transparent' : 'border-bati-600'} ${className}`}
      style={gorge ? { backgroundColor: 'var(--color-risk-critical-drape)' } : undefined}
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-2.5 sm:px-6">
        <p className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="text-[0.8125rem] leading-none"
            style={cran && !gorge ? { color: cran.trait } : undefined}
          >
            {cran?.glyphe ?? '○'}
          </span>
          <span className="t-legende text-craie">{cran?.nom ?? 'État inconnu'}</span>
        </p>

        <p className="min-w-0 flex-1 text-sm text-craie-douce">
          {phrase ?? cran?.phrase ?? 'Aucun relevé disponible pour l’instant.'}
        </p>

        {action ? (
          <Link
            to={action.vers}
            className="t-menu shrink-0 text-action-claire underline underline-offset-4 hover:text-craie"
          >
            {action.libelle}
          </Link>
        ) : null}
      </div>
    </aside>
  )
}
