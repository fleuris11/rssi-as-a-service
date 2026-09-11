import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WatchPanel from './WatchPanel'

// L'écran de veille est en console : aucun client ne le voit. Ce qui compte
// n'est donc pas son apparence, mais les quatre endroits où une régression
// silencieuse coûterait cher :
//
//   1. le tri d'une suggestion part bien vers l'API, avec le bon statut ;
//   2. on ne peut pas ajouter une mesure sans avoir RÉDIGÉ son contenu —
//      c'est la garde centrale d'ADR-034, et elle doit tenir côté écran
//      autant que côté serveur ;
//   3. l'état des sources remonte, parce qu'une source qui échoue en silence
//      est pire qu'une source absente ;
//   4. une source « jamais configurée » n'est pas présentée comme une panne.

vi.mock('../../../api/endpoints', () => ({
  platformApi: {
    watchQueue: vi.fn(),
    watchSources: vi.fn(),
    reviewWatchUpdate: vi.fn(),
    integrateWatchUpdate: vi.fn(),
    summarizeWatchUpdate: vi.fn(),
    pollWatchSource: vi.fn(),
    updateWatchSource: vi.fn(),
  },
}))

const showToast = vi.fn()
vi.mock('../../../components/ui/Toast', () => ({
  useToast: () => ({ showToast }),
}))

const { platformApi } = await import('../../../api/endpoints')

const SUGGESTION = {
  id: 7,
  title: 'Recommandations relatives aux systèmes d’IA générative',
  url: 'https://exemple-autorite.test/publications/ia',
  source_name: 'Guides et publications',
  source_publisher: 'Autorité de test',
  published_at: '2026-09-08T09:00:00Z',
  detected_at: '2026-09-10T06:15:00Z',
  source_excerpt: 'Le présent guide énonce dix mesures applicables aux systèmes concernés.',
  status: 'new',
  kind: 'unqualified',
  ai_summary: '',
  review_note: '',
  integrated_measures: [],
}

const REFERENTIELS = [
  {
    slug: 'anssi-hygiene',
    name: 'Guide d’hygiène (ANSSI)',
    domains: [{ code: 'sensibiliser-former', name: 'Sensibiliser et former' }],
  },
]

/** L'état par défaut : une suggestion à examiner, toutes les sources saines. */
function mockOk({ health, results = [SUGGESTION] } = {}) {
  platformApi.watchQueue.mockResolvedValue({
    data: {
      summary: { new: results.length, kept: 0, integrated: 0, promise: 'Nous suivons…' },
      health: health || { total: 5, active: 4, failing: [], unconfigured: [] },
      results,
    },
  })
  platformApi.watchSources.mockResolvedValue({ data: [] })
  platformApi.reviewWatchUpdate.mockResolvedValue({ data: {} })
  platformApi.integrateWatchUpdate.mockResolvedValue({ data: {} })
}

describe('WatchPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockOk()
  })

  it('envoie le tri d’une suggestion avec son statut', async () => {
    const user = userEvent.setup()
    render(<WatchPanel referentiels={REFERENTIELS} />)

    await user.click(await screen.findByRole('button', { name: /Retenir/ }))

    await waitFor(() =>
      expect(platformApi.reviewWatchUpdate).toHaveBeenCalledWith(7, { status: 'kept' })
    )
  })

  it('écarter une suggestion ne crée aucune mesure', async () => {
    const user = userEvent.setup()
    render(<WatchPanel referentiels={REFERENTIELS} />)

    await user.click(await screen.findByRole('button', { name: /Écarter/ }))

    await waitFor(() =>
      expect(platformApi.reviewWatchUpdate).toHaveBeenCalledWith(7, { status: 'dismissed' })
    )
    // Trier n'est pas intégrer : ce sont deux gestes séparés (ADR-034 §2).
    expect(platformApi.integrateWatchUpdate).not.toHaveBeenCalled()
  })

  it('refuse d’ajouter une mesure tant que le contenu n’est pas rédigé', async () => {
    const user = userEvent.setup()
    render(<WatchPanel referentiels={REFERENTIELS} />)

    await user.click(await screen.findByRole('button', { name: /Ajouter une mesure/ }))

    // Le formulaire s'ouvre, mais la validation reste fermée : ni l'intitulé
    // ni l'énoncé ne sont repris du titre de la publication.
    const valider = await screen.findByRole('button', { name: /^Ajouter la mesure/ })
    expect(valider).toBeDisabled()

    expect(platformApi.integrateWatchUpdate).not.toHaveBeenCalled()
  })

  it('n’ouvre pas l’ajout de mesure sans référentiel où la ranger', async () => {
    render(<WatchPanel referentiels={[]} />)

    expect(await screen.findByRole('button', { name: /Ajouter une mesure/ })).toBeDisabled()
  })

  it('remonte les sources en panne, avec leur nombre d’échecs', async () => {
    mockOk({
      health: {
        total: 5,
        active: 4,
        failing: [
          { slug: 'cnil', name: 'Actualités CNIL', consecutive_failures: 3, last_error: 'HTTP 503' },
        ],
        unconfigured: [],
      },
    })
    render(<WatchPanel referentiels={REFERENTIELS} />)

    expect(await screen.findByText(/Actualités CNIL/)).toBeInTheDocument()
    expect(screen.getByText(/3 échecs consécutifs/)).toBeInTheDocument()
    expect(screen.getByText(/HTTP 503/)).toBeInTheDocument()
  })

  it('distingue une source jamais configurée d’une source en panne', async () => {
    // Sinon EUR-Lex, livrée sans adresse, serait comptée comme un incident
    // pendant des mois.
    mockOk({
      health: {
        total: 5,
        active: 4,
        failing: [],
        unconfigured: [{ slug: 'eurlex-cyber', name: 'Journal officiel — EUR-Lex' }],
      },
    })
    render(<WatchPanel referentiels={REFERENTIELS} />)

    expect(await screen.findByText(/à configurer/)).toBeInTheDocument()
    expect(screen.queryByText(/échecs consécutifs/)).not.toBeInTheDocument()
  })

  it('affiche la promesse servie par le serveur, sans la réécrire', async () => {
    // La phrase est portée par l'API pour qu'elle ne dérive pas d'un écran à
    // l'autre : un test backend interdit déjà « exhaustive » et « temps réel ».
    render(<WatchPanel referentiels={REFERENTIELS} />)

    expect(await screen.findByText('Nous suivons…')).toBeInTheDocument()
  })

  it('conserve le texte source à côté du résumé par IA', async () => {
    mockOk({
      results: [{ ...SUGGESTION, ai_summary: 'Un résumé en trois phrases.' }],
    })
    render(<WatchPanel referentiels={REFERENTIELS} />)

    // Le résumé ne remplace jamais la référence.
    expect(await screen.findByText('Un résumé en trois phrases.')).toBeInTheDocument()
    expect(screen.getByText(/dix mesures applicables/)).toBeInTheDocument()
  })

  it('propose les domaines du référentiel choisi, sans saisie libre', async () => {
    // Le parcours d'intégration butait ici : l'exploitant devait deviner un
    // code de domaine qu'aucun écran ne lui montrait, et le service refuse
    // tout code inexistant.
    const user = userEvent.setup()
    render(<WatchPanel referentiels={REFERENTIELS} />)

    await user.click(await screen.findByRole('button', { name: /Ajouter une mesure/ }))

    const champ = await screen.findByLabelText('Domaine')
    expect(champ.tagName).toBe('SELECT')
    expect(champ).toHaveTextContent('Sensibiliser et former')
  })
})
