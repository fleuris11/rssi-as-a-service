import { test } from '@playwright/test'

// Captures de référence pour la refonte visuelle. Fichier temporaire.
// Variable d'environnement CAPTURE_PHASE : "avant" ou "apres".

const PHASE = process.env.CAPTURE_PHASE || 'avant'
const COMPTE = 'marie.durand@cabinet-durand-demo.fr'
const MDP = 'DemoDurand2026!'

const PAGES = [
  { chemin: '/tableau-de-bord', nom: 'tableau' },
  { chemin: '/exposition', nom: 'exposition' },
  { chemin: '/compromissions', nom: 'compromissions' },
]

async function connecter(page) {
  await page.goto('/connexion')
  await page.getByLabel('Email').fill(COMPTE)
  await page.getByLabel('Mot de passe').fill(MDP)
  await page.getByRole('button', { name: /Se connecter/i }).click()
  await page.waitForURL('**/tableau-de-bord')
}

test('captures bureau', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await connecter(page)
  for (const { chemin, nom } of PAGES) {
    await page.goto(chemin)
    // D'abord attendre que le titre soit là (React a monté la page), PUIS
    // que les squelettes aient disparu. Attendre seulement l'absence de
    // squelettes passe instantanément : au premier tour, React n'a encore
    // rien monté et le compte vaut déjà zéro.
    await page.getByRole('heading', { level: 1 }).waitFor({ timeout: 30_000 })
    await page.waitForFunction(
      () => document.querySelectorAll('[data-loading="true"]').length === 0,
      undefined,
      { timeout: 30_000 }
    )
    await page.waitForTimeout(1500)
    await page.screenshot({
      path: `captures/${PHASE}-${nom}-bureau.png`,
      fullPage: true,
    })
  }
})

test('captures telephone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await connecter(page)
  for (const { chemin, nom } of PAGES) {
    await page.goto(chemin)
    // D'abord attendre que le titre soit là (React a monté la page), PUIS
    // que les squelettes aient disparu. Attendre seulement l'absence de
    // squelettes passe instantanément : au premier tour, React n'a encore
    // rien monté et le compte vaut déjà zéro.
    await page.getByRole('heading', { level: 1 }).waitFor({ timeout: 30_000 })
    await page.waitForFunction(
      () => document.querySelectorAll('[data-loading="true"]').length === 0,
      undefined,
      { timeout: 30_000 }
    )
    await page.waitForTimeout(1500)
    await page.screenshot({
      path: `captures/${PHASE}-${nom}-telephone.png`,
      fullPage: true,
    })
  }
})

// --- Vitrine publique : aucune authentification -------------------------
const PAGES_PUBLIQUES = [
  { chemin: '/', nom: 'vitrine' },
  { chemin: '/demonstration', nom: 'demonstration' },
]

/** Capture PLEINE HAUTEUR sans défiler.
 *
 * Le piège de la phase 9 : les apparitions au défilement (`Reveal`) partent à
 * `opacity-0`. Une capture pleine hauteur prise sans avoir fait défiler la
 * page montre donc en noir sur blanc ce qui dépend d'une animation pour être
 * visible — c'est exactement le contrôle qu'on veut, et il ne vaut QUE si on
 * ne défile pas d'abord. */
async function capturerPublique(page, phase, suffixeNom) {
  for (const { chemin, nom } of PAGES_PUBLIQUES) {
    await page.goto(chemin)
    await page.getByRole('heading', { level: 1 }).waitFor({ timeout: 30_000 })
    await page.waitForTimeout(2500)
    await page.screenshot({
      path: `captures/${phase}-${nom}-${suffixeNom}.png`,
      fullPage: true,
    })
  }
}

test('captures vitrine bureau', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await capturerPublique(page, PHASE, 'bureau')
})

test('captures vitrine telephone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await capturerPublique(page, PHASE, 'telephone')
})
