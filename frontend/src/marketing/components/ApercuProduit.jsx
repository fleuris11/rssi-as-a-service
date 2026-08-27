import CaptureProduit from './CaptureProduit'

/**
 * Cadre « ceci est le produit ».
 *
 * La vitrine n'a pas le droit d'employer l'échelle de gravité — rouge, orange,
 * olive — pour décorer. Une page marketing qui teinte ses encadrés en rouge
 * parce que c'est joli détruit le sens de ces couleurs dans l'application :
 * le client finit par voir du rouge partout, donc nulle part.
 *
 * Mais la vitrine doit MONTRER ce que le produit affiche, et une reproduction
 * d'alerte en gris ne montre rien. La règle est donc de frontière, pas
 * d'interdiction :
 *
 *   - **hors de ce cadre** : bleu de marque et gris d'encre, exclusivement ;
 *   - **dans ce cadre** : les couleurs du produit, à l'identique.
 *
 * Le cadre est ce qui rend la règle tenable. Il dit au visiteur « vous
 * regardez l'écran », et il dit au développeur où s'arrête la licence.
 *
 * Volontairement plus léger que `BrowserFrame` : celui-ci accueille une
 * capture pleine page, celui-là un fragment d'interface au fil du texte.
 */
export default function ApercuProduit({
  label = 'Dans l’application',
  src,
  alt,
  children,
  className = '',
}) {
  return (
    <figure className={`overflow-hidden rounded-lg border border-ink-200 bg-surface shadow-soft ${className}`}>
      <figcaption className="flex items-center gap-2 border-b border-ink-200 bg-ink-50 px-4 py-2">
        <span className="flex gap-1" aria-hidden="true">
          <span className="size-1.5 rounded-full bg-ink-300" />
          <span className="size-1.5 rounded-full bg-ink-300" />
          <span className="size-1.5 rounded-full bg-ink-300" />
        </span>
        <span className="t-eyebrow">{label}</span>
      </figcaption>
      {/* Une capture réelle occupe tout le cadre ; le substitut CSS garde sa
          marge intérieure. */}
      {src ? (
        <CaptureProduit src={src} alt={alt}>
          <div className="p-5">{children}</div>
        </CaptureProduit>
      ) : (
        <div className="p-5">{children}</div>
      )}
    </figure>
  )
}
