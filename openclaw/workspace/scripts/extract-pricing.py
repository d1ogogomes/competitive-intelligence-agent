#!/usr/bin/env python3
"""extract-pricing.py

Best-effort extraction of per-model API prices ($/1M tokens) from each lab's
latest pricing snapshot, into data/pricing.csv. Feeds the email's cross-lab
price comparison (chart + table).

Heuristic: walk the pricing snapshot lines; the "current model" is the most
recent line that looks like a model name; an Input/Output label with a nearby
price is attributed to that model. "Cached" prices are ignored.

CSV: week,lab,model,input_per_1m,output_per_1m,flagship
  flagship = "1" for the model with the highest output price per lab (used for the bar chart).

Usage:
  ./extract-pricing.py [week-id] [snapshots_dir]
"""
import csv
import datetime as dt
import re
import sys
from pathlib import Path

LAB_NAMES = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google / Gemini",
    "xai": "xAI", "mistral": "Mistral AI",
}
MODEL_RE = re.compile(
    r"\b(?:GPT-[\w.]+|o[1-9](?:-\w+)?|Claude\s(?:Opus|Sonnet|Haiku)\s?[\w.]*|"
    r"Gemini[\s-][\w.]+(?:\s(?:Pro|Flash|Ultra))?|Grok[\s-]?[\w.]+|"
    r"Mistral\s(?:Large|Medium|Small|Nemo)\s?[\w.]*|Codestral[\w.]*|Pixtral[\w.]*)\b"
)
PRICE_RE = re.compile(r"[$€£]\s?(\d[\d,]*(?:\.\d+)?)")
# Only treat a price as API token pricing if it carries a per-token unit — this
# filters out consumer $/month plans (e.g. Anthropic/Mistral consumer pages).
TOKEN_UNIT_RE = re.compile(r"(1\s*M|/\s*M\b|per\s*million|million\s*tokens|MTok|/1M|1M\s*tokens)", re.I)


def iso_week(d=None):
    d = d or dt.date.today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def latest_snapshot(d):
    snaps = sorted(d.glob("*.md"))
    return snaps[-1] if snaps else None


def content_lines(path):
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out, sep = [], False
    for ln in raw:
        if not sep:
            if ln.strip() == "---":
                sep = True
            continue
        if ln.strip():
            out.append(ln.strip())
    return out


def price_near(lines, i, require_unit=False):
    """First price on line i or the next line. When require_unit, the price line
    must carry a per-token unit (filters out consumer $/month plans)."""
    for j in (i, i + 1):
        if j < len(lines):
            m = PRICE_RE.search(lines[j])
            if m and (not require_unit or TOKEN_UNIT_RE.search(lines[j])):
                return float(m.group(1).replace(",", ""))
    return None


def extract_lab(lines):
    models = {}
    cur = None
    for i, ln in enumerate(lines):
        mm = MODEL_RE.search(ln)
        if mm and len(ln) < 80:
            cur = mm.group(0).strip()
            models.setdefault(cur, {"input": None, "output": None})
            continue
        low = ln.lower()
        if "cached" in low:
            continue
        # A price block (Input/Output) without a matched model name still counts —
        # attribute it to a generic "(API)" entry (e.g. xAI lists prices per tier).
        if cur is None and re.search(r"\b(input|output)\b", low) and price_near(lines, i, require_unit=True) is not None:
            cur = "(API)"
            models.setdefault(cur, {"input": None, "output": None})
        if cur is None:
            continue
        require_unit = (cur == "(API)")
        if re.search(r"\binput\b", low):
            p = price_near(lines, i, require_unit)
            if p is not None and models[cur]["input"] is None:
                models[cur]["input"] = p
        elif re.search(r"\boutput\b", low):
            p = price_near(lines, i, require_unit)
            if p is not None and models[cur]["output"] is None:
                models[cur]["output"] = p
    # Inline "$5 / input MTok" ... "$25 / output MTok" pairs. Anthropic lists prices
    # in a flattened table on its models page; this inline format pairs input↔output
    # unambiguously by position, so prefer it over name-association when present.
    text = " ".join(lines)
    ins = [float(x) for x in re.findall(r"\$\s?(\d[\d.]*)\s*/?\s*input\s*MTok", text, re.I)]
    outs = [float(x) for x in re.findall(r"\$\s?(\d[\d.]*)\s*/?\s*output\s*MTok", text, re.I)]
    if ins:
        return {("Flagship" if i == 0 else f"Tier {i + 1}"):
                {"input": inp, "output": outs[i] if i < len(outs) else None}
                for i, inp in enumerate(ins)}
    # keep models with at least an input price
    return {k: v for k, v in models.items() if v["input"] is not None}


def main():
    week = sys.argv[1] if len(sys.argv) >= 2 and re.match(r"\d{4}-W\d", sys.argv[1]) else iso_week()
    snaps_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path(__file__).resolve().parent.parent / "data" / "snapshots"
    data_dir = snaps_dir.parent

    # 1. Scrape each lab's flagship price (best-effort, for change DETECTION).
    scraped = {}
    for dir_name, display in LAB_NAMES.items():
        # Read pricing AND models snapshots: some labs (Anthropic) list API token
        # prices on the models page, not the (consumer) pricing page.
        lines = []
        for src in ("pricing", "models"):
            sdir = snaps_dir / dir_name / src
            snap = latest_snapshot(sdir) if sdir.is_dir() else None
            if snap:
                lines += content_lines(snap)
        models = extract_lab(lines) if lines else {}
        if not models:
            continue
        fl = max(models, key=lambda k: (models[k]["output"] or 0, models[k]["input"] or 0))
        scraped[display] = {"input": models[fl]["input"], "output": models[fl]["output"]}

    # 2. The human-verified seed is the source of TRUTH for display.
    seed_path = Path(__file__).resolve().parent / "pricing-seed.csv"
    seed = {}
    if seed_path.is_file():
        with seed_path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                seed[r["lab"]] = r

    # 3. Reconcile: emit seed values (trustworthy) + a drift flag when the live
    #    scrape disagrees beyond a small tolerance (= "preço pode ter mudado").
    def near(a, b):
        try:
            a, b = float(a), float(b)
        except (TypeError, ValueError):
            return True
        return abs(a - b) <= max(0.01, 0.02 * max(a, b))

    rows = []
    for lab, s in seed.items():
        sc = scraped.get(lab, {})
        drift = ""
        if sc.get("input") is not None and not near(s["input_per_1m"], sc["input"]):
            drift = f"scrape input ${sc['input']}"
        if sc.get("output") is not None and s.get("output_per_1m") and not near(s["output_per_1m"], sc["output"]):
            drift = (drift + "; " if drift else "") + f"scrape output ${sc['output']}"
        rows.append({
            "week": week, "lab": lab, "model": s["model"],
            "input_per_1m": s["input_per_1m"], "output_per_1m": s.get("output_per_1m", ""),
            "flagship": "1", "drift": drift, "source": s.get("source_url", ""),
        })

    out = data_dir / "pricing.csv"
    fields = ["week", "lab", "model", "input_per_1m", "output_per_1m", "flagship", "drift", "source"]
    keep = []
    if out.is_file():
        with out.open(newline="", encoding="utf-8") as fh:
            keep = [r for r in csv.DictReader(fh) if r.get("week") != week]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(keep + rows)

    print(f"[pricing] {week}: {len(rows)} labs (seed verificada) -> {out.name}")
    for r in rows:
        d = f"  ⚠ DRIFT: {r['drift']}" if r["drift"] else ""
        print(f"  {r['lab']:<16} {r['model']:<20} in ${r['input_per_1m']} / out ${r['output_per_1m']}{d}")


if __name__ == "__main__":
    main()
