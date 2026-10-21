"""Petri default audit, restricted to non-prefill seeds and run with prefill disabled.

Differences from petri-v2's stock `audit()` task, all deliberate:
  1. prefill=False for the auditor (stock task leaves it on); GPT-5 mini cannot be prefilled.
  2. Prefill-tagged seeds are excluded.
  3. Seeds get stable labels: upstream ids where present, otherwise "idx<position>"
     (69 seeds have no id upstream). Seed wording is unchanged.
  4. The judge's hardcoded reasoning_tokens=10_000 is dropped, because Claude 4.7+
     judges reject a fixed thinking budget. Rubrics and judge prompt are unchanged.
  5. The judge runs inside its own cost limit (Inspect's per-sample limit excludes scoring).
"""

import copy

from inspect_ai import Task, task
from inspect_ai.model import GenerateConfig
from inspect_ai.scorer import Score, Scorer, mean, scorer, stderr
from inspect_ai.util import LimitExceededError, cost_limit

import petri.scorers.judge as judge_module
from petri.cleanup.save_transcripts import save_transcripts
from petri.scorers.judge import alignment_judge
from petri.solvers.auditor_agent import auditor_agent
from petri.solvers.prompts import AUDITOR_SYSTEM_PROMPT
from petri.tasks.petri import SEED_INSTRUCTIONS

from config import MAX_AUDITOR_TURNS

JUDGE_COST_LIMIT_ANSWER = "JUDGE_COST_LIMIT_REACHED"

_upstream_get_model = judge_module.get_model


def _judge_get_model(*args, config: GenerateConfig = GenerateConfig(), **kwargs):
    # Keep everything the upstream judge asks for except the fixed thinking budget.
    return _upstream_get_model(*args, config=config.model_copy(update={"reasoning_tokens": None}), **kwargs)


judge_module.get_model = _judge_get_model


@scorer(metrics={"*": [mean(), stderr()]}, name="alignment_judge")
def capped_alignment_judge(judge_cost_cap: float | None = None) -> Scorer:
    """Stock alignment_judge run inside its own cost limit.

    Scoring happens outside Inspect's per-sample cost limit, so without this the
    judge (and its retries) would be uncapped. The judge catches errors per attempt,
    so reaching the cap ends in a parse failure; it is flagged explicitly here.
    """
    inner = alignment_judge()

    async def score(state, target) -> Score:
        with cost_limit(judge_cost_cap) as limit:
            try:
                result = await inner(state, target)
            except LimitExceededError:
                result = Score(value={}, answer=JUDGE_COST_LIMIT_ANSWER, explanation=JUDGE_COST_LIMIT_ANSWER)
        hit = judge_cost_cap is not None and limit.usage >= judge_cost_cap
        result.metadata = (result.metadata or {}) | {"judge_cost_usd": limit.usage, "judge_cost_cap_reached": hit}
        return result

    return score


def seed_label(index: int, sample_id) -> str:
    return str(sample_id) if sample_id is not None else f"idx{index}"


def labelled_seeds() -> list:
    seeds = []
    for index, sample in enumerate(copy.deepcopy(SEED_INSTRUCTIONS)):
        sample.id = seed_label(index, sample.id)
        sample.metadata = (sample.metadata or {}) | {"seed_label": sample.id, "seed_index": index}
        seeds.append(sample)
    return seeds


def is_prefill(sample) -> bool:
    return "prefill" in (sample.metadata or {}).get("tags", [])


@task
def petri_noprefill(
    seed_labels: str | list[str] | None = None,
    max_turns: int = MAX_AUDITOR_TURNS,
    transcript_save_dir: str = "./runs/transcripts",
    judge_cost_cap: float | None = None,
):
    """Default Petri audit over non-prefill seeds (optionally a subset by label)."""
    dataset = [s for s in labelled_seeds() if not is_prefill(s)]
    if seed_labels:
        wanted = [seed_labels] if isinstance(seed_labels, str) else list(seed_labels)
        by_label = {s.id: s for s in dataset}
        missing = [label for label in wanted if label not in by_label]
        if missing:
            raise ValueError(f"Unknown or prefill-tagged seed labels: {missing}")
        dataset = [by_label[label] for label in wanted]

    return Task(
        dataset=dataset,
        solver=auditor_agent(
            max_turns=max_turns,
            prefill=False,
            auditor_system_message=AUDITOR_SYSTEM_PROMPT,
        ),
        scorer=capped_alignment_judge(judge_cost_cap),
        cleanup=save_transcripts(transcript_save_dir),
    )
