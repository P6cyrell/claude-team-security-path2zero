---
schema_version: 1
cluster_id: "03"
cluster_name: "sss-dbinit — minimist + braces overrides"
repos:
  - sss-dbinit
cve_count_investigated: 2
fix_family: A
target_close_date: 2026-05-22
blocked_by: []
depends_on_cluster_id: []
confidence: high
estimated_effort_engineer_weeks: 0.1
investigator: "cluster-investigator-03"
investigated_at: "2026-05-22T18:40:00Z"
scanner_noise_cves: []
---

## Summary

Two criticals in `sss-dbinit`, both from transitive npm dependencies:
**braces** (CVE-2024-4068, ReDoS) and **minimist** (prototype pollution).
**Recommended fix family: A — ship-now patch.** Target close: today
(2026-05-22). Confidence: high — `sss-dbinit` is a one-shot DB
initialization job, not a long-running service; the attack surface is
negligible and a clean dep refresh closes both findings.

## Reachability

- **braces** — used by glob expansion in `gulp-watch`. The job only runs
  at deploy time with internal config inputs. ReDoS requires attacker-
  controlled regex input. Not reachable in production; latent only.
- **minimist** — used by the CLI entrypoint. Inputs come from
  `package.json` `scripts` block, not from user input. Not reachable.

Both criticals are real findings (the package versions ARE vulnerable)
but the exploit pathways are not present in this job. Still worth
patching to clear the dashboard.

## Recommendation

Family A: add overrides to `package.json`:

```json
"overrides": {
  "braces": "^3.0.3",
  "minimist": "^1.2.8"
}
```

Lockfile refresh + commit. Job re-builds on next deploy.

Rejected alternatives:
- **B (framework upgrade)** — the job has no framework. Inapplicable.
- **Drop dependencies entirely** — `gulp-watch` is used in the build
  pipeline; cannot remove without rewriting the build script. Not
  worthwhile for 2 latent findings.

## Effort breakdown

- Apply overrides: ~10 min
- PR + review: ~20 min
- Deploy with next batch: piggybacks on cluster 02

## Risks / unknowns

None. This is the lowest-risk patch in the BRM portfolio.

## CVEs in scope

- CVE-2024-4068 — braces ReDoS — fixed in 3.0.3
- CVE-2021-44906 — minimist prototype pollution — fixed in 1.2.8
