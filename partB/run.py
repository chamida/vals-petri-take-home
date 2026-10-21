"""Run a frozen Part B plan through Petri, both targets for every job.

    .venv/bin/python partB/run.py --plan partB/plans/paid_v5_final_extension.json --dry-run --out runs/part_b_dryrun
    .venv/bin/python partB/run.py --plan partB/plans/paid_v5_final_extension.json --out runs/part_b_new

Jobs run in plan order, one batch per plan block (and repetition). Before each batch
the runner reserves the worst case for *every target* on the whole block (per-audit
solver cap + judge cap), so a budget stop falls between blocks: each block runs on all
targets before the next starts, and a block is never left half done.
Two guards: the plan budget for this run, and the assignment-wide total (every
Inspect log and API pilot in runs/ plus the archived setup runs) against the $20
reimbursement budget. A call already in flight can still cross a cap. The run
refuses to start if cases.py or task.py differ from the hashes frozen in the plan.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelCost, get_model

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from partA import config as model_config  # noqa: E402
from partA.costs import PRICING, log_paths, sample_rows  # noqa: E402
from task import grading_appeal  # noqa: E402

MAX_TURNS = 10


def model(spec, dry_run):
    return get_model("mockllm/model") if dry_run else get_model(spec["model"], config=spec["config"], **spec["model_args"])


def spend(log_dir: Path) -> float:
    return sum(r["usd"] for p in log_paths(str(log_dir)) for r in sample_rows(p)) if log_dir.is_dir() else 0.0


def pilot_spend(run_dir: Path) -> float:
    """API spend recorded by pilot.py (claude-cli pilots record 0)."""
    path = run_dir / "results.jsonl"
    return sum(json.loads(line).get("usd", 0.0) for line in path.open()) if path.exists() else 0.0


def assignment_spend() -> float:
    """Every Inspect log and API pilot in runs/, plus the archived setup runs outside the repo."""
    runs = [d for d in (ROOT / "runs").iterdir() if d.is_dir()]
    log_dirs = {(d / "logs").resolve() for d in runs if (d / "logs").is_dir()}  # a symlinked copy counts once
    return model_config.ARCHIVED_SETUP_SPEND_USD + sum(spend(d) for d in log_dirs) + sum(pilot_spend(d) for d in runs)


def batches_of(jobs):
    return [list(group) for _, group in groupby(jobs, key=lambda j: (j["block"], j["rep"]))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text())
    for f, digest in plan["frozen_files_sha256"].items():
        if hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != digest:
            ap.error(f"{f} changed since the plan was frozen; re-freeze the plan first")
    targets, caps = plan["targets"], plan["per_audit_caps_usd"]
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        ap.error(f"refusing to overwrite {out}")
    load_dotenv(ROOT / ".env")
    if not args.dry_run and not all(os.getenv(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")):
        ap.error("a paid run needs both API keys in .env")
    out.mkdir(parents=True)

    (out / "manifest.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(), "dry_run": args.dry_run, "plan": plan,
        "assignment_spend_at_start_usd": None if args.dry_run else round(assignment_spend(), 4),
        "reimbursement_budget_usd": model_config.REIMBURSEMENT_BUDGET_USD, "max_turns": MAX_TURNS,
        "auditor": model_config.AUDITOR["model"], "judge": model_config.JUDGE["model"],
        "target_models": {t: model_config.TARGETS[t]["model"] for t in targets},
    }, indent=2))
    costs = {name: ModelCost(input=p["input"], output=p["output"], input_cache_write=p["cache_write"],
                             input_cache_read=p["cache_read"]) for name, p in PRICING.items()}
    records = []

    def save():
        (out / "run_log.json").write_text(json.dumps(records, indent=2))

    batches = batches_of(plan["jobs"])
    for n, batch in enumerate(batches):
        worst = len(batch) * len(targets) * (caps["solver"] + caps["judge"])
        if not args.dry_run:
            here, total = spend(out / "logs"), assignment_spend()
            if here + worst > plan["budget_usd"] or total + worst > model_config.REIMBURSEMENT_BUDGET_USD:
                records += [{**j, "status": "not_launched_budget"} for b in batches[n:] for j in b]
                print(f"Budget guard: stopping before batch {n} (run ${here:.4f}, assignment ${total:.4f}).")
                break
        rep = batch[0]["rep"]
        for target in targets:
            logs = inspect_eval(
                grading_appeal(sample_ids=[j["seed"] for j in batch],
                               transcript_save_dir=str(out / "transcripts" / target / f"rep{rep}"),
                               judge_cap_usd=None if args.dry_run else caps["judge"], max_turns=MAX_TURNS),
                model=model(model_config.AUDITOR, args.dry_run),
                model_roles={"auditor": model(model_config.AUDITOR, args.dry_run),
                             "target": model(model_config.TARGETS[target], args.dry_run),
                             "judge": model(model_config.JUDGE, args.dry_run)},
                log_dir=str(out / "logs"), max_samples=len(batch), fail_on_error=False, retry_on_error=0,
                cost_limit=None if args.dry_run else caps["solver"], model_cost_config=None if args.dry_run else costs,
                metadata={"target_name": target, "rep": rep, "block": batch[0]["block"]}, display="plain",
            )
            for log in logs:
                usd = 0.0 if args.dry_run else sum(r["usd"] for r in sample_rows(log.location))
                records += [{**j, "target": target, "status": log.status, "log": log.location} for j in batch]
                print(f"batch {n} ({batch[0]['block']}, rep {rep}) {target}: {log.status}; ${usd:.4f}", flush=True)
            save()
    save()
    print(f"Done: {out}; run spend ${0.0 if args.dry_run else spend(out / 'logs'):.4f}")


if __name__ == "__main__":
    main()
