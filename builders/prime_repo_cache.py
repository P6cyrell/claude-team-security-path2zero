"""
Phase 3 — Prime the repo cache for cluster investigation.

Reads clusters.json, computes the union of all repos any cluster needs, and
shallow-clones each into <repo_cache_root>/<repo_name>/. Repo names are
resolved to GitHub URLs via ~/.claude/shared/team-repos.json (produced by the
team-repo-sync skill).

Idempotent: existing clones are git-fetched + checked-out to default branch
instead of re-cloned. Failures don't abort — they accumulate in a report so
the orchestrator can fan out anyway and Phase 4 sub-agents handle missing
repos gracefully.

Run:
  python3 prime_repo_cache.py --clusters path/to/_facts/clusters.json
  python3 prime_repo_cache.py --clusters path/to/_facts/clusters.json --team-repos /path/override.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys


DEFAULT_TEAM_REPOS = pathlib.Path.home() / ".claude" / "shared" / "team-repos.json"


def _load_team_repos(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"team-repos.json not found at {path}.\n"
            f"Run /team-repo-sync to generate it, or pass --team-repos."
        )
    d = json.loads(path.read_text())
    if not isinstance(d, dict) or "teams" not in d:
        raise SystemExit(f"{path} is not in the expected /team-repo-sync format")
    return d["teams"]


def _resolve_repo_url(team: str, repo_name: str, all_teams: list[dict]) -> str | None:
    """Find repo_name within the named team's repo list."""
    # Case-insensitive team match
    team_entry = next(
        (t for t in all_teams if t.get("team_name", "").lower() == team.lower()),
        None,
    )
    if team_entry is None:
        return None
    for r in team_entry.get("repos", []):
        if r.get("repo_name") == repo_name:
            return r.get("html_url") or f"https://github.com/{r['full_name']}"
    return None


def _git(args: list[str], cwd: pathlib.Path | None = None) -> tuple[int, str]:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=False
    )
    out = (result.stdout + result.stderr).strip()
    return result.returncode, out


def _clone(url: str, dest: pathlib.Path) -> tuple[bool, str]:
    rc, out = _git(["clone", "--depth=20", "--filter=blob:none", url, str(dest)])
    return rc == 0, out


def _refresh(dest: pathlib.Path) -> tuple[bool, str]:
    rc1, out1 = _git(["fetch", "--depth=20"], cwd=dest)
    if rc1 != 0:
        return False, out1
    rc2, out2 = _git(["pull", "--ff-only"], cwd=dest)
    return rc2 == 0, out2


def prime(clusters_path: pathlib.Path, team_repos_path: pathlib.Path) -> dict:
    clusters = json.loads(clusters_path.read_text())
    team = clusters["team"]
    cache_root = pathlib.Path(clusters["repo_cache_root"])
    cache_root.mkdir(parents=True, exist_ok=True)

    all_repos = sorted({r for c in clusters["clusters"] for r in c["repos"]})
    teams_data = _load_team_repos(team_repos_path)

    report = {
        "team": team,
        "cache_root": str(cache_root),
        "total": len(all_repos),
        "primed_new": [],
        "refreshed": [],
        "failed": [],
        "unresolved": [],
    }

    for repo in all_repos:
        url = _resolve_repo_url(team, repo, teams_data)
        if not url:
            report["unresolved"].append(repo)
            continue
        dest = cache_root / repo
        if dest.exists() and (dest / ".git").exists():
            ok, msg = _refresh(dest)
            if ok:
                report["refreshed"].append(repo)
            else:
                report["failed"].append({"repo": repo, "stage": "refresh", "error": msg[:200]})
        else:
            ok, msg = _clone(url, dest)
            if ok:
                report["primed_new"].append(repo)
            else:
                report["failed"].append({"repo": repo, "stage": "clone", "url": url, "error": msg[:200]})

    return report


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clusters", required=True)
    ap.add_argument("--team-repos", default=str(DEFAULT_TEAM_REPOS),
                    help=f"Path to /team-repo-sync output. Default: {DEFAULT_TEAM_REPOS}")
    ap.add_argument("--report", default=None,
                    help="Optional path to write the JSON report")
    args = ap.parse_args(argv)

    report = prime(
        pathlib.Path(args.clusters).resolve(),
        pathlib.Path(args.team_repos).resolve(),
    )

    print(f"team        : {report['team']}")
    print(f"cache_root  : {report['cache_root']}")
    print(f"total repos : {report['total']}")
    print(f"primed new  : {len(report['primed_new'])}")
    print(f"refreshed   : {len(report['refreshed'])}")
    print(f"unresolved  : {len(report['unresolved'])}")
    print(f"failed      : {len(report['failed'])}")

    if report["unresolved"]:
        print("\nUnresolved (not in team-repos.json):")
        for r in report["unresolved"]:
            print(f"  - {r}")

    if report["failed"]:
        print("\nFailures:")
        for f in report["failed"]:
            print(f"  - {f['repo']} [{f['stage']}]: {f['error']}")

    if args.report:
        out = pathlib.Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nreport written to {out}")

    # Exit non-zero only if zero repos primed AND there were failures
    if not (report["primed_new"] or report["refreshed"]) and (report["failed"] or report["unresolved"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
