#!/usr/bin/env python3
"""QA guardrail for AI Model & Provider Radar reports."""
import csv
import re
import sys
from pathlib import Path

REQUIRED = [
    "## 1. Mudanças críticas da semana",
    "## 2. Decisão recomendada",
    "## 3. Top picks por cenário",
    "## 4. Ranking de modelos",
    "## 5. Comparador preço / contexto / modalidades",
    "## 6. Gráficos visuais",
    "## 7. Riscos e depreciações",
    "## 8. Fontes e metodologia",
]
BAD = ["[modelo/provider]", "[mudança relevante]", "[TODO]", "como modelo de linguagem", "não tenho acesso em tempo real"]


def fail(msg):
    print(f"[qa] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        fail("usage: qa-check.py <report.md> [model-radar.csv]")
    path = Path(sys.argv[1])
    if not path.is_file():
        fail(f"report missing: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        fail("report is empty")
    if "# AI Model & Provider Radar" not in text:
        fail("missing AI Model & Provider Radar title")

    positions = []
    for h in REQUIRED:
        idx = text.find(h)
        if idx < 0:
            fail(f"missing required heading: {h}")
        positions.append(idx)
    if positions != sorted(positions):
        fail("required headings are not in the mandated order")

    low = text.lower()
    for bad in BAD:
        if bad.lower() in low:
            fail(f"placeholder/LLM fallback detected: {bad}")

    if "artificial analysis intelligence index" not in low or "provider score" not in low or "movement score" not in low:
        fail("report must explicitly separate intelligence index, Provider Score and Movement Score")

    ranking = text[text.find("## 4. Ranking de modelos"):text.find("## 5. Comparador preço / contexto / modalidades")]
    if not re.search(r"\b(rank|#)\b", ranking, re.I) or "artificial analysis intelligence index" not in ranking.lower():
        fail("ranking section does not expose rank and Artificial Analysis Intelligence Index")

    # Guard against local paths masquerading as public sources.
    sources_section = text[text.find("## 8. Fontes e metodologia"):]
    if re.search(r"\b(data|reports|scripts|/root|/home)/", sources_section):
        fail("sources section contains local file paths; use public URLs and describe local data only as methodology")
    if not re.search(r"https?://", sources_section):
        fail("sources section has no public URLs")

    if len(sys.argv) >= 3 and Path(sys.argv[2]).is_file():
        rows = list(csv.DictReader(open(sys.argv[2], newline="", encoding="utf-8")))
        if rows and not {"rank", "model_name", "model_score", "provider_score", "movement_score"}.issubset(rows[0].keys()):
            fail("model-radar.csv missing required score columns")

    print("[qa] PASS: AI Model & Provider Radar report structure and traceability checks passed")


if __name__ == "__main__":
    main()
