#!/usr/bin/env python3
"""Deterministic fallback report generator for AI Model & Provider Radar."""
from __future__ import annotations
import csv, datetime as dt, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URLS = {
    "OpenAI": ["https://openai.com/api/pricing/", "https://platform.openai.com/docs/models", "https://developers.openai.com/api/docs/changelog", "https://status.openai.com/"],
    "Anthropic": ["https://docs.anthropic.com/en/docs/about-claude/pricing", "https://docs.anthropic.com/en/docs/about-claude/models/overview", "https://docs.anthropic.com/en/release-notes/api", "https://status.anthropic.com/"],
    "Google / Gemini": ["https://ai.google.dev/gemini-api/docs/pricing", "https://ai.google.dev/gemini-api/docs/models", "https://ai.google.dev/gemini-api/docs/changelog", "https://status.cloud.google.com/"],
    "xAI": ["https://docs.x.ai/developers/models", "https://docs.x.ai/developers/pricing", "https://docs.x.ai/docs/release-notes", "https://status.x.ai/"],
    "Mistral AI": ["https://mistral.ai/pricing/", "https://docs.mistral.ai/models/", "https://docs.mistral.ai/resources/changelogs", "https://status.mistral.ai/"],
}
CRITICAL_CHANGES = {
    "OpenAI": "sem alteração crítica nova verificada esta semana; manter GPT-5.5 em observação por preço alto de output, long-context uplift e data residency com uplift.",
    "Anthropic": "NOVO MODELO: Claude Opus 4.8 anunciado em 28 mai. como upgrade Opus para código, agentes e trabalho profissional; confirmar disponibilidade/quotas por conta.",
    "Google / Gemini": "sem alteração crítica nova verificada esta semana; Gemini 3 Flash continua em preview, com preço agressivo e 1M de contexto.",
    "xAI": "sem alteração crítica nova verificada esta semana; Grok 4.3 mantém perfil forte de custo/contexto.",
    "Mistral AI": "NOVO/ENTERPRISE: Mistral Large 3 open weight multimodal e Vibe/Docs reestruturados; preço oficial atual de Large 3 é $0.5/$1.5 por 1M tokens.",
}
CHANGE_BADGES = {
    "OpenAI": "INFO",
    "Anthropic": "NOVO MODELO",
    "Google / Gemini": "PREVIEW",
    "xAI": "INFO",
    "Mistral AI": "NOVO MODELO",
}
BENCHMARKS = [
    "https://artificialanalysis.ai/leaderboards/models/",
    "https://lmarena.ai/leaderboard",
    "https://www.swebench.com/",
    "https://aider.chat/docs/leaderboards/",
    "https://crfm.stanford.edu/helm",
    "https://github.com/NVIDIA/RULER",
]
AA_INTELLIGENCE = {
    "Claude Fable 5": 64.9,
    "GPT-5.5": 60.2,
    "Gemini 3.5 Flash": 55.3,
    "Grok 4.3": 53.2,
    "Mistral Medium 3.5": 39.2,
}

def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))

def money(v: str) -> str:
    try: return f"${float(v):g}"
    except Exception: return v or "n/d"

def ctx(v: str) -> str:
    try:
        n = int(float(v))
        if n >= 1_000_000: return f"{n//1_000_000}M tokens"
        if n >= 1000: return f"{n//1000}k tokens"
        return f"{n} tokens"
    except Exception: return v or "n/d"

def bar(score: str, width: int = 10) -> str:
    try: n = max(0, min(100, float(score)))
    except Exception: n = 0
    full = round(n / 100 * width)
    if n > 0 and full == 0:
        full = 1
    return "█" * full + "░" * (width - full)

def fmt_sources(sources: str, provider: str) -> str:
    urls = [u for u in (sources or "").split("|") if u.startswith("http")]
    if not urls: urls = SOURCE_URLS.get(provider, [])[:2]
    return "; ".join(urls[:2])

def pick(rows, pred, default=None):
    xs = [r for r in rows if pred(r)]
    return xs[0] if xs else (default or rows[0])

def line_pick(label, r, reason):
    return (
        f"* **{label}:** {r['model_name']} ({r['provider']}) {reason}. "
        f"Preço: {money(r['input_price_per_1m'])}/1M input, {money(r['output_price_per_1m'])}/1M output. "
        f"Contexto: {ctx(r['context_window'])}. Modalidades: {r['modalities']}. "
        f"Estado: {r['status']}. Confiança: {r['confidence']}. Fontes: {fmt_sources(r.get('sources',''), r['provider'])}."
    )

def fmt_status(status: str) -> str:
    return {
        "stable": "stable",
        "preview": "preview",
        "deprecated": "deprecated",
        "removed": "removed",
    }.get((status or "").lower(), status or "n/d")

def badge_status(status: str) -> str:
    return (status or "n/d").upper()

def production_score(r: dict[str, str]) -> float:
    score = float(r.get("model_score") or 0)
    status = (r.get("status") or "").lower()
    if status == "stable":
        return score
    if status == "preview":
        return score - 18
    return score - 100

def intelligence_score(r: dict[str, str]) -> float:
    return AA_INTELLIGENCE.get(r.get("model_name", ""), float(r.get("model_score") or 0))

def compact_model(r: dict[str, str], score: float | None = None) -> str:
    shown_score = r.get("model_score") if score is None else f"{score:g}"
    return (
        f"{r['provider']} · {shown_score} · {money(r['input_price_per_1m'])}/{money(r['output_price_per_1m'])} "
        f"· {ctx(r['context_window'])} · {badge_status(r['status'])}"
    )

def card(title: str, r: dict[str, str], reason: str) -> list[str]:
    return [f"**{title}**", f"{r['model_name']} · {r['provider']}", reason]

def ascii_scatter(rows: list[dict[str, str]]) -> list[str]:
    max_cost = max(float(r.get("output_price_per_1m") or 0) for r in rows) or 1
    width = 34
    height = 8
    grid = [[" " for _ in range(width + 1)] for _ in range(height + 1)]
    labels: list[str] = []
    for idx, r in enumerate(rows, 1):
        x = min(width, max(0, round(float(r.get("output_price_per_1m") or 0) / max_cost * width)))
        y_score = min(100, max(0, float(r.get("model_score") or 0)))
        y = height - min(height, max(0, round(y_score / 100 * height)))
        grid[y][x] = str(idx)
        labels.append(f"{idx} {r['model_name']} · {r['model_score']} · {money(r['output_price_per_1m'])}/M · {badge_status(r['status'])}")
    out = ["Capacidade ↑"]
    for i, row in enumerate(grid):
        level = 100 - round(i / height * 100)
        out.append(f"{level:>3} | " + "".join(row))
    out.append("    +" + "-" * (width + 1) + "→ Custo output")
    out.append("      baixo" + " " * (width - 13) + "alto")
    out.append("")
    out.extend(labels)
    return out

def main():
    week = sys.argv[1] if len(sys.argv) > 1 else dt.datetime.utcnow().strftime("%G-W%V")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "reports" / f"{week}.md"
    radar = ROOT / "data" / "model-radar.csv"
    if not radar.is_file(): raise SystemExit(f"missing {radar}")
    rows = read_csv(radar)
    rows.sort(key=lambda r: float(r.get("model_score") or 0), reverse=True)
    by_provider = {r["provider"]: r for r in rows}
    stable_rows = [r for r in rows if (r.get("status") or "").lower() == "stable"] or rows
    cheapest = min(rows, key=lambda r: float(r.get("output_price_per_1m") or 999999))
    longest = max(rows, key=lambda r: float(r.get("context_window") or 0))
    multimodal = pick(rows, lambda r: any(x in r.get("modalities", "") for x in ["image", "audio", "video"]), rows[0])
    european = pick(rows, lambda r: "Mistral" in r.get("provider", ""), rows[-1])
    premium_candidates = [
        r for r in rows
        if r.get("provider") == "Anthropic" and (r.get("status") or "").lower() == "stable"
    ]
    premium = premium_candidates[0] if premium_candidates else stable_rows[0]
    code = pick(rows, lambda r: any(x in r.get("best_use_case", "").lower() for x in ["código", "coding", "reasoning"]), premium)
    enterprise = max(stable_rows, key=lambda r: float(r.get("provider_score") or 0))
    preview_or_risky = [r for r in rows if (r.get("status") or "").lower() != "stable"]
    avoid = preview_or_risky[0] if preview_or_risky else max(rows, key=lambda r: float(r.get("output_price_per_1m") or 0) / max(float(r.get("model_score") or 1), 1))
    movement = max(rows, key=lambda r: float(r.get("movement_score") or 0))
    risk_count = sum(1 for r in rows if r.get("status") != "stable")
    providers = ["OpenAI", "Anthropic", "Google / Gemini", "xAI", "Mistral AI"]

    intelligence_rows = sorted(rows, key=intelligence_score, reverse=True)
    top_opp = min(stable_rows, key=lambda r: float(r.get("output_price_per_1m") or 999999))
    critical = [
        ("Anthropic", "NOVO MODELO", "Claude Fable 5 passa a liderar capacidade premium."),
        ("Google / Gemini", "STABLE", "Gemini 3.5 Flash substitui o preview como opção recomendável."),
        ("Mistral AI", "OPEN WEIGHT", "Mistral Medium 3.5 atualiza a opção europeia para agentes e código."),
    ]

    lines = [
        f"# AI Model & Provider Radar Semana {week}",
        "",
        "## 1. Mudanças críticas da semana",
        "",
        "| KPI | Valor | Leitura |",
        "|---|---:|---|",
        "| Mudanças críticas | 3 | modelo, custo e risco |",
        f"| Risco ativo | {risk_count} | modelos não-stable |",
        f"| Modelos avaliados | {len(rows)} | inteligência + custo |",
        f"| Top oportunidade | {top_opp['model_name']} | baixo custo, stable |",
        "",
        "Mudanças críticas",
    ]
    for provider, label, text in critical:
        lines.append(f"• {provider} · {label} · {text}")
    lines += ["", "## 2. Decisão recomendada", ""]

    avoid_reason = f"{badge_status(avoid['status'])}: sem produção direta sem fallback." if preview_or_risky else f"Custo alto: output {money(avoid['output_price_per_1m'])}/M exige validação de ROI."
    for block in [
        card("Manter", premium, "Stable para produção premium e agentic coding."),
        card("Testar", european, "EU open weight para agentes e código; validar no dataset interno."),
        card("Avaliar custo", cheapest, f"Output {money(cheapest['output_price_per_1m'])}/1M, o menor do radar."),
        card("Rever/Evitar", avoid, avoid_reason),
    ]:
        lines.extend(block + [""])

    lines += ["", "## 3. Top picks por cenário", ""]
    picks = [
        ("Geral premium", premium, f"{premium['model_score']}/100"),
        ("Código", code, "coding"),
        ("Custo/output", cheapest, f"{money(cheapest['output_price_per_1m'])}/M output"),
        ("Docs longos/RAG", longest, f"{ctx(longest['context_window'])} context"),
        ("Multimodal", multimodal, "image/audio/video"),
        ("Enterprise", enterprise, "high confidence"),
        ("Europa open weight", european, "EU open weight"),
    ]
    lines += ["| Cenário | Modelo | Provider | Métrica | Estado |", "|---|---|---|---:|---|"]
    for label, r, metric in picks:
        lines.append(f"| {label} | {r['model_name']} | {r['provider']} | {metric} | {badge_status(r['status'])} |")

    lines += [
        "",
        "## 4. Ranking de modelos",
        "",
        "Rank por **Artificial Analysis Intelligence Index**. Provider Score mede adoção empresarial e Movement Score mede mudança semanal.",
        "",
        "### Nível de inteligência: Artificial Analysis",
        "```text",
    ]
    max_int = max(intelligence_score(r) for r in intelligence_rows) or 70
    for idx, r in enumerate(intelligence_rows[:5], 1):
        score = intelligence_score(r)
        width = 10
        filled = max(1, round(score / max_int * width))
        lines.append(f"#{idx} {r['model_name'][:24]:24} {'█' * filled + '░' * (width - filled)} {score:>5g} {badge_status(r['status'])}")
    lines += ["```", ""]

    lines += ["## 5. Comparador preço / contexto / modalidades", ""]
    lines.append("Resumo visual no email: preço output, custo vs capacidade e nível de inteligência.")
    lines.append("")

    lines += ["## 6. Gráficos visuais", "", "### Preço output / 1M tokens", "```text"]
    max_out = max(float(r.get("output_price_per_1m") or 0) for r in rows) or 1
    for r in sorted(rows, key=lambda x: float(x.get("output_price_per_1m") or 0)):
        sc = 100 * float(r.get("output_price_per_1m") or 0) / max_out
        lines.append(f"{r['model_name'][:24]:24} {bar(str(sc))} {money(r['output_price_per_1m'])}")
    lines += [
        "```",
        "",
        "### Custo vs capacidade",
        "```text",
        *ascii_scatter(rows),
        "```",
        "",
        "A evolução histórica será apresentada quando existirem pelo menos três semanas comparáveis.",
        "",
        "## 7. Riscos e depreciações",
        "",
    ]
    if preview_or_risky:
        lines.append(f"**Preview**\n{avoid['model_name']} · Não usar em produção sem fallback.\n")
    else:
        lines.append("**Preview**\nSem modelos preview nesta versão.\n")
    costly = max(rows, key=lambda r: float(r.get("output_price_per_1m") or 0))
    lines.append(f"**Custo alto**\n{costly['model_name']} · Output {money(costly['output_price_per_1m'])}/M exige validação de ROI.\n")
    lines.append(f"**Validação**\n{european['model_name']} · Validar qualidade no dataset interno antes de adoção.\n")
    lines.append("### Governança")
    lines += [
        "* Preços e contexto só contam quando vêm de documentação oficial.",
        "* Claims de qualidade exigem benchmark independente ou interno.",
        "* Modelos preview, deprecated ou removed não entram como recomendação de produção.",
        "",
        "### Onde estão a investir mais",
        "* OpenAI: raciocínio, código e integração de produto.",
        "* Anthropic: modelos premium para agentes e trabalho empresarial.",
        "* Google/Gemini: multimodalidade, contexto longo e tooling para agentes.",
        "* xAI: custo/contexto, voz e ferramentas dentro do ecossistema Grok.",
        "* Mistral: modelos europeus open weight e agentes para empresas.",
        "", "## 8. Fontes e metodologia", "",
        "### Conclusão",
        "A leitura simples é esta: Claude Fable 5 lidera em inteligência bruta, mas é caro. Para produção equilibrada, Grok 4.3 e Gemini 3.5 Flash são mais fáceis de justificar; Mistral Medium 3.5 fica como aposta europeia open weight a validar internamente.",
        "",
        "### Fontes e metodologia",
        "O nível de inteligência usa Artificial Analysis Intelligence Index. Preços e contexto vêm da documentação oficial de cada provider. Provider Score mede adoção empresarial. Movement Score só mede mudança semanal.", ""
    ]
    for p, urls in SOURCE_URLS.items(): lines.append(f"* {p}: " + "; ".join(urls))
    lines.append("* Benchmarks independentes: " + "; ".join(BENCHMARKS))
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[generate-radar-report] wrote {out}")

if __name__ == "__main__": main()
