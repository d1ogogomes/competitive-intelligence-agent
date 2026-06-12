#!/usr/bin/env python3
"""Build transparent model/provider/movement scores for the executive radar."""
import csv
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ["OpenAI", "Anthropic", "Google / Gemini", "xAI", "Mistral AI"]


def rows(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def provider_scores(path):
    out = {}
    for r in rows(path):
        values = [num(r[k]) for k in (
            "privacy_score", "data_residency_score", "documentation_score",
            "status_sla_score", "enterprise_support_score", "api_stability_score"
        )]
        out[r["provider"]] = round(sum(values) / len(values), 1)
    return out


def movement_scores(report_path):
    scores = {lab: 0 for lab in LABS}
    if not report_path.is_file():
        return scores
    current = None
    in_changes = False
    for raw in report_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("• "):
            for lab in LABS:
                if line.startswith(f"• {lab}:"):
                    low = line.lower()
                    if "sem alteração crítica" in low:
                        break
                    weight = 8
                    if any(k in low for k in ("novo modelo", "lançad", "released", "deprecia", "removed")):
                        weight = 20
                    if any(k in low for k in ("preço", "pricing", "$", "api", "contexto", "multimodal", "enterprise")):
                        weight = max(weight, 12)
                    scores[lab] = min(100, scores[lab] + weight)
                    break
            continue
        if line.startswith("## "):
            current = line[3:] if line[3:] in LABS else None
            in_changes = False
        elif line.lower() == "### o que mudou":
            in_changes = True
        elif line.startswith("### "):
            in_changes = False
        elif current and in_changes and line.startswith("- ") and "sem alteraç" not in line.lower():
            weight = 8
            low = line.lower()
            if any(k in low for k in ("novo modelo", "lançad", "disponível", "deprecia", "removed")):
                weight = 15
            elif any(k in low for k in ("preço", "pricing", "api", "contexto", "multimodal")):
                weight = 10
            scores[current] = min(100, scores[current] + weight)
    return scores


def main():
    week = sys.argv[1] if len(sys.argv) > 1 else ""
    report = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "reports" / f"{week}.md"
    model_seed = ROOT / "scripts" / "model-seed.csv"
    provider_seed = ROOT / "scripts" / "provider-seed.csv"
    out = ROOT / "data" / "model-radar.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    provider = provider_scores(provider_seed)
    movement = movement_scores(report)
    models = rows(model_seed)
    max_cost = max(num(r["input_price_per_1m"]) + num(r["output_price_per_1m"]) for r in models)
    max_context = max(num(r["context_window"]) for r in models)
    result = []
    for r in models:
        cost = num(r["input_price_per_1m"]) + num(r["output_price_per_1m"])
        cost_score = 100 * (1 - (cost / max_cost) * 0.85)
        context_score = 100 * math.log1p(num(r["context_window"])) / math.log1p(max_context)
        modality_count = len([x for x in re.split(r"[|>-]+", r["modalities"]) if x and x != "text"])
        modality_score = min(100, 55 + modality_count * 15)
        stable = 100 if r["status"] == "stable" else (55 if r["status"] == "preview" else 10)
        model_score = round(
            num(r["quality_score"]) * .30 + cost_score * .20 + context_score * .15 +
            modality_score * .10 + num(r["tool_use_score"]) * .10 +
            stable * .075 + num(r["maturity_score"]) * .075, 1
        )
        result.append({
            "week": week, **r, "model_score": model_score,
            "provider_score": provider.get(r["provider"], num(r["provider_score"])),
            "movement_score": movement.get(r["provider"], 0),
        })
    result.sort(key=lambda r: -float(r["model_score"]))
    fields = ["week", "rank", "model_name", "model_slug", "provider", "model_score", "provider_score",
              "movement_score", "input_price_per_1m", "output_price_per_1m", "context_window",
              "modalities", "status", "best_use_case", "confidence", "sources"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rank, r in enumerate(result, 1):
            writer.writerow({k: (rank if k == "rank" else r.get(k, "")) for k in fields})
    print(f"[model-radar] {week}: {len(result)} models -> {out}")
    for rank, r in enumerate(result, 1):
        print(f"  #{rank} {r['model_name']:<20} model={r['model_score']:>4} provider={r['provider_score']:>4} movement={r['movement_score']:>3}")


if __name__ == "__main__":
    main()
