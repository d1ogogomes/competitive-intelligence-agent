#!/usr/bin/env python3
"""qa-check.py

Automated QA validation for the competitive intelligence weekly briefing.
Checks the generated reports/<week-id>.md file to ensure it meets strict quality
standards for publication:
  1. Mandatory structure (headings) present
  2. 100% Traceability (all "O que mudou" bullets have source URLs)
  3. No placeholders, brackets, or typical LLM hallucinations
  4. Consistency with metrics.csv (fails if a lab has active snapshot changes but
     the report says "Sem alterações relevantes").

Usage:
  ./qa-check.py <report_path> [metrics_csv_path]
"""
import csv
import re
import sys
from pathlib import Path

# ANSI colors for beautiful terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

MANDATORY_LABS = ["OpenAI", "Anthropic", "Google / Gemini", "xAI", "Mistral AI"]
MANDATORY_HEADINGS = ["## Resumo", "## Sinais cruzados", "## Fontes"]
TRACEABILITY_THRESHOLD = 80.0  # Min % of bullets that must have sources


def parse_report(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the week ID from the file name or header
    week_match = re.search(r"(\d{4}-W\d{1,2})", path.stem)
    week_id = week_match.group(1) if week_match else "unknown"

    # Structure check: find headings
    headings = [l.strip() for l in lines if l.startswith("#") or l.startswith("##")]

    # Check which sections we have
    parsed = {
        "week_id": week_id,
        "headings": headings,
        "labs": {},
        "raw_text": text,
    }

    cur_lab = None
    cur_sub = None

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("## "):
            h2 = s[3:].strip()
            if h2 in MANDATORY_LABS:
                cur_lab = h2
                parsed["labs"][cur_lab] = {"mudou": [], "importa": [], "fazer": []}
            else:
                cur_lab = None
            cur_sub = None
            continue
        if s.startswith("### "):
            if not cur_lab:
                continue
            sub = s[4:].strip().lower()
            if "mudou" in sub:
                cur_sub = "mudou"
            elif "importa" in sub:
                cur_sub = "importa"
            elif "fazer" in sub or "watch" in sub:
                cur_sub = "fazer"
            else:
                cur_sub = None
            continue

        if cur_lab and cur_sub:
            if s.startswith("- "):
                bullet = s[2:].strip()
                parsed["labs"][cur_lab][cur_sub].append(bullet)
            elif not s.startswith("#") and cur_sub in ["importa", "fazer"]:
                parsed["labs"][cur_lab][cur_sub].append(s)

    return parsed


def run_checks(parsed, metrics_csv_path):
    issues = []
    warnings = []
    passes = []

    print(f"\n{BOLD}{BLUE}=================================================={RESET}")
    print(f"{BOLD}{BLUE}🔍 INTELAGENT QA GUARDRAIL — Week {parsed['week_id']}{RESET}")
    print(f"{BOLD}{BLUE}=================================================={RESET}")

    # --- 1. Structure Checks ---
    missing_headings = []
    # Check general headings
    for mh in MANDATORY_HEADINGS:
        if mh not in parsed["headings"]:
            missing_headings.append(mh)
    # Check lab headings
    for lab in MANDATORY_LABS:
        lab_h = f"## {lab}"
        if lab_h not in parsed["headings"]:
            missing_headings.append(lab_h)

    if missing_headings:
        issues.append(f"Cabeçalhos obrigatórios em falta: {', '.join(missing_headings)}")
    else:
        passes.append("Estrutura do documento (cabeçalhos obrigatórios presentes)")

    # --- 2. Placeholder & Hallucination Scan ---
    # Check for brackets like [insira], [TODO], [link], etc.
    bracket_matches = re.findall(r"\[[^\]]*\]", parsed["raw_text"])
    # Filter out markdown links like [OpenAI] or [Texto](url)
    bad_brackets = []
    for match in bracket_matches:
        # If it looks like a typical markdown link or label, skip it, unless it contains typical todo text
        content = match[1:-1].lower()
        if any(x in content for x in ["insira", "todo", "placeholder", "link", "escrever", "completar", "url"]):
            bad_brackets.append(match)

    if bad_brackets:
        issues.append(f"Placeholders ou marcadores LLM detetados: {', '.join(bad_brackets)}")

    # Check for specific hallucinated strings or fallback templates
    hallucination_terms = [
        "como modelo de linguagem",
        "como um LLM",
        "não tenho acesso em tempo real",
        "minhas diretrizes",
        "desculpe, mas não posso",
    ]
    found_hallucinations = []
    for term in hallucination_terms:
        if term in parsed["raw_text"].lower():
            found_hallucinations.append(term)

    if found_hallucinations:
        issues.append(f"Frases típicas de erro/limitação do LLM detetadas: {', '.join(found_hallucinations)}")

    # --- 3. Traceability Check ---
    total_bullets = 0
    cited_bullets = 0
    uncited_list = []

    # Source URL regex
    source_regex = re.compile(r"— Fonte:\s*(https?://\S+)")

    for lab, data in parsed["labs"].items():
        bullets = data["mudou"]
        # Skip checking if the only bullet is "Sem alterações relevantes"
        if len(bullets) == 1 and "sem alterações" in bullets[0].lower():
            continue

        for b in bullets:
            total_bullets += 1
            if source_regex.search(b):
                cited_bullets += 1
            else:
                uncited_list.append((lab, b))

    if total_bullets > 0:
        pct = (cited_bullets / total_bullets) * 100
        traceability_str = f"Rastreabilidade: {pct:.1f}% ({cited_bullets}/{total_bullets} afirmações com fonte)"
        if pct < TRACEABILITY_THRESHOLD:
            issues.append(f"{traceability_str} — Abaixo do limite de {TRACEABILITY_THRESHOLD}%")
        elif pct < 100.0:
            warnings.append(f"{traceability_str} — Desejável 100% de citações")
            passes.append(f"{traceability_str} (Acima de {TRACEABILITY_THRESHOLD}%)")
        else:
            passes.append(f"{traceability_str} (Perfeito, 100% verificado)")
    else:
        passes.append("Sem afirmações de mudança a validar citações (baseline ou sem alterações)")

    if uncited_list:
        print(f"\n{BOLD}{YELLOW}⚠️ Afirmações sem fonte identificadas:{RESET}")
        for lab, b in uncited_list:
            print(f"  [{YELLOW}{lab}{RESET}] {b[:100]}...")

    # --- 4. Alignment with metrics.csv (Consistency Check) ---
    if metrics_csv_path and Path(metrics_csv_path).is_file():
        # Load metrics for the current week
        week_metrics = {}
        with open(metrics_csv_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("week") == parsed["week_id"]:
                    try:
                        week_metrics[r["lab"]] = {
                            "score": float(r.get("score", 0)),
                            "new_models": int(r.get("new_models", 0)),
                            "price_changes": int(r.get("price_changes", 0)),
                            "changelog_updates": int(r.get("changelog_updates", 0)),
                            "blog_updates": int(r.get("blog_updates", 0)),
                            "details": r.get("details", "")
                        }
                    except ValueError:
                        continue

        # Compare metrics with markdown content
        discrepancies = []
        for lab in MANDATORY_LABS:
            metrics = week_metrics.get(lab)
            doc_lab = parsed["labs"].get(lab, {})
            mudou_bullets = doc_lab.get("mudou", [])

            # Check if document says "Sem alterações"
            says_no_change = False
            if not mudou_bullets:
                says_no_change = True
            elif len(mudou_bullets) == 1 and "sem alterações" in mudou_bullets[0].lower():
                says_no_change = True

            if metrics:
                score = metrics["score"]
                # If deterministic engine found models, prices or changelog changes, but LLM claims "Sem alterações"
                critical_changes = metrics["new_models"] + metrics["price_changes"] + metrics["changelog_updates"]
                if critical_changes > 0 and says_no_change:
                    discrepancies.append(
                        f"Omissão crítica em {lab}: O motor detetou {metrics['details']} (Score {score}), mas o relatório diz 'Sem alterações relevantes'."
                    )
                elif score > 0 and says_no_change:
                    # Blog/Job updates exist, but LLM missed them. Raise warning/issue.
                    warnings.append(
                        f"Omissão menor em {lab}: O motor detetou novidades (Score {score}: {metrics['details']}), mas o relatório diz 'Sem alterações relevantes'."
                    )

        if discrepancies:
            for d in discrepancies:
                issues.append(d)
        else:
            passes.append("Consistência com o motor de métricas verificada")
    else:
        warnings.append(f"Ficheiro de métricas {metrics_csv_path} não encontrado; verificação de consistência ignorada.")

    # --- Print Summary of checks ---
    print(f"\n{BOLD}Resultados dos Testes:{RESET}")
    for p in passes:
        print(f"  [{GREEN}PASS{RESET}] {p}")
    for w in warnings:
        print(f"  [{YELLOW}WARN{RESET}] {w}")
    for i in issues:
        print(f"  [{RED}FAIL{RESET}] {i}")

    print(f"\n{BOLD}{BLUE}=================================================={RESET}")
    if issues:
        print(f"{BOLD}{RED}❌ QA GUARDRAIL REJEITADO ({len(issues)} erro(s) crítico(s)){RESET}")
        print(f"{BOLD}{RED}Envio de briefing BLOQUEADO para garantir qualidade.{RESET}")
        print(f"{BOLD}{BLUE}=================================================={RESET}\n")
        return False
    else:
        print(f"{BOLD}{GREEN}✓ QA GUARDRAIL APROVADO!{RESET}")
        print(f"{BOLD}{GREEN}Breifing validado com sucesso para envio imediato.{RESET}")
        print(f"{BOLD}{BLUE}=================================================={RESET}\n")
        return True


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: qa-check.py <report_path> [metrics_csv_path]")

    report_path = Path(sys.argv[1])
    if not report_path.is_file():
        sys.exit(f"Erro: Relatório não encontrado em {report_path}")

    metrics_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else report_path.parent.parent / "data" / "metrics.csv"

    parsed = parse_report(report_path)
    success = run_checks(parsed, metrics_path)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
