# Part A seed selection

The analysis covers **16 attempted seeds** from Petri's default suite. Every attempted seed was evaluated on both targets. Eleven yielded valid scores for both targets and enter the paired comparison; judge refusals and other incomplete outcomes are reported separately in `RESULTS.md`. Seed 22 was selected but not attempted because of the budget guard.

| Family | Attempted seeds | Selected, not attempted |
|---|---|---|
| Autonomy | 66, 80, idx161, 93, idx156, 70 | — |
| Misuse | idx140, idx175, idx142, 76, idx166, 27 | — |
| User wellbeing | 44, 9, 36, 62 | 22 |

The selection used two documented draws. The first drew one seed for each of the 12 most common tags from the non-prefill pool with `random.Random(20261018)`, without replacement. The 22 prefill-tagged seeds and six seeds used in setup checks (12, 49, 65, idx115, idx143, 68) were excluded. After 11 of those seeds had run, a second draw added five candidates using `random.Random(20261019)`. It favored autonomy and misuse because those families had fewer valid pairs. The second draw used non-prefill seeds not in the first draw or setup checks, assigned each candidate to exactly one of the three families by its tags, and did not screen for judge-refusal risk. `select_extension.py` records that rule.

Both targets used the same auditor and judge models, tool options, scoring rubric, and 30-turn limit. A shared seed is a common starting instruction, not an identical conversation: the auditor adapts separately to each target. The run manifests record the settings and outcomes for each attempted seed.
