import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Les jetons sont la source unique de la direction visuelle (docs/design.md,
 * ADR-042). Deux gardes, et elles sont là parce que les deux défauts qu'elles
 * attrapent ne se voient pas à la relecture :
 *
 * 1. une couleur écrite dans un composant échappe au système — on la découvre
 *    six mois plus tard, quand la palette change et qu'un écran ne suit pas ;
 * 2. un contraste s'ESTIME très mal à l'œil. Le gris de texte secondaire de
 *    l'ancienne palette rendait 4,09:1 là où on le croyait conforme.
 */

const RACINE = path.resolve(import.meta.dirname, '..')
const JETONS = path.join(RACINE, 'src/tokens.css')

function luminance(hex) {
  const canal = (v) => {
    const c = v / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const r = canal(parseInt(hex.slice(1, 3), 16))
  const g = canal(parseInt(hex.slice(3, 5), 16))
  const b = canal(parseInt(hex.slice(5, 7), 16))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contraste(a, b) {
  const [clair, sombre] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (clair + 0.05) / (sombre + 0.05)
}

function jetons() {
  const source = fs.readFileSync(JETONS, 'utf8')
  const table = {}
  for (const [, nom, valeur] of source.matchAll(/(--[\w-]+):\s*(#[0-9a-f]{6})\s*;/gi)) {
    table[nom] = valeur.toLowerCase()
  }
  return table
}

function fichiersJsx(dossier, sortie = []) {
  for (const entree of fs.readdirSync(dossier, { withFileTypes: true })) {
    const chemin = path.join(dossier, entree.name)
    if (entree.isDirectory()) fichiersJsx(chemin, sortie)
    else if (entree.name.endsWith('.jsx')) sortie.push(chemin)
  }
  return sortie
}

describe('les jetons sont la source unique', () => {
  it('aucune couleur hexadécimale n’est écrite dans un composant', () => {
    // Les séries de graphiques (recharts) prennent une couleur en propriété
    // JavaScript et ne peuvent pas lire une classe Tailwind : elles sont
    // autorisées à condition de LIRE le jeton, pas de le recopier.
    const fautes = []
    for (const fichier of fichiersJsx(path.join(RACINE, 'src'))) {
      const contenu = fs.readFileSync(fichier, 'utf8')
      for (const ligne of contenu.split('\n')) {
        if (!/#[0-9a-fA-F]{6}\b/.test(ligne)) continue
        if (ligne.includes('var(--color-')) continue
        fautes.push(`${path.relative(RACINE, fichier)} : ${ligne.trim().slice(0, 100)}`)
      }
    }
    expect(fautes, `Couleurs en dur hors de tokens.css :\n${fautes.join('\n')}`).toEqual([])
  })

  it('déclare les familles du monde retenu, et aucune autre', () => {
    const source = fs.readFileSync(JETONS, 'utf8')
    expect(source).toContain('Archivo Variable')
    expect(source).toContain('Chivo Mono Variable')
    // Les faces de l'ancienne direction ne doivent plus exister nulle part :
    // une police fantôme dans une pile de repli se voit le jour où la
    // première ne charge pas.
    expect(source).not.toContain('Fraunces')
    expect(source).not.toContain('Inter')
  })
})

describe('les contrastes sont calculés, pas crus', () => {
  const t = jetons()

  const surLaFace = [
    ['--color-ink-900', 'texte principal'],
    ['--color-ink-800', 'texte courant'],
    ['--color-ink-700', 'texte de corps'],
    ['--color-ink-600', 'texte secondaire'],
    ['--color-ink-500', 'légendes et méta'],
    ['--color-brand-600', 'action et liens'],
    ['--color-risk-calm', 'cran calme'],
    ['--color-risk-watch', 'cran à surveiller'],
    ['--color-risk-concern', 'cran préoccupant'],
    ['--color-risk-critical', 'cran critique'],
  ]

  it.each(surLaFace)('%s (%s) atteint 4,5:1 sur le fond de page', (jeton) => {
    expect(contraste(t[jeton], t['--color-canvas'])).toBeGreaterThanOrEqual(4.5)
  })

  it.each(surLaFace)('%s (%s) atteint 4,5:1 sur un panneau blanc', (jeton) => {
    expect(contraste(t[jeton], t['--color-surface'])).toBeGreaterThanOrEqual(4.5)
  })

  // Le fond CREUSE est le plus clair des trois pièges : c'est celui des têtes
  // de panneau, des en-têtes de tableau et des lignes alternées. C'est là
  // qu'axe-core a pris le texte secondaire en défaut (4,38:1), pas sur le
  // fond de page.
  it.each(surLaFace)('%s (%s) atteint 4,5:1 sur la face creuse', (jeton) => {
    expect(contraste(t[jeton], t['--color-creuse'])).toBeGreaterThanOrEqual(4.5)
  })

  const crans = ['calm', 'watch', 'concern', 'critical']
  it.each(crans)('le cran %s reste lisible sur sa propre pastille', (cran) => {
    expect(
      contraste(t[`--color-risk-${cran}`], t[`--color-risk-${cran}-surface`])
    ).toBeGreaterThanOrEqual(4.5)
  })

  const surLeBati = [
    ['--color-craie', 'texte sur bâti'],
    ['--color-craie-douce', 'texte secondaire sur bâti'],
    ['--color-action-claire', 'lien sur bâti'],
  ]
  it.each(surLeBati)('%s (%s) atteint 4,5:1 sur le bâti', (jeton) => {
    expect(contraste(t[jeton], t['--color-bati-800'])).toBeGreaterThanOrEqual(4.5)
    expect(contraste(t[jeton], t['--color-bati-900'])).toBeGreaterThanOrEqual(4.5)
  })

  it('le bandeau gorgé de critique reste lisible en craie', () => {
    expect(contraste(t['--color-craie'], t['--color-risk-critical-drape'])).toBeGreaterThanOrEqual(
      4.5
    )
  })

  it('l’action n’emprunte aucun cran de risque', () => {
    for (const cran of crans) {
      expect(t['--color-brand-600']).not.toBe(t[`--color-risk-${cran}`])
    }
  })
})
