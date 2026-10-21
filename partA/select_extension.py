"""Draw the Part A extension seeds (recorded in SEEDS.md before any of them ran).

    ../.venv/bin/python partA/select_extension.py

Pool: non-prefill seeds, minus the six setup seeds and the 12 frozen seeds.
A seed belongs to a family if it has one of that family's tags and none of the
other families' tags. Draw 2 autonomy, 2 misuse and 1 user-wellbeing seed with
random.Random(20261019); the frozen seed 62 (never run) goes first.
"""

import random

import config
from task import is_prefill, labelled_seeds

SETUP_SEEDS = {"12", "49", "65", "idx115", "idx143", "68"}
FAMILY_TAGS = {
    "autonomy": {"initiative", "multi_agent", "oversight_subversion", "self_preservation"},
    "misuse": {"deception", "cooperation_with_misuse", "jailbreak", "privacy_violation"},
    "user wellbeing": {"bias", "sycophancy", "censorship", "delusional_user"},
}
DRAWS = {"autonomy": 2, "misuse": 2, "user wellbeing": 1}
RNG_SEED = 20261019


def family_of(sample):
    tags = set(sample.metadata.get("tags", []))
    hits = [f for f, family_tags in FAMILY_TAGS.items() if tags & family_tags]
    return hits[0] if len(hits) == 1 else None


def select():
    pool = [s for s in labelled_seeds()
            if not is_prefill(s) and s.id not in SETUP_SEEDS and s.id not in config.SEEDS]
    rng = random.Random(RNG_SEED)
    drawn = {}
    for family, n in DRAWS.items():
        candidates = [s.id for s in pool if family_of(s) == family]
        drawn[family] = rng.sample(candidates, n)
        print(f"{family}: {len(candidates)} candidates -> {drawn[family]}")
    order = ["62", drawn["autonomy"][0], drawn["misuse"][0],
             drawn["autonomy"][1], drawn["misuse"][1], drawn["user wellbeing"][0]]
    return order, drawn


if __name__ == "__main__":
    order, _ = select()
    tags = {s.id: s.metadata.get("tags", []) for s in labelled_seeds()}
    for seed in order:
        print(seed, tags[seed])
