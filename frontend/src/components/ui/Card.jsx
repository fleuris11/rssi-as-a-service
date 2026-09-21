/**
 * Le trait plutôt que l'ombre (refonte visuelle).
 *
 * L'ombre au repos fabriquait un relief qui ne correspondait à aucune
 * profondeur réelle : six cartes par écran, toutes légèrement décollées du
 * fond, donc aucune plus importante qu'une autre. Le filet suffit à poser une
 * surface ; l'ombre est réservée à ce qui flotte vraiment — modale, menu,
 * infobulle — et reste disponible par `elevation`.
 */
export default function Card({
  as: Tag = 'div',
  className = '',
  padding = 'p-6',
  elevation = false,
  children,
  ...props
}) {
  return (
    <Tag
      className={`rounded-lg border border-ink-200 bg-surface ${
        elevation ? 'shadow-elevated' : ''
      } ${padding} ${className}`}
      {...props}
    >
      {children}
    </Tag>
  )
}

/**
 * `subtitle` est accepté au même titre que `description`. Il ne l'était pas :
 * six en-têtes le passaient (dont les questions des courbes de la page
 * Rapports) et le composant l'ignorait sans rien dire — ces phrases n'ont
 * jamais été affichées. Trouvé au lot C en écrivant le test qui cherche la
 * question d'une courbe.
 */
export function CardHeader({ title, description, subtitle, action, className = '' }) {
  const sousTitre = description ?? subtitle
  return (
    <div className={`mb-4 flex items-start justify-between gap-4 ${className}`}>
      <div>
        <h2 className="font-display text-lg font-semibold text-ink-900">{title}</h2>
        {sousTitre && <p className="mt-0.5 text-sm text-ink-500">{sousTitre}</p>}
      </div>
      {action}
    </div>
  )
}
