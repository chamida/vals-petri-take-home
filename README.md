# Vals AI take-home

Start with the [one-page report](report.pdf). This repository contains the supporting code, case definitions, and detailed results. Part A compares GPT-5 mini and Claude Haiku 4.5 on a budgeted subset of Petri's default safety instructions. Part B tests whether a model reviewing grade appeals restores earned credit while resisting requests for unearned points.

Supporting material: [Part A](partA/README.md), [Part B](partB/README.md), and [selected conversations](evidence/README.md). The report is built from [report/](report/report.html) with `bash report/build.sh` (headless Chrome); `report/make_figure.py` recomputes the Part B figure from the analyzed runs and keeps the counts in `report/partb_counts.csv`.

## Setup

From the repository root (Python 3.12 and uv):

```bash
git clone -b petri-v2 https://github.com/meridianlabs-ai/inspect_petri refs/inspect_petri
git -C refs/inspect_petri checkout f02b3ec70a6b9c2a1a7da172b2f3f69a1e1b0585
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env   # then set OPENAI_API_KEY and ANTHROPIC_API_KEY
```

Node 20 may be needed for Petri's transcript viewer.

API keys belong in `.env`; generated logs and transcripts belong in `runs/`. Both are ignored by Git. Re-running the paid evaluations requires API keys and incurs charges.
