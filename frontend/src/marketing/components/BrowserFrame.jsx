/**
 * Cadre de navigateur stylisé accueillant une capture d'écran réelle du
 * produit. Tant qu'aucune capture n'est déposée (voir
 * `public/screenshots/README.md`), affiche un substitut composé en CSS/SVG
 * plutôt qu'une image d'illustration générique : mieux vaut un schéma
 * honnête qu'une photo qui ne montre pas le produit.
 */
export default function BrowserFrame({ src, alt, caption, children, className = '' }) {
  return (
    <figure className={`overflow-hidden ${className}`}>
      <div className="overflow-hidden rounded-xl border border-ink-200 bg-surface shadow-elevated">
        <div className="flex items-center gap-2 border-b border-ink-200 bg-ink-50 px-3.5 py-2.5">
          <span className="flex gap-1.5" aria-hidden="true">
            <span className="size-2.5 rounded-full bg-ink-300" />
            <span className="size-2.5 rounded-full bg-ink-300" />
            <span className="size-2.5 rounded-full bg-ink-300" />
          </span>
          <span
            aria-hidden="true"
            className="ml-2 flex-1 truncate rounded bg-surface px-2.5 py-1 font-mono text-[11px] text-ink-500"
          >
            rssiasservice.online/exposition
          </span>
        </div>
        <div className="bg-surface">
          {src ? (
            <img src={src} alt={alt} loading="lazy" className="block w-full" />
          ) : (
            children
          )}
        </div>
      </div>
      {caption && (
        <figcaption className="mt-2.5 text-xs text-ink-500">{caption}</figcaption>
      )}
    </figure>
  )
}
