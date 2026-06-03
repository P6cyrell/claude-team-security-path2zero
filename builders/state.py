"""
Orchestrator state tracking for team-security-path2zero.

Maintains a single state.json file per team-advisory so the orchestrator can
resume mid-pipeline (auth-token expiry, cluster sub-agent failure, user
interrupt). Lightweight on purpose — read/write the whole file each call.

Commands:
  init       --work-dir D --team T --as-of YYYY-MM-DD [--portfolio]
  set-phase  --work-dir D --phase NAME --status STATUS [--note "..."]
  set-advisory --work-dir D --cluster-id NN --status STATUS [--error "..."]
  resume-point --work-dir D
  show       --work-dir D

Phase names (in order):
  0_preflight, 1_data_fetcher, 2_clusters, 3_repo_cache,
  4_investigation, 5_synthesis, 6_render, 7_portfolio

Statuses:
  pending | in_progress | done | failed | skipped
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


PHASE_ORDER = [
    "0_preflight",
    "1_data_fetcher",
    "2_clusters",
    "3_repo_cache",
    "4_investigation",
    "5_synthesis",
    "6_render",
    "7_portfolio",
]

VALID_STATUSES = {"pending", "in_progress", "done", "failed", "skipped"}


def _state_path(work_dir: pathlib.Path) -> pathlib.Path:
    return work_dir / "state.json"


def _now() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _load(work_dir: pathlib.Path) -> dict:
    p = _state_path(work_dir)
    if not p.exists():
        raise SystemExit(
            f"no state.json at {p} — run `state.py init` first"
        )
    return json.loads(p.read_text())


def _save(work_dir: pathlib.Path, state: dict) -> None:
    state["updated_at"] = _now()
    p = _state_path(work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2) + "\n")


def cmd_init(args) -> int:
    work_dir = pathlib.Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    p = _state_path(work_dir)
    if p.exists() and not args.force:
        print(f"state.json already exists at {p}. Use --force to overwrite.",
              file=sys.stderr)
        return 1
    state = {
        "schema_version": 1,
        "team": args.team,
        "as_of_date": args.as_of,
        "portfolio_mode": bool(args.portfolio),
        "started_at": _now(),
        "updated_at": _now(),
        "phases": {name: {"status": "pending"} for name in PHASE_ORDER},
        "advisories": {},
    }
    _save(work_dir, state)
    print(f"initialized state at {p}")
    return 0


def cmd_set_phase(args) -> int:
    work_dir = pathlib.Path(args.work_dir).resolve()
    if args.phase not in PHASE_ORDER:
        print(f"unknown phase {args.phase}; valid: {PHASE_ORDER}", file=sys.stderr)
        return 2
    if args.status not in VALID_STATUSES:
        print(f"unknown status {args.status}; valid: {sorted(VALID_STATUSES)}",
              file=sys.stderr)
        return 2
    state = _load(work_dir)
    entry = state["phases"].setdefault(args.phase, {})
    entry["status"] = args.status
    entry["at"] = _now()
    if args.note:
        entry["note"] = args.note
    _save(work_dir, state)
    print(f"{args.phase} -> {args.status}")
    return 0


def cmd_set_advisory(args) -> int:
    work_dir = pathlib.Path(args.work_dir).resolve()
    if args.status not in VALID_STATUSES:
        print(f"unknown status {args.status}; valid: {sorted(VALID_STATUSES)}",
              file=sys.stderr)
        return 2
    state = _load(work_dir)
    entry = state["advisories"].setdefault(args.cluster_id, {})
    entry["status"] = args.status
    entry["at"] = _now()
    if args.error:
        entry["error"] = args.error[:500]
    if args.fix_family:
        entry["fix_family"] = args.fix_family
    if args.target_close_date:
        entry["target_close_date"] = args.target_close_date
    _save(work_dir, state)
    print(f"advisory {args.cluster_id} -> {args.status}")
    return 0


def cmd_resume_point(args) -> int:
    state = _load(pathlib.Path(args.work_dir).resolve())
    # Resume = first phase that isn't 'done' or 'skipped'
    for name in PHASE_ORDER:
        s = state["phases"].get(name, {}).get("status", "pending")
        if s not in ("done", "skipped"):
            print(name)
            return 0
    print("complete")
    return 0


def cmd_show(args) -> int:
    state = _load(pathlib.Path(args.work_dir).resolve())
    print(f"team        : {state['team']}")
    print(f"as_of_date  : {state['as_of_date']}")
    print(f"portfolio   : {state.get('portfolio_mode', False)}")
    print(f"started_at  : {state['started_at']}")
    print(f"updated_at  : {state['updated_at']}")
    print("")
    print("phases:")
    for name in PHASE_ORDER:
        s = state["phases"].get(name, {})
        status = s.get("status", "pending")
        marker = {"done": "✓", "failed": "✗", "in_progress": "…", "skipped": "⊘"}.get(status, " ")
        line = f"  {marker} {name:<18} {status}"
        if "at" in s:
            line += f"    {s['at']}"
        print(line)
        if s.get("note"):
            print(f"        note: {s['note']}")
    if state["advisories"]:
        print("")
        print("advisories:")
        for cid in sorted(state["advisories"]):
            a = state["advisories"][cid]
            marker = {"done": "✓", "failed": "✗", "in_progress": "…"}.get(a["status"], " ")
            line = f"  {marker} {cid}  {a['status']}"
            if "fix_family" in a:
                line += f"   {a['fix_family']}"
            if "target_close_date" in a:
                line += f"   target={a['target_close_date']}"
            print(line)
            if a.get("error"):
                print(f"        error: {a['error']}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("--work-dir", required=True)
    pi.add_argument("--team", required=True)
    pi.add_argument("--as-of", required=True)
    pi.add_argument("--portfolio", action="store_true")
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

    ps = sub.add_parser("set-phase")
    ps.add_argument("--work-dir", required=True)
    ps.add_argument("--phase", required=True)
    ps.add_argument("--status", required=True)
    ps.add_argument("--note", default=None)
    ps.set_defaults(func=cmd_set_phase)

    pa = sub.add_parser("set-advisory")
    pa.add_argument("--work-dir", required=True)
    pa.add_argument("--cluster-id", required=True)
    pa.add_argument("--status", required=True)
    pa.add_argument("--error", default=None)
    pa.add_argument("--fix-family", default=None)
    pa.add_argument("--target-close-date", default=None)
    pa.set_defaults(func=cmd_set_advisory)

    pr = sub.add_parser("resume-point")
    pr.add_argument("--work-dir", required=True)
    pr.set_defaults(func=cmd_resume_point)

    psh = sub.add_parser("show")
    psh.add_argument("--work-dir", required=True)
    psh.set_defaults(func=cmd_show)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
