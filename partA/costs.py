"""Price every model call in Inspect .eval logs, per sample and role.

Usage: python costs.py runs/part_a/logs   (prints a role x target summary)

inspect_ai normalizes usage so that input_tokens excludes cached tokens and
output_tokens includes reasoning/thinking tokens, for both providers.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from inspect_ai.event import ModelEvent
from inspect_ai.log import list_eval_logs, read_eval_log

PRICING = json.loads((Path(__file__).parent / "pricing.json").read_text())["models"]


def _price_table(model: str) -> dict:
    name = model.split("/")[-1]
    for key, table in PRICING.items():
        if key.split("/")[-1] == name:
            return table
    raise KeyError(f"No pricing for model {model!r}; add it to pricing.json")


def call_cost(model: str, usage) -> tuple[float, bool]:
    """Return (usd, long_prompt_tier_used) for one model call."""
    if model.startswith("mockllm"):
        return 0.0, False
    table = _price_table(model)
    uncached = usage.input_tokens or 0
    cache_read = usage.input_tokens_cache_read or 0
    cache_write = usage.input_tokens_cache_write or 0
    prompt = uncached + cache_read + cache_write
    long_tier = "long_prompt" in table and prompt > table["long_prompt_threshold"]
    rates = table["long_prompt"] if long_tier else table
    usd = (
        uncached * rates["input"]
        + cache_write * rates["cache_write"]
        + cache_read * rates["cache_read"]
        + (usage.output_tokens or 0) * rates["output"]
    ) / 1e6
    return usd, long_tier


def sample_rows(log_path) -> list[dict]:
    """One row per (sample, role) with token totals and cost."""
    log = read_eval_log(log_path)
    target_model = log.eval.model_roles["target"].model if log.eval.model_roles else log.eval.model
    rows = []
    for sample in log.samples or []:
        agg = defaultdict(lambda: defaultdict(float))
        for event in sample.events:
            if not isinstance(event, ModelEvent):
                continue
            role = event.role or "unknown"
            a = agg[role]
            a["calls"] += 1
            a["retries"] += event.retries or 0
            if event.error:
                a["errored_calls"] += 1
            usage = event.output.usage if event.output else None
            if usage is None:
                continue
            usd, long_tier = call_cost(event.model, usage)
            a["usd"] += usd
            a["long_tier_calls"] += int(long_tier)
            a["input"] += usage.input_tokens or 0
            a["cache_read"] += usage.input_tokens_cache_read or 0
            a["cache_write"] += usage.input_tokens_cache_write or 0
            a["output"] += usage.output_tokens or 0
            a["reasoning"] += usage.reasoning_tokens or 0
            a["max_prompt"] = max(
                a["max_prompt"],
                (usage.input_tokens or 0) + (usage.input_tokens_cache_read or 0) + (usage.input_tokens_cache_write or 0),
            )
        for role, a in agg.items():
            # "usd" defaults to 0: a call interrupted before returning usage (e.g. a cancelled run) has no cost fields.
            rows.append({"log": Path(str(log_path)).name, "target_model": target_model, "seed": sample.id,
                         "role": role, "usd": 0.0,
                         **{k: round(v, 6) if k == "usd" else int(v) for k, v in a.items()}})
    return rows


def log_paths(log_dir: str) -> list[str]:
    return [info.name for info in list_eval_logs(log_dir)]


def total_spend(log_dir: str) -> float:
    return sum(r["usd"] for p in log_paths(log_dir) for r in sample_rows(p))


if __name__ == "__main__":
    import pandas as pd

    log_dir = sys.argv[1] if len(sys.argv) > 1 else "runs/part_a/logs"
    df = pd.DataFrame([r for p in log_paths(log_dir) for r in sample_rows(p)])
    if df.empty:
        sys.exit("No model calls found.")
    print(df.groupby(["role", "target_model"])[["usd", "calls", "input", "cache_read", "cache_write", "output", "reasoning"]].sum())
    print(f"\nTOTAL ${df['usd'].sum():.4f}")
