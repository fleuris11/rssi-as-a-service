import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ContenuEcran from './ContenuEcran'

describe('ContenuEcran', () => {
  it('rend chacun des six types de bloc', () => {
    render(
      <ContenuEcran
        blocs={[
          { type: 'paragraphe', texte: 'Un paragraphe.' },
          { type: 'titre', niveau: 3, texte: 'Un titre' },
          { type: 'liste', items: ['Premier', 'Second'] },
          { type: 'encadre', ton: 'attention', texte: 'Un avertissement.' },
          { type: 'image', source: '/formation/schema.svg', alternative: 'Un schéma.' },
          { type: 'citation', texte: 'Une citation.', source: 'ANSSI' },
        ]}
      />
    )

    expect(screen.getByText('Un paragraphe.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Un titre' })).toBeInTheDocument()
    expect(screen.getByText('Premier')).toBeInTheDocument()
    expect(screen.getByText('Un avertissement.')).toBeInTheDocument()
    expect(screen.getByText('Une citation.')).toBeInTheDocument()
    expect(screen.getByText('— ANSSI')).toBeInTheDocument()
  })

  it('donne toujours un texte alternatif à une image', () => {
    render(
      <ContenuEcran
        blocs={[{ type: 'image', source: '/formation/x.svg', alternative: 'Un schéma.' }]}
      />
    )
    // getByAltText échoue si l'attribut manque : c'est la garantie côté
    // interface de ce que le serveur impose déjà à l'écriture.
    expect(screen.getByAltText('Un schéma.')).toBeInTheDocument()
  })

  it('ne descend jamais sous un h3, pour ne pas casser la hiérarchie de la page', () => {
    // Le titre de l'écran est un h2 porté par la page. Un bloc titre ne peut
    // être que h3 ou h4 — ce qui permet de naviguer par en-têtes au lecteur
    // d'écran.
    render(<ContenuEcran blocs={[{ type: 'titre', niveau: 4, texte: 'Sous-titre' }]} />)
    expect(screen.getByRole('heading', { level: 4, name: 'Sous-titre' })).toBeInTheDocument()
  })

  it('nomme le ton d’un encadré, et ne le laisse pas à la seule couleur', () => {
    render(<ContenuEcran blocs={[{ type: 'encadre', ton: 'attention', texte: 'Prudence.' }]} />)
    // Une couleur seule ne dit rien à qui ne la distingue pas.
    expect(screen.getByText('Point de vigilance :')).toBeInTheDocument()
  })

  it('ignore silencieusement un type inconnu plutôt que d’afficher une erreur', () => {
    // Si le studio de F2 produit un jour un type que cette version ignore, un
    // salarié doit voir un écran incomplet — pas un message technique.
    const { container } = render(
      <ContenuEcran
        blocs={[
          { type: 'venu-du-futur', texte: 'Inconnu' },
          { type: 'paragraphe', texte: 'Le reste s’affiche.' },
        ]}
      />
    )
    expect(screen.getByText('Le reste s’affiche.')).toBeInTheDocument()
    expect(container.textContent).not.toContain('Inconnu')
  })
})
