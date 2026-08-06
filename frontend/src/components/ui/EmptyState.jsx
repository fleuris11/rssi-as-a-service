export default function EmptyState({ icon: Icon, title, description, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-lg border border-dashed border-ink-200 bg-ink-50/50 px-6 py-12 text-center ${className}`}>
      {Icon && (
        <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <Icon className="size-6" aria-hidden="true" />
        </div>
      )}
      <p className="font-display text-base font-semibold text-ink-900">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm text-ink-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
