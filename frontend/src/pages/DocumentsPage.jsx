import { AlertTriangle, ChevronDown, ChevronUp, FileDown, FileText, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi } from '../api/endpoints'
import Badge from '../components/ui/Badge'
import FeatureGate from '../components/FeatureGate'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
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
        {/* Depuis V2-5, couper l'IA ne coupe plus la bibliothèque : six
            documents sur sept sont composés à partir de vos données, sans
            aucun appel d'IA. Le dire ici évite au client de croire qu'il vient
            de tout perdre. */}
        <p className="mt-1 text-xs text-ink-500">
          {aiEnabled
            ? quota &&
              `Quota mensuel : ${quota.tokens_used.toLocaleString('fr-FR')} / ${quota.monthly_token_limit.toLocaleString('fr-FR')} tokens (${quota.remaining_tokens.toLocaleString('fr-FR')} restants)`
            : 'Seule la charte informatique, rédigée par l’IA, est indisponible. Les autres documents restent générables.'}
        </p>
      </div>
      <Button variant="secondary" size="sm" loading={toggling} onClick={() => onToggle(!aiEnabled)}>
        {aiEnabled ? 'Désactiver l’IA' : 'Activer l’IA'}
      </Button>
    </Card>
  )
}

/** L'aperçu de ce qui partirait vers l'IA — ne concerne que la charte. */
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
    setOpen((value) => !value)
  }

  return (
    <Card padding="p-4">
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={open}
        className="transition-smooth flex w-full items-center justify-between gap-2 text-left text-sm font-medium text-ink-700 hover:text-brand-600"
      >
        Ce qui serait transmis à l’IA pour rédiger la charte
        {open ? (
          <ChevronUp className="size-4" aria-hidden="true" />
        ) : (
          <ChevronDown className="size-4" aria-hidden="true" />
        )}
      </button>
      {open && (
        <div className="mt-3">
          {loading ? (
            <p className="text-sm text-ink-500">Chargement…</p>
          ) : (
            <pre className="max-h-72 overflow-auto rounded-md bg-ink-50 p-3 text-xs text-ink-700">
              {JSON.stringify(preview, null, 2)}
            </pre>
          )}
          <p className="mt-2 text-xs text-ink-500">
            Les noms, domaines et adresses sont remplacés par des marqueurs avant l’envoi, et
            restaurés dans le document.
          </p>
        </div>
      )}
    </Card>
  )
}

/** Une entrée du catalogue : ce que le document sert à faire, et son état. */
function CatalogEntry({ entry, versions, onGenerate, onSelect, selectedId, generating, aiEnabled }) {
  const indisponible = entry.source === 'ai' && !aiEnabled
  const verbe = entry.latest_version ? 'Régénérer' : 'Générer'
  const bouton = (
    <Button
      variant="primary"
      size="sm"
      icon={entry.source === 'ai' ? Sparkles : FileText}
      loading={generating === entry.type}
      disabled={indisponible}
      onClick={() => onGenerate(entry)}
      // Le catalogue affiche un bouton par type de document : sans ce nom
      // accessible, la page expose sept boutons nommés « Générer », que rien
      // ne distingue pour qui navigue au lecteur d'écran ou au clavier. Le
      // libellé visible reste court ; c'est le nom accessible qui porte le
      // document concerné.
      aria-label={`${verbe} — ${entry.label}`}
    >
      {verbe}
    </Button>
  )

  return (
    <Card padding="p-4" className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-800">{entry.label}</p>
          <p className="mt-0.5 max-w-2xl text-xs text-ink-500">{entry.purpose}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Badge variant={entry.source === 'ai' ? 'accent' : 'neutral'}>
            {entry.source === 'ai' ? 'Rédigé par l’IA' : 'Composé'}
          </Badge>
          {entry.source === 'ai' ? (
            <FeatureGate feature="charter_generation">{bouton}</FeatureGate>
          ) : (
            bouton
          )}
        </div>
      </div>

      {/* Prévenir AVANT la génération, pas après : un plan de continuité sans
          actif déclaré n'est pas faux, il est vide. */}
      {entry.missing.length > 0 && (
        <p className="flex items-start gap-1.5 text-xs text-warning-strong">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>Sera générique : {entry.missing.join(' ; ')}.</span>
        </p>
      )}
      {indisponible && (
        <p className="text-xs text-ink-500">
          L’IA est désactivée pour cette entreprise : ce document ne peut pas être rédigé.
        </p>
      )}

      {versions.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-ink-100 pt-3">
          {versions.map((version) => (
            <button
              key={version.id}
              type="button"
              onClick={() => onSelect(version.id)}
              className={`transition-smooth rounded-md border px-2 py-1 text-xs ${
                selectedId === version.id
                  ? 'border-brand-600 bg-brand-50 text-ink-800'
                  : 'border-ink-200 text-ink-600 hover:border-brand-300'
              }`}
            >
              v{version.version} — {STATUS_LABELS[version.status]}
            </button>
          ))}
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
      showToast({ type: 'success', message: 'Document enregistré.' })
    } catch {
      showToast({ type: 'error', message: 'Impossible d’enregistrer ce document.' })
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

  async function handleExport(kind) {
    const appels = {
      md: [aiApi.exportDocument, 'md'],
      docx: [aiApi.exportDocumentDocx, 'docx'],
      pdf: [aiApi.exportDocumentPdf, 'pdf'],
    }
    const [appel, extension] = appels[kind]
    try {
      const response = await appel(doc.id)
      downloadBlob(response.data, `${doc.type}-v${doc.version}.${extension}`)
    } catch {
      showToast({ type: 'error', message: 'Impossible d’exporter ce document.' })
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-ink-800">
            {doc.type_label} — v{doc.version}
          </p>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant={STATUS_VARIANT[doc.status]}>{STATUS_LABELS[doc.status]}</Badge>
            <span className="text-xs text-ink-500">{doc.source_label}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {/* L'export Markdown n'est PAS gardé : le contenu appartient au
              client et doit rester récupérable. Ce qui relève de l'offre, ce
              sont les formats de rendu. */}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => handleExport('md')}
            disabled={isGenerating || !content}
          >
            .md
          </Button>
          <FeatureGate feature="pdf_export">
            <Button
              variant="secondary"
              size="sm"
              icon={FileDown}
              onClick={() => handleExport('docx')}
              disabled={isGenerating || !content}
            >
              Word (.docx)
            </Button>
          </FeatureGate>
          <FeatureGate feature="pdf_export">
            <Button
              variant="primary"
              size="sm"
              icon={FileText}
              onClick={() => handleExport('pdf')}
              disabled={isGenerating || !content}
            >
              PDF
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
          aria-label={`Contenu de ${doc.type_label} v${doc.version}`}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          readOnly={isValidated}
          rows={24}
          className="transition-smooth mt-4 w-full rounded-md border border-ink-200 p-3 font-mono text-xs focus-visible:outline-2 focus-visible:outline-brand-600 disabled:bg-ink-50"
        />
      )}
    </Card>
  )
}

export default function DocumentsPage() {
  const { showToast } = useToast()
  const [settings, setSettings] = useState(null)
  const [catalog, setCatalog] = useState([])
  const [documents, setDocuments] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(null)
  const [togglingAI, setTogglingAI] = useState(false)
  const poll = usePolling()
  const toastRef = useRef(showToast)
  toastRef.current = showToast

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [settingsRes, catalogRes, documentsRes] = await Promise.all([
        aiApi.getSettings(),
        aiApi.documentCatalog(),
        aiApi.listDocuments(),
      ])
      setSettings(settingsRes.data)
      setCatalog(catalogRes.data)
      setDocuments(documentsRes.data.results)
    } catch (err) {
      if (err.response?.status !== 403) {
        toastRef.current({ type: 'error', message: 'Impossible de charger les documents.' })
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
    } catch {
      showToast({
        type: 'error',
        message: 'Seul un administrateur de l’entreprise peut activer/désactiver l’IA.',
      })
    } finally {
      setTogglingAI(false)
    }
  }

  async function handleGenerate(entry) {
    setGenerating(entry.type)
    try {
      const response = await aiApi.generateDocument(entry.type)
      const { document, job } = response.data
      setDocuments((docs) => [document, ...docs])
      setSelectedId(document.id)

      if (!job) {
        // Document composé : il est déjà prêt dans la réponse, il n'y a
        // aucun travail asynchrone à attendre.
        setGenerating(null)
        const catalogRes = await aiApi.documentCatalog()
        setCatalog(catalogRes.data)
        showToast({ type: 'success', message: `${entry.label} — v${document.version} composé.` })
        return
      }

      poll(job.id, async () => {
        const refreshed = await aiApi.getDocument(document.id)
        setDocuments((docs) => docs.map((d) => (d.id === document.id ? refreshed.data : d)))
        setGenerating(null)
      })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de lancer la génération.',
      })
      setGenerating(null)
    }
  }

  const selectedDocument = documents.find((d) => d.id === selectedId) || null

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
          Les documents qu’un RSSI produit, composés à partir de ce que la plateforme sait déjà de
          votre entreprise. À relire, compléter là où c’est indiqué, puis valider.
        </p>
      </div>

      <AISettingsBanner settings={settings} onToggle={handleToggleAI} toggling={togglingAI} />

      <div className="space-y-3">
        {catalog.map((entry) => (
          <CatalogEntry
            key={entry.type}
            entry={entry}
            versions={documents.filter((d) => d.type === entry.type)}
            onGenerate={handleGenerate}
            onSelect={setSelectedId}
            selectedId={selectedId}
            generating={generating}
            aiEnabled={Boolean(settings?.ai_enabled)}
          />
        ))}
      </div>

      {settings?.ai_enabled && <PreviewPanel />}

      {selectedDocument ? (
        <DocumentEditor
          document={selectedDocument}
          onUpdated={(updated) =>
            setDocuments((docs) => docs.map((d) => (d.id === updated.id ? updated : d)))
          }
        />
      ) : (
        documents.length > 0 && (
          <Card padding="p-4">
            <CardHeader
              title="Choisissez une version"
              description="Cliquez sur une version ci-dessus pour la relire, la modifier et l’exporter."
            />
          </Card>
        )
      )}
    </div>
  )
}
