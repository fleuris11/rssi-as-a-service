// `tone` : tous les états vides ne disent pas la même chose.
//
// « Aucune fuite détectée » n'est pas une absence de données, c'est une bonne
// nouvelle — et l'écrire en gris, avec un pictogramme d'alerte, la faisait
// lire comme une panne. Sur un produit dont la matière est le risque, le
// client doit pouvoir distinguer d'un coup d'œil « rien à afficher » de
// « rien à craindre ».
//
// La couleur n'est jamais seule porteuse : le pictogramme et le texte disent
// la même chose.
const TONS = {
  neutral: 'bg-brand-100 text-brand-700',
  positive: 'bg-risk-calm-surface text-risk-calm',
}

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  tone = 'neutral',
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-lg border border-dashed border-ink-200 bg-ink-50/50 px-6 py-12 text-center ${className}`}
    >
      {Icon && (
        <div
          className={`mb-4 flex size-12 items-center justify-center rounded-full ${TONS[tone] || TONS.neutral}`}
        >
          <Icon className="size-6" aria-hidden="true" />
        </div>
      )}
      <p className="font-display text-base font-semibold text-ink-900">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm text-ink-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
