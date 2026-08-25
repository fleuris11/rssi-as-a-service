import AxeBuilder from '@axe-core/playwright'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
export const API_BASE_URL = 'http://localhost:8000'
export const E2E_PASSWORD = 'E2eTestPassword2026!'

export function uniqueSuffix() {
  return `${Date.now()}-${Math.floor(Math.random() * 100000)}`
}

// RGAA baseline (Phase 5, mission item 8): fail only on the violation
// severities that mean an interactive element is genuinely unusable
// ("critical"/"serious") — minor/moderate axe findings are tracked as
// backlog, not a CI-blocking bar, matching the mission's "sans violation
// critique" wording rather than a zero-violations bar the app isn't at yet.
const BLOCKING_IMPACTS = new Set(['critical', 'serious'])

export function assertNoCriticalViolations(axeResults) {
  const blocking = axeResults.violations.filter((violation) =>
    BLOCKING_IMPACTS.has(violation.impact)
  )
  if (blocking.length === 0) return

  // Ce que le message doit contenir pour être exploitable : la RAISON, pas
  // seulement l'endroit. L'ancien format concaténait les sélecteurs de tous
  // les nœuds sur une seule ligne — quarante sélecteurs illisibles qui
  // disaient « ça ne va pas quelque part » sans jamais dire pourquoi.
  // `failureSummary` porte les chiffres d'axe : contraste obtenu, contraste
  // attendu, couleurs calculées. Sur un défaut de contraste, c'est la
  // différence entre chercher et voir.
  const details = blocking
    .map((v) => {
      const exemples = v.nodes
        .slice(0, 3)
        .map((n) => `      ${n.target.join(' ')}\n${indenter(n.failureSummary)}`)
        .join('\n')
      const reste = v.nodes.length > 3 ? `\n      (+ ${v.nodes.length - 3} autres éléments)` : ''
      return `- [${v.impact}] ${v.id} — ${v.nodes.length} élément(s) : ${v.help}\n${exemples}${reste}`
    })
    .join('\n')
  throw new Error(`Violations d'accessibilité bloquantes détectées :\n${details}`)
}

function indenter(texte = '') {
  return texte
    .split('\n')
    .map((ligne) => `        ${ligne.trim()}`)
    .join('\n')
}

/**
 * Attend la fin du chargement d'une page — c'est-à-dire la disparition des
 * squelettes (`data-loading`, voir `components/ui/Skeleton.jsx`).
 *
 * Ce n'est PAS un délai de confort déguisé : la condition attendue est un
 * état de l'interface, et si le chargement n'aboutit jamais, l'attente
 * échoue au lieu de laisser passer.
 *
 * Nécessaire parce que le premier rendu du tableau de bord demande environ
 * 6 s sur le poste de développement (contre ~1 s en intégration continue),
 * au-delà du délai par défaut d'une assertion. La cause de fond est
 * mesurée et connue : le tableau de bord appelle `/auth/me/` TROIS fois,
 * `/assessments/` et `/monitoring/dashboard/` deux fois chacun. Attendre ici
 * ne corrige pas ce gaspillage — c'est une dette ouverte au journal, pas un
 * problème réglé.
 */
export async function waitForContentLoaded(page) {
  await page.waitForFunction(
    () => document.querySelectorAll('[data-loading="true"]').length === 0,
    undefined,
    { timeout: 30_000 }
  )
}

/**
 * Audit d'accessibilité d'une page, une fois celle-ci STABILISÉE.
 *
 * L'attente n'est pas un délai de confort : elle porte sur un état défini —
 * « plus aucune transition CSS en cours ». Sans elle, axe mesure des éléments
 * en plein fondu (`Reveal`, 700 ms) et calcule le contraste sur une couleur
 * mélangée au fond. Le symptôme est déroutant : un texte quasi noir
 * (`text-ink-800`) est signalé en défaut de contraste, ce qui est impossible
 * une fois l'apparition terminée.
 *
 * Ce défaut ne se voit que sur une machine RAPIDE. Le même parcours prend
 * 2 s en intégration continue et 45 s sur le poste de développement : ici,
 * les apparitions sont posées depuis longtemps quand axe mesure, et le test
 * passe. C'est l'inverse du réflexe habituel — ce n'est pas le poste lent qui
 * révèle la fragilité, c'est le serveur rapide.
 *
 * On attend la fin des TRANSITIONS uniquement, jamais des animations : une
 * animation en boucle (indicateur de chargement) ne se termine par définition
 * jamais, et attendre sa fin bloquerait indéfiniment.
 */
export async function auditAccessibility(page) {
  await waitForContentLoaded(page)
  await page.waitForFunction(
    () =>
      typeof CSSTransition === 'undefined' ||
      document
        .getAnimations()
        .every((a) => !(a instanceof CSSTransition) || a.playState === 'finished'),
    undefined,
    { timeout: 10_000 }
  )
  const resultats = await new AxeBuilder({ page }).exclude('svg').analyze()
  assertNoCriticalViolations(resultats)
}

/** Fills the registration form and submits — leaves the browser on
 * /tableau-de-bord (RegisterPage redirects there on success), authenticated. */
export async function registerNewTenant(page, { companyName, email }) {
  await page.goto('/inscription')
  await page.getByLabel('Nom de l’entreprise').fill(companyName)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Mot de passe').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: 'Créer mon compte' }).click()
  await page.waitForURL('**/tableau-de-bord')
  await waitForContentLoaded(page)
}

/** Reads the freshly-registered user's own tenant slug straight from the
 * API, using the JWT the SPA already stored in localStorage — avoids
 * re-deriving auth state a second time just to know which tenant to target
 * for the management-command-based check simulation (flow b). */
export async function getCurrentTenantSlug(page) {
  return page.evaluate(async (apiBaseUrl) => {
    const access = localStorage.getItem('rssi.access')
    const response = await fetch(`${apiBaseUrl}/api/v1/auth/me/`, {
      headers: { Authorization: `Bearer ${access}` },
    })
    const data = await response.json()
    return data.memberships[0].tenant_slug
  }, API_BASE_URL)
}

/** Runs the `simulate_check_failure` management command inside the
 * docker-compose `web` container — injects 3 consecutive CRITICAL
 * http_uptime CheckResults for the given declared asset and opens a real
 * DOWN alert through the actual alert engine (apps.monitoring.services).
 * See backend/apps/monitoring/management/commands/simulate_check_failure.py. */
export function simulateAssetDown({ tenantSlug, assetValue }) {
  execFileSync(
    'docker',
    [
      'compose',
      'exec',
      '-T',
      'web',
      'python',
      'manage.py',
      'simulate_check_failure',
      '--tenant-slug',
      tenantSlug,
      '--asset-value',
      assetValue,
    ],
    { cwd: REPO_ROOT, stdio: 'pipe' }
  )
}

/** Vide le compteur de limitation de débit du formulaire public.
 *
 * L'endpoint est volontairement limité à 3 demandes par heure et par IP (une
 * valeur de production, pas un réglage de test). Rejouer la suite plusieurs
 * fois depuis la même machine l'épuise donc légitimement : on repart d'un
 * compteur propre plutôt que d'assouplir la protection pour les besoins du
 * test. */
export function resetDemoRequestThrottle() {
  const script = [
    'import redis',
    'from django.conf import settings',
    'r = redis.Redis.from_url(settings.CACHES["default"]["LOCATION"], decode_responses=True)',
    'keys = [k for k in r.scan_iter("*demo_request*")]',
    '[r.delete(k) for k in keys]',
  ].join('\n')
  execFileSync(
    'docker',
    ['compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c', script],
    { cwd: REPO_ROOT, stdio: 'pipe' }
  )
}


/** Rend au pool les emplacements engagés par les entreprises de test.
 *
 * Le pool de surveillance est PARTAGÉ par toute la plateforme (ADR-013), et un
 * essai en consomme réellement. Sans ce nettoyage, chaque exécution laisse des
 * abonnements ouverts, et au bout de quelques passages la garde de capacité
 * refuse — à juste titre — les inscriptions des exécutions suivantes. Le
 * symptôme ressemble à une régression ; c'en est l'inverse.
 *
 * Cible les préfixes utilisés par les parcours, jamais les données de
 * démonstration ni de vrais clients.
 */
export function releaseE2ETenants(prefixes = ["E2E "]) {
  const script = [
    "from apps.tenants.models import Tenant",
    `for prefix in ${JSON.stringify(prefixes)}:`,
    "    Tenant.objects.filter(name__startswith=prefix).delete()",
  ].join('\n')
  try {
    execFileSync(
      "docker",
      ["compose", "exec", "-T", "web", "python", "manage.py", "shell", "--no-imports", "-c", script],
      { cwd: REPO_ROOT, stdio: "pipe" }
    )
  } catch {
    // Le nettoyage est un confort : son échec ne doit pas faire échouer un
    // parcours par ailleurs vert.
  }
}
