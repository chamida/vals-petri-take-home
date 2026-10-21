"""Run the fixed Part A seed set once for each target.

    ../.venv/bin/python partA/run.py --dry-run  # free wiring check
    ../.venv/bin/python partA/run.py            # paid evaluation
    ../.venv/bin/python partA/run.py --continue-from runs/part_a --seeds 66 idx140 ...

Results go to runs/part_a. An existing output directory is never overwritten.

--continue-from writes a new directory (default runs/part_a_cont) and launches only
the seed/target audits that have no valid score in the earlier run directories
(invalid ones, e.g. cost-limited or cancelled, are rerun; their logs are kept).
It uses the continuation solver caps and the combined Part A budget from config.py,
counting the earlier runs' spend against that budget.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelCost, get_model

import config
from analyze import audit_rows
from costs import PRICING, log_paths, sample_rows, total_spend
from task import petri_noprefill

ROOT = Path(__file__).resolve().parent.parent


def model(spec, dry_run):
    if dry_run:
        return get_model("mockllm/model")
    return get_model(spec["model"], config=spec["config"], **spec["model_args"])


def model_costs():
    return {
        name: ModelCost(
            input=p["input"], output=p["output"],
            input_cache_write=p["cache_write"], input_cache_read=p["cache_read"],
        )
        for name, p in PRICING.items()
    }


def spec_record(spec):
    return {
        "model": spec["model"],
        "model_args": spec["model_args"],
        "config": spec["config"].model_dump(exclude_none=True),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--continue-from", type=Path, nargs="+", default=[])
    parser.add_argument("--seeds", nargs="+", help="seeds from config.SEEDS / EXTENSION_SEEDS, run in the order given")
    args = parser.parse_args()

    seeds = config.SEEDS
    if args.seeds:
        known = config.SEEDS + config.EXTENSION_SEEDS
        unknown = sorted(set(args.seeds) - set(known))
        if unknown:
            sys.exit(f"Seeds not in config.SEEDS or config.EXTENSION_SEEDS: {unknown}")
        seeds = list(dict.fromkeys(args.seeds))  # run in the order given

    prior = [p.resolve() for p in args.continue_from]
    if prior:
        name = "part_a_cont"
        budget = config.PART_A_BUDGET_USD
        caps = config.CONTINUATION_SOLVER_COST_CAP_USD
    else:
        name = "part_a"
        budget = config.RUN_BUDGET_USD
        caps = {target: config.SOLVER_COST_CAP_USD for target in config.TARGETS}
    out = args.out or ROOT / "runs" / (f"{name}_dryrun" if args.dry_run else name)
    out = out.resolve()
    if out in prior:
        sys.exit("--out must differ from --continue-from.")
    if out.exists() and any(out.iterdir()):
        sys.exit(f"Refusing to overwrite {out}; choose a new --out directory.")

    load_dotenv(ROOT / ".env")
    if not args.dry_run:
        missing = [k for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY") if not os.getenv(k)]
        if missing:
            sys.exit(f"Missing {', '.join(missing)} in the environment or .env")

    # Real spend and valid audits already on disk; read even in a dry run (free).
    prior_paths = [p for run in prior for p in log_paths(str(run / "logs"))]
    prior_spend = sum(r["usd"] for p in prior_paths for r in sample_rows(p))
    done = {(a["target"], a["seed"]) for p in prior_paths for a in audit_rows(p)[0] if a["status"] == "scored"}

    out.mkdir(parents=True, exist_ok=True)
    petri = ROOT / "refs" / "inspect_petri"
    commit = subprocess.run(
        ["git", "-C", str(petri), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "petri_commit": commit,
        "seeds": config.SEEDS,
        "families": config.FAMILIES,
        "max_auditor_turns": config.MAX_AUDITOR_TURNS,
        "prefill": False,
        "run_budget_usd": budget,
        "continue_from": [str(p) for p in prior],
        "prior_spend_usd": round(prior_spend, 4),
        "prior_valid_audits": sorted(f"{seed}/{target}" for target, seed in done),
        "seeds_requested": seeds,
        "per_audit_solver_cap_usd": caps,
        "per_audit_judge_cap_usd": config.JUDGE_COST_CAP_USD,
        "auditor": spec_record(config.AUDITOR),
        "judge": spec_record(config.JUDGE),
        "targets": {name: spec_record(spec) for name, spec in config.TARGETS.items()},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    log_dir = out / "logs"
    records = []

    def record(entry):
        records.append(entry)
        (out / "run_log.json").write_text(json.dumps(records, indent=2))

    def spend():
        return prior_spend + (0 if args.dry_run else total_spend(str(log_dir)))

    def reservation(target_name):
        return caps[target_name] + config.JUDGE_COST_CAP_USD

    for seed in seeds:
        todo = [(n, t) for n, t in config.TARGETS.items() if (n, seed) not in done]
        if not todo:
            record({"seed": seed, "status": "already_valid"})
            continue
        if spend() + sum(reservation(n) for n, _ in todo) > budget:
            record({"seed": seed, "status": "not_launched_budget"})
            print(f"Stopping before seed {seed}: remaining budget cannot reserve its audits.")
            break

        for index, (target_name, target) in enumerate(todo):
            if index and spend() + reservation(target_name) > budget:
                record({"seed": seed, "target": target_name, "status": "incomplete_pair_budget"})
                print(f"Stopping before {target_name} on seed {seed}: insufficient budget.")
                return

            task = petri_noprefill(
                seed_labels=[seed],
                max_turns=config.MAX_AUDITOR_TURNS,
                transcript_save_dir=str(out / "transcripts" / target_name),
                judge_cost_cap=None if args.dry_run else config.JUDGE_COST_CAP_USD,
            )
            logs = inspect_eval(
                task,
                model=model(config.AUDITOR, args.dry_run),
                model_roles={
                    "auditor": model(config.AUDITOR, args.dry_run),
                    "target": model(target, args.dry_run),
                    "judge": model(config.JUDGE, args.dry_run),
                },
                log_dir=str(log_dir),
                max_samples=1,
                fail_on_error=False,
                retry_on_error=0,
                cost_limit=None if args.dry_run else caps[target_name],
                model_cost_config=None if args.dry_run else model_costs(),
                metadata={"seed": seed, "target_name": target_name},
                display="plain",
            )
            for log in logs:
                usd = 0 if args.dry_run else sum(r["usd"] for r in sample_rows(log.location))
                audit = [a["status"] for a in audit_rows(log.location)[0]]
                record({
                    "seed": seed, "target": target_name, "status": log.status, "audit_status": audit,
                    "log": log.location, "usd": round(usd, 4),
                })
                print(f"{seed} / {target_name}: {log.status} ({', '.join(audit)}); ${usd:.4f}; total ${spend():.4f}")

    print(f"Finished. Results: {out}; estimated cost: ${spend():.4f}")


if __name__ == "__main__":
    main()
