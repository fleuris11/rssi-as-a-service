import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CompromisesPage from './CompromisesPage'

// Ce qui est vérifié ici : les deux états que le jeu de démonstration ne
// permet pas d'atteindre à la main. Une entreprise de démonstration a
// toujours des fuites ouvertes — l'écran « aucune fuite » est donc invisible
// en vérification manuelle, alors que c'est celui que le client verra le jour
// où le produit a fait son travail.

vi.mock('../api/endpoints', () => ({
  threatIntelligenceApi: {
    listFindings: vi.fn(),
    status: vi.fn(),
    listMonitoredAssets: vi.fn(),
    listRevealAudit: vi.fn(),
    getScanJob: vi.fn(),
    triggerScan: vi.fn(),
    updateFindingStatus: vi.fn(),
    registerMonitoredAsset: vi.fn(),
    unregisterMonitoredAsset: vi.fn(),
  },
  monitoringApi: { listAssets: vi.fn() },
}))
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { is_staff: false }, currentTenant: { role: 'admin' } }),
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

const { threatIntelligenceApi, monitoringApi } = await import('../api/endpoints')

const fuite = (id, severity, asset, extra = {}) => ({
  id,
  severity,
  status: 'open',
  asset_value: asset,
  source_endpoint: 'stealer',
  meaning: 'Explication.',
  impact: 'Le compte est utilisable immédiatement.',
  recommended_action: 'Action.',
  has_secret: false,
  breach_date: '2026-07-03',
  identifier: 'marie@exemple.fr',
  details: [],
  ...extra,
})

function servir(findings, statut = {}) {
  threatIntelligenceApi.listFindings.mockResolvedValue({ data: { results: findings } })
  // Statut CLOISONNÉ : ce que l'offre du client comprend, jamais les
  // chiffres de la plateforme (voir le test « ne montre jamais… » plus bas).
  threatIntelligenceApi.status.mockResolvedValue({
    data: {
      scans_quota: 20,
      scans_used: 3,
      scans_remaining: 17,
      monitored_quota: 1,
      monitored_used: 0,
      monitored_remaining: 1,
      cooldown_active: false,
      // Le serveur envoie une phrase déjà formée. `cooldown_hours` n'existe
      // plus depuis que le délai se règle en minutes : l'écran affichait
      // « d’ici  h ».
      cooldown_minutes: 1440,
      cooldown_label: '24 h',
      running_scan_id: null,
      last_scan_finished_at: null,
      ...statut,
    },
  })
  monitoringApi.listAssets.mockResolvedValue({ data: { results: [] } })
  threatIntelligenceApi.listMonitoredAssets.mockResolvedValue({ data: { results: [] } })
}

describe('CompromisesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('annonce l’absence de fuite comme une bonne nouvelle, pas comme un vide', async () => {
    // « Aucune compromission ouverte », en gris sous un pictogramme d'alerte,
    // se lisait comme une panne. C'est pourtant le résultat que le client
    // paie pour obtenir.
    servir([])
    render(<CompromisesPage />)

    expect(await screen.findByText('Aucune fuite en cours')).toBeInTheDocument()
    expect(screen.getByText(/La surveillance continue en arrière-plan/)).toBeInTheDocument()
  })

  // V2-1 : une fuite déjà traitée que l'analyse revoit ne revient pas dans la
  // liste — mais l'écran doit le DIRE. Masquer sans le dire serait cacher, et
  // le client se demanderait pourquoi son analyse ne trouve « plus rien ».
  it('annonce les fuites déjà traitées que l’analyse a revues, et y donne accès', async () => {
    servir([], { running_scan_id: 7 })
    threatIntelligenceApi.getScanJob.mockResolvedValue({
      data: {
        id: 7,
        status: 'done',
        result_ref: { findings_created: 0, already_treated_seen: 3 },
      },
    })
    render(<CompromisesPage />)

    expect(await screen.findByText(/3 compromissions/)).toBeInTheDocument()
    expect(screen.getByText(/ne reviennent pas dans cette liste/)).toBeInTheDocument()

    // Le lien mène à l'onglet où elles se trouvent réellement.
    await userEvent.click(screen.getByRole('button', { name: 'Les consulter' }))
    expect(threatIntelligenceApi.listFindings).toHaveBeenCalledWith('treated')
  })

  it('ne dit rien quand l’analyse n’a revu aucune fuite déjà traitée', async () => {
    servir([], { running_scan_id: 8 })
    threatIntelligenceApi.getScanJob.mockResolvedValue({
      data: { id: 8, status: 'done', result_ref: { findings_created: 0, already_treated_seen: 0 } },
    })
    render(<CompromisesPage />)

    // `waitFor` plutôt que `findByText` : la page traverse trois rendus
    // avant de se poser (squelette, reprise de l'analyse en cours,
    // rechargement), et `findByText` ne la rattrapait pas de façon fiable
    // quand tout le fichier tourne.
    await waitFor(() =>
      expect(screen.getByText('Aucune fuite en cours')).toBeInTheDocument()
    )
    expect(screen.queryByText(/déjà traitée/)).not.toBeInTheDocument()
  })

  // ADR-026 : proposer « Surveiller » sur un actif dont la possession n'est
  // pas prouvée mènerait droit à un refus. L'écran nomme d'emblée l'étape qui
  // manque, au lieu de laisser le client la découvrir en échouant.
  it('propose de prouver la possession au lieu de surveiller un actif non prouvé', async () => {
    servir([])
    monitoringApi.listAssets.mockResolvedValue({
      data: { results: [{ id: 4, value: 'https://acme.example', ownership_state: 'declared' }] },
    })
    render(<CompromisesPage />)

    expect(await screen.findByRole('button', { name: 'Prouver la possession' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Surveiller' })).not.toBeInTheDocument()
  })

  it('propose de surveiller un actif dont la possession est prouvée', async () => {
    servir([])
    monitoringApi.listAssets.mockResolvedValue({
      data: { results: [{ id: 4, value: 'https://acme.example', ownership_state: 'proven' }] },
    })
    render(<CompromisesPage />)

    expect(await screen.findByRole('button', { name: 'Surveiller' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Prouver la possession' })).not.toBeInTheDocument()
  })

  // V2-2 (ADR-027) : ce que la source renvoie et que le produit taisait.
  it('restitue les champs de la source avec leur libellé et ce qu’ils impliquent', async () => {
    servir([
      fuite(1, 'critical', 'a.example', {
        details: [
          {
            label: 'Logiciel malveillant identifié',
            value: 'Raccoon',
            implication: 'C’est un logiciel qui recopie les mots de passe du navigateur.',
          },
          {
            label: 'Poste infecté',
            value: 'Windows 10 Home',
            implication: 'Le poste doit être nettoyé avant tout accès sensible.',
          },
        ],
      }),
    ])
    render(<CompromisesPage />)

    // Replié par défaut : le détail ne doit pas noyer « ce qu'il faut faire ».
    const bascule = await screen.findByRole('button', { name: /Ce que l’on sait de plus \(2\)/ })
    expect(screen.queryByText('Raccoon')).not.toBeInTheDocument()

    await userEvent.click(bascule)

    expect(screen.getByText('Logiciel malveillant identifié')).toBeInTheDocument()
    expect(screen.getByText('Raccoon')).toBeInTheDocument()
    // La valeur seule n'informe pas : « Raccoon » ne dit rien à un dirigeant.
    expect(
      screen.getByText('C’est un logiciel qui recopie les mots de passe du navigateur.')
    ).toBeInTheDocument()
  })

  it('n’affiche jamais le nom technique du champ à la place du libellé', async () => {
    servir([
      fuite(1, 'critical', 'a.example', {
        details: [{ label: 'Détecté le', value: '4 septembre 2026', implication: 'Une date.' }],
      }),
    ])
    render(<CompromisesPage />)

    await userEvent.click(await screen.findByRole('button', { name: /Ce que l’on sait de plus/ }))

    expect(screen.getByText('Détecté le')).toBeInTheDocument()
    expect(screen.queryByText('fnd')).not.toBeInTheDocument()
  })

  it('affiche ce que la fuite implique, pas seulement ce qu’elle est', async () => {
    servir([fuite(1, 'critical', 'a.example')])
    render(<CompromisesPage />)

    expect(await screen.findByText('Le compte est utilisable immédiatement.')).toBeInTheDocument()
    expect(screen.getByText('Explication.')).toBeInTheDocument()
  })

  it('sert l’adresse telle que le serveur la donne, sans arbitrer côté écran', async () => {
    // Le serveur décide selon le rôle (ADR-027). Un arbitrage ici serait une
    // garde qui saute au premier composant qui oublie de la refaire.
    servir([fuite(1, 'critical', 'a.example', { identifier: 'ma••••@ex••••.fr' })])
    render(<CompromisesPage />)

    expect(await screen.findByText(/ma••••@ex••••\.fr/)).toBeInTheDocument()
  })

  it('regroupe par gravité et met le compte dans le séparateur', async () => {
    // Le serveur ne garantit pas l'ordre : ici, une critique arrive APRÈS
    // deux élevées, comme sur le jeu de démonstration.
    servir([
      fuite(1, 'high', 'a.example'),
      fuite(2, 'high', 'b.example'),
      fuite(3, 'critical', 'c.example'),
    ])
    render(<CompromisesPage />)

    expect(await screen.findByRole('heading', { name: 'Critique — 1 fuite' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Élevée — 2 fuites' })).toBeInTheDocument()

    // Le groupe critique passe devant, quel que soit l'ordre d'arrivée.
    const titres = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(titres.indexOf('Critique — 1 fuite')).toBeLessThan(titres.indexOf('Élevée — 2 fuites'))
  })

  it('ne laisse qu’une seule action remplie par fuite', async () => {
    // Trois actions de poids voisin ne disent plus laquelle est le chemin
    // normal. `Button` rend l'action primaire avec `bg-brand-600`.
    servir([fuite(1, 'critical', 'a.example')])
    render(<CompromisesPage />)

    const traiter = await screen.findByRole('button', { name: 'Marquer traité' })
    expect(traiter.className).toContain('bg-brand-600')
    expect(screen.getByRole('button', { name: 'Ignorer' }).className).not.toContain('bg-brand-600')
  })
  it('ne montre jamais les chiffres de la plateforme au client', async () => {
    // Cet écran affichait « Quota de requêtes restant (plateforme) : 971 » et
    // « 0 / 15 emplacements utilisés … pour toute la plateforme ». Deux
    // nombres qui ne concernent pas celui qui les lit, et qui publient la
    // consommation des autres clients — dans un produit dont l'argument est
    // le cloisonnement.
    servir([fuite(1, 'critical', 'a.example')])
    render(<CompromisesPage />)
    await screen.findByRole('heading', { name: 'Critique — 1 fuite' })

    const texte = document.body.textContent
    expect(texte).not.toMatch(/plateforme/i)
    expect(texte).not.toMatch(/toute la plateforme/i)
    expect(texte).not.toMatch(/15 actifs/)
  })

  it('affiche le quota d’analyses de l’offre du client', async () => {
    servir([fuite(1, 'critical', 'a.example')])
    render(<CompromisesPage />)
    await screen.findByRole('heading', { name: 'Critique — 1 fuite' })

    expect(screen.getByText(/Analyses restantes ce mois/)).toBeInTheDocument()
    expect(screen.getByText('17')).toBeInTheDocument()
    expect(screen.getByText(/sur 20 comprises dans votre offre/)).toBeInTheDocument()
  })

  // Remonté par le client : « quand l'analyse est lancée ça ne me dit pas si
  // c'est terminé ou pas, et si je change d'écran je ne sais pas si l'analyse
  // s'arrête ». Elle ne s'arrête pas — elle tourne dans un worker. C'est
  // l'écran qui l'oubliait, parce que l'état ne vivait que dans le composant.
  describe('suivi de l’analyse', () => {
    it('retrouve une analyse déjà en cours au chargement de la page', async () => {
      // Le scénario exact : le client lance une analyse, va sur une autre
      // page, revient. Le composant est neuf, mais le job tourne toujours.
      servir([], { running_scan_id: 42 })
      threatIntelligenceApi.getScanJob.mockResolvedValue({ data: { id: 42, status: 'running' } })
      render(<CompromisesPage />)

      expect(await screen.findByRole('button', { name: /Analyse en cours/ })).toBeInTheDocument()
      expect(threatIntelligenceApi.getScanJob).toHaveBeenCalledWith(42)
    })

    it('dit que l’analyse continue si on quitte la page', async () => {
      servir([], { running_scan_id: 42 })
      threatIntelligenceApi.getScanJob.mockResolvedValue({ data: { id: 42, status: 'running' } })
      render(<CompromisesPage />)

      await screen.findByRole('button', { name: /Analyse en cours/ })
      expect(screen.getByText(/se poursuit sur nos serveurs/)).toBeInTheDocument()
    })

    it('indique quand la dernière analyse s’est terminée', async () => {
      // Sans cette phrase, une page sans analyse en cours est indiscernable
      // d'une page où rien n'a jamais été lancé.
      servir([], { last_scan_finished_at: '2026-09-06T16:08:57Z' })
      render(<CompromisesPage />)

      expect(await screen.findByText(/Dernière analyse terminée le/)).toBeInTheDocument()
    })

    it('n’affiche pas le délai anti-abus avec une unité perdue', async () => {
      // `cooldown_hours` n'existe plus côté serveur : la phrase se composait
      // en « Une nouvelle sera possible d’ici  h ».
      servir([], { cooldown_active: true, cooldown_minutes: 90, cooldown_label: '1 h 30' })
      render(<CompromisesPage />)

      expect(await screen.findByText(/possible d’ici 1 h 30/)).toBeInTheDocument()
      expect(document.body.textContent).not.toMatch(/d’ici\s+h/)
    })
  })
})
