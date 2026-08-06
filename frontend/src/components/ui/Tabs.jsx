export default function Tabs({ tabs, activeId, onChange, className = '' }) {
  return (
    <div role="tablist" className={`flex gap-1 border-b border-ink-200 ${className}`}>
      {tabs.map((tab) => {
        const isActive = tab.id === activeId
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={`transition-smooth -mb-px border-b-2 px-3 py-2 text-sm font-medium outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand-600 ${
              isActive
                ? 'border-accent-600 text-ink-900'
                : 'border-transparent text-ink-500 hover:text-ink-800'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
