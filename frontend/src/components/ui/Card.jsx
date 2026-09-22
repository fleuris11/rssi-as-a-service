/**
 * LE PANNEAU D'INSTRUMENT.
 *
 * Ce composant s'appelait « carte », et c'était le problème : six cartes de
 * forme identique par écran, toutes légèrement décollées du fond, donc aucune
 * plus importante qu'une autre. Un panneau de pupitre, lui, a une tête réglée
 * qui le nomme et un corps qui porte la mesure.
 *
 * La profondeur vient d'un FILET d'1 px, jamais d'une ombre au repos. L'ombre
 * est réservée à ce qui flotte vraiment — modale, menu, infobulle — et reste
 * disponible par `elevation`.
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
      className={`rounded-md border border-ink-200 bg-surface ${
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
        <h2 className="t-title">{title}</h2>
        {sousTitre && <p className="t-meta mt-0.5">{sousTitre}</p>}
      </div>
      {action}
    </div>
  )
}
