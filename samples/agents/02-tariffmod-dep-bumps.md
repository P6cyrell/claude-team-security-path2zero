---
schema_version: 1
cluster_id: "02"
cluster_name: "Tariff-modifier facade — npm dependency bumps"
repos:
  - hub-parking-tariffmodifiers-facade
cve_count_investigated: 3
fix_family: A
target_close_date: 2026-05-22
blocked_by: []
depends_on_cluster_id: []
confidence: high
estimated_effort_engineer_weeks: 0.2
investigator: "cluster-investigator-02"
investigated_at: "2026-05-22T18:35:00Z"
scanner_noise_cves: []
---

## Summary

Three criticals in a single repo, all from outdated npm dependencies:
**axios** (CVE-2024-axios-ssrf), **form-data** (boundary issue), and
**handlebars** (prototype pollution). All three close with a single PR
adding `overrides` to `package.json` and refreshing the lockfile.
**Recommended fix family: A — ship-now patch.** Target close: today
(2026-05-22). Confidence: high — the repo has CI that runs on every PR;
no behavioral regressions expected.

## Reachability

- **axios** — used in 4 outbound HTTP calls to internal services
  (`tariff-rules`, `pricing-engine`, etc.). Not exposed to attacker input
  on the request side; the CVE is server-side SSRF which is not the
  exploit pathway for this usage. Still worth patching to clear the
  scanner.
- **form-data** — transitive only (axios → form-data). Patched by axios
  bump.
- **handlebars** — used in two template-rendering paths. Inputs are
  internal config strings, not user input. Not reachable.

## Recommendation

Family A: single PR. Diff:

```json
"overrides": {
  "axios": "^1.7.7",
  "handlebars": "^4.7.8"
}
```

Then `rm -rf node_modules package-lock.json && npm install`. CI runs
~14 minutes; merge + deploy same day.

Rejected alternatives:
- **B (Node major bump)** — unnecessary; the repo is already on Node 20.
- **C (containment)** — over-engineering for 3 deps.

## Effort breakdown

- Apply overrides + reinstall: ~30 min
- PR review: ~30 min
- Deploy via batch 62 or hot-fix: same day

## Risks / unknowns

None material. The repo is small (~3K LOC), well-tested, and has been
through similar dep bumps in the past 6 months without incident.

## CVEs in scope

- CVE-2024-axios-ssrf — axios 1.x SSRF — fixed in 1.7.7
- CVE-2024-form-data-boundary — transitive, closed by axios bump
- CVE-2023-handlebars-proto — fixed in 4.7.8
