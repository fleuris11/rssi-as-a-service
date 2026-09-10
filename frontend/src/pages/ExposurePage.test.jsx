import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ExposurePage from './ExposurePage'

// Ce qui est vérifié ici : que la page rend fidèlement ce que le serveur
// calcule. Les règles métier (score, vulgarisation, vocabulaire de
// corrélation) vivent côté backend et y sont testées ; le risque côté
// frontend est de les déformer ou de les perdre en route.

vi.mock('../api/endpoints', () => ({
  threatIntelligenceApi: {
    exposureFeed: vi.fn(),
    preIncident: vi.fn(),
    updateFindingStatus: vi.fn(),
    refreshExposureSynthesis: vi.fn(),
  },
  aiApi: { getJob: vi.fn() },
}))
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { is_staff: false }, currentTenant: { role: 'admin' } }),
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
// La page affiche désormais certaines actions derrière FeatureGate. Les droits
// eux-mêmes sont testés dans FeatureGate.test.jsx : ici on se place sur une
// offre complète, pour que ces tests continuent de porter sur le RENDU de ce
// que calcule le serveur.
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    featureInfo: () => null,
    requiredPlanFor: () => '',
    isOperational: true,
    loading: false,
  }),
}))

const { threatIntelligenceApi } = await import('../api/endpoints')

const PURGED_FINDING = {
  id: 10,
  source_endpoint: 'combo',
  source_label: 'Liste combo (identifiant + mot de passe)',
  finding_type: 'combo',
  severity: 'high',
  severity_label: 'Élevée',
  identifier: 'sophie@exemple.fr',
  secret_masked: '••••••19',
  has_secret: false,
  secret_purged_at: '2026-05-02T09:00:00Z',
  breach_date: '2025-06-01',
  detected_at: '2025-06-03T09:00:00Z',
  meaning: 'Cet identifiant circule dans une liste de comptes compromis.',
  recommended_action: 'Changez ce mot de passe dès que possible.',
  reuse_signals: [],
}

const CORRELATED_FINDING = {
  ...PURGED_FINDING,
  id: 11,
  has_secret: true,
  secret_purged_at: null,
  reuse_signals: [
    {
      signal_type: 'external_service',
      label: 'Réutilisation possible — adresse professionnelle sur un service externe',
      explanation:
        'Une adresse professionnelle de votre entreprise apparaît dans la fuite d’un service qui n’est pas le vôtre. C’est une hypothèse à vérifier.',
      identifier: 'marie@exemple.fr',
      related_finding_ids: [],
      external_service: 'boutique.example',
    },
  ],
}

function feed(findings, overrides = {}) {
  return {
    data: {
      assets: [
        {
          asset_id: 1,
          asset_value: 'exemple.fr',
          asset_type_label: 'Domaine email',
          score: 62,
          level: 'preoccupant',
          level_label: 'Préoccupant',
          findings_count: findings.length,
          // Le serveur envoie TOUJOURS ces deux champs, y compris à zéro.
          // Les omettre du fixture rendait vide le test « ne dit rien quand
          // tout est affiché » : `undefined > 0` est faux quelle que soit la
          // condition écrite dans la page, donc le test passait même avec le
          // bandeau affiché en permanence.
          findings_shown: findings.length,
          findings_hidden: 0,
          components: [
            {
              finding_id: 11,
              label: 'Identifiants exposés',
              severity: 'high',
              points: 29,
              detail: 'gravité élevée, fuite moins de trois mois, mot de passe récupérable',
            },
            {
              finding_id: 10,
              label: 'Liste combo',
              severity: 'high',
              points: 0,
              detail: '2e fuite sur cet actif, pondérée à la baisse',
            },
          ],
          findings,
          reuse_signals: findings.flatMap((f) => f.reuse_signals),
        },
      ],
      total_findings: findings.length,
      highest_score: 62,
      retention_policy: { secret_retention_days: 90, reveal_audit_retention_days: 365 },
      synthesis: null,
      ...overrides,
    },
  }
}

describe('ExposurePage', () => {
  beforeEach(() => {
    threatIntelligenceApi.preIncident.mockResolvedValue({ data: { signals: [], total: 0 } })
  })

  describe('score et son explication', () => {
    it('affiche le score et le niveau calculés par le serveur', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      expect(await screen.findByText('62')).toBeInTheDocument()
      expect(screen.getByText('Préoccupant')).toBeInTheDocument()
    })

    it('détaille les composantes du score (ADR-016 : score explicable)', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      expect(await screen.findByText('D’où vient ce score')).toBeInTheDocument()
      expect(screen.getByText('+29')).toBeInTheDocument()
      expect(
        screen.getByText(/gravité élevée, fuite moins de trois mois, mot de passe récupérable/)
      ).toBeInTheDocument()
    })

    it('n’écrit jamais « +0 » pour une contribution négligeable', async () => {
      // « +0 » est arithmétiquement honnête — cette n-ième fuite ne pèse
      // presque plus — mais se lit comme un bug côté client.
      //
      // L'assertion porte sur le COMPORTEMENT (« +0 » n'apparaît jamais) et
      // non sur la formulation retenue : le libellé est passé de « moins
      // de 1 » à « < 1 » quand la colonne des poids est devenue alignée à
      // droite en chiffres tabulaires. Une assertion sur le texte exact
      // faisait rougir un test de fond pour un choix de mise en forme.
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      expect(await screen.findByText('< 1')).toBeInTheDocument()
      expect(screen.queryByText('+0')).not.toBeInTheDocument()
    })
  })

  describe('fuite dont le secret a été purgé', () => {
    it('indique que le mot de passe a été effacé, avec le délai de conservation', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([PURGED_FINDING]))
      render(<ExposurePage />)

      // Le dire explicitement évite de laisser croire qu'il n'y a jamais eu
      // de mot de passe (ADR-014). Le délai figure aussi dans le rappel de
      // politique en bas de page, d'où l'assertion scopée à la mention.
      const purgeNotice = await screen.findByText(/Mot de passe effacé le/)
      expect(purgeNotice).toBeInTheDocument()
      expect(purgeNotice.textContent).toMatch(/90 jours/)
    })

    it('n’offre pas de révélation sur une fuite purgée', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([PURGED_FINDING]))
      render(<ExposurePage />)

      await screen.findByText(/Mot de passe effacé le/)
      expect(
        screen.queryByRole('button', { name: 'Révéler le mot de passe' })
      ).not.toBeInTheDocument()
    })

    it('propose la révélation quand le secret est encore disponible', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      expect(
        await screen.findByRole('button', { name: 'Révéler le mot de passe' })
      ).toBeInTheDocument()
    })
  })

  describe('corrélation de réutilisation', () => {
    it('affiche le signal avec le vocabulaire du serveur, sans le reformuler', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      expect(await screen.findByText(/Réutilisation possible — à vérifier/)).toBeInTheDocument()
      // `findByText` et non `getByText` : l'explication est peinte APRÈS le
      // libellé du signal. La lecture synchrone passait tant que la machine
      // était rapide, et échouait environ une fois sur deux dès que la suite
      // s'est allongée — un test intermittent finit par être ignoré, ce qui
      // coûte plus cher que le test lui-même. L'assertion est inchangée :
      // c'est bien le texte exact du serveur qui est exigé.
      expect(await screen.findByText(/hypothèse à vérifier/)).toBeInTheDocument()
    })

    it('n’affirme jamais une réutilisation confirmée', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      const { container } = render(<ExposurePage />)

      await screen.findByText(/Réutilisation possible — à vérifier/)
      expect(container.textContent).not.toMatch(/réutilisation confirmée/i)
      expect(container.textContent).not.toMatch(/compromis confirmé/i)
    })
  })

  describe('politique de conservation', () => {
    it('est lisible par le client sur la page', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      expect(await screen.findByText(/Conservation :/)).toBeInTheDocument()
      expect(screen.getByText(/365 jours/)).toBeInTheDocument()
    })
  })

  describe('bandeau de synthèse', () => {
    it('reste absent quand aucune analyse n’existe, sans bloquer la page', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      await screen.findByText('62')
      // La page est complète sans la synthèse : c'est une couche au-dessus.
      expect(screen.queryByRole('heading', { name: 'Analyse' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Générer l’analyse/ })).toBeInTheDocument()
    })

    it('signale une analyse antérieure aux dernières actions', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(
        feed([CORRELATED_FINDING], {
          synthesis: {
            content: 'Votre exposition est concentrée sur un compte.',
            generated_at: '2026-08-01T10:00:00Z',
            is_stale: true,
          },
        })
      )
      render(<ExposurePage />)

      expect(await screen.findByRole('heading', { name: 'Analyse' })).toBeInTheDocument()
      expect(screen.getByText(/Antérieure à vos dernières actions/)).toBeInTheDocument()
    })
  })

  // Le serveur ne transmet plus que les cent fuites les plus graves par actif
  // (panne du 06/09/2026 : 28 450 fuites sérialisées figeaient l'onglet du
  // client). Une liste tronquée sans mention de la troncature ment par
  // omission — le dirigeant croirait avoir tout vu.
  describe('liste tronquée', () => {
    it('dit combien de fuites sont affichées et combien restent', async () => {
      threatIntelligenceApi.exposureFeed.mockResolvedValue(
        feed([CORRELATED_FINDING], {
          assets: [
            {
              asset_id: 1,
              asset_value: 'exemple.fr',
              asset_type_label: 'Domaine email',
              score: 96,
              level: 'critique',
              level_label: 'Critique',
              findings_count: 28450,
              findings_shown: 100,
              findings_hidden: 28350,
              components: [],
              findings: [CORRELATED_FINDING],
              reuse_signals: [],
            },
          ],
        })
      )
      render(<ExposurePage />)

      await screen.findByText('96')
      expect(screen.getByText(/28450 au total pour cet actif/)).toBeInTheDocument()
      expect(screen.getByText(/28350 autres sont plus anciens ou moins graves/)).toBeInTheDocument()
      expect(screen.getByText(/restent comptés dans le score/)).toBeInTheDocument()
    })

    it('ne dit rien quand tout est affiché', async () => {
      // Le cas de la quasi-totalité des clients : douze fuites, aucune
      // troncature. Une mention permanente inquiéterait pour rien.
      threatIntelligenceApi.exposureFeed.mockResolvedValue(feed([CORRELATED_FINDING]))
      render(<ExposurePage />)

      await screen.findByText('62')
      expect(screen.queryByText(/au total pour cet actif/)).not.toBeInTheDocument()
    })
  })
})
