"""
Compute concentration.json from the raw security-issues dump.

Pure data transform — no LLM, no network. Phase 1's data-fetcher sub-agent
runs this after pagination to produce concentration.json from the cached
raw JSON.

Inputs:
  --issues path/to/_raw/issues-<date>.json     (paginated get_security_issues output)
  --open-vulns path/to/_raw/open-vulnerabilities-<date>.json   (authoritative count)
  --endpoint-status path/to/_raw/endpoint-status.json   (which endpoints worked)
  --team <name>
  --as-of <YYYY-MM-DD>
  --out path/to/_facts/concentration.json

The script is tolerant to minor field-name variations in the raw security-
insights schema (it tries several known keys for repo / tool / severity).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _classify_source(tool_name: str) -> str:
    t = (tool_name or "").lower()
    if "trivy" in t:
        return "trivy-base-image"
    if "dependabot" in t:
        return "dependabot-npm"  # may be refined below if we know the ecosystem
    if "codeql" in t or "code-scanning" in t:
        return "code-scanning"
    if "secret" in t:
        return "secret-scanning"
    return "mixed"


def _refine_dep_source(source: str, ecosystem: str | None) -> str:
    if source != "dependabot-npm":
        return source
    eco = (ecosystem or "").lower()
    if eco in ("npm", "node", "yarn"):
        return "dependabot-npm"
    if eco:
        return "dependabot-other"
    return "dependabot-npm"


def compute(issues_path: pathlib.Path,
            open_vulns_path: pathlib.Path,
            endpoint_status_path: pathlib.Path | None,
            team: str,
            as_of: str) -> dict:
    raw = json.loads(issues_path.read_text())
    # security-insights pagination wrapper or raw array — accept either
    if isinstance(raw, dict) and "items" in raw:
        items = raw["items"]
    elif isinstance(raw, dict) and "issues" in raw:
        items = raw["issues"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise SystemExit(f"unexpected issues.json shape; top-level keys: {list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__}")

    # Filter to criticals only
    crits = [i for i in items
             if str(_pick(i, "severity", "severity_name", default="")).lower() == "critical"]
    highs = [i for i in items
             if str(_pick(i, "severity", "severity_name", default="")).lower() == "high"]

    repo_crits: Counter = Counter()
    repo_highs: Counter = Counter()
    repo_sources: defaultdict[str, Counter] = defaultdict(Counter)

    for issue in crits:
        repo = _pick(issue, "repo", "repository", "repo_name", "asset")
        if not repo:
            continue
        tool = _pick(issue, "tool", "scanner", "source", default="")
        eco  = _pick(issue, "ecosystem", "package_ecosystem", default=None)
        source = _refine_dep_source(_classify_source(str(tool)), eco)
        repo_crits[repo] += 1
        repo_sources[repo][source] += 1

    for issue in highs:
        repo = _pick(issue, "repo", "repository", "repo_name", "asset")
        if not repo:
            continue
        repo_highs[repo] += 1

    open_vulns = json.loads(open_vulns_path.read_text())
    if isinstance(open_vulns, dict):
        total_criticals = (
            _pick(open_vulns, "critical", "critical_count")
            or _pick(open_vulns, "by_severity", default={}).get("critical")
            or sum(repo_crits.values())
        )
    else:
        total_criticals = sum(repo_crits.values())

    total_for_pct = total_criticals or 1

    repos = []
    for repo, cnt in repo_crits.most_common():
        sources = repo_sources[repo]
        primary_source = sources.most_common(1)[0][0] if sources else "mixed"
        # If a single source isn't dominant (>60%), call it mixed
        if sources and sources.most_common(1)[0][1] / cnt < 0.6:
            primary_source = "mixed"
        repos.append({
            "repo": repo,
            "critical_count": cnt,
            "pct_of_total": round(100.0 * cnt / total_for_pct, 1),
            "primary_source": primary_source,
            "high_count": repo_highs.get(repo, 0),
        })

    endpoint_status = {
        "open_vulnerabilities": "ok",
        "security_issues":      "ok",
        "top_assets":           "ok",
        "resolving_trends":     "ok",
        "mttr":                 "ok",
        "sla":                  "ok",
    }
    if endpoint_status_path and endpoint_status_path.exists():
        endpoint_status.update(json.loads(endpoint_status_path.read_text()))

    return {
        "schema_version": 1,
        "team": team,
        "as_of_date": as_of,
        "total_criticals": int(total_criticals),
        "repos": repos,
        "endpoint_status": endpoint_status,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", required=True)
    ap.add_argument("--open-vulns", required=True)
    ap.add_argument("--endpoint-status", default=None)
    ap.add_argument("--team", required=True)
    ap.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    out = compute(
        pathlib.Path(args.issues),
        pathlib.Path(args.open_vulns),
        pathlib.Path(args.endpoint_status) if args.endpoint_status else None,
        args.team,
        args.as_of,
    )

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {out_path}  ({out_path.stat().st_size:,} bytes)")
    print(f"  total_criticals={out['total_criticals']}  repos={len(out['repos'])}")


if __name__ == "__main__":
    main(sys.argv[1:])
