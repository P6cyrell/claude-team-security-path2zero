"""
Derive clusters.json from concentration.json + raw issues.

Phase 2 — pure deterministic Python. Heuristics:

  1. Repos holding >=20% of all criticals each become their own cluster.
  2. Remaining issues are grouped by primary_source (Trivy / Dependabot / etc).
  3. Within Dependabot, if one package dominates (>=40% of the cluster's CVEs),
     split into a package-specific sub-cluster.
  4. Cap at 6 total clusters: merge the two smallest by cve_count if over.
  5. Assign cluster IDs ("01".."NN") in descending order of cve_count.

Cluster names are auto-generated; the orchestrator (or hand-edit) can refine
before fan-out.

Run:
  python3 derive_clusters.py \\
    --concentration <path>/_facts/concentration.json \\
    --issues <path>/_raw/issues-<date>.json \\
    --repo-cache-root <path>/_shared/repo-cache/<team> \\
    --out <path>/_facts/clusters.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict


MAX_CLUSTERS = 6
SINGLE_REPO_THRESHOLD_PCT = 20.0
PACKAGE_DOMINANCE_PCT = 40.0


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len] or "cluster"


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _load_issues(path: pathlib.Path) -> list[dict]:
    raw = json.loads(path.read_text())
    if isinstance(raw, dict):
        return raw.get("items", raw.get("issues", []))
    return raw


def _classify_source(tool: str, ecosystem: str | None = None) -> str:
    t = (tool or "").lower()
    if "trivy" in t:
        return "trivy-base-image"
    if "dependabot" in t:
        eco = (ecosystem or "").lower()
        if eco and eco not in ("npm", "node", "yarn"):
            return "dependabot-other"
        return "dependabot-npm"
    if "codeql" in t or "code-scanning" in t:
        return "code-scanning"
    if "secret" in t:
        return "secret-scanning"
    return "mixed"


def _make_cluster(name: str,
                  repos: list[str],
                  issues: list[dict],
                  primary_source: str,
                  primary_package: str | None,
                  rationale: str,
                  blocked_by: list[str] | None = None) -> dict:
    cluster = {
        "id": "00",  # filled in by caller
        "slug": _slugify(name),
        "name": name,
        "repos": sorted(set(repos)),
        "cve_count": len(issues),
        "primary_source": primary_source,
        "rationale": rationale,
    }
    if primary_package:
        cluster["primary_package"] = primary_package
    if blocked_by:
        cluster["blocked_by"] = blocked_by
    return cluster


def derive(concentration: dict, issues: list[dict],
           repo_cache_root: str) -> dict:
    total = concentration["total_criticals"]
    repos_by_count = concentration["repos"]

    used_repos: set[str] = set()
    clusters: list[dict] = []

    # Filter to criticals only
    crit_issues = [
        i for i in issues
        if str(_pick(i, "severity", "severity_name", default="")).lower() == "critical"
    ]

    # Step 1: big-repo clusters
    for r in repos_by_count:
        if r["pct_of_total"] < SINGLE_REPO_THRESHOLD_PCT:
            break  # repos_by_count is sorted desc; no later one qualifies
        repo_name = r["repo"]
        repo_issues = [i for i in crit_issues
                       if _pick(i, "repo", "repository", "repo_name", "asset") == repo_name]
        if not repo_issues:
            continue
        source_counter = Counter(
            _classify_source(_pick(i, "tool", "scanner", default=""),
                             _pick(i, "ecosystem", "package_ecosystem"))
            for i in repo_issues
        )
        primary = source_counter.most_common(1)[0][0]
        clusters.append(_make_cluster(
            name=f"{repo_name} — {r['pct_of_total']:.0f}% of backlog",
            repos=[repo_name],
            issues=repo_issues,
            primary_source=primary,
            primary_package=None,
            rationale=(
                f"Single repo holds {r['pct_of_total']:.0f}% of remaining criticals "
                f"({r['critical_count']}/{total}). Concentrating fix effort here is the "
                f"highest-leverage path to zero."
            ),
        ))
        used_repos.add(repo_name)

    # Step 2: remaining issues bucketed by source (+ package dominance within Dependabot)
    remaining = [i for i in crit_issues
                 if _pick(i, "repo", "repository", "repo_name", "asset") not in used_repos]

    by_source: defaultdict[str, list[dict]] = defaultdict(list)
    for issue in remaining:
        src = _classify_source(_pick(issue, "tool", "scanner", default=""),
                               _pick(issue, "ecosystem", "package_ecosystem"))
        by_source[src].append(issue)

    for source, src_issues in by_source.items():
        if not src_issues:
            continue

        if source.startswith("dependabot"):
            # Check for package dominance
            pkg_counter = Counter(
                _pick(i, "package", "package_name", default="(unknown)") for i in src_issues
            )
            top_pkg, top_count = pkg_counter.most_common(1)[0]
            if top_count / len(src_issues) >= PACKAGE_DOMINANCE_PCT / 100.0 and top_count >= 3:
                pkg_issues = [i for i in src_issues
                              if _pick(i, "package", "package_name") == top_pkg]
                pkg_repos = sorted({
                    _pick(i, "repo", "repository", "repo_name", "asset") for i in pkg_issues
                })
                clusters.append(_make_cluster(
                    name=f"{top_pkg} — cross-repo {source.split('-')[1]} cluster",
                    repos=pkg_repos,
                    issues=pkg_issues,
                    primary_source=source,
                    primary_package=top_pkg,
                    rationale=(
                        f"Package `{top_pkg}` accounts for {top_count} of {len(src_issues)} "
                        f"({100*top_count/len(src_issues):.0f}%) {source} criticals across "
                        f"{len(pkg_repos)} repo(s). Single overrides/version bump can close the cluster."
                    ),
                ))
                # Other source issues become a separate residual cluster
                other_issues = [i for i in src_issues
                                if _pick(i, "package", "package_name") != top_pkg]
                if other_issues:
                    repos = sorted({_pick(i, "repo", "repository", "repo_name", "asset")
                                    for i in other_issues})
                    clusters.append(_make_cluster(
                        name=f"{source} long-tail",
                        repos=repos,
                        issues=other_issues,
                        primary_source=source,
                        primary_package=None,
                        rationale=(
                            f"Remaining {len(other_issues)} {source} criticals after the {top_pkg} "
                            f"split. Mixed packages across {len(repos)} repo(s)."
                        ),
                    ))
                continue

        # No dominance: one cluster per source
        repos = sorted({_pick(i, "repo", "repository", "repo_name", "asset") for i in src_issues})
        clusters.append(_make_cluster(
            name=f"{source} cluster",
            repos=repos,
            issues=src_issues,
            primary_source=source,
            primary_package=None,
            rationale=(
                f"{len(src_issues)} criticals from {source} across {len(repos)} repo(s). "
                f"Typically share a common fix path (base-image swap / framework upgrade / "
                f"override bump depending on source)."
            ),
        ))

    # Step 3: cap at MAX_CLUSTERS by merging smallest two
    while len(clusters) > MAX_CLUSTERS:
        clusters.sort(key=lambda c: c["cve_count"])
        a, b = clusters[0], clusters[1]
        merged_repos = sorted(set(a["repos"]) | set(b["repos"]))
        merged = {
            "id": "00",
            "slug": _slugify(f"{a['slug']}-and-{b['slug']}"),
            "name": f"{a['name']} + {b['name']}",
            "repos": merged_repos,
            "cve_count": a["cve_count"] + b["cve_count"],
            "primary_source": "mixed" if a["primary_source"] != b["primary_source"]
                               else a["primary_source"],
            "rationale": "Merged from two smaller residual clusters to fit the 6-cluster cap.",
        }
        clusters = [merged] + clusters[2:]

    # Step 4: assign IDs in descending cve_count order
    clusters.sort(key=lambda c: -c["cve_count"])
    for i, c in enumerate(clusters, start=1):
        c["id"] = f"{i:02d}"

    return {
        "schema_version": 1,
        "team": concentration["team"],
        "derived_at": concentration["as_of_date"],
        "repo_cache_root": repo_cache_root,
        "clusters": clusters,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--concentration", required=True)
    ap.add_argument("--issues", required=True)
    ap.add_argument("--repo-cache-root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    concentration = json.loads(pathlib.Path(args.concentration).read_text())
    issues = _load_issues(pathlib.Path(args.issues))
    out = derive(concentration, issues, args.repo_cache_root)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {out_path}  ({out_path.stat().st_size:,} bytes)")
    print(f"  derived {len(out['clusters'])} cluster(s); "
          f"sum cve_count={sum(c['cve_count'] for c in out['clusters'])}")
    for c in out["clusters"]:
        print(f"   - {c['id']} {c['name']}  ({c['cve_count']} CVEs, {len(c['repos'])} repo(s))")


if __name__ == "__main__":
    main(sys.argv[1:])
