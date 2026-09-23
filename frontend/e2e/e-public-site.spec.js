import { expect, test } from '@playwright/test'
import { auditAccessibility, resetDemoRequestThrottle, uniqueSuffix, waitForContentLoaded, waitForMotionSettled } from './helpers.js'

// Site vitrine public (phase 9). Deux parcours réels : le visiteur qui
// découvre le produit et demande une démonstration, et le client existant qui
// passe de la vitrine à son espace.

// LA VITRINE N'EST PLUS UNE PAGE, C'EST CINQ (refonte du 22/09/2026,
// ADR-042). L'accueil accroche en six actes, les pages secondaires portent le
// détail. Rien n'a été supprimé, tout a été déplacé : ces tests suivent donc
// le contenu là où il est parti, au lieu d'être allégés.
const ACTES_ACCUEIL = ['accroche', 'probleme', 'recevoir', 'commencer', 'faits', 'voir']

// Ce qui a quitté l'accueil, et où le retrouver. C'est l'inventaire du
// déplacement, exécutable : si une section disparaissait vraiment, ce tableau
// le dirait.
const CONTENU_DEPLACE = [
  { chemin: '/fonctionnalites', ancre: 'produit', titre: /Quatre choses que nous faisons/ },
  { chemin: '/fonctionnalites', ancre: 'alertes', titre: /Ce que vous recevez sans vous connecter/ },
  { chemin: '/fonctionnalites', ancre: 'diagnostic', titre: /Savoir par où commencer/ },
  { chemin: '/fonctionnalites', ancre: 'fonctionnement', titre: /Comment cela fonctionne/ },
  { chemin: '/securite-du-produit', ancre: 'donnees', titre: /Vos données, et ce que nous en faisons/ },
  { chemin: '/offres', ancre: 'tarifs', titre: /^Offres$/ },
  { chemin: '/questions', ancre: 'questions', titre: /Questions fréquentes/, niveau: 2 },
]

test('parcours visiteur : accueil, sections, demande de démonstration', async ({ page }) => {
  resetDemoRequestThrottle()
  const suffix = uniqueSuffix()

  await page.goto('/')

  await waitForContentLoaded(page)
  await expect(
    page.getByRole('heading', { level: 1, name: /identifiants ont fuité/ })
  ).toBeVisible()

  // Les six actes, dans l'ordre. Les apparitions au défilement doivent
  // révéler le contenu, pas le laisser invisible.
  for (const id of ACTES_ACCUEIL) {
    await page.locator(`#${id}`).scrollIntoViewIfNeeded()
    await expect(page.locator(`#${id}`)).toBeVisible()
  }

  // L'instrument du premier écran montre le produit EN MARCHE, sur le client
  // de démonstration. Son caractère fictif est dit, sans quoi la capture
  // finit par être lue comme un vrai client.
  await expect(page.getByText('Données de démonstration')).toBeVisible()
  await expect(page.getByText(/client de démonstration/).first()).toBeVisible()
  await expect(page.getByText(/42 mesures/)).toBeVisible()

  await auditAccessibility(page)

  // Conversion
  await page.getByRole('link', { name: /Demander une démonstration/ }).first().click()
  await page.waitForURL('**/demonstration')
  await waitForContentLoaded(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Demander une démonstration' })).toBeVisible()

  await page.getByLabel(/Nom et prénom/).fill('Camille Prospect')
  await page.getByLabel(/^Société/).fill(`Société Test ${suffix}`)
  await page.getByLabel(/Fonction/).fill('Directrice')
  await page.getByLabel(/Email professionnel/).fill(`camille-${suffix}@societe-test.example`)
  await page.getByLabel(/Taille de la société/).selectOption('10-49')
  await page.getByLabel(/Créneau souhaité/).selectOption('morning')
  await page.getByLabel(/Votre message/).fill('Nous aimerions voir la détection de fuites.')

  await auditAccessibility(page)

  await page.getByRole('button', { name: /Envoyer ma demande/ }).click()

  await expect(page.getByText(/Votre demande est bien enregistrée/)).toBeVisible()
  await expect(page.getByText(/jour ouvré/)).toBeVisible()
})

test('rien n’a été supprimé de la vitrine : tout est retrouvable', async ({ page }) => {
  // C'est le test qui tient la promesse de la refonte. L'accueil est passé de
  // sept sections d'un seul tenant à six actes, et le reproche était juste :
  // le visiteur s'y perdait. Mais raccourcir ne doit pas vouloir dire jeter.
  for (const { chemin, ancre, titre, niveau } of CONTENU_DEPLACE) {
    await page.goto(chemin)
    await waitForContentLoaded(page)
    await page.locator(`#${ancre}`).scrollIntoViewIfNeeded()
    await expect(page.locator(`#${ancre}`)).toBeVisible()
    // Le niveau est precise quand le titre de la PAGE et celui de la SECTION
    // portent le meme texte — sur /questions, par exemple.
    await expect(
      page.getByRole('heading', niveau ? { name: titre, level: niveau } : { name: titre })
    ).toBeVisible()
  }

  // Le contenu détaillé, vérifié là où il vit maintenant.
  await page.goto('/fonctionnalites')
  await waitForContentLoaded(page)
  await expect(page.getByText('La météo cyber, chaque matin')).toBeVisible()
  await expect(page.getByText(/plan d’action priorisé/i).first()).toBeVisible()

  // Les quotas viennent des champs de l'offre : on vérifie qu'ils sont rendus
  // et qu'aucun ne dépasse le pool partagé de la plateforme (ADR-013).
  await page.goto('/offres')
  await waitForContentLoaded(page)
  const tarifs = page.locator('#tarifs')
  await expect(tarifs.getByText(/actifs? en surveillance continue/).first()).toBeVisible()
  await expect(
    tarifs.getByText(/\b(1[6-9]|[2-9]\d+) actifs? en surveillance continue/)
  ).toHaveCount(0)
  await expect(page.getByText('Le plus demandé')).toBeVisible()

  await page.goto('/questions')
  await waitForContentLoaded(page)
  await expect(
    page.getByRole('button', { name: /Faut-il installer quelque chose/ })
  ).toBeVisible()
})

test('parcours client : accueil vers connexion', async ({ page }) => {
  await page.goto('/')
  await waitForContentLoaded(page)

  await page.getByRole('link', { name: 'Se connecter' }).first().click()
  await page.waitForURL('**/connexion')
  await waitForContentLoaded(page)

  await expect(page.getByLabel('Email')).toBeVisible()
  await expect(page.getByLabel('Mot de passe')).toBeVisible()
})

test('la vitrine est lisible sur un écran de téléphone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await waitForContentLoaded(page)

  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

  // Aucun débordement horizontal : c'est le défaut le plus visible sur
  // téléphone, et le plus facile à laisser passer en développant au large.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  )
  expect(overflow).toBe(false)

  // Les six actes se parcourent au doigt, contenu compris : c'est là qu'une
  // grille mal bornée déborde ou se replie sur elle-même.
  for (const id of ACTES_ACCUEIL) {
    await page.locator(`#${id}`).scrollIntoViewIfNeeded()
    await expect(page.locator(`#${id}`)).toBeVisible()
  }
  await expect(page.getByText(/42 mesures/)).toBeVisible()

  // Le débordement se re-mesure APRÈS le parcours : une carte trop large ne
  // se révèle qu'une fois la section montée et son contenu rendu.
  const overflowApresParcours = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  )
  expect(overflowApresParcours).toBe(false)

  // Le menu replié doit s'ouvrir et donner accès à la conversion.
  await page.getByRole('button', { name: /Ouvrir le menu/ }).click()
  await expect(
    page.getByRole('link', { name: /Demander une démonstration/ }).last()
  ).toBeVisible()

  await auditAccessibility(page)
})

test('les pages légales sont accessibles et annoncent ce qui reste à compléter', async ({
  page,
}) => {
  await page.goto('/mentions-legales')
  await waitForContentLoaded(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Mentions légales' })).toBeVisible()
  await expect(page.getByText(/à compléter par l’éditeur/)).toBeVisible()

  await page.goto('/confidentialite')

  await waitForContentLoaded(page)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Politique de confidentialité' })
  ).toBeVisible()
  await expect(page.getByText(/90 jours/).first()).toBeVisible()

  await auditAccessibility(page)
})

test('aucun contenu ne dépend d’une animation pour être visible', async ({ page }) => {
  // Règle posée en phase 9, et enfreinte jusqu'ici : constaté en capture
  // pleine hauteur, la grille tarifaire était ABSENTE de la page. Les cartes
  // existaient dans le DOM, à `opacity-0` — rendues après la réponse de
  // l'API, donc montées tardivement, donc le filet de sécurité de 2 s de
  // `Reveal` repartait de zéro. Un filet dont le compte à rebours redémarre
  // n'est pas un filet.
  //
  // Ce test ne défile PAS, à dessein : c'est la condition qui reproduit le
  // robot d'indexation, l'impression et la capture pleine hauteur.
  // La grille tarifaire vit maintenant sur /offres : c'est elle qui portait
  // le defaut, c'est donc elle qu'on mesure, sans defiler.
  await page.goto('/offres')
  await waitForContentLoaded(page)
  await page.getByRole('heading', { level: 1 }).waitFor()
  // Les apparitions AU-DESSUS de la ligne de flottaison se déclenchent, elles :
  // on attend qu'elles soient retombées, sinon on mesure un fondu en cours et
  // le test échoue sur du mouvement légitime.
  await waitForMotionSettled(page)

  const invisibles = await page.evaluate(() =>
    [...document.querySelectorAll('main *')]
      .filter((el) => {
        const opacite = Number.parseFloat(getComputedStyle(el).opacity)
        return (
          opacite < 0.99 &&
          el.textContent.trim().length > 0 &&
          el.getBoundingClientRect().height > 0
        )
      })
      .map((el) => `${el.tagName} — ${el.textContent.trim().slice(0, 60)}`)
  )

  const message = ['Contenu invisible sans défilement :', ...invisibles].join('\n')
  expect(invisibles, message).toEqual([])

  // Et le contenu servi par l'API en fait partie : c'est lui qui manquait.
  await expect(page.locator('#tarifs')).toContainText('Veille')
})
