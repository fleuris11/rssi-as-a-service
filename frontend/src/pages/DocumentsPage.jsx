import { AlertTriangle, ChevronDown, ChevronUp, Eye, FileDown, FileText, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi } from '../api/endpoints'
import ApercuMarkdown, { compterACompleter } from '../components/documents/ApercuMarkdown'
import { ProfileDate } from '../components/DisplayProfile'
import FeatureGate from '../components/FeatureGate'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import Modal from '../components/ui/Modal'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

/**
 * La bibliothèque documentaire (V2-5, ADR-032 ; refondue au lot C, C3).
 *
 * Ce que le lot C corrige : on voyait sept boutons sans savoir ce qu'ils
 * produisaient. Les documents sont désormais rangés par USAGE (point 12),
 * disent à quoi ils servent et à qui ils s'adressent (13), se prévisualisent
 * avant d'être générés (14), et gardent leur historique daté (15).
 */

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

/** Les usages dans l'ordre où le serveur les sert : c'est lui qui les définit. */
export function groupesParUsage(catalogue) {
  const groupes = []
  for (const entree of catalogue) {
    let groupe = groupes.find((g) => g.usage === entree.usage)
    if (!groupe) {
      groupe = {
        usage: entree.usage,
        label: entree.usage_label,
        description: entree.usage_description,
        entrees: [],
      }
      groupes.push(groupe)
    }
    groupe.entrees.push(entree)
  }
  return groupes
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
            documents sur sept sont composés à partir de vos données. */}
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

/** Ce qui partirait vers l'IA pour rédiger la charte — la transparence d'US-4.3. */
function DonneesTransmises() {
  const { showToast } = useToast()
  const [donnees, setDonnees] = useState(null)
  const [ouvert, setOuvert] = useState(false)
  const [chargement, setChargement] = useState(false)

  async function basculer() {
    if (!ouvert && !donnees) {
      setChargement(true)
      try {
        const reponse = await aiApi.previewCharter()
        setDonnees(reponse.data)
      } catch {
        showToast({ type: 'error', message: 'Impossible de charger les données transmises.' })
      } finally {
        setChargement(false)
      }
    }
    setOuvert((v) => !v)
  }

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={basculer}
        aria-expanded={ouvert}
        className="transition-smooth flex items-center gap-1 text-xs font-medium text-ink-600 hover:text-brand-700"
      >
        {ouvert ? <ChevronUp className="size-3.5" aria-hidden="true" /> : <ChevronDown className="size-3.5" aria-hidden="true" />}
        Ce qui serait transmis à l’IA pour la rédiger
      </button>
      {ouvert && (
        <div className="mt-2">
          {chargement ? (
            <p className="text-xs text-ink-500">Chargement…</p>
          ) : (
            <pre className="max-h-60 overflow-auto rounded-md bg-ink-50 p-3 text-xs text-ink-700">
              {JSON.stringify(donnees, null, 2)}
            </pre>
          )}
          <p className="mt-2 text-xs text-ink-500">
            Les noms, domaines et adresses sont remplacés par des marqueurs avant l’envoi, et
            restaurés dans le document.
          </p>
        </div>
      )}
    </div>
  )
}

function FenetreApercu({ entree, apercu, chargement, aiEnabled, onFermer, onGenerer }) {
  if (!entree) return null
  const aCompleter = compterACompleter(apercu?.content_markdown)
  const redigeParIA = entree.source === 'ai'

  const generer = (
    <Button
      variant="primary"
      icon={redigeParIA ? Sparkles : FileText}
      disabled={redigeParIA && !aiEnabled}
      onClick={() => onGenerer(entree)}
    >
      Générer ce document
    </Button>
  )

  return (
    <Modal open onClose={onFermer} title={`Aperçu — ${entree.label}`} className="max-w-3xl">
      <p className="text-sm text-ink-600">{entree.purpose}</p>
      <p className="mt-1 text-xs text-ink-500">
        <span className="font-medium text-ink-700">Pour : </span>
        {entree.audience}
      </p>

      {chargement || !apercu ? (
        <p className="mt-4 text-sm text-ink-500">Préparation de l’aperçu…</p>
      ) : (
        <>
          {apercu.missing?.length > 0 && (
            <p className="mt-3 flex items-start gap-1.5 text-xs text-warning-strong">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>Sera générique : {apercu.missing.join(' ; ')}.</span>
            </p>
          )}

          {apercu.content_markdown ? (
            <>
              {/* Ce qui reste à la charge du client, dit AVANT la génération. */}
              <p className="mt-3 text-sm text-ink-700">
                {aCompleter === 0
                  ? 'Tout ce que la plateforme sait est déjà rempli, et rien ne reste à compléter.'
                  : `${aCompleter} passage(s) à compléter par vous — surlignés ci-dessous. Tout le reste est rempli avec ce que la plateforme sait déjà.`}
              </p>
              <div className="mt-3 max-h-[55vh] overflow-y-auto rounded-md border border-ink-200 bg-canvas p-4">
                <ApercuMarkdown markdown={apercu.content_markdown} />
              </div>
            </>
          ) : (
            <div className="mt-3 rounded-md border border-ink-200 bg-canvas p-4">
              <p className="text-sm text-ink-700">
                Ce document est rédigé par l’IA au moment de la génération : son texte n’existe pas
                encore. Voici le plan qu’il suivra.
              </p>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-ink-800">
                {apercu.outline.map((section) => (
                  <li key={section}>{section}</li>
                ))}
              </ol>
              {aiEnabled && <DonneesTransmises />}
            </div>
          )}
        </>
      )}

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" onClick={onFermer}>
          Fermer l’aperçu
        </Button>
        {redigeParIA ? <FeatureGate feature="charter_generation">{generer}</FeatureGate> : generer}
      </div>
    </Modal>
  )
}

/** Une entrée du catalogue : à quoi le document sert, pour qui, et son historique. */
function CatalogEntry({ entry, versions, onGenerate, onPreview, onSelect, selectedId, generating, aiEnabled }) {
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
      // Un bouton par document : sans ce nom accessible, la page exposait
      // sept boutons « Générer » que rien ne distinguait au lecteur d'écran.
      aria-label={`${verbe} — ${entry.label}`}
    >
      {verbe}
    </Button>
  )

  return (
    <Card padding="p-4" className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-ink-800">{entry.label}</h3>
          <p className="mt-0.5 max-w-2xl text-xs text-ink-600">{entry.purpose}</p>
          <p className="mt-1 max-w-2xl text-xs text-ink-500">
            <span className="font-medium text-ink-700">Pour : </span>
            {entry.audience}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Badge variant={entry.source === 'ai' ? 'accent' : 'neutral'}>
            {entry.source === 'ai' ? 'Rédigé par l’IA' : 'Composé'}
          </Badge>
          <Button
            variant="secondary"
            size="sm"
            icon={Eye}
            onClick={() => onPreview(entry)}
            aria-label={`Aperçu — ${entry.label}`}
          >
            Aperçu
          </Button>
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

      {/* Point 15 : l'historique, daté et versionné. Le nom accessible porte
          le document : « v1 — Brouillon » se répéterait sinon d'une carte à
          l'autre, indistinguable au clavier. */}
      {versions.length > 0 && (
        <div className="border-t border-ink-100 pt-3">
          <p className="t-eyebrow mb-2">Historique</p>
          <ul className="flex flex-wrap gap-2">
            {versions.map((version) => (
              <li key={version.id}>
                <button
                  type="button"
                  onClick={() => onSelect(version.id)}
                  aria-label={`${entry.label}, version ${version.version} — ${STATUS_LABELS[version.status]}`}
                  aria-pressed={selectedId === version.id}
                  className={`transition-smooth rounded-md border px-2 py-1 text-left text-xs ${
                    selectedId === version.id
                      ? 'border-brand-600 bg-brand-50 text-ink-800'
                      : 'border-ink-200 text-ink-600 hover:border-brand-300'
                  }`}
                >
                  <span className="font-medium">v{version.version}</span> —{' '}
                  {STATUS_LABELS[version.status]}
                  {version.created_at && (
                    <span className="block text-[11px] text-ink-500">
                      <ProfileDate value={version.created_at} />
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
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
              client et doit rester récupérable. */}
          <Button variant="secondary" size="sm" onClick={() => handleExport('md')} disabled={isGenerating || !content}>
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
  const [apercuDe, setApercuDe] = useState(null)
  const [apercu, setApercu] = useState(null)
  const [chargementApercu, setChargementApercu] = useState(false)
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

  async function handlePreview(entry) {
    setApercuDe(entry)
    setApercu(null)
    setChargementApercu(true)
    try {
      const reponse = await aiApi.previewDocument(entry.type)
      setApercu(reponse.data)
    } catch {
      setApercuDe(null)
      showToast({ type: 'error', message: 'L’aperçu n’a pas pu être préparé.' })
    } finally {
      setChargementApercu(false)
    }
  }

  async function handleGenerate(entry) {
    setApercuDe(null)
    setGenerating(entry.type)
    try {
      const response = await aiApi.generateDocument(entry.type)
      const { document, job } = response.data
      setDocuments((docs) => [document, ...docs])
      setSelectedId(document.id)

      if (!job) {
        // Document composé : il est déjà prêt dans la réponse.
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
          Rangés selon ce que vous voulez en faire. Chacun est composé à partir de ce que la
          plateforme sait déjà de votre entreprise : prévisualisez-le, générez-le, relisez, validez.
        </p>
      </div>

      <AISettingsBanner settings={settings} onToggle={handleToggleAI} toggling={togglingAI} />

      {groupesParUsage(catalog).map((groupe) => (
        <section key={groupe.usage} aria-labelledby={`usage-${groupe.usage}`} className="space-y-3">
          <div>
            <h2 id={`usage-${groupe.usage}`} className="font-display text-lg font-semibold text-ink-900">
              {groupe.label}
            </h2>
            <p className="text-sm text-ink-500">{groupe.description}</p>
          </div>
          {groupe.entrees.map((entry) => (
            <CatalogEntry
              key={entry.type}
              entry={entry}
              versions={documents.filter((d) => d.type === entry.type)}
              onGenerate={handleGenerate}
              onPreview={handlePreview}
              onSelect={setSelectedId}
              selectedId={selectedId}
              generating={generating}
              aiEnabled={Boolean(settings?.ai_enabled)}
            />
          ))}
        </section>
      ))}

      <FenetreApercu
        entree={apercuDe}
        apercu={apercu}
        chargement={chargementApercu}
        aiEnabled={Boolean(settings?.ai_enabled)}
        onFermer={() => setApercuDe(null)}
        onGenerer={handleGenerate}
      />

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
              description="Ouvrez une version dans l’historique d’un document pour la relire, la modifier et l’exporter."
            />
          </Card>
        )
      )}
    </div>
  )
}
