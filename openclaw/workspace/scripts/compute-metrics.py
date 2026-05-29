#!/usr/bin/env python3
"""compute-metrics.py

Deterministic, defensible metrics for the weekly briefing — the opposite of an
LLM "vibe" score. For each lab it compares the two most recent snapshots per
source and measures REAL facts:

  price_changes      $/€ price tokens added or removed in the pricing page
  new_models         model-name tokens that appear in the models page this week
  changelog_updates  new content lines in the API changelog/release notes
  blog_updates       new content lines in the blog/news page (≈ posts/updates)
  job_delta          change in the number of lines on the careers page

The activity score is a TRANSPARENT function of those facts (weights are a
stated editorial choice, shown to the reader):

  score = min(10, round(3*new_models + 2*price_changes + 1*changelog_updates + 1*blog_updates + 0.5*job_delta))

Outputs:
  data/metrics.csv   week,lab,new_models,price_changes,changelog_updates,blog_updates,job_delta,score,breakdown,details
  data/ranks.csv     week,lab,score,rank,destaque   (destaque = breakdown; idempotent per week)

Usage:
  ./compute-metrics.py [week-id] [snapshots_dir]
  (week-id defaults to current ISO week; snapshots_dir defaults to ../data/snapshots)
"""
import csv
import datetime as dt
import re
import sys
from pathlib import Path

# Snapshot dir name -> display name (must match LABS keys in render-briefing-html.py)
LAB_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google / Gemini",
    "xai": "xAI",
    "mistral": "Mistral AI",
}

# Transparent weights (stated editorial choice).
WEIGHTS = {"new_models": 3, "price_changes": 2, "changelog_updates": 1, "blog_updates": 1, "job_delta": 0.5}
CAP = {"blog_updates": 6, "changelog_updates": 6, "job_delta": 8, "price_changes": 8, "new_models": 6}

PRICE_RE = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?")
# Conservative model-name detector across the main families.
MODEL_RE = re.compile(
    r"\b(?:GPT-[\w.]+|o[1-9](?:-\w+)?|Claude\s(?:Opus|Sonnet|Haiku)\s?[\w.]*|"
    r"Gemini\s[\w.]+(?:\sPro|\sFlash)?|Grok-?[\w.]+|"
    r"Mistral\s(?:Large|Medium|Small|Nemo)\s?[\w.]*|Codestral[\w.\s]*|Pixtral[\w.\s]*)\b"
)


def iso_week(date=None):
    d = date or dt.date.today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def snapshot_lines(path):
    """Content lines of a snapshot, with the header (up to the first '---') removed."""
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out, seen_sep = [], False
    for ln in raw:
        if not seen_sep:
            if ln.strip() == "---":
                seen_sep = True
            continue
        s = ln.strip()
        if s:
            out.append(s)
    return out


def two_latest(source_dir):
    snaps = sorted(source_dir.glob("*.md"))
    if len(snaps) < 2:
        return (None, snaps[-1]) if snaps else (None, None)
    return snaps[-2], snaps[-1]


def added_removed(prev_lines, curr_lines):
    p, c = set(prev_lines), set(curr_lines)
    return [l for l in curr_lines if l not in p], [l for l in prev_lines if l not in c]


def lab_metrics(lab_dir):
    """Return (metrics dict, details list of strings) for one lab."""
    m = {"new_models": 0, "price_changes": 0, "changelog_updates": 0, "blog_updates": 0, "job_delta": 0}
    details = []

    def src(name):
        """Returns (prev_lines, curr_lines) only when a PREVIOUS snapshot exists.
        Baseline (single snapshot) yields (None, None) so it counts as 0 change."""
        d = lab_dir / name
        if not d.is_dir():
            return None, None
        prev, curr = two_latest(d)
        if curr is None or prev is None:  # no baseline to compare against
            return None, None
        return snapshot_lines(prev), snapshot_lines(curr)

    # pricing: changed price tokens
    pl, cl = src("pricing")
    if cl is not None:
        prev_prices = PRICE_RE.findall(" ".join(pl)) if pl else []
        curr_prices = PRICE_RE.findall(" ".join(cl))
        added = [x for x in curr_prices if x not in set(prev_prices)]
        removed = [x for x in prev_prices if x not in set(curr_prices)]
        m["price_changes"] = len(set(added) | set(removed))
        if added:
            details.append("preços novos: " + ", ".join(sorted(set(added))[:4]))
        if removed:
            details.append("preços removidos: " + ", ".join(sorted(set(removed))[:4]))

    # models: new model-name tokens
    pl, cl = src("models")
    if cl is not None:
        prev_models = set(MODEL_RE.findall(" ".join(pl))) if pl else set()
        curr_models = set(MODEL_RE.findall(" ".join(cl)))
        new = [x for x in curr_models if x not in prev_models]
        m["new_models"] = len(new)
        if new:
            details.append("modelos novos: " + ", ".join(sorted(new)[:5]))

    # changelog: new content lines (proxy for API updates/releases)
    pl, cl = src("changelog")
    if cl is not None:
        add, _ = added_removed(pl, cl)
        meaningful = [l for l in add if len(l) > 20]
        m["changelog_updates"] = len(meaningful)
        if meaningful:
            details.append(f"{len(meaningful)} atualização(ões) de API")

    # blog: new content lines (proxy for posts/updates)
    pl, cl = src("blog")
    if cl is not None:
        add, _ = added_removed(pl, cl)
        meaningful = [l for l in add if len(l) > 25]
        m["blog_updates"] = len(meaningful)
        if meaningful:
            details.append(f"{len(meaningful)} novidade(s) no blog")

    # jobs: delta in number of listing-ish lines
    pl, cl = src("jobs")
    if cl is not None:
        m["job_delta"] = abs(len(cl) - len(pl)) if pl else 0

    return m, details


def score_of(m):
    capped = {k: min(v, CAP[k]) for k, v in m.items()}
    raw = sum(WEIGHTS[k] * capped[k] for k in WEIGHTS)
    return max(0, min(10, round(raw)))


def breakdown_of(m):
    parts = []
    if m["new_models"]:
        parts.append(f'{m["new_models"]} modelo(s) novo(s)')
    if m["price_changes"]:
        parts.append(f'{m["price_changes"]} preço(s) alterado(s)')
    if m["changelog_updates"]:
        parts.append(f'{m["changelog_updates"]} atualização(ões) de API')
    if m["blog_updates"]:
        parts.append(f'{m["blog_updates"]} novidade(s) no blog')
    if m["job_delta"]:
        parts.append(f'Δ{m["job_delta"]} vagas')
    return " · ".join(parts) if parts else "sem mudanças mensuráveis"


def main():
    week = sys.argv[1] if len(sys.argv) >= 2 and re.match(r"\d{4}-W\d", sys.argv[1]) else iso_week()
    snaps_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path(__file__).resolve().parent.parent / "data" / "snapshots"
    data_dir = snaps_dir.parent

    results = []
    for dir_name, display in LAB_NAMES.items():
        lab_dir = snaps_dir / dir_name
        if not lab_dir.is_dir():
            continue
        m, details = lab_metrics(lab_dir)
        results.append({
            "lab": display, "metrics": m, "score": score_of(m),
            "breakdown": breakdown_of(m), "details": " | ".join(details),
        })

    if not results:
        sys.exit(f"[metrics] no lab snapshots under {snaps_dir}")

    # ranks by score desc
    results.sort(key=lambda r: -r["score"])

    # write metrics.csv (replace this week's rows)
    metrics_csv = data_dir / "metrics.csv"
    fields = ["week", "lab", "new_models", "price_changes", "changelog_updates", "blog_updates", "job_delta", "score", "breakdown", "details"]
    keep = []
    if metrics_csv.is_file():
        with metrics_csv.open(newline="", encoding="utf-8") as fh:
            keep = [r for r in csv.DictReader(fh) if r.get("week") != week]
    rows = keep + [{
        "week": week, "lab": r["lab"], **r["metrics"],
        "score": r["score"], "breakdown": r["breakdown"], "details": r["details"],
    } for r in results]
    rows.sort(key=lambda r: (r["week"], -int(r["score"])))
    with metrics_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)

    # write/refresh ranks.csv (score-driven, destaque = breakdown)
    ranks_csv = data_dir / "ranks.csv"
    rk_fields = ["week", "lab", "score", "rank", "destaque"]
    keep = []
    if ranks_csv.is_file():
        with ranks_csv.open(newline="", encoding="utf-8") as fh:
            keep = [r for r in csv.DictReader(fh) if r.get("week") != week]
    new_rk = [{"week": week, "lab": r["lab"], "score": r["score"], "rank": i,
               "destaque": r["breakdown"]} for i, r in enumerate(results, 1)]
    allr = keep + new_rk
    allr.sort(key=lambda r: (r["week"], int(r["rank"])))
    with ranks_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rk_fields); w.writeheader(); w.writerows(allr)

    print(f"[metrics] {week}: {len(results)} labs -> {metrics_csv.name}, {ranks_csv.name}")
    for i, r in enumerate(results, 1):
        print(f"  #{i} {r['lab']:<16} score {r['score']:>2}  ({r['breakdown']})")


if __name__ == "__main__":
    main()
