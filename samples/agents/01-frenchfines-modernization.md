---
schema_version: 1
cluster_id: "01"
cluster_name: "FrenchFines — Node 8/Buster modernization"
repos:
  - sss-enforcement-frenchfines-service
cve_count_investigated: 268
fix_family: C
target_close_date: 2026-06-26
blocked_by:
  - PSDEV-62502
depends_on_cluster_id: []
confidence: medium
estimated_effort_engineer_weeks: 6.0
investigator: "cluster-investigator-01"
investigated_at: "2026-05-22T18:30:00Z"
scanner_noise_cves: []
---

## Summary

The FrenchFines enforcement service holds 268 of BRM's 273 remaining
criticals (98%). The service runs on **Node 8 / Debian Buster**, both 5+
years past EOL. **Recommended fix family: C — containment + legacy
modernization.** Lighter options (A npm overrides, B Node major bump alone)
do not close the base-image criticals which constitute the majority. The
work is tracked under PSDEV-62502 and is now unblocked: the ES production
data migration prerequisite is complete across AU/EU/US as of 2026-05-22.
Target close date is 2026-06-26 — the originally-planned late-June
landing per Geoffray's 2026-05-19 status update. Confidence is **medium**
because 5/10 sub-tasks are complete and the remaining 5 include the
runtime-version upgrade itself, which historically surfaces unexpected
breakages.

## Reachability

Of the 268 criticals, ~205 are container-base-image CVEs (Trivy) flagged
on Debian Buster: kernel, openssl, glibc, perl, sqlite, others. None are
reachable from request handlers — they exist in the OS image. They are
"real" in the sense that the image is shipped, but they are not
attacker-input reachable; they require local code execution to exploit.
The remaining 63 are Node 8-era npm criticals (legacy lodash, minimist,
qs, etc.) that the upgrade resolves transitively.

## Recommendation

Family C: complete the Node 8 → Node 20 LTS upgrade + swap base image to
`gcr.io/distroless/nodejs20-debian12:nonroot`. Sequence:

1. **Node 20 + Alpine-or-distroless** — the dependency surgery.
2. **ES7 client migration** — already complete; consume from PSDEV-62501.
3. **CI / integration tests** — ~1.5 engineer-weeks; FrenchFines has
   moderate behavioral test coverage but ES interaction edges are fragile.
4. **Staged deploy** — canary 1 region (likely AU per regulatory profile)
   for 72h before EU/US.

Rejected alternatives:
- **Family A (npm overrides)** — closes ~30 of 268. Insufficient.
- **Family B (Node major bump only, keep Buster)** — closes ~63 npm CVEs
  but leaves 205 base-image CVEs. Insufficient.

## Effort breakdown

| Task                                          | Weeks |
|-----------------------------------------------|------:|
| Node 20 dep surgery (lodash, qs, minimist)    |   1.5 |
| Base-image swap + Dockerfile rewrite          |   0.5 |
| CI / integration test fixes                   |   1.5 |
| ES7 client adapter verification               |   0.5 |
| Staged deploy + monitoring                    |   1.0 |
| Buffer (Node major surfaces breakages)        |   1.0 |
| **Total**                                     |   **6.0** |

## Risks / unknowns

- **Node 20 surfaces a behavioral regression in ES7 query pagination.**
  This bit the Control upgrade (PSDEV-62501) for ~3 days; FrenchFines uses
  more complex queries. Mitigation: extend canary to 5 days if 24h shows
  any error-rate anomaly.
- **Two engineers allocated** (the technical-upgrade stream per
  Geoffray's resource plan). Loss of either pushes close date by ~2 weeks.
- **Buster→distroless** removes shell/utility commands. If any
  ops-runbook script SSHes in to run a command, it breaks silently.
  Need ops audit before cutover.

## CVEs in scope

- 205 × Trivy base-image (Buster) — closed by base-image swap
- 38 × `lodash` variants — closed by Node 20 dep refresh
- 14 × `minimist` / `qs` — closed by overrides + refresh
- 11 × `handlebars` (older versions) — closed by refresh

No scanner-noise CVEs found in this cluster.
