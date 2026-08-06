export default function Card({ as: Tag = 'div', className = '', padding = 'p-6', children, ...props }) {
  return (
    <Tag
      className={`rounded-lg border border-ink-200/70 bg-surface shadow-soft ${padding} ${className}`}
      {...props}
    >
      {children}
    </Tag>
  )
}

export function CardHeader({ title, description, action, className = '' }) {
  return (
    <div className={`mb-4 flex items-start justify-between gap-4 ${className}`}>
      <div>
        <h2 className="font-display text-lg font-semibold text-ink-900">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-ink-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}
