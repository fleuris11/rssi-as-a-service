import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ResultatsComptes from './ResultatsComptes'

// Le défaut corrigé, relevé en production : 3 222 résultats pour un seul
// compte, affichés en lignes rigoureusement identiques. Ces tests épinglent
// ce qui rend l'écran lisible — et qui se reperdrait sans bruit :
//
//   1. on affiche des GROUPES, pas des lignes ;
//   2. le détail déplié porte les champs qui distinguent les occurrences ;
//   3. l'écran dit ce qui vient de la reprise d'historique ;
//   4. on masque, on ne cache pas : le traité reste annoncé et atteignable.

vi.mock('../../api/endpoints', () => ({
  threatIntelligenceApi: {
    listWatchedAccountFindings: vi.fn(),
    updateWatchedAccountFinding: vi.fn(),
    watchedAccountFindingsExportUrl: vi.fn(() => '/export.csv'),
  },
}))

const showToast = vi.fn()
vi.mock('../../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { threatIntelligenceApi } = await import('../../api/endpoints')

const GROUPE = {
  key: '1|sessions|.gmail.com',
  account_id: 1,
  account_value: 'dirigeant@exemple.test',
  account_label: 'Direction',
  finding_type: 'sessions',
  service: '.gmail.com',
  occurrences: 3165,
  open_count: 3165,
  treated_count: 0,
  ignored_count: 0,
  severity: 'critical',
  latest_breach_date: '2025-10-05',
  oldest_breach_date: '2020-01-01',
}

const LIGNE = {
  id: 7,
  status: 'open',
  status_label: 'Ouvert',
  breach_date: '2025-10-05',
  has_secret: true,
  from_first_scan: true,
  details: [
    {
      label: 'Service concerné',
      value: '.gmail.com',
      implication: 'Le service sur lequel la session a été volée.',
    },
    { label: 'Jeton concerné', value: '__utma', implication: 'Le nom du cookie dérobé.' },
  ],
}

const COMPTES = [{ id: 1, value: 'dirigeant@exemple.test', label: 'Direction' }]

function mockOk(groupes = [GROUPE]) {
  threatIntelligenceApi.listWatchedAccountFindings.mockResolvedValue({
    data: {
      count: groupes.length,
      results: groupes,
      filters: { types: ['sessions'], severities: ['critical'] },
    },
  })
}

describe('ResultatsComptes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockOk()
  })

  it('affiche un groupe avec son nombre d’occurrences, pas 3 165 lignes', async () => {
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)

    expect(await screen.findByText('.gmail.com')).toBeInTheDocument()
    expect(screen.getByText(/3165 occurrences/)).toBeInTheDocument()
  })

  it('annonce les bornes de dates du groupe', async () => {
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)

    // « de 01/01/2020 à 05/10/2025 » : ce qui remplace une date unique répétée.
    expect(await screen.findByText(/01\/01\/2020/)).toBeInTheDocument()
    expect(screen.getByText(/05\/10\/2025/)).toBeInTheDocument()
  })

  it('ne charge le détail qu’à l’ouverture du groupe', async () => {
    const user = userEvent.setup()
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)
    await screen.findByText('.gmail.com')

    threatIntelligenceApi.listWatchedAccountFindings.mockResolvedValue({
      data: { count: 1, results: [LIGNE] },
    })
    await user.click(screen.getByRole('button', { expanded: false }))

    await waitFor(() =>
      expect(threatIntelligenceApi.listWatchedAccountFindings).toHaveBeenCalledWith(
        expect.objectContaining({ group: '1|sessions|.gmail.com' })
      )
    )
  })

  it('le détail porte les champs qui distinguent les occurrences', async () => {
    const user = userEvent.setup()
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)
    await screen.findByText('.gmail.com')

    threatIntelligenceApi.listWatchedAccountFindings.mockResolvedValue({
      data: { count: 1, results: [LIGNE] },
    })
    await user.click(screen.getByRole('button', { expanded: false }))

    // Sans ces deux champs, les lignes redeviennent indiscernables.
    expect(await screen.findByText('Jeton concerné')).toBeInTheDocument()
    expect(screen.getByText('__utma')).toBeInTheDocument()
    expect(screen.getByText(/Le nom du cookie dérobé/)).toBeInTheDocument()
  })

  it('dit ce qui vient de la reprise d’historique', async () => {
    const user = userEvent.setup()
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)
    await screen.findByText('.gmail.com')

    threatIntelligenceApi.listWatchedAccountFindings.mockResolvedValue({
      data: { count: 1, results: [LIGNE] },
    })
    await user.click(screen.getByRole('button', { expanded: false }))

    expect(await screen.findByText(/historique découvert au premier scan/)).toBeInTheDocument()
  })

  it('annonce ce qui est déjà traité plutôt que de le cacher', async () => {
    render(
      <ResultatsComptes
        comptes={COMPTES}
        resume={{ treated_findings: 12, ignored_findings: 3, from_first_scan: 3165 }}
      />
    )

    expect(await screen.findByText(/12 résultat\(s\) déjà traité\(s\)/)).toBeInTheDocument()
    expect(screen.getByText(/3 écarté\(s\)/)).toBeInTheDocument()
  })

  it('organise les groupes par compte déclaré', async () => {
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)

    expect(await screen.findByRole('heading', { name: /Direction/ })).toBeInTheDocument()
  })

  it('propose un export qui reprend les filtres de l’écran', async () => {
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)
    await screen.findByText('.gmail.com')

    expect(threatIntelligenceApi.watchedAccountFindingsExportUrl).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'open' })
    )
  })

  it('ne propose que les filtres qui existent chez ce client', async () => {
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)
    await screen.findByText('.gmail.com')

    const typeSelect = screen.getByLabelText('Type')
    expect(typeSelect).toHaveTextContent('sessions')
  })

  it('affiche un état vide explicite quand rien ne correspond', async () => {
    mockOk([])
    render(<ResultatsComptes comptes={COMPTES} resume={{}} />)

    expect(await screen.findByText('Rien à traiter')).toBeInTheDocument()
  })
})
