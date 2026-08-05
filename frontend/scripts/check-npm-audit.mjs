#!/usr/bin/env node
// Fails CI on any high/critical npm audit finding, except explicitly
// accepted-risk advisories documented below and in docs/security_review.md.
// Rationale: `npm audit` has no native allowlist — this is the smallest
// mechanism that keeps CI honest without permanently masking the package.
import { execSync } from "node:child_process";

const ACCEPTED_RISK_ADVISORIES = new Set([
  // GHSA-qwww-vcr4-c8h2 (react-router / react-router-dom, CWE-352):
  // "RSC Mode... Action Execution Before 400 Response". This app uses plain
  // declarative <Routes>/<Route> routing with no React Server Components and
  // no framework-mode data actions, so the vulnerable code path is unused.
  // The only available fix is a breaking downgrade to an older, differently
  // vulnerable release. See docs/security_review.md (A06) for the full
  // justification.
  "GHSA-qwww-vcr4-c8h2",
]);

let report;
try {
  const output = execSync("npm audit --audit-level=high --json", {
    encoding: "utf-8",
    maxBuffer: 1024 * 1024 * 20,
  });
  report = JSON.parse(output);
} catch (error) {
  // npm audit exits non-zero when vulnerabilities are found; stdout still
  // carries the JSON report in that case.
  if (!error.stdout) {
    console.error("npm audit did not produce a report:", error.message);
    process.exit(1);
  }
  report = JSON.parse(error.stdout);
}

const vulnerabilities = report.vulnerabilities ?? {};

// `via` entries are either advisory objects (direct finding) or a plain
// package-name string (the vulnerability is inherited from that dependency)
// — resolve the latter transitively to the advisory objects that caused it.
function collectAdvisoryIds(packageName, seen = new Set()) {
  if (seen.has(packageName)) return [];
  seen.add(packageName);

  const vuln = vulnerabilities[packageName];
  if (!vuln) return [];

  const ids = [];
  for (const entry of vuln.via ?? []) {
    if (typeof entry === "object" && entry.url) {
      ids.push(entry.url.split("/").pop());
    } else if (typeof entry === "string") {
      ids.push(...collectAdvisoryIds(entry, seen));
    }
  }
  return ids;
}

const unaccepted = [];

for (const [packageName, vuln] of Object.entries(vulnerabilities)) {
  if (vuln.severity !== "high" && vuln.severity !== "critical") continue;

  const advisoryIds = collectAdvisoryIds(packageName);
  const fullyAccepted =
    advisoryIds.length > 0 && advisoryIds.every((id) => ACCEPTED_RISK_ADVISORIES.has(id));

  if (!fullyAccepted) {
    unaccepted.push({ packageName, severity: vuln.severity, advisoryIds });
  }
}

if (unaccepted.length > 0) {
  console.error("Unaccepted high/critical vulnerabilities found:");
  for (const entry of unaccepted) {
    console.error(`  - ${entry.packageName} (${entry.severity}): ${entry.advisoryIds.join(", ")}`);
  }
  process.exit(1);
}

console.log(
  "npm audit: no unaccepted high/critical vulnerabilities " +
    `(${Object.keys(vulnerabilities).length} finding(s) covered by documented accepted risk).`,
);
