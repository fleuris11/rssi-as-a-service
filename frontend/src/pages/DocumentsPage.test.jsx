import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DocumentsPage from './DocumentsPage'

// Lot C, C3. Ce que ces tests tiennent : rangé par usage (12), à quoi ça sert
// et pour qui (13), l'aperçu AVANT la génération sans rien générer (14),
// l'historique daté (15) — et aucun bouton dont le nom se répète, le défaut
// des « sept boutons Générer » trouvé à la revue d'accessibilité.

vi.mock('../api/endpoints', () => ({
  aiApi: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    documentCatalog: vi.fn(),
    listDocuments: vi.fn(),
    previewDocument: vi.fn(),
    previewCharter: vi.fn(),
    generateDocument: vi.fn(),
    getDocument: vi.fn(),
    getJob: vi.fn(),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    featureInfo: () => null,
    requiredPlanFor: () => '',
    isOperational: true,
    loading: false,
  }),
}))

const { aiApi } = await import('../api/endpoints')

const USAGES = {
  frame: ['Pour cadrer ma sécurité', 'Les engagements de l’entreprise.'],
  awareness: ['Pour sensibiliser mes équipes', 'Ce que chacun doit savoir.'],
  answer: ['Pour répondre à un client ou un assureur', 'Les preuves qu’on vous demande.'],
  committee: ['Pour un comité', 'Où en est la sécurité.'],
}

function entree(type, label, usage, source = 'composed', extra = {}) {
  return {
    type,
    label,
    purpose: `À quoi sert ${label}.`,
    source,
    usage,
    usage_label: USAGES[usage][0],
    usage_description: USAGES[usage][1],
    audience: `Les destinataires de ${label}.`,
    latest_version: null,
    latest_status: null,
    latest_id: null,
    ready: true,
    missing: [],
    ...extra,
  }
}

const CATALOGUE = [
  entree('security_policy', 'Politique de sécurité', 'frame', 'composed', { latest_version: 1 }),
  entree('it_charter', 'Charte informatique', 'awareness', 'ai'),
  entree('incident_register', 'Registre des incidents', 'answer', 'composed', { latest_version: 2 }),
  entree('committee_report', 'Rapport de comité', 'committee'),
]

const VERSIONS = [
  { id: 11, type: 'incident_register', version: 2, status: 'draft', created_at: '2026-09-12T08:00:00Z', content_markdown: '# R', type_label: 'Registre des incidents', source_label: 'Composé' },
  { id: 10, type: 'incident_register', version: 1, status: 'validated', created_at: '2026-06-02T08:00:00Z', content_markdown: '# R', type_label: 'Registre des incidents', source_label: 'Composé' },
  { id: 5, type: 'security_policy', version: 1, status: 'draft', created_at: '2026-09-01T08:00:00Z', content_markdown: '# P', type_label: 'Politique de sécurité', source_label: 'Composé' },
]

function servir() {
  aiApi.getSettings.mockResolvedValue({ data: { ai_enabled: true, quota: null } })
  aiApi.documentCatalog.mockResolvedValue({ data: CATALOGUE })
  aiApi.listDocuments.mockResolvedValue({ data: { results: VERSIONS } })
}

describe('DocumentsPage — les documents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('range les documents par usage, pas par type de fichier', async () => {
    servir()
    render(<DocumentsPage />)

    for (const [libelle] of Object.values(USAGES)) {
      expect(await screen.findByRole('heading', { level: 2, name: libelle })).toBeInTheDocument()
    }
    const repondre = screen
      .getByRole('heading', { level: 2, name: 'Pour répondre à un client ou un assureur' })
      .closest('section')
    expect(within(repondre).getByRole('heading', { name: 'Registre des incidents' })).toBeInTheDocument()
    expect(within(repondre).queryByRole('heading', { name: 'Charte informatique' })).not.toBeInTheDocument()
  })

  it('dit à quoi sert chaque document et à qui il s’adresse', async () => {
    servir()
    render(<DocumentsPage />)

    expect(await screen.findByText('À quoi sert Charte informatique.')).toBeInTheDocument()
    expect(screen.getByText('Les destinataires de Charte informatique.')).toBeInTheDocument()
  })

  it('montre l’aperçu d’un document composé sans le générer', async () => {
    servir()
    aiApi.previewDocument.mockResolvedValue({
      data: {
        type: 'incident_register',
        source: 'composed',
        content_markdown: '# Registre des incidents\n\n| Validé par | *[à compléter]* |\n|---|---|\n| Date | *[à compléter]* |',
        outline: [],
        missing: [],
      },
    })
    render(<DocumentsPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Aperçu — Registre des incidents' }))

    const fenetre = await screen.findByRole('dialog')
    expect(aiApi.previewDocument).toHaveBeenCalledWith('incident_register')
    expect(within(fenetre).getByRole('heading', { name: 'Registre des incidents', level: 3 })).toBeInTheDocument()
    expect(within(fenetre).getByText(/2 passage\(s\) à compléter par vous/)).toBeInTheDocument()
    expect(aiApi.generateDocument).not.toHaveBeenCalled()
  })

  it('montre le plan de la charte, dont le texte n’existe qu’à la rédaction', async () => {
    servir()
    aiApi.previewDocument.mockResolvedValue({
      data: {
        type: 'it_charter',
        source: 'ai',
        content_markdown: null,
        outline: ['Accès et mots de passe', 'Télétravail et mobilité'],
        missing: [],
      },
    })
    render(<DocumentsPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Aperçu — Charte informatique' }))

    const fenetre = await screen.findByRole('dialog')
    expect(within(fenetre).getByText('Accès et mots de passe')).toBeInTheDocument()
    expect(within(fenetre).getByText(/son texte n’existe pas encore/)).toBeInTheDocument()
    expect(aiApi.generateDocument).not.toHaveBeenCalled()
  })

  it('génère depuis l’aperçu quand le document convient', async () => {
    servir()
    aiApi.previewDocument.mockResolvedValue({
      data: { type: 'committee_report', source: 'composed', content_markdown: '# Rapport', outline: [], missing: [] },
    })
    aiApi.generateDocument.mockResolvedValue({
      data: { document: { id: 99, type: 'committee_report', version: 1, status: 'draft', content_markdown: '# Rapport' }, job: null },
    })
    render(<DocumentsPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Aperçu — Rapport de comité' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Générer ce document' }))

    await waitFor(() => expect(aiApi.generateDocument).toHaveBeenCalledWith('committee_report'))
  })

  it('garde un historique daté et versionné de chaque document', async () => {
    servir()
    render(<DocumentsPage />)

    const v2 = await screen.findByRole('button', { name: 'Registre des incidents, version 2 — Brouillon' })
    const v1 = screen.getByRole('button', { name: 'Registre des incidents, version 1 — Validé' })
    expect(within(v2).getByText(/12 septembre 2026/)).toBeInTheDocument()
    expect(within(v1).getByText(/2 juin 2026/)).toBeInTheDocument()
  })

  it('ne présente jamais deux boutons au même nom', async () => {
    servir()
    render(<DocumentsPage />)
    await screen.findByRole('heading', { level: 2, name: 'Pour un comité' })

    const noms = screen.getAllByRole('button').map((b) => b.getAttribute('aria-label') || b.textContent.trim())
    const doublons = noms.filter((nom, i) => noms.indexOf(nom) !== i)
    expect(doublons).toEqual([])
  })
})
