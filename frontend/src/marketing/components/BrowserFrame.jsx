/**
 * Cadre de navigateur autour d'une capture réelle du produit.
 *
 * Tant qu'aucune capture n'est déposée (voir `public/screenshots/README.md`),
 * affiche un substitut composé en CSS/SVG plutôt qu'une image d'illustration
 * générique : mieux vaut un schéma honnête qu'une photo qui ne montre pas le
 * produit.
 *
 * La barre de titre porte le BÂTI, comme le rail de l'application : le cadre
 * est la matière du produit, pas un ornement gris. L'adresse est en Chivo
 * Mono — c'est une chaîne exacte, donc une mesure.
 *
 * Largeur d'affichage maximale mesurée : 728 px (point de rupture 768 px, en
 * colonne unique). Les captures sont donc à produire en 1456 px de large.
 */
import CaptureProduit from './CaptureProduit'

export default function BrowserFrame({
  src,
  alt,
  caption,
  url = 'rssiasservice.online',
  children,
  className = '',
}) {
  return (
    <figure className={`overflow-hidden ${className}`}>
      <div className="overflow-hidden rounded-lg border border-bati-700 bg-surface shadow-elevated">
        <div className="flex items-center gap-2 bg-bati-800 px-3 py-2">
          <span className="flex gap-1.5" aria-hidden="true">
            <span className="size-2 rounded-full bg-bati-500" />
            <span className="size-2 rounded-full bg-bati-500" />
            <span className="size-2 rounded-full bg-bati-500" />
          </span>
          <span
            aria-hidden="true"
            className="n ml-2 flex-1 truncate rounded-sm bg-bati-700 px-2.5 py-1 text-[11px] text-craie-douce"
          >
            {url}
          </span>
        </div>
        <div className="bg-surface">
          <CaptureProduit src={src} alt={alt}>
            {children}
          </CaptureProduit>
        </div>
      </div>
      {caption && <figcaption className="t-meta mt-2.5">{caption}</figcaption>}
    </figure>
  )
}
