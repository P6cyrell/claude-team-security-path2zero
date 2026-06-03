"""
Validate clusters.json against schemas/clusters.schema.json.

Exits 0 with no output on success.
Exits 1 with a human-readable error message on failure.

Phase 2 (cluster derivation) calls this before writing clusters.json.
Phase 4 (orchestrator) calls this before fanning out sub-agents.

Run:
  python3 validate_clusters.py path/to/clusters.json
"""

from __future__ import annotations

import json
import pathlib
import sys


SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = SKILL_DIR / "schemas" / "clusters.schema.json"


def validate(clusters_path: pathlib.Path) -> list[str]:
    try:
        clusters = json.loads(clusters_path.read_text())
    except Exception as e:
        return [f"clusters.json failed to parse as JSON: {e}"]

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["jsonschema not installed. Run: pip install jsonschema"]

    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(clusters), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = []
        for err in errors:
            loc = ".".join(str(p) for p in err.absolute_path) or "(root)"
            msgs.append(f"[{loc}] {err.message}")
        return msgs

    return _semantic_checks(clusters)


def _semantic_checks(clusters: dict) -> list[str]:
    msgs = []

    ids = [c["id"] for c in clusters["clusters"]]
    if len(ids) != len(set(ids)):
        msgs.append(f"cluster ids must be unique, got: {ids}")

    slugs = [c["slug"] for c in clusters["clusters"]]
    if len(slugs) != len(set(slugs)):
        msgs.append(f"cluster slugs must be unique (used in advisory filenames), got: {slugs}")

    # Repos may appear in multiple clusters (a repo can have multiple vuln families),
    # but warn if a repo is in >2 clusters — likely over-fragmentation.
    from collections import Counter
    repo_in_clusters = Counter()
    for c in clusters["clusters"]:
        for repo in c["repos"]:
            repo_in_clusters[repo] += 1
    over = [r for r, n in repo_in_clusters.items() if n > 2]
    if over:
        msgs.append(
            f"repo(s) appear in >2 clusters — likely over-fragmentation: {over}. "
            f"Consider merging clusters."
        )

    repo_cache = pathlib.Path(clusters["repo_cache_root"])
    if not repo_cache.exists():
        msgs.append(
            f"repo_cache_root does not exist: {repo_cache} — run Phase 3 (repo-primer) first."
        )

    return msgs


def main(argv):
    if len(argv) != 1:
        print("usage: validate_clusters.py path/to/clusters.json", file=sys.stderr)
        return 2
    msgs = validate(pathlib.Path(argv[0]).resolve())
    if msgs:
        print("clusters.json validation FAILED:", file=sys.stderr)
        for m in msgs:
            print(f"  - {m}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
