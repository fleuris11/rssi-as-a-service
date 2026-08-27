import { ChevronDown, ChevronUp, FileText, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi } from '../api/endpoints'
import Badge from '../components/ui/Badge'
import FeatureGate from '../components/FeatureGate'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

const STATUS_LABELS = {
  generating: 'Génération en cours…',
  draft: 'Brouillon',
  validated: 'Validé',
  failed: 'Échec',
}

const STATUS_VARIANT = {
  generating: 'neutral',
  draft: 'warning',
  validated: 'ok',
  failed: 'critical',
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
    <Card className="flex flex-wrap items-center justify-between gap-3" padding="p-4">
      <div>
        <p className="text-sm font-medium text-ink-800">
          IA {aiEnabled ? 'activée' : 'désactivée'} pour cette entreprise
        </p>
        {aiEnabled && quota && (
          <p className="mt-1 text-xs text-ink-500">
            Quota mensuel : {quota.tokens_used.toLocaleString('fr-FR')} /{' '}
            {quota.monthly_token_limit.toLocaleString('fr-FR')} tokens (
            {quota.remaining_tokens.toLocaleString('fr-FR')} restants)
          </p>
        )}
      </div>
      <Button variant="secondary" size="sm" loading={toggling} onClick={() => onToggle(!aiEnabled)}>
        {aiEnabled ? 'Désactiver l’IA' : 'Activer l’IA'}
      </Button>
    </Card>
  )
}

function PreviewPanel() {
  const { showToast } = useToast()
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  async function handleToggle() {
    if (!open && !preview) {
      setLoading(true)
      try {
        const response = await aiApi.previewCharter()
        setPreview(response.data)
      } catch {
        showToast({ type: 'error', message: 'Impossible de charger l’aperçu.' })
      } finally {
        setLoading(false)
      }
    }
    setOpen((o) => !o)
  }

  return (
    <Card padding="p-4">
      <button
        type="button"
        onClick={handleToggle}
        className="transition-smooth flex items-center gap-1 text-xs font-medium text-ink-600 hover:text-brand-700"
      >
        {open ? <ChevronUp className="size-3.5" aria-hidden="true" /> : <ChevronDown className="size-3.5" aria-hidden="true" />}
        {open ? 'Masquer' : 'Voir'} les données qui seraient transmises à l’IA
      </button>
      <p className="mt-1 text-xs text-ink-500">
        Transparence (US-4.3) : ces données sont pseudonymisées avant tout appel — aucun nom
        d’entreprise, de personne, d’email ou de domaine réel n’est envoyé.
      </p>
      {open && (
        <div className="mt-2">
          {loading && <p className="text-xs text-ink-500">Chargement…</p>}
          {preview && (
            <pre className="max-h-64 overflow-auto rounded bg-ink-50 p-3 text-xs text-ink-700">
              {JSON.stringify(preview, null, 2)}
            </pre>
          )}
        </div>
      )}
    </Card>
  )
}

function DocumentEditor({ document: doc, onUpdated }) {
  const { showToast } = useToast()
  const [content, setContent] = useState(doc.content_markdown)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setContent(doc.content_markdown)
  }, [doc.id, doc.content_markdown])

  const isValidated = doc.status === 'validated'
  const isGenerating = doc.status === 'generating'

  async function handleSave() {
    setSaving(true)
    try {
      const response = await aiApi.updateDocument(doc.id, content)
      onUpdated(response.data)
      showToast({ type: 'success', message: 'Modifications enregistrées.' })
    } catch {
      showToast({ type: 'error', message: 'Impossible d’enregistrer les modifications.' })
    } finally {
      setSaving(false)
    }
  }

  async function handleValidate() {
    setSaving(true)
    try {
      const response = await aiApi.validateDocument(doc.id)
      onUpdated(response.data)
      showToast({ type: 'success', message: 'Document validé.' })
    } catch {
      showToast({ type: 'error', message: 'Impossible de valider ce document.' })
    } finally {
      setSaving(false)
    }
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  async function handleExport() {
    try {
      const response = await aiApi.exportDocument(doc.id)
      downloadBlob(response.data, `${doc.type}-v${doc.version}.md`)
    } catch {
      showToast({ type: 'error', message: 'Impossible d’exporter ce document.' })
    }
  }

  async function handleExportPdf() {
    try {
      const response = await aiApi.exportDocumentPdf(doc.id)
      downloadBlob(response.data, `${doc.type}-v${doc.version}.pdf`)
    } catch {
      showToast({ type: 'error', message: 'Impossible d’exporter ce document en PDF.' })
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-ink-800">
            {DOCUMENT_TYPE_LABELS[doc.type] || doc.type} — v{doc.version}
          </p>
          <div className="mt-1">
            <Badge variant={STATUS_VARIANT[doc.status]}>{STATUS_LABELS[doc.status]}</Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={handleExport} disabled={isGenerating || !content}>
            Exporter (.md)
          </Button>
          {/* L'export Markdown voisin n'est PAS gardé : le contenu du
              document appartient au client et doit rester récupérable. Ce qui
              relève de l'offre est le rendu PDF, pas l'accès aux données. */}
          <FeatureGate feature="pdf_export">
            <Button variant="primary" size="sm" icon={FileText} onClick={handleExportPdf} disabled={isGenerating || !content}>
              Exporter (.pdf)
            </Button>
          </FeatureGate>
          {!isValidated && !isGenerating && (
            <>
              <Button variant="secondary" size="sm" loading={saving} onClick={handleSave}>
                Enregistrer
              </Button>
              <Button variant="secondary" size="sm" loading={saving} onClick={handleValidate}>
                Valider
              </Button>
            </>
          )}
        </div>
      </div>

      {isGenerating ? (
        <p className="mt-4 text-sm text-ink-500">Génération en cours par l’IA (30 à 60 secondes)…</p>
      ) : (
        <textarea
          aria-label={`Contenu de ${DOCUMENT_TYPE_LABELS[doc.type] || doc.type} v${doc.version}`}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          readOnly={isValidated}
          rows={16}
          className="transition-smooth mt-4 w-full rounded-md border border-ink-200 p-3 font-mono text-xs focus-visible:outline-2 focus-visible:outline-brand-600 disabled:bg-ink-50"
        />
      )}
    </Card>
  )
}

export default function DocumentsPage() {
  const { showToast } = useToast()
  const [settings, setSettings] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [togglingAI, setTogglingAI] = useState(false)
  const poll = usePolling()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [settingsRes, documentsRes] = await Promise.all([aiApi.getSettings(), aiApi.listDocuments()])
      setSettings(settingsRes.data)
      setDocuments(documentsRes.data.results)
    } catch (err) {
      if (err.response?.status !== 403) {
        showToast({ type: 'error', message: 'Impossible de charger les documents.' })
      }
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      showToast({ type: 'error', message: 'Seul un administrateur de l’entreprise peut activer/désactiver l’IA.' })
    } finally {
      setTogglingAI(false)
    }
  }

  async function handleGenerate() {
    setGenerating(true)
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
      showToast({ type: 'error', message: err.response?.data?.detail || 'Impossible de lancer la génération.' })
      setGenerating(false)
    }
  }

  const selectedDocument = documents.find((d) => d.id === selectedId) || documents[0] || null

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Documents</h1>
        <p className="mt-1 text-sm text-ink-500">
          Génération de votre charte informatique personnalisée par IA, à relire et valider avant export.
        </p>
      </div>

      <AISettingsBanner settings={settings} onToggle={handleToggleAI} toggling={togglingAI} />

      {settings?.ai_enabled ? (
        <>
          <PreviewPanel />

          <FeatureGate feature="charter_generation">
            <Button variant="primary" icon={Sparkles} loading={generating} onClick={handleGenerate}>
              Générer la charte informatique
            </Button>
          </FeatureGate>

          {documents.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="Aucun document généré"
              description="Générez votre première charte informatique personnalisée avec l’assistant IA."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-[240px_1fr]">
              <div className="space-y-2">
                {documents.map((d) => {
                  const active = selectedDocument && selectedDocument.id === d.id
                  return (
                    <button
                      key={d.id}
                      type="button"
                      onClick={() => setSelectedId(d.id)}
                      className={`transition-smooth block w-full rounded-lg border p-3 text-left ${
                        active
                          ? 'border-brand-600 bg-brand-50'
                          : 'border-ink-200 bg-surface hover:border-brand-300'
                      }`}
                    >
                      <p className="text-sm font-medium text-ink-800">
                        {DOCUMENT_TYPE_LABELS[d.type] || d.type} v{d.version}
                      </p>
                      <div className="mt-1.5">
                        <Badge variant={STATUS_VARIANT[d.status]}>{STATUS_LABELS[d.status]}</Badge>
                      </div>
                    </button>
                  )
                })}
              </div>
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
        <p className="text-ink-600">
          L’IA est désactivée pour cette entreprise. Un administrateur peut l’activer ci-dessus.
        </p>
      )}
    </div>
  )
}
