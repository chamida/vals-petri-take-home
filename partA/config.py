"""Frozen configuration for the Part A comparison."""

from inspect_ai.model import GenerateConfig

# Drawn before this evaluation from Petri's non-prefill seeds. The earlier setup
# runs are archived outside this folder and are excluded from the results.
SEEDS = [
    "66", "idx140", "44",
    "80", "idx175", "9",
    "idx161", "idx142", "36",
    "93", "76", "62",
]
FAMILIES = {
    "autonomy": ["66", "80", "idx161", "93"],
    "misuse": ["idx140", "idx175", "idx142", "76"],
    "user wellbeing": ["44", "9", "36", "62"],
}

# Extension, drawn by select_extension.py after the first 11 frozen seeds ran and
# recorded in SEEDS.md before any of these ran. 62 is the last unrun frozen seed.
EXTENSION_SEEDS = ["idx156", "idx166", "70", "27", "22"]
EXTENSION_FAMILIES = {
    "autonomy": ["idx156", "70"],
    "misuse": ["idx166", "27"],
    "user wellbeing": ["22"],
}

MAX_AUDITOR_TURNS = 30  # Petri's default
RUN_BUDGET_USD = 8.00   # leaves most of the $20 assignment budget for Part B
SOLVER_COST_CAP_USD = 0.40  # per audit; auditor and target
JUDGE_COST_CAP_USD = 0.40   # per audit; judge runs outside Inspect's sample cap

# Continuation (run.py --continue-from runs/part_a). The $0.40 cap cut off Haiku 4.5
# on idx140 at its 30th auditor turn, so Haiku 4.5 audits get $0.80 from here on.
# GPT-5 mini audits used under $0.10 of their cap and keep $0.40.
CONTINUATION_SOLVER_COST_CAP_USD = {"gpt-5-mini": 0.40, "claude-haiku-4.5": 0.80}
PART_A_BUDGET_USD = 8.73  # all Part A runs combined; $4.73 spent before the extension + $4.00
REIMBURSEMENT_BUDGET_USD = 20.00
ARCHIVED_SETUP_SPEND_USD = 1.43  # pilot + stopped run, archived outside this repo; not in results

_TRANSPORT = dict(max_retries=3, timeout=300)
AUDITOR = {
    "model": "anthropic/claude-haiku-5-5",
    "model_args": {"cache_ttl": "5m"},
    "config": GenerateConfig(max_tokens=16_000, reasoning_effort="medium", **_TRANSPORT),
}
JUDGE = {
    "model": "anthropic/claude-sonnet-5-5",
    "model_args": {"cache_ttl": "5m"},
    "config": GenerateConfig(max_tokens=32_000, reasoning_effort="high", **_TRANSPORT),
}
TARGETS = {
    "gpt-5-mini": {
        "model": "openai/gpt-5-mini-2025-08-07",
        "model_args": {},
        "config": GenerateConfig(max_tokens=16_000, reasoning_effort="medium", **_TRANSPORT),
    },
    "claude-haiku-4.5": {
        "model": "anthropic/claude-haiku-4-5-20251001",
        "model_args": {"cache_ttl": "5m"},
        "config": GenerateConfig(max_tokens=16_000, **_TRANSPORT),
    },
}
