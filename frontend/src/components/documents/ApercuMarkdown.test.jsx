import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ApercuMarkdown, { compterACompleter } from './ApercuMarkdown'

const DOCUMENT = [
  '# Procédure de gestion des incidents',
  '',
  '**Cabinet Durand**',
  '',
  '| | |',
  '|---|---|',
  '| Version | v2 |',
  '| Validé par | *[à compléter]* |',
  '',
  '## Dans la première heure',
  '',
  '1. Débrancher le réseau.',
  '2. Prévenir : *[à compléter]* (référent sécurité).',
].join('\n')

describe('ApercuMarkdown', () => {
  it('rend les titres, les tableaux et les listes du document', () => {
    render(<ApercuMarkdown markdown={DOCUMENT} />)

    expect(screen.getByRole('heading', { name: 'Procédure de gestion des incidents' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dans la première heure' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'v2' })).toBeInTheDocument()
    expect(screen.getByText('Débrancher le réseau.')).toBeInTheDocument()
    expect(screen.getByText('Cabinet Durand').tagName).toBe('STRONG')
  })

  it('surligne ce qui reste à compléter, et le compte', () => {
    const { container } = render(<ApercuMarkdown markdown={DOCUMENT} />)

    expect(container.querySelectorAll('mark')).toHaveLength(2)
    expect(compterACompleter(DOCUMENT)).toBe(2)
  })

  it('n’interprète jamais le HTML d’un champ saisi par le client', () => {
    const { container } = render(
      <ApercuMarkdown markdown={'# <img src=x onerror="alert(1)"> Durand'} />
    )

    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByRole('heading')).toHaveTextContent('<img src=x onerror="alert(1)"> Durand')
  })
})
