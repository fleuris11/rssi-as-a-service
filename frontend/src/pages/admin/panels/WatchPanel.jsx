import {
  AlertTriangle,
  Check,
  ExternalLink,
  Newspaper,
  RefreshCw,
  Sparkles,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import Badge from '../../../components/ui/Badge'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import EmptyState from '../../../components/ui/EmptyState'
import { SkeletonCard } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/Toast'

const STATUT_VARIANT = {
  new: 'warning',
  kept: 'brand',
  integrated: 'ok',
  dismissed: 'neutral',
}

const QUALIFICATIONS = [
  { value: 'new_requirement', label: 'Nouvelle exigence' },
  { value: 'update', label: 'Évolution d’une exigence' },
  { value: 'information', label: 'Information' },
]

function dateCourte(valeur) {
  return valeur ? new Date(valeur).toLocaleDateString('fr-FR') : '—'
}

/**
 * Le formulaire d'intégration (V2-7, ADR-034).
 *
 * Le contenu de la mesure est **saisi**, jamais repris du titre de la
 * publication : une exigence rédigée par copie d'un titre de communiqué est
 * illisible pour un dirigeant, et fausse le score. Le lien vers la source, lui,
 * est posé automatiquement — c'est le seul champ que la machine remplit.
 */
function FormulaireIntegration({ suggestion, referentiels, onIntegre, onCancel }) {
  const { showToast } = useToast()
  const [referentiel, setReferentiel] = useState(referentiels[0]?.slug || '')
  const [domaine, setDomaine] = useState('')
  const [code, setCode] = useState('')
  const [intitule, setIntitule] = useState('')
  const [enonce, setEnonce] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const complet = referentiel && domaine.trim() && code.trim() && intitule.trim() && enonce.trim()

  async function handleSubmit(event) {
    event.preventDefault()
    setEnvoi(true)
    try {
      await platformApi.integrateWatchUpdate(suggestion.id, {
        referential: referentiel,
        domain_code: domaine.trim(),
        code: code.trim(),
        official_title: intitule.trim(),
        plain_language: enonce.trim(),
      })
      showToast({ type: 'success', message: 'Mesure ajoutée, avec le lien vers sa source.' })
      onIntegre()
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible d’ajouter cette mesure.',
      })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 rounded-md border border-ink-200 bg-canvas p-3">
      <p className="text-xs text-ink-500">
        La mesure gardera le lien vers <span className="text-ink-700">{suggestion.url}</span>.
        Rédigez-la : le titre de la publication n’est pas un énoncé de mesure.
      </p>
      <div className="mt-2.5 grid gap-2.5 sm:grid-cols-2">
        <div>
          <label className="t-eyebrow" htmlFor={`ref-${suggestion.id}`}>
            Référentiel
          </label>
          <select
            id={`ref-${suggestion.id}`}
            value={referentiel}
            onChange={(event) => setReferentiel(event.target.value)}
            className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          >
            {referentiels.map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="t-eyebrow" htmlFor={`dom-${suggestion.id}`}>
            Code du domaine
          </label>
          <input
            id={`dom-${suggestion.id}`}
            value={domaine}
            onChange={(event) => setDomaine(event.target.value)}
            placeholder="sensibiliser-former"
            className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="t-eyebrow" htmlFor={`code-${suggestion.id}`}>
            Code de la mesure
          </label>
          <input
            id={`code-${suggestion.id}`}
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="43"
            className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="t-eyebrow" htmlFor={`titre-${suggestion.id}`}>
            Intitulé officiel
          </label>
          <input
            id={`titre-${suggestion.id}`}
            value={intitule}
            onChange={(event) => setIntitule(event.target.value)}
            className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          />
        </div>
      </div>
      <div className="mt-2.5">
        <label className="t-eyebrow" htmlFor={`enonce-${suggestion.id}`}>
          Énoncé en langage clair (ce que lira le dirigeant)
        </label>
        <textarea
          id={`enonce-${suggestion.id}`}
          rows={2}
          value={enonce}
          onChange={(event) => setEnonce(event.target.value)}
          placeholder="Avez-vous encadré l’usage des outils d’IA générative par vos équipes ?"
          className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
        />
      </div>
      <div className="mt-2.5 flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" variant="primary" size="sm" loading={envoi} disabled={!complet}>
          Ajouter la mesure
        </Button>
      </div>
    </form>
  )
}

function Suggestion({ suggestion, referentiels, onAction, occupe }) {
  const [integration, setIntegration] = useState(false)

  return (
    <li className="py-3.5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-800">{suggestion.title}</p>
          <p className="mt-0.5 text-xs text-ink-500">
            {suggestion.source_publisher} · publié le {dateCourte(suggestion.published_at)} ·
            détecté le {dateCourte(suggestion.detected_at)}
          </p>
          {/* Le lien vers la source OFFICIELLE : c'est lui qu'on ouvre avant
              de décider, et il reste la référence. */}
          <a
            href={suggestion.url}
            target="_blank"
            rel="noreferrer noopener"
            className="transition-smooth mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-700 underline underline-offset-2 hover:text-brand-800"
          >
            Ouvrir la publication officielle
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        </div>
        <Badge variant={STATUT_VARIANT[suggestion.status]}>{suggestion.status_label}</Badge>
      </div>

      {suggestion.source_format === 'page' && (
        <p className="mt-1.5 text-xs italic text-ink-500">
          Cette source ne publie pas de flux : nous savons que la page a changé, pas ce qui y a
          changé. Ouvrez-la pour voir.
        </p>
      )}

      {suggestion.source_excerpt && (
        <p className="mt-2 max-h-24 overflow-y-auto rounded-md bg-ink-50 px-3 py-2 text-xs text-ink-600">
          {suggestion.source_excerpt}
        </p>
      )}

      {/* Le résumé machine vient À CÔTÉ du texte source, jamais à sa place,
          et il est identifié comme tel. */}
      {suggestion.ai_summary && (
        <div className="mt-2 rounded-md border border-brand-200 bg-brand-50 px-3 py-2">
          <p className="text-xs font-medium text-brand-800">
            Résumé par IA — {dateCourte(suggestion.ai_summary_at)} · à vérifier contre le texte
            source
          </p>
          <p className="mt-1 text-sm text-ink-700">{suggestion.ai_summary}</p>
        </div>
      )}

      {suggestion.integrated_measures.length > 0 && (
        <p className="mt-2 text-xs text-ok-strong">
          Intégrée :{' '}
          {suggestion.integrated_measures
            .map((mesure) => `${mesure.referential} — ${mesure.code}`)
            .join(', ')}
        </p>
      )}

      {suggestion.status !== 'integrated' && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {!suggestion.ai_summary && suggestion.source_excerpt && (
            <Button
              variant="ghost"
              size="sm"
              icon={Sparkles}
              loading={occupe === `summary-${suggestion.id}`}
              onClick={() => onAction(suggestion, 'summary')}
            >
              Résumer
            </Button>
          )}
          {suggestion.status !== 'kept' && (
            <Button
              variant="secondary"
              size="sm"
              icon={Check}
              loading={occupe === `kept-${suggestion.id}`}
              onClick={() => onAction(suggestion, 'kept')}
            >
              Retenir
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIntegration((ouvert) => !ouvert)}
            disabled={referentiels.length === 0}
          >
            Ajouter une mesure…
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={X}
            loading={occupe === `dismissed-${suggestion.id}`}
            onClick={() => onAction(suggestion, 'dismissed')}
          >
            Écarter
          </Button>
          {QUALIFICATIONS.map((qualification) => (
            <button
              key={qualification.value}
              type="button"
              onClick={() => onAction(suggestion, 'kept', qualification.value)}
              className={`transition-smooth rounded-full border px-2.5 py-1 text-xs ${
                suggestion.kind === qualification.value
                  ? 'border-brand-600 bg-brand-50 text-ink-800'
                  : 'border-ink-200 text-ink-500 hover:border-brand-300'
              }`}
            >
              {qualification.label}
            </button>
          ))}
        </div>
      )}

      {integration && (
        <FormulaireIntegration
          suggestion={suggestion}
          referentiels={referentiels}
          onCancel={() => setIntegration(false)}
          onIntegre={() => {
            setIntegration(false)
            onAction(suggestion, 'refresh')
          }}
        />
      )}
    </li>
  )
}

/**
 * La file de veille (V2-7, ADR-034).
 *
 * Ce que cet écran ne fait pas, et c'est l'essentiel : **rien n'entre dans un
 * référentiel sans qu'un humain l'ait lu et rédigé**. La collecte ne produit
 * que des suggestions ; le bouton « Ajouter une mesure » demande un
 * référentiel, un domaine, un code, un intitulé et un énoncé, tous saisis.
 */
export default function WatchPanel({ referentiels = [] }) {
  const { showToast } = useToast()
  const [file, setFile] = useState(null)
  const [sources, setSources] = useState([])
  const [filtre, setFiltre] = useState('new')
  const [occupe, setOccupe] = useState(null)

  const charger = useCallback(async () => {
    const [queue, listeSources] = await Promise.all([
      platformApi.watchQueue(filtre ? { status: filtre } : {}),
      platformApi.watchSources(),
    ])
    setFile(queue.data)
    setSources(listeSources.data)
  }, [filtre])

  useEffect(() => {
    charger()
  }, [charger])

  async function handleAction(suggestion, action, kind) {
    if (action === 'refresh') {
      await charger()
      return
    }
    setOccupe(`${action}-${suggestion.id}`)
    try {
      if (action === 'summary') {
        await platformApi.summarizeWatchUpdate(suggestion.id)
      } else {
        await platformApi.reviewWatchUpdate(suggestion.id, {
          status: action,
          ...(kind ? { kind } : {}),
        })
      }
      await charger()
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Action impossible.',
      })
    } finally {
      setOccupe(null)
    }
  }

  async function relancer(slug) {
    setOccupe(`poll-${slug}`)
    try {
      const response = await platformApi.pollWatchSource(slug)
      await charger()
      showToast({
        type: 'success',
        message: response.data.created
          ? `${response.data.created} nouveauté(s) détectée(s).`
          : 'Aucune nouveauté depuis le dernier passage.',
      })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Cette source n’a pas répondu.',
      })
    } finally {
      setOccupe(null)
    }
  }

  if (!file) return <SkeletonCard />

  const enPanne = file.health.failing
  const aConfigurer = file.health.unconfigured

  return (
    <div className="space-y-4">
      <Card padding="p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap gap-6">
            <div>
              <p className="t-eyebrow">À examiner</p>
              <p className="font-display text-2xl font-semibold text-ink-900">
                {file.summary.new}
              </p>
            </div>
            <div>
              <p className="t-eyebrow">Retenues</p>
              <p className="font-display text-2xl font-semibold text-ink-900">
                {file.summary.kept}
              </p>
            </div>
            <div>
              <p className="t-eyebrow">Intégrées</p>
              <p className="font-display text-2xl font-semibold text-ink-900">
                {file.summary.integrated}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {[
              { value: 'new', label: 'À examiner' },
              { value: 'kept', label: 'Retenues' },
              { value: 'integrated', label: 'Intégrées' },
              { value: 'dismissed', label: 'Écartées' },
              { value: '', label: 'Toutes' },
            ].map((onglet) => (
              <button
                key={onglet.value || 'all'}
                type="button"
                onClick={() => setFiltre(onglet.value)}
                aria-pressed={filtre === onglet.value}
                className={`transition-smooth rounded-full px-3 py-1.5 text-xs ${
                  filtre === onglet.value
                    ? 'bg-brand-600 text-white'
                    : 'bg-ink-100 text-ink-600 hover:text-brand-700'
                }`}
              >
                {onglet.label}
              </button>
            ))}
          </div>
        </div>
        {/* Ce que le produit promet, mot pour mot. Ni exhaustive, ni temps
            réel : la phrase est portée par le serveur pour qu'elle ne dérive
            pas d'un écran à l'autre. */}
        <p className="mt-3 text-xs text-ink-500">{file.summary.promise}</p>
      </Card>

      {(enPanne.length > 0 || aConfigurer.length > 0) && (
        <Card padding="p-4">
          <CardHeader
            title="État des sources"
            description="Une source qui échoue en silence est pire qu'une source absente : on croit surveiller."
          />
          <ul className="space-y-1.5 text-sm">
            {enPanne.map((source) => (
              <li key={source.slug} className="flex items-start gap-2 text-critical-strong">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                <span>
                  {source.name} — {source.consecutive_failures} échecs consécutifs
                  {source.last_error ? ` (${source.last_error})` : ''}
                </span>
              </li>
            ))}
            {aConfigurer.map((source) => (
              <li key={source.slug} className="flex items-start gap-2 text-ink-600">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning-strong" aria-hidden="true" />
                <span>{source.name} — à configurer (aucune adresse de flux)</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card padding="p-0">
        <div className="p-5 pb-0">
          <CardHeader title="Suggestions" />
        </div>
        {file.results.length === 0 ? (
          <div className="p-5 pt-0">
            <EmptyState
              icon={Newspaper}
              title="Rien à examiner"
              description="Les publications détectées depuis le dernier passage apparaîtront ici."
            />
          </div>
        ) : (
          <ul className="divide-y divide-ink-100 px-5 pb-3">
            {file.results.map((suggestion) => (
              <Suggestion
                key={suggestion.id}
                suggestion={suggestion}
                referentiels={referentiels}
                onAction={handleAction}
                occupe={occupe}
              />
            ))}
          </ul>
        )}
      </Card>

      <Card padding="p-0">
        <div className="p-5 pb-0">
          <CardHeader
            title="Sources suivies"
            description="Uniquement des sources primaires : l'organisme qui publie le texte, jamais celui qui le commente."
          />
        </div>
        <div className="overflow-x-auto px-5 pb-4">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-ink-500">
                <th className="py-2 pr-4 font-medium">Source</th>
                <th className="py-2 pr-4 font-medium">Format</th>
                <th className="py-2 pr-4 font-medium">Rythme attendu</th>
                <th className="py-2 pr-4 font-medium">Dernier passage</th>
                <th className="py-2 font-medium">&nbsp;</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {sources.map((source) => (
                <tr key={source.slug}>
                  <td className="py-2 pr-4">
                    <p className="text-ink-800">
                      {source.publisher} — {source.name}
                    </p>
                    <p className="max-w-xl text-xs text-ink-500">{source.scope_note}</p>
                  </td>
                  <td className="py-2 pr-4 text-ink-600">{source.format_label}</td>
                  <td className="py-2 pr-4 text-ink-600">{source.expected_frequency || '—'}</td>
                  <td className="py-2 pr-4 text-ink-600">
                    {dateCourte(source.last_success_at)}
                    {!source.is_healthy && (
                      <span className="block text-xs text-critical-strong">
                        {source.consecutive_failures} échec(s)
                      </span>
                    )}
                    {source.needs_configuration && (
                      <span className="block text-xs text-warning-strong">à configurer</span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={RefreshCw}
                      loading={occupe === `poll-${source.slug}`}
                      disabled={source.needs_configuration}
                      onClick={() => relancer(source.slug)}
                    >
                      Relancer
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
