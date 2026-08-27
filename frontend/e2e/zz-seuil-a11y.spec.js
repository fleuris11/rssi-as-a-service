import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import {
  registerNewTenant,
  releaseE2ETenants,
  uniqueSuffix,
  waitForContentLoaded,
} from './helpers.js'

// Mesure temporaire : que ferait rougir un seuil abaissé à « moderate » ?
// On n'assène rien, on compte.

// Le locataire créé ici engage un vrai emplacement sur le pool PARTAGÉ de la
// licence (ADR-013). Sans cette restitution, deux exécutions suffisent à le
// saturer — 13 des 15 emplacements sont déjà pris par le jeu de démonstration
// — et les suivantes se voient refuser l'inscription. Le symptôme ressemble à
// une panne ; c'est la garde qui fait son travail.
test.afterAll(() => {
  releaseE2ETenants()
})

const PAGES = [
  '/tableau-de-bord',
  '/resultats',
  '/exposition',
  '/compromissions',
  '/assistant',
  '/documents',
  '/preferences',
  '/securite',
]

test('inventaire des violations par gravité', async ({ page }) => {
  const suffixe = uniqueSuffix()
  await registerNewTenant(page, {
    companyName: `E2E Seuil ${suffixe}`,
    email: `seuil-${suffixe}@example.com`,
  })

  const total = {}
  const parRegle = {}

  for (const chemin of ['/connexion', '/inscription']) {
    await page.goto(chemin)
    await waitForContentLoaded(page)
    const r = await new AxeBuilder({ page }).analyze()
    for (const v of r.violations) {
      total[v.impact] = (total[v.impact] || 0) + v.nodes.length
      const cle = `${v.impact} | ${v.id} | ${chemin} | ${v.nodes.map((n) => n.target.join(" ")).join(" ;; ")}`
      parRegle[cle] = (parRegle[cle] || 0) + v.nodes.length
    }
  }

  for (const chemin of PAGES) {
    await page.goto(chemin)
    await waitForContentLoaded(page)
    const r = await new AxeBuilder({ page }).analyze()
    for (const v of r.violations) {
      total[v.impact] = (total[v.impact] || 0) + v.nodes.length
      const cle = `${v.impact} | ${v.id} | ${chemin} | ${v.nodes.map((n) => n.target.join(" ")).join(" ;; ")}`
      parRegle[cle] = (parRegle[cle] || 0) + v.nodes.length
    }
  }

  console.log('\n=== VIOLATIONS PAR GRAVITE (10 pages) ===')
  for (const g of ['critical', 'serious', 'moderate', 'minor']) {
    console.log(`  ${g.padEnd(9)} : ${total[g] || 0} élément(s)`)
  }
  console.log('\n=== DETAIL PAR REGLE ===')
  for (const [cle, n] of Object.entries(parRegle).sort()) {
    console.log(`  ${cle} — ${n} élément(s)`)
  }
  expect(true).toBe(true)
})
