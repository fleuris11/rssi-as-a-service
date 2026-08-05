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
  if (blocking.length > 0) {
    const details = blocking
      .map((v) => {
        const targets = v.nodes.map((n) => n.target.join(' ')).join(', ')
        return `- [${v.impact}] ${v.id}: ${v.help} — ${targets}`
      })
      .join('\n')
    throw new Error(`Violations d'accessibilité bloquantes détectées :\n${details}`)
  }
}

/** Fills the registration form and submits — leaves the browser on
 * /diagnostic (RegisterPage redirects there on success), authenticated. */
export async function registerNewTenant(page, { companyName, email }) {
  await page.goto('/inscription')
  await page.getByLabel('Nom de l’entreprise').fill(companyName)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Mot de passe').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: 'Créer mon compte' }).click()
  await page.waitForURL('**/diagnostic')
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
