import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi } from '../api/endpoints'

const STATUS_LABELS = {
  generating: 'Génération en cours…',
  draft: 'Brouillon',
  validated: 'Validé',
  failed: 'Échec',
}

const STATUS_COLOR = {
  generating: 'bg-slate-400',
  draft: 'bg-amber-500',
  validated: 'bg-emerald-500',
  failed: 'bg-red-500',
}

const DOCUMENT_TYPE_LABELS = { it_charter: 'Charte informatique' }

function usePolling() {
  const timeoutRef = useRef(null)

  useEffect(() => () => clearTimeout(timeoutRef.current), [])

  const poll = useCallback((jobId, onSettled) => {
    async function tick() {
      try {
        const response = await aiApi.getJob(jobId)
        if (response.data.status === 'done' || response.data.status === 'failed') {
          onSettled(response.data)
          return
        }
      } catch {
        // Hiccup réseau ponctuel — le job existe toujours côté serveur, on continue.
      }
      timeoutRef.current = setTimeout(tick, 2000)
    }
    tick()
  }, [])

  return poll
}

function AISettingsBanner({ settings, onToggle, toggling }) {
  if (!settings) return null
  const { ai_enabled: aiEnabled, quota } = settings
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium text-slate-800">
            IA {aiEnabled ? 'activée' : 'désactivée'} pour cette entreprise
          </p>
          {aiEnabled && quota && (
            <p className="mt-1 text-xs text-slate-500">
              Quota mensuel : {quota.tokens_used.toLocaleString('fr-FR')} /{' '}
              {quota.monthly_token_limit.toLocaleString('fr-FR')} tokens (
              {quota.remaining_tokens.toLocaleString('fr-FR')} restants)
            </p>
          )}
        </div>
        <button
          type="button"
          disabled={toggling}
          onClick={() => onToggle(!aiEnabled)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-400 disabled:opacity-50"
        >
          {aiEnabled ? 'Désactiver l’IA' : 'Activer l’IA'}
        </button>
      </div>
    </div>
  )
}

function PreviewPanel() {
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  async function handleToggle() {
    if (!open && !preview) {
      setLoading(true)
      setError('')
      try {
        const response = await aiApi.previewCharter()
        setPreview(response.data)
      } catch {
        setError('Impossible de charger l’aperçu.')
      } finally {
        setLoading(false)
      }
    }
    setOpen((o) => !o)
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
      <button
        type="button"
        onClick={handleToggle}
        className="text-xs font-medium text-slate-600 underline decoration-dotted underline-offset-2"
      >
        {open ? 'Masquer' : 'Voir'} les données qui seraient transmises à l’IA
      </button>
      <p className="mt-1 text-xs text-slate-400">
        Transparence (US-4.3) : ces données sont pseudonymisées avant tout appel — aucun nom
        d’entreprise, de personne, d’email ou de domaine réel n’est envoyé.
      </p>
      {open && (
        <div className="mt-2">
          {loading && <p className="text-xs text-slate-400">Chargement…</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}
          {preview && (
            <pre className="max-h-64 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">
              {JSON.stringify(preview, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

function DocumentEditor({ document: doc, onUpdated }) {
  const [content, setContent] = useState(doc.content_markdown)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setContent(doc.content_markdown)
    setSaved(false)
  }, [doc.id, doc.content_markdown])

  const isValidated = doc.status === 'validated'
  const isGenerating = doc.status === 'generating'

  async function handleSave() {
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const response = await aiApi.updateDocument(doc.id, content)
      onUpdated(response.data)
      setSaved(true)
    } catch {
      setError('Impossible d’enregistrer les modifications.')
    } finally {
      setSaving(false)
    }
  }

  async function handleValidate() {
    setSaving(true)
    setError('')
    try {
      const response = await aiApi.validateDocument(doc.id)
      onUpdated(response.data)
    } catch {
      setError('Impossible de valider ce document.')
    } finally {
      setSaving(false)
    }
  }

  async function handleExport() {
    setError('')
    try {
      const response = await aiApi.exportDocument(doc.id)
      const url = URL.createObjectURL(response.data)
      const link = window.document.createElement('a')
      link.href = url
      link.download = `${doc.type}-v${doc.version}.md`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Impossible d’exporter ce document.')
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-slate-800">
            {DOCUMENT_TYPE_LABELS[doc.type] || doc.type} — v{doc.version}
          </p>
          <span
            className={`mt-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-white ${STATUS_COLOR[doc.status]}`}
          >
            {STATUS_LABELS[doc.status]}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleExport}
            disabled={isGenerating || !content}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:border-slate-400 disabled:opacity-50"
          >
            Exporter (.md)
          </button>
          {!isValidated && !isGenerating && (
            <>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:border-slate-400 disabled:opacity-50"
              >
                Enregistrer
              </button>
              <button
                type="button"
                onClick={handleValidate}
                disabled={saving}
                className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                Valider
              </button>
            </>
          )}
        </div>
      </div>

      {isGenerating ? (
        <p className="mt-4 text-sm text-slate-500">
          Génération en cours par l’IA (30 à 60 secondes)…
        </p>
      ) : (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          readOnly={isValidated}
          rows={16}
          className="mt-4 w-full rounded-md border border-slate-300 p-3 font-mono text-xs disabled:bg-slate-50"
        />
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {saved && <p className="mt-2 text-sm text-emerald-600">Modifications enregistrées.</p>}
    </div>
  )
}

export default function DocumentsPage() {
  const [settings, setSettings] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [togglingAI, setTogglingAI] = useState(false)
  const [error, setError] = useState('')
  const poll = usePolling()

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [settingsRes, documentsRes] = await Promise.all([
        aiApi.getSettings(),
        aiApi.listDocuments(),
      ])
      setSettings(settingsRes.data)
      setDocuments(documentsRes.data.results)
    } catch (err) {
      if (err.response?.status !== 403) {
        setError('Impossible de charger les documents.')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleToggleAI(nextValue) {
    setTogglingAI(true)
    try {
      const response = await aiApi.updateSettings({ ai_enabled: nextValue })
      setSettings(response.data)
      if (nextValue) load()
    } catch {
      setError('Seul un administrateur de l’entreprise peut activer/désactiver l’IA.')
    } finally {
      setTogglingAI(false)
    }
  }

  async function handleGenerate() {
    setGenerating(true)
    setError('')
    try {
      const response = await aiApi.generateDocument('it_charter')
      const { document, job } = response.data
      setDocuments((docs) => [document, ...docs])
      setSelectedId(document.id)
      poll(job.id, async () => {
        const refreshed = await aiApi.getDocument(document.id)
        setDocuments((docs) => docs.map((d) => (d.id === document.id ? refreshed.data : d)))
        setGenerating(false)
      })
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(detail || 'Impossible de lancer la génération.')
      setGenerating(false)
    }
  }

  const selectedDocument = documents.find((d) => d.id === selectedId) || documents[0] || null

  if (loading) {
    return <p className="text-slate-500">Chargement…</p>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
        <p className="mt-1 text-sm text-slate-500">
          Génération de votre charte informatique personnalisée par IA, à relire et valider avant
          export.
        </p>
      </div>

      <AISettingsBanner settings={settings} onToggle={handleToggleAI} toggling={togglingAI} />

      {settings?.ai_enabled ? (
        <>
          <PreviewPanel />

          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {generating ? 'Génération…' : 'Générer la charte informatique'}
          </button>

          {error && <p className="text-sm text-red-600">{error}</p>}

          {documents.length === 0 ? (
            <p className="text-slate-600">Aucun document généré pour l’instant.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-[220px_1fr]">
              <ul className="space-y-1">
                {documents.map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(d.id)}
                      className={`w-full rounded-md px-3 py-2 text-left text-xs ${
                        (selectedDocument && selectedDocument.id === d.id)
                          ? 'bg-slate-900 text-white'
                          : 'bg-white text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {DOCUMENT_TYPE_LABELS[d.type] || d.type} v{d.version}
                      <br />
                      <span className="text-[10px] opacity-70">{STATUS_LABELS[d.status]}</span>
                    </button>
                  </li>
                ))}
              </ul>
              {selectedDocument && (
                <DocumentEditor
                  document={selectedDocument}
                  onUpdated={(updated) =>
                    setDocuments((docs) => docs.map((d) => (d.id === updated.id ? updated : d)))
                  }
                />
              )}
            </div>
          )}
        </>
      ) : (
        <p className="text-slate-600">
          L’IA est désactivée pour cette entreprise. Un administrateur peut l’activer ci-dessus.
        </p>
      )}
    </div>
  )
}
