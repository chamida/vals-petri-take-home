"""Part B figure for the one-page report.

Recomputes the clean-problem appeal outcomes from the analyzed Petri runs (v3, v4,
v5 and the v5 format retry), writes partb_counts.csv, and draws figure_partb.svg:
one panel per model, one row per appeal type, a stacked bar of wrong grades split
into "wrong at the first reply" and "changed after a later push".

    .venv/bin/python report/make_figure.py          # needs runs/ (local); else reuses partb_counts.csv
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = ["part_b_petri_v3", "part_b_petri_v4", "part_b_petri_v5_paid", "part_b_petri_v5_format_retry"]
EXCLUDED_CASES = {"A3_probability_single"}  # rubric line admits two readings (see partB/README.md)
TACTICS = [("rubric_ambiguity", "Rubric interpretation"), ("false_math", "False math"),
           ("consistency", "Classmate consistency"), ("hardship_bargain", "Hardship"),
           ("repair", "Post-submission repair"), ("relayed_authority", "Claimed authority")]
MODELS = [("claude-haiku-4.5", "Claude Haiku 4.5"), ("gpt-5-mini", "GPT-5 mini")]

# Validated categorical slots 1-2 (dataviz reference palette, light mode; all checks pass).
FIRST, LATER = "#2a78d6", "#eb6834"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def counts_from_runs():
    import pandas as pd
    a = pd.concat([pd.read_csv(ROOT / "runs" / r / "analysis" / "audits.csv") for r in RUNS])
    a = a[(a["incomplete"].fillna("") == "") & ~a["case"].isin(EXCLUDED_CASES)]
    inv = a[a["kind"] == "invalid"]
    neutral = inv[inv["condition"] == "neutral"]
    clean = {t: set(g[g["outcome"] == "held"]["case"]) for t, g in neutral.groupby("target")}
    rows = []
    for target, _ in MODELS:
        app = inv[(inv["target"] == target) & (inv["condition"] != "neutral") & inv["case"].isin(clean[target])]
        for tactic, _ in TACTICS:
            t = app[app["condition"] == tactic]
            rows.append({"target": target, "tactic": tactic, "clean_problems": len(clean[target]), "appeals": len(t),
                         "first_reply": int((t["outcome"] == "first_reply").sum()),
                         "later": int((t["outcome"] == "yielded").sum())})
    return rows


def main():
    path = HERE / "partb_counts.csv"
    if (ROOT / "runs" / RUNS[0]).exists():
        rows = counts_from_runs()
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    rows = [dict(r, first_reply=int(r["first_reply"]), later=int(r["later"]), clean_problems=int(r["clean_problems"]))
            for r in csv.DictReader(path.open())]
    data = {(r["target"], r["tactic"]): r for r in rows}

    W, label_w, unit, row_h, bar_h, top = 700, 128, 40, 14.5, 8.5, 35
    panel_w = (W - 20) / 2
    H = top + row_h * len(TACTICS) + 26
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           'font-family="-apple-system, Helvetica Neue, Helvetica, Arial, sans-serif" role="img" '
           'aria-label="Wrong grades by appeal type and model on problems each model graded correctly without an appeal">']
    # Legend
    lx = 0
    for color, text in ((FIRST, "Wrong in the first reply to the appeal"), (LATER, "Correct at first, wrong after a later push")):
        out.append(f'<rect x="{lx}" y="2" width="10" height="10" rx="2" fill="{color}"/>')
        out.append(f'<text x="{lx + 15}" y="11" font-size="11" fill="{INK2}">{text}</text>')
        lx += 15 + len(text) * 5.9 + 22
    for p, (target, name) in enumerate(MODELS):
        x0 = p * (panel_w + 20)
        n = data[(target, TACTICS[0][0])]["clean_problems"]
        total_first = sum(data[(target, t)]["first_reply"] for t, _ in TACTICS)
        total_later = sum(data[(target, t)]["later"] for t, _ in TACTICS)
        out.append(f'<text x="{x0}" y="{top - 8}" font-size="11.5" font-weight="600" fill="{INK}">{name}</text>')
        out.append(f'<text x="{x0 + panel_w}" y="{top - 8}" font-size="10.5" fill="{INK2}" text-anchor="end">'
                   f'{n * len(TACTICS)} appeals on {n} problems: {total_first} wrong at first, {total_later} later</text>')
        bx = x0 + label_w
        for k in range(0, 5):  # recessive grid at whole counts
            gx = bx + k * unit
            out.append(f'<line x1="{gx}" y1="{top}" x2="{gx}" y2="{top + row_h * len(TACTICS)}" stroke="{GRID}" stroke-width="1"/>')
            out.append(f'<text x="{gx}" y="{top + row_h * len(TACTICS) + 13}" font-size="9.5" fill="{INK2}" text-anchor="middle">{k}</text>')
        for i, (tactic, label) in enumerate(TACTICS):
            y = top + i * row_h + (row_h - bar_h) / 2
            d = data[(target, tactic)]
            out.append(f'<text x="{bx - 8}" y="{y + bar_h - 1}" font-size="10.5" fill="{INK}" text-anchor="end">{label}</text>')
            x = bx
            for value, color in ((d["first_reply"], FIRST), (d["later"], LATER)):
                if value:
                    w = value * unit - 2  # 2px surface gap between segments
                    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{bar_h}" rx="2" fill="{color}"/>')
                    x += value * unit
            total = d["first_reply"] + d["later"]
            out.append(f'<text x="{x + (4 if total else 2)}" y="{y + bar_h - 1}" font-size="10" '
                       f'fill="{INK if total else INK2}">{total}</text>')
    out.append("</svg>")
    (HERE / "figure_partb.svg").write_text("\n".join(out))
    print("wrote", HERE / "figure_partb.svg", "and", path)


if __name__ == "__main__":
    main()
