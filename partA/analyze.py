"""Per-audit status, interaction counts, scores and cost for a set of Petri logs.

Usage: python analyze.py runs/part_a
       python analyze.py runs/part_a runs/part_a_cont --out runs/part_a_combined

Writes <out>/analysis/{audits.csv, scores_long.csv, costs.csv, paired_concerning.md};
<out> defaults to the run directory when only one is given.
An audit only counts as "scored" if it finished without error AND the judge's
response parsed fully. Petri fills unparsed dimensions with 1 (the safest score),
so judge failures are excluded rather than treated as safe. Likewise a solver
limit (the judge then sees an empty transcript) or a cancelled log is excluded.
Across run directories every audit is kept on disk and in audits.csv, but only
"scored" audits enter the results, and two scored audits of the same seed and
target are rejected.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from inspect_ai.event import ModelEvent, ToolEvent
from inspect_ai.log import read_eval_log

import config
from costs import log_paths, sample_rows
from task import JUDGE_COST_LIMIT_ANSWER

HEADLINE = "concerning"


def judge_status(score) -> str:
    if score is None:
        return "missing"
    cap_reached = (score.metadata or {}).get("judge_cost_cap_reached", False)
    if score.answer == JUDGE_COST_LIMIT_ANSWER:
        return "judge_cost_limit"
    if score.answer == "Failed to parse judge's response":
        return "judge_cost_limit" if cap_reached else "judge_failed"
    if (score.explanation or "").startswith("Partial parse"):
        return "judge_partial"
    return "ok"


def audit_rows(log_path) -> tuple[list[dict], list[dict]]:
    log = read_eval_log(log_path)
    target_model = log.eval.model_roles["target"].model
    target_name = (log.eval.metadata or {}).get("target_name", target_model)
    audits, scores = [], []
    for s in log.samples or []:
        tools = Counter(e.function for e in s.events if isinstance(e, ToolEvent))
        roles = Counter(e.role for e in s.events if isinstance(e, ModelEvent))
        target_errors = sum(1 for e in s.events if isinstance(e, ToolEvent) and e.error
                            and "Error calling target model" in str(e.error.message))
        score = (s.scores or {}).get("alignment_judge")
        jstatus = judge_status(score)
        if log.status == "cancelled":
            status = "cancelled"
        elif s.error:
            status = "sample_error"
        elif s.limit:
            status = f"limit_{s.limit.type}"
        else:
            status = "scored" if jstatus == "ok" else jstatus
        audits.append({
            "log": Path(str(log_path)).name,
            "target": target_name,
            "target_model": target_model,
            "seed": s.id,
            "tags": ",".join(s.metadata.get("tags", [])),
            "status": status,
            "error": (s.error.message[:200] if s.error else ""),
            "auditor_turns": roles.get("auditor", 0),
            "target_exchanges": roles.get("target", 0),
            "judge_calls": roles.get("judge", 0),
            "ended_naturally": tools.get("end_conversation", 0) > 0,
            "send_message": tools.get("send_message", 0),
            "send_tool_call_result": tools.get("send_tool_call_result", 0),
            "create_tool": tools.get("create_tool", 0),
            "rollback": tools.get("rollback_conversation", 0),
            "set_system_message": tools.get("set_target_system_message", 0),
            "auditor_tool_errors": sum(1 for e in s.events if isinstance(e, ToolEvent) and e.error),
            "target_call_errors": target_errors,
            HEADLINE: score.value.get(HEADLINE) if score and status == "scored" else None,
            "judge_cost_usd": (score.metadata or {}).get("judge_cost_usd") if score else None,
            "judge_summary": (score.answer or "")[:400] if score else "",
        })
        if score and status == "scored":
            for dim, value in score.value.items():
                scores.append({"target": target_name, "target_model": target_model, "seed": s.id, "dimension": dim, "score": value})
    return audits, scores


def main(run_dirs: list[Path], out_dir: Path):
    out = out_dir / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    paths = [p for run in run_dirs for p in log_paths(str(run / "logs"))]
    audits, scores, costs = [], [], []
    for p in paths:
        a, sc = audit_rows(p)
        audits += a
        scores += sc
        costs += sample_rows(p)

    audits_df = pd.DataFrame(audits)
    audits_df["valid"] = audits_df["status"] == "scored"
    valid = audits_df[audits_df["valid"]]
    dupes = valid[valid.duplicated(["target", "seed"], keep=False)]
    if not dupes.empty:
        pairs = sorted(set(zip(dupes["target"], dupes["seed"])))
        sys.exit(f"Refusing to analyze: more than one valid score for seed/target {pairs} "
                 f"in {[str(r) for r in run_dirs]}. Each seed/target pair may have only one scored audit.")
    costs_df = pd.DataFrame(costs)
    audits_df.to_csv(out / "audits.csv", index=False)
    pd.DataFrame(scores).to_csv(out / "scores_long.csv", index=False)
    costs_df.to_csv(out / "costs.csv", index=False)

    cols = ["target", "seed", "status", "valid", "auditor_turns", "target_exchanges", "ended_naturally",
            "create_tool", "send_tool_call_result", "rollback", "auditor_tool_errors", HEADLINE]
    print(audits_df[cols].sort_values(["seed", "target"]).to_string(index=False))

    paired = valid.pivot_table(index="seed", columns="target", values=HEADLINE, aggfunc="first")
    status = audits_df.pivot_table(index="seed", columns="target", values="status", aggfunc=lambda s: "+".join(s))
    md = ["| seed | " + " | ".join(f"{c} ({HEADLINE})" for c in status.columns) + " |",
          "|---|" + "---|" * len(status.columns)]
    for seed in status.index:
        cells = []
        for c in status.columns:
            v = paired.loc[seed, c] if seed in paired.index and c in paired.columns else None
            cells.append(f"{int(v)}" if pd.notna(v) else f"n/a ({status.loc[seed, c]})")
        md.append(f"| {seed} | " + " | ".join(cells) + " |")
    (out / "paired_concerning.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md))

    if not costs_df.empty:
        by_role = costs_df.groupby(["role", "target_model"])["usd"].sum()
        print("\nCost by role/target:\n", by_role.round(4).to_string())
        part_a = costs_df["usd"].sum()
        left = config.REIMBURSEMENT_BUDGET_USD - config.ARCHIVED_SETUP_SPEND_USD - part_a
        print(f"TOTAL ${part_a:.4f}  (all audits above, including excluded ones)")
        print(f"Reimbursement budget ${config.REIMBURSEMENT_BUDGET_USD:.2f} - archived setup "
              f"${config.ARCHIVED_SETUP_SPEND_USD:.2f} - Part A ${part_a:.4f} = ${left:.4f} left")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="*", type=Path, default=[Path("runs/part_a")])
    parser.add_argument("--out", type=Path, help="defaults to the run directory if only one is given")
    args = parser.parse_args()
    if args.out is None and len(args.run_dirs) > 1:
        sys.exit("Pass --out when combining run directories.")
    main(args.run_dirs, args.out or args.run_dirs[0])
