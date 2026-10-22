"""Offline preparation and scoring CLI for CDD-MAR-001."""
from __future__ import annotations

import argparse
import json

from .runner import configure_run, evaluate_run, make_plan, prepare_run, reset_owned_run


def main() -> int:
    parser = argparse.ArgumentParser(description="CoDesk Blender Model-and-Review case")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--condition", required=True)
    plan.add_argument("--run-id", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--run-root", required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--fixture")
    prepare.add_argument("--blender-bin")
    configure = sub.add_parser("configure")
    configure.add_argument("--run-root", required=True)
    configure.add_argument("--condition", required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--run-root", required=True)
    evaluate.add_argument("--blender-bin")
    reset = sub.add_parser("reset")
    reset.add_argument("--run-root", required=True)
    reset.add_argument("--run-id", required=True)
    reset.add_argument("--fixture")
    reset.add_argument("--blender-bin")
    args = parser.parse_args()

    if args.command == "plan":
        result = make_plan(args.condition, args.run_id)
    elif args.command == "prepare":
        result = prepare_run(args.run_root, args.run_id, fixture_path=args.fixture, blender_bin=args.blender_bin)
    elif args.command == "configure":
        result = configure_run(args.run_root, args.condition)
    elif args.command == "evaluate":
        result = evaluate_run(args.run_root, blender_bin=args.blender_bin)
    else:
        result = reset_owned_run(args.run_root, args.run_id, fixture_path=args.fixture, blender_bin=args.blender_bin)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
