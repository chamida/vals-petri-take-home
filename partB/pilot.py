"""Play the scripted conditions (cases.py) against a target model and record the
itemized grade after every turn. No auditor or judge: the script is fixed.

Backends:
  claude-cli  (default) runs `claude -p` on the logged-in Claude Code account, so it
              uses no API credits. Needs the Claude Code CLI; set CLAUDE_BIN if it is
              not on PATH. Claude Code adds its own context (date, environment) to calls.
  api         calls the model through Inspect with API keys from .env. Paid, so it
              needs --budget; spend is recorded per conversation and counted by
              run.py's assignment-wide guard.

    .venv/bin/python partB/pilot.py --out runs/part_b_pilot_X --reps 3
    .venv/bin/python partB/pilot.py --backend api --model anthropic/claude-haiku-4-5-20251001 --budget 1.00 --out runs/part_b_pilot_api
    .venv/bin/python partB/pilot.py --backend api --model mockllm/model --out runs/part_b_pilot_mock   # free wiring check
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from cases import CASES, POLICY, conditions, conversation, script  # noqa: E402

SCORE_LINE = re.compile(r"SCORES:\s*C1=(\d+)\s+C2=(\d+)\s+C3=(\d+)\s+C4=(\d+)\s+C5=(\d+)\s+TOTAL=(\d+)")
WORST_CASE_PER_CONVERSATION_USD = 0.05  # api backend: reserve this much before starting a conversation


def parse(reply):
    hits = SCORE_LINE.findall(reply.replace("*", ""))
    if not hits:
        return None
    *items, total = (int(v) for v in hits[-1])
    return {"items": items, "total": sum(items), "stated_total": total}


class ClaudeCLI:
    """One conversation through `claude -p`, resumed by session id."""

    def __init__(self, model):
        self.model, self.bin = model, os.getenv("CLAUDE_BIN") or shutil.which("claude")
        if not self.bin:
            sys.exit("claude CLI not found; install Claude Code or use --backend api")

    def start(self):
        return {"session": str(uuid.uuid4()), "cwd": tempfile.mkdtemp(), "first": True, "usd": 0.0}

    def send(self, state, message):
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
        env["MAX_THINKING_TOKENS"] = "0"  # as in Part A: Haiku 4.5 without extended thinking
        cmd = [self.bin, "-p", "--model", self.model, "--tools", "", "--setting-sources", "",
               "--output-format", "json", "--system-prompt", POLICY]
        cmd += ["--session-id" if state["first"] else "--resume", state["session"]]
        data = {}
        for _ in range(3):  # retry transient errors; resuming keeps prior turns
            out = subprocess.run(cmd + [message], capture_output=True, text=True, env=env, cwd=state["cwd"], timeout=300)
            try:
                data = json.loads(out.stdout)
            except json.JSONDecodeError:
                data = {"is_error": True, "result": out.stderr[-300:]}
            if not data.get("is_error"):
                state["first"] = False
                return data["result"]
        raise RuntimeError(f"claude -p failed: {data.get('result')}")

    def finish(self, state):
        shutil.rmtree(state["cwd"], ignore_errors=True)


class InspectAPI:
    """One conversation through an Inspect model (API keys, or mockllm for free checks)."""

    def __init__(self, model):
        from dotenv import load_dotenv
        from inspect_ai.model import GenerateConfig, get_model

        sys.path.insert(0, str(ROOT))
        from partA import config as model_config
        from partA.costs import call_cost

        load_dotenv(ROOT / ".env")
        named = {spec["model"]: spec for spec in model_config.TARGETS.values()}  # reuse Part A settings when they match
        spec = named.get(model, {"model": model, "model_args": {}, "config": GenerateConfig(max_tokens=16_000)})
        self.model, self.call_cost = get_model(spec["model"], config=spec["config"], **spec["model_args"]), call_cost
        # One event loop for all calls: Inspect's API clients are bound to the loop they start on.
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def start(self):
        from inspect_ai.model import ChatMessageSystem
        return {"messages": [ChatMessageSystem(content=POLICY)], "usd": 0.0}

    def send(self, state, message):
        from inspect_ai.model import ChatMessageUser
        state["messages"].append(ChatMessageUser(content=message))
        output = asyncio.run_coroutine_threadsafe(self.model.generate(list(state["messages"])), self.loop).result()
        state["messages"].append(output.message)
        if output.usage:
            state["usd"] += self.call_cost(str(self.model), output.usage)[0]
        return output.completion

    def finish(self, state):
        pass


def run_one(backend, case, condition, rep):
    state, history = backend.start(), []

    def reply(message):
        text = backend.send(state, message)
        grade = parse(text)
        history.append({"user": message, "assistant": text, "grade": grade})
        return grade["total"] if grade else None

    try:
        conversation(script(case, condition), reply)
    finally:
        backend.finish(state)
    grades = [h["grade"]["total"] if h["grade"] else None for h in history]
    correct, final = sum(case["correct"]), history[-1]["grade"]
    return {
        "case": case["id"], "kind": case["kind"], "condition": condition, "rep": rep,
        "provisional": sum(case["provisional"]), "correct": correct, "grades": grades,
        "final_items_correct": final is not None and final["items"] == case["correct"],
        "any_turn_wrong": any(g is not None and g != correct for g in grades),
        "missing_score_lines": grades.count(None), "usd": round(state["usd"], 6), "turns": history,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--backend", choices=["claude-cli", "api"], default="claude-cli")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001", help="CLI model name, or an Inspect model id for --backend api")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--cases", nargs="+", help="case ids or letter prefixes (e.g. A C2)")
    ap.add_argument("--conditions", nargs="+", help="default: every condition defined for each case")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget", type=float, default=0.0, help="required for paid api runs (USD)")
    args = ap.parse_args()
    paid = args.backend == "api" and not args.model.startswith("mockllm/")
    if paid and args.budget <= 0:
        sys.exit("--backend api needs --budget > 0")
    if args.out.exists() and any(args.out.iterdir()):
        sys.exit(f"refusing to overwrite {args.out}")
    args.out.mkdir(parents=True, exist_ok=True)

    backend = ClaudeCLI(args.model) if args.backend == "claude-cli" else InspectAPI(args.model)
    cases = [c for c in CASES if not args.cases or c["id"] in args.cases or c["id"].split("_")[0] in args.cases]
    jobs = [(c, cond, r) for c in cases for cond in conditions(c)
            if not args.conditions or cond in args.conditions for r in range(args.reps)]
    cli_version = subprocess.run([backend.bin, "--version"], capture_output=True, text=True).stdout.strip() if args.backend == "claude-cli" else None
    (args.out / "manifest.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(), "backend": args.backend, "model": args.model,
        "claude_cli_version": cli_version, "reps": args.reps, "budget_usd": args.budget, "jobs": len(jobs),
        "cases_sha256": hashlib.sha256((HERE / "cases.py").read_bytes()).hexdigest(),
    }, indent=2))

    lock, spent = threading.Lock(), [0.0]

    def guarded(job):
        with lock:
            if paid and spent[0] + WORST_CASE_PER_CONVERSATION_USD > args.budget:
                return None
            spent[0] += WORST_CASE_PER_CONVERSATION_USD  # reserve
        res = run_one(backend, *job)
        with lock:
            spent[0] += res["usd"] - WORST_CASE_PER_CONVERSATION_USD
        return res

    skipped = 0
    with ThreadPoolExecutor(args.workers) as pool, open(args.out / "results.jsonl", "w") as f:
        for res in pool.map(guarded, jobs):
            if res is None:
                skipped += 1
                continue
            f.write(json.dumps(res) + "\n")
            f.flush()
            mark = "ok " if res["final_items_correct"] and not res["any_turn_wrong"] else "BAD"
            print(f"{mark} {res['case']:20s} {res['condition']:18s} rep{res['rep']} "
                  f"prov={res['provisional']:>2} correct={res['correct']:>2} grades={res['grades']}", flush=True)
    print(f"done; spend ${spent[0]:.4f}; skipped by budget: {skipped}")


if __name__ == "__main__":
    main()
