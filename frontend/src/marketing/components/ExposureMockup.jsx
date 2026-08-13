/**
 * Reconstitution fidèle, en CSS, de la page Exposition telle qu'elle existe :
 * un actif, son score, son niveau, et une fuite avec sa vulgarisation.
 *
 * Sert de substitut tant qu'aucune capture réelle n'a été déposée. Les
 * valeurs affichées sont celles du tenant de démonstration, donc conformes à
 * ce qu'un prospect verra à l'écran — pas une maquette idéalisée.
 */
export default function ExposureMockup() {
  return (
    <div className="space-y-3 p-4 sm:p-5" aria-hidden="true">
      {/* Bandeau d'analyse */}
      <div className="rounded-lg border border-brand-200 bg-brand-50/60 p-3.5">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-800">Analyse</p>
        <p className="mt-1 text-[11px] leading-relaxed text-ink-700">
          Votre exposition est concentrée sur deux points : le compte de M. D., qui apparaît dans
          trois fuites distinctes, et votre webmail, dont une session active a été compromise.
        </p>
      </div>

      {/* Carte d'actif avec score */}
      <div className="rounded-lg border border-ink-200 p-3.5">
        <div className="flex items-center gap-3">
          <div className="relative size-11 shrink-0">
            <svg viewBox="0 0 48 48" className="size-full -rotate-90">
              <circle cx="24" cy="24" r="20" fill="none" strokeWidth="4" className="stroke-ink-200" />
              <circle
                cx="24"
                cy="24"
                r="20"
                fill="none"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray="94 126"
                className="stroke-critical-strong"
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center font-display text-[11px] font-semibold text-ink-900">
              75
            </span>
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-ink-900">webmail.votre-societe.fr</p>
            <p className="text-[11px] text-ink-500">Site web — 3 éléments à traiter</p>
          </div>
          <span className="ml-auto rounded-full bg-critical-subtle px-2 py-0.5 text-[10px] font-medium text-critical-strong">
            Critique
          </span>
        </div>

        {/* Une fuite, avec sa vulgarisation */}
        <div className="mt-3 rounded-md border border-ink-200/70 p-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <p className="text-[11px] font-medium text-ink-800">Sessions / cookies compromis</p>
            <span className="rounded-full bg-critical-subtle px-1.5 py-0.5 text-[10px] font-medium text-critical-strong">
              Critique
            </span>
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-ink-700">
            Un cookie de session a été volé : avec ce jeton, un attaquant entre dans le compte sans
            avoir besoin du mot de passe ni du code de double authentification.
          </p>
          <div className="mt-1.5 rounded bg-accent-100/50 px-2 py-1.5">
            <p className="text-[11px] text-accent-900">
              <span className="font-semibold">À faire : </span>
              Déconnectez toutes les sessions actives de ce compte, puis changez le mot de passe.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
