import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import Age, { formuler } from './Age'
import BandeauEtat from './BandeauEtat'
import ChiffreAnime from './ChiffreAnime'
import Jauge from './Jauge'
import ListeQuiTombe from './ListeQuiTombe'
import Serie from './Serie'
import { cranDe } from './crans'

const avec = (noeud) => render(<MemoryRouter>{noeud}</MemoryRouter>)

describe('les crans', () => {
  it('traduit le nom que le serveur renvoie, sans recalculer', () => {
    // Le serveur décide. Si sa réponse dit « critique » avec un score de 12,
    // c'est qu'il applique une règle que l'interface ne connaît pas.
    expect(cranDe(12, 'critical').nom).toBe('Critique')
  })

  it('ne tombe sur le calcul local que si le nom manque', () => {
    expect(cranDe(80).nom).toBe('Critique')
    expect(cranDe(60).nom).toBe('Préoccupant')
    expect(cranDe(30).nom).toBe('À surveiller')
    expect(cranDe(5).nom).toBe('Calme')
  })

  it('ne fabrique pas un cran quand il n’y a pas de mesure', () => {
    expect(cranDe(null)).toBeNull()
    expect(cranDe(undefined)).toBeNull()
  })

  it('donne à chaque cran un mot ET un glyphe, jamais la couleur seule', () => {
    for (const score of [5, 30, 60, 80]) {
      const cran = cranDe(score)
      expect(cran.nom).toBeTruthy()
      expect(cran.glyphe).toBeTruthy()
    }
  })
})

describe('le bandeau d’état', () => {
  it('dit le cran en toutes lettres', () => {
    avec(<BandeauEtat score={80} phrase="Un domaine n’est plus protégé." />)
    expect(screen.getByText('Critique')).toBeInTheDocument()
    expect(screen.getByText('Un domaine n’est plus protégé.')).toBeInTheDocument()
  })

  it('porte une seule action', () => {
    avec(<BandeauEtat score={30} action={{ vers: '/exposition', libelle: 'Voir l’exposition' }} />)
    expect(screen.getAllByRole('link')).toHaveLength(1)
  })

  it('reste lisible quand aucun relevé n’existe', () => {
    avec(<BandeauEtat score={null} />)
    expect(screen.getByText('État inconnu')).toBeInTheDocument()
    expect(screen.getByText(/Aucun relevé disponible/)).toBeInTheDocument()
  })
})

describe('la jauge', () => {
  it('affiche la valeur et son cran', () => {
    render(<Jauge score={62} />)
    expect(screen.getByText('62')).toBeInTheDocument()
    expect(screen.getByText('Préoccupant')).toBeInTheDocument()
  })

  it('dit « non mesuré » plutôt que zéro quand il n’y a pas de score', () => {
    render(<Jauge score={null} />)
    expect(screen.getByText('Non mesuré')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })
})

describe('le chiffre animé', () => {
  it('affiche la valeur juste, sans animer, quand rien ne dit qu’on le regarde', () => {
    // Sans IntersectionObserver — un test, un rendu hors navigateur, une
    // capture sans JavaScript complet — le composant n'anime pas : un chiffre
    // qui n'existe qu'à la fin d'une animation n'existe pas.
    render(<ChiffreAnime valeur={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('n’invente rien quand la valeur n’est pas un nombre', () => {
    render(<ChiffreAnime valeur={null} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})

describe('la liste qui tombe', () => {
  it('rend TOUS les éléments dès le premier rendu', () => {
    render(
      <ListeQuiTombe>
        <span key="a">Première alerte</span>
        <span key="b">Deuxième alerte</span>
        <span key="c">Troisième alerte</span>
      </ListeQuiTombe>
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByText('Troisième alerte')).toBeInTheDocument()
  })

  it('garde l’ordre chronologique dans le DOM, l’inversion est visuelle', () => {
    const { container } = render(
      <ListeQuiTombe>
        <span key="a">Plus ancienne</span>
        <span key="b">Plus récente</span>
      </ListeQuiTombe>
    )
    const items = container.querySelectorAll('li')
    expect(items[0].textContent).toBe('Plus ancienne')
    expect(container.querySelector('ul').className).toContain('flex-col-reverse')
  })
})

describe('la série', () => {
  const points = Array.from({ length: 12 }, (_, rang) => ({
    valeur: 20 + rang,
    libelle: `jour ${rang + 1}`,
  }))

  it('décrit la série en texte pour qui ne voit pas le tracé', () => {
    render(<Serie points={points} legende="Exposition" unite=" points" />)
    expect(screen.getByText(/12 mesures/)).toBeInTheDocument()
    expect(screen.getByText(/flèches gauche et droite/)).toBeInTheDocument()
  })

  it('est atteignable au clavier', () => {
    const { container } = render(<Serie points={points} />)
    expect(container.querySelector('svg').getAttribute('tabindex')).toBe('0')
  })

  it('dit qu’il manque des mesures plutôt que de tracer une ligne vide', () => {
    render(<Serie points={[{ valeur: 3, libelle: 'hier' }]} />)
    expect(screen.getByText(/Pas encore assez de mesures/)).toBeInTheDocument()
  })
})

describe('l’âge', () => {
  it('parle en jours plutôt qu’en dates à soustraire', () => {
    expect(formuler(0)).toBe("aujourd'hui")
    expect(formuler(1)).toBe('hier')
    expect(formuler(3)).toBe('il y a 3 jours')
    expect(formuler(70)).toBe('il y a 2 mois')
    expect(formuler(800)).toBe('il y a 2 ans')
  })

  it('garde la date exacte accessible', () => {
    render(<Age date="2026-09-01T10:00:00Z" />)
    expect(screen.getByTitle(/1 septembre 2026/)).toBeInTheDocument()
  })
})
