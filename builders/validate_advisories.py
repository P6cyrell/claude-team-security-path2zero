"""
Validate every advisory in a directory against schemas/advisory.schema.json.

Each advisory is a markdown file with a YAML frontmatter block at the top:

    ---
    schema_version: 1
    cluster_id: "01"
    cluster_name: "..."
    ...
    ---

    # prose body...

Exits 0 with no output on success.
Exits 1 with per-file error lines on failure.

The synthesizer (Phase 5) calls this before reading advisories, to catch
any Phase 4 sub-agent that returned a malformed advisory.

Run:
  python3 validate_advisories.py path/to/advisory-dir/
  python3 validate_advisories.py path/to/advisory-dir/ --clusters path/to/clusters.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = SKILL_DIR / "schemas" / "advisory.schema.json"


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _stringify_dates(value):
    """Recursively convert datetime.date / datetime.datetime to ISO strings.

    PyYAML's safe_load auto-resolves YYYY-MM-DD to datetime.date, which fails
    JSON Schema 'type: string' checks. Convert back to the on-disk form so
    schema validation matches what the file actually contains.
    """
    import datetime as _dt
    if isinstance(value, _dt.datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _stringify_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_dates(v) for v in value]
    return value


def extract_frontmatter(text: str) -> tuple[dict | None, str]:
    """Return (frontmatter_dict, error_message_or_empty)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, "missing YAML frontmatter block at top of file"
    try:
        import yaml
    except ImportError:
        return None, "pyyaml not installed. Run: pip install pyyaml"
    try:
        data = yaml.safe_load(m.group(1))
    except Exception as e:
        return None, f"frontmatter YAML failed to parse: {e}"
    if not isinstance(data, dict):
        return None, f"frontmatter must be a YAML mapping; got {type(data).__name__}"
    return _stringify_dates(data), ""


def validate_one(path: pathlib.Path, validator) -> list[str]:
    msgs = []
    text = path.read_text()
    fm, err = extract_frontmatter(text)
    if fm is None:
        return [f"{path.name}: {err}"]
    errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    for err in errors:
        loc = ".".join(str(p) for p in err.absolute_path) or "(frontmatter root)"
        msgs.append(f"{path.name}: [{loc}] {err.message}")
    # Filename convention: <cluster_id>-<slug>.md
    if "cluster_id" in fm:
        expected_prefix = f"{fm['cluster_id']}-"
        if not path.name.startswith(expected_prefix):
            msgs.append(
                f"{path.name}: filename should start with cluster_id+dash "
                f"(expected '{expected_prefix}…')"
            )
    return msgs


def validate_against_clusters(advisories_dir: pathlib.Path,
                              clusters: dict) -> list[str]:
    msgs = []
    expected_ids = {c["id"] for c in clusters["clusters"]}
    found_files = sorted(advisories_dir.glob("*.md"))
    found_ids = set()
    for f in found_files:
        m = re.match(r"^([0-9]{2})-", f.name)
        if m:
            found_ids.add(m.group(1))
    missing = expected_ids - found_ids
    extra   = found_ids - expected_ids
    if missing:
        msgs.append(f"missing advisories for cluster_id(s): {sorted(missing)}")
    if extra:
        msgs.append(f"unexpected advisory file(s) for cluster_id(s) not in clusters.json: {sorted(extra)}")
    return msgs


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("advisories_dir", help="path to dir containing advisory .md files")
    ap.add_argument("--clusters", default=None,
                    help="optional clusters.json to cross-check that every cluster has an advisory")
    args = ap.parse_args(argv)

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
        return 1

    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)

    advisories_dir = pathlib.Path(args.advisories_dir).resolve()
    if not advisories_dir.is_dir():
        print(f"not a directory: {advisories_dir}", file=sys.stderr)
        return 2

    all_msgs: list[str] = []
    files = sorted(advisories_dir.glob("*.md"))
    if not files:
        all_msgs.append(f"no .md files found in {advisories_dir}")

    for f in files:
        all_msgs.extend(validate_one(f, validator))

    if args.clusters:
        clusters = json.loads(pathlib.Path(args.clusters).read_text())
        all_msgs.extend(validate_against_clusters(advisories_dir, clusters))

    if all_msgs:
        print("advisory validation FAILED:", file=sys.stderr)
        for m in all_msgs:
            print(f"  - {m}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
