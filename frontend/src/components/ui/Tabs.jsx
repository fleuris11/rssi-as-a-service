/**
 * Une barre d'onglets qui DÉFILE quand elle ne tient pas.
 *
 * La console en compte neuf : à 390 px ils totalisaient 1 155 px et
 * élargissaient la page entière, sans aucun moyen d'atteindre les derniers.
 * Un `overflow-x-auto` suffit à contenir la barre ; les onglets étant eux-
 * mêmes focalisables, la zone est atteignable au clavier sans `tabIndex`
 * supplémentaire — c'est exactement l'exception que prévoit la règle
 * `scrollable-region-focusable`.
 *
 * `shrink-0` sur chaque onglet : sans lui, flexbox les comprime au lieu de
 * faire défiler, et les libellés se coupent en deux lignes illisibles.
 */
export default function Tabs({ tabs, activeId, onChange, className = '' }) {
  return (
    <div className={`overflow-x-auto border-b border-ink-200 ${className}`}>
      <div role="tablist" className="flex w-max gap-1">
        {tabs.map((tab) => {
          const actif = tab.id === activeId
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={actif}
              onClick={() => onChange(tab.id)}
              className={`transition-smooth t-menu -mb-px shrink-0 whitespace-nowrap border-b-2 px-3 py-2 ${
                actif
                  ? 'border-brand-600 text-ink-900'
                  : 'border-transparent text-ink-600 hover:text-ink-900'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
