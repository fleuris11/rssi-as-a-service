import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { assertNoCriticalViolations, resetDemoRequestThrottle, uniqueSuffix } from './helpers.js'

// Site vitrine public (phase 9). Deux parcours réels : le visiteur qui
// découvre le produit et demande une démonstration, et le client existant qui
// passe de la vitrine à son espace.

test('parcours visiteur : accueil, sections, demande de démonstration', async ({ page }) => {
  resetDemoRequestThrottle()
  const suffix = uniqueSuffix()

  await page.goto('/')
  await expect(
    page.getByRole('heading', { level: 1, name: /identifiants ont fuité/ })
  ).toBeVisible()

  // Défilement de toutes les sections : les apparitions au défilement doivent
  // révéler le contenu, pas le laisser invisible.
  for (const id of ['probleme', 'produit', 'fonctionnement', 'securite', 'tarifs', 'questions']) {
    await page.locator(`#${id}`).scrollIntoViewIfNeeded()
    await expect(page.locator(`#${id}`)).toBeVisible()
  }

  await expect(page.getByText('Le plus demandé')).toBeVisible()
  await expect(page.getByRole('button', { name: /Faut-il installer quelque chose/ })).toBeVisible()

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)

  // Conversion
  await page.getByRole('link', { name: /Demander une démonstration/ }).first().click()
  await page.waitForURL('**/demonstration')
  await expect(page.getByRole('heading', { level: 1, name: 'Demander une démonstration' })).toBeVisible()

  await page.getByLabel(/Nom et prénom/).fill('Camille Prospect')
  await page.getByLabel(/^Société/).fill(`Société Test ${suffix}`)
  await page.getByLabel(/Fonction/).fill('Directrice')
  await page.getByLabel(/Email professionnel/).fill(`camille-${suffix}@societe-test.example`)
  await page.getByLabel(/Taille de la société/).selectOption('10-49')
  await page.getByLabel(/Créneau souhaité/).selectOption('morning')
  await page.getByLabel(/Votre message/).fill('Nous aimerions voir la détection de fuites.')

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)

  await page.getByRole('button', { name: /Envoyer ma demande/ }).click()

  await expect(page.getByText(/Votre demande est bien enregistrée/)).toBeVisible()
  await expect(page.getByText(/jour ouvré/)).toBeVisible()
})

test('parcours client : accueil vers connexion', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('link', { name: 'Se connecter' }).first().click()
  await page.waitForURL('**/connexion')

  await expect(page.getByLabel('Email')).toBeVisible()
  await expect(page.getByLabel('Mot de passe')).toBeVisible()
})

test('la vitrine est lisible sur un écran de téléphone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

  // Aucun débordement horizontal : c'est le défaut le plus visible sur
  // téléphone, et le plus facile à laisser passer en développant au large.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  )
  expect(overflow).toBe(false)

  // Le menu replié doit s'ouvrir et donner accès à la conversion.
  await page.getByRole('button', { name: /Ouvrir le menu/ }).click()
  await expect(
    page.getByRole('link', { name: /Demander une démonstration/ }).last()
  ).toBeVisible()

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)
})

test('les pages légales sont accessibles et annoncent ce qui reste à compléter', async ({
  page,
}) => {
  await page.goto('/mentions-legales')
  await expect(page.getByRole('heading', { level: 1, name: 'Mentions légales' })).toBeVisible()
  await expect(page.getByText(/à compléter par l’éditeur/)).toBeVisible()

  await page.goto('/confidentialite')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Politique de confidentialité' })
  ).toBeVisible()
  await expect(page.getByText(/90 jours/).first()).toBeVisible()

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)
})
