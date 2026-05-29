#!/usr/bin/env python3
"""render-briefing-html.py

Renders a weekly briefing (Markdown) into a rich, "subscription-grade" HTML
email: hero header, KPI tiles, a ranking leaderboard (medals + activity bars +
weekly movement), three QuickChart visuals (score bar, rank-evolution line,
share-of-changes donut), per-lab cards with brand accents, cross-signals, and a
footer with sources + a subscription CTA.

Charts are QuickChart images (email clients run no JS). Layout uses tables +
inline styles for Outlook/Gmail compatibility.

Usage:
  ./render-briefing-html.py <report.md> [ranks.csv] > body.html
"""
import csv
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

# Brand colour + favicon domain per lab. Keys MUST match the report headings.
LABS = {
    "OpenAI": {"color": "#10a37f", "domain": "openai.com"},
    "Anthropic": {"color": "#d97757", "domain": "anthropic.com"},
    "Google / Gemini": {"color": "#4285f4", "domain": "ai.google.dev"},
    "xAI": {"color": "#111827", "domain": "x.ai"},
    "Mistral AI": {"color": "#fb6a00", "domain": "mistral.ai"},
}
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
# Stated, transparent scoring formula (kept in sync with compute-metrics.py).
WEIGHTS_NOTE = "3×modelos novos + 2×preços alterados + 1×changelog + 1×novidades no blog + 0,5×Δ vagas (cap 10)"


# Per-source signal columns from metrics.csv, for the activity heatmap.
SOURCE_COLS = ["new_models", "price_changes", "changelog_updates", "blog_updates", "job_delta"]
SOURCE_LABELS = {"new_models": "Modelos", "price_changes": "Preços", "changelog_updates": "Changelog",
                 "blog_updates": "Blog", "job_delta": "Vagas"}


def favicon(domain):
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


def inline(text):
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text))
    # Linkify bare URLs (e.g. the "Fonte: https://..." citations).
    out = re.sub(r"(https?://[^\s<)\"]+)", r'<a href="\1" style="color:#2563eb">\1</a>', out)
    return out


URL_RE = re.compile(r"https?://")


def info_for(name):
    return LABS.get(name.strip())


def color_for(name):
    i = info_for(name)
    return i["color"] if i else "#6b7280"


def logo_for(name):
    i = info_for(name)
    return favicon(i["domain"]) if i else None


def week_key(week):
    m = re.search(r"(\d{4})-W(\d{1,2})", week)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def chart_img(config, w=620, h=300, alt="", style=""):
    encoded = urllib.parse.quote(json.dumps(config, ensure_ascii=False))
    url = f"https://quickchart.io/chart?v=4&bkg=white&w={w}&h={h}&c={encoded}"
    base = "max-width:100%;height:auto;border:1px solid #e7ebef;border-radius:8px;" + style
    return f'<img src="{url}" width="{w}" alt="{html.escape(alt)}" style="{base}">'


# ----------------------------- parsing --------------------------------------

def load_ranks(csv_path):
    rows = []
    if csv_path and Path(csv_path).is_file():
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    r["score"] = int(r["score"]); r["rank"] = int(r["rank"])
                except (ValueError, KeyError):
                    continue
                rows.append(r)
    return rows


def load_metrics(csv_path, week):
    """lab -> {source_col: int} for the given week."""
    out = {}
    if csv_path and Path(csv_path).is_file():
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("week") != week:
                    continue
                out[r["lab"]] = {c: int(float(r.get(c, 0) or 0)) for c in SOURCE_COLS}
    return out


def load_pricing(csv_path, week):
    rows = []
    if csv_path and Path(csv_path).is_file():
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("week") != week:
                    continue
                try:
                    r["input_per_1m"] = float(r["input_per_1m"])
                except (ValueError, KeyError):
                    continue
                r["output_per_1m"] = float(r["output_per_1m"]) if r.get("output_per_1m") not in (None, "") else None
                rows.append(r)
    return rows


def heatmap(metrics_by_lab):
    """Activity heatmap: labs x sources, cells shaded by intensity. Pure HTML/CSS."""
    if not metrics_by_lab:
        return ""
    labs = [l for l in LABS if l in metrics_by_lab]
    if not labs:
        return ""
    head = ('<tr style="color:#5d6975;font-size:11px;text-transform:uppercase;letter-spacing:.4px">'
            '<th style="padding:6px;text-align:left">Lab</th>'
            + "".join(f'<th style="padding:6px 4px">{SOURCE_LABELS[c]}</th>' for c in SOURCE_COLS) + '</tr>')
    rows = []
    for lab in labs:
        cells = []
        for c in SOURCE_COLS:
            v = metrics_by_lab[lab].get(c, 0)
            # shade by intensity (0 = empty, higher = more saturated brand colour)
            if v <= 0:
                bg, fg, txt = "#f1f4f7", "#c2cad2", "·"
            else:
                alpha = min(1.0, 0.30 + 0.18 * v)
                bg, fg, txt = _rgba(color_for(lab), alpha), "#ffffff", str(v)
            cells.append(f'<td style="padding:0"><div style="background:{bg};color:{fg};'
                         f'text-align:center;font-weight:700;font-size:13px;padding:12px 4px;'
                         f'margin:2px;border-radius:5px">{txt}</div></td>')
        logo = logo_for(lab)
        limg = (f'<img src="{logo}" width="16" height="16" style="vertical-align:middle;'
                f'border-radius:3px;margin-right:6px" alt="">' if logo else "")
        rows.append(f'<tr><td style="padding:4px 6px;white-space:nowrap;font-weight:600;font-size:13px">'
                    f'{limg}{html.escape(lab)}</td>' + "".join(cells) + '</tr>')
    return ('<table style="width:100%;border-collapse:collapse">'
            f'<thead>{head}</thead><tbody>' + "".join(rows) + '</tbody></table>')


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"


def pricing_block(pricing_rows):
    """Cross-lab price comparison: bar of flagship input $/1M + a per-lab table.
    Shows only labs with reliably extracted token pricing (transparent coverage)."""
    if not pricing_rows:
        return ""
    labs = [l for l in LABS if any(r["lab"] == l for r in pricing_rows)]
    flagship = {}
    for lab in labs:
        rs = [r for r in pricing_rows if r["lab"] == lab]
        fl = next((r for r in rs if r.get("flagship") == "1"), None) or max(rs, key=lambda r: r["input_per_1m"])
        flagship[lab] = fl

    bar = chart_img({
        "type": "bar",
        "data": {"labels": labs,
                 "datasets": [{"label": "$ / 1M tokens (input)",
                               "data": [round(flagship[l]["input_per_1m"], 2) for l in labs],
                               "backgroundColor": [color_for(l) for l in labs], "borderRadius": 6}]},
        "options": {"indexAxis": "y", "plugins": {"legend": {"display": False},
                    "title": {"display": True, "text": "Preço input do modelo flagship ($/1M tokens)", "font": {"size": 13}}}},
    }, w=620, h=210, alt="Comparação de preços", style="margin:0 0 8px")

    trows = []
    for lab in labs:
        fl = flagship[lab]
        out = f'${fl["output_per_1m"]:.2f}' if fl["output_per_1m"] is not None else "—"
        logo = logo_for(lab)
        limg = (f'<img src="{logo}" width="16" height="16" style="vertical-align:middle;'
                f'border-radius:3px;margin-right:6px" alt="">' if logo else "")
        trows.append(f'<tr style="border-bottom:1px solid #eef1f4">'
                     f'<td style="padding:7px 6px;font-weight:600">{limg}{html.escape(lab)}</td>'
                     f'<td style="padding:7px 6px;color:#5d6975">{html.escape(fl["model"])}</td>'
                     f'<td style="padding:7px 6px;text-align:right;font-weight:700">${fl["input_per_1m"]:.2f}</td>'
                     f'<td style="padding:7px 6px;text-align:right">{out}</td></tr>')
    table = ('<table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:4px">'
             '<thead><tr style="color:#5d6975;font-size:11px;text-transform:uppercase;letter-spacing:.4px">'
             '<th style="padding:6px;text-align:left">Lab</th><th style="padding:6px;text-align:left">Flagship</th>'
             '<th style="padding:6px;text-align:right">Input /1M</th><th style="padding:6px;text-align:right">Output /1M</th>'
             '</tr></thead><tbody>' + "".join(trows) + '</tbody></table>')

    missing = [l for l in LABS if l not in labs]
    note = (f'<p style="color:#9aa4af;font-size:11px;margin:6px 0 0">Cobertura de preços: {", ".join(labs)}. '
            f'Sem dados fiáveis: {", ".join(missing)} (página protegida ou sem pricing de API por token).</p>') if missing else ""
    return bar + table + note


NO_CHANGE = "sem alteraç"


def parse_report(text):
    """Extract title, resumo, per-lab sections, cross-signals and sources."""
    data = {"title": "", "resumo": [], "sinais": [], "fontes": [], "labs": {}}
    cur_h2 = None
    cur_lab = None
    cur_sub = None  # 'mudou' | 'importa' | 'fazer'
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        if s.startswith("# ") and not data["title"]:
            data["title"] = s[2:].strip()
            continue
        if s.startswith("## "):
            cur_h2 = s[3:].strip()
            low = cur_h2.lower()
            if cur_h2 in LABS:
                cur_lab = cur_h2
                data["labs"][cur_lab] = {"mudou": [], "importa": [], "fazer": []}
            else:
                cur_lab = None
            cur_sub = None
            data["_h2low"] = low
            continue
        if s.startswith("### "):
            sub = s[4:].strip().lower()
            if "mudou" in sub:
                cur_sub = "mudou"
            elif "importa" in sub:
                cur_sub = "importa"
            elif "fazer" in sub or "watch" in sub:
                cur_sub = "fazer"
            elif "relev" in sub:  # backward compat with old reports
                cur_sub = "importa"
            else:
                cur_sub = None
            continue
        # content line
        text_line = s[2:].strip() if s.startswith("- ") else s
        is_bullet = s.startswith("- ")
        low = data.get("_h2low", "")
        if cur_lab:
            if cur_sub == "mudou" and is_bullet and NO_CHANGE not in text_line.lower():
                data["labs"][cur_lab]["mudou"].append(text_line)
            elif cur_sub == "importa":
                data["labs"][cur_lab]["importa"].append(text_line)
            elif cur_sub == "fazer":
                data["labs"][cur_lab]["fazer"].append(text_line)
        elif low.startswith("resumo") and is_bullet:
            data["resumo"].append(text_line)
        elif "sinais" in low and is_bullet:
            data["sinais"].append(text_line)
        elif "fonte" in low and is_bullet:
            data["fontes"].append(text_line)
    return data


# --------------------------- HTML building ----------------------------------

def kpi_tile(value, label, accent):
    return (
        f'<td class="kpi" style="padding:6px;vertical-align:top" width="25%"><div style="background:#ffffff;border:1px solid #e7ebef;'
        f'border-top:3px solid {accent};border-radius:8px;padding:14px 12px;text-align:center">'
        f'<div style="font-size:22px;font-weight:800;color:#101820;line-height:1.1">{value}</div>'
        f'<div style="font-size:11px;color:#5d6975;text-transform:uppercase;letter-spacing:.4px;margin-top:5px">{label}</div>'
        f'</div></td>'
    )


def leaderboard(cur, prev_rank):
    rows = []
    for r in cur:
        lab = r["lab"]
        medal = MEDALS.get(r["rank"], f'<span style="color:#9aa4af">{r["rank"]}</span>')
        logo = logo_for(lab)
        limg = (f'<img src="{logo}" width="18" height="18" style="vertical-align:middle;'
                f'border-radius:4px;margin-right:7px" alt="">' if logo else "")
        bar_w = max(4, r["score"] * 10)
        bar = (f'<div style="background:#eceff3;border-radius:6px;height:16px;min-width:90px">'
               f'<div style="background:{color_for(lab)};height:16px;border-radius:6px;width:{bar_w}%"></div></div>')
        if lab in prev_rank:
            d = prev_rank[lab] - r["rank"]
            mv = (f'<span style="color:#1a9c52;font-weight:700">▲{d}</span>' if d > 0 else
                  f'<span style="color:#d23b3b;font-weight:700">▼{abs(d)}</span>' if d < 0 else
                  '<span style="color:#9aa4af">—</span>')
        else:
            mv = '<span style="color:#3b82f6;font-weight:700">novo</span>'
        rows.append(
            f'<tr style="border-bottom:1px solid #eef1f4">'
            f'<td style="padding:10px 6px;text-align:center;font-size:18px;width:34px">{medal}</td>'
            f'<td style="padding:10px 6px;white-space:nowrap;font-weight:600">{limg}{html.escape(lab)}</td>'
            f'<td style="padding:10px 6px;width:40%">{bar}</td>'
            f'<td style="padding:10px 6px;text-align:right;font-weight:800;width:34px">{r["score"]}</td>'
            f'<td style="padding:10px 6px;text-align:center;width:52px">{mv}</td>'
            f'<td class="hide-sm" style="padding:10px 6px;color:#5d6975;font-size:13px">{html.escape(r.get("destaque",""))}</td>'
            f'</tr>')
    return (
        '<table class="lb" style="width:100%;border-collapse:collapse;font-size:14px;margin:4px 0 8px">'
        '<thead><tr style="border-bottom:2px solid #e7ebef;color:#5d6975;font-size:11px;'
        'text-transform:uppercase;letter-spacing:.5px">'
        '<th style="padding:6px;text-align:center">#</th><th style="padding:6px;text-align:left">Lab</th>'
        '<th style="padding:6px;text-align:left">Atividade</th><th style="padding:6px;text-align:right">Score</th>'
        '<th style="padding:6px;text-align:center">Δ</th><th class="hide-sm" style="padding:6px;text-align:left">Destaque</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')


def lab_cards(report, score_by_lab, breakdown_by_lab):
    cells = []
    for lab in LABS:
        sec = report["labs"].get(lab)
        if not sec:
            continue
        color = color_for(lab)
        logo = logo_for(lab)
        limg = (f'<img src="{logo}" width="22" height="22" style="vertical-align:middle;'
                f'border-radius:5px;margin-right:8px" alt="">' if logo else "")
        score = score_by_lab.get(lab)
        badge = (f'<span style="background:{color};color:#fff;font-size:12px;font-weight:700;'
                 f'border-radius:12px;padding:2px 9px">{score}</span>' if score is not None else "")
        bullets = sec["mudou"][:4]
        if bullets:
            items = "".join(f'<li style="margin:4px 0;line-height:1.45">{inline(b)}</li>' for b in bullets)
            body = f'<ul style="margin:8px 0 0;padding-left:18px;font-size:13px;color:#2b3640">{items}</ul>'
        else:
            body = '<p style="margin:8px 0 0;font-size:13px;color:#9aa4af">Sem alterações relevantes esta semana.</p>'
        importa = " ".join(sec.get("importa", [])).strip()
        importa_html = (f'<p style="margin:10px 0 0;font-size:12px;color:#5d6975">'
                        f'<strong style="color:{color}">Porque importa:</strong> {inline(importa)}</p>'
                        ) if importa and importa.lower() != "n/a" else ""
        fazer = [x for x in sec.get("fazer", []) if x and x.lower() != "n/a"]
        if fazer:
            fitems = "".join(f'<li style="margin:3px 0;line-height:1.4">{inline(x)}</li>' for x in fazer[:3])
            fazer_html = (f'<p style="margin:10px 0 2px;font-size:12px;color:{color};font-weight:600">O que fazer</p>'
                          f'<ul style="margin:0;padding-left:18px;font-size:12px;color:#5d6975">{fitems}</ul>')
        else:
            fazer_html = ""
        bd = breakdown_by_lab.get(lab)
        metric_html = (f'<div style="margin:10px 0 0;padding-top:8px;border-top:1px dashed #e7ebef;'
                       f'font-size:11px;color:#8a949e">📊 Sinais medidos: {html.escape(bd)}</div>') if bd else ""
        header = (
            f'<table width="100%" style="border-collapse:collapse"><tr>'
            f'<td style="font-size:15px;font-weight:700;color:#101820">{limg}{html.escape(lab)}</td>'
            f'<td align="right" style="white-space:nowrap">{badge}</td></tr></table>')
        cells.append(
            f'<td class="stack" width="50%" valign="top" style="padding:8px">'
            f'<div style="background:#fff;border:1px solid #e7ebef;border-left:4px solid {color};'
            f'border-radius:8px;padding:14px 16px">'
            f'{header}{body}{importa_html}{fazer_html}{metric_html}</div></td>')
    # pack 2 per row
    rows = []
    for i in range(0, len(cells), 2):
        pair = cells[i:i + 2]
        if len(pair) == 1:
            pair.append('<td class="stack" width="50%"></td>')
        rows.append("<tr>" + "".join(pair) + "</tr>")
    return ('<table style="width:100%;border-collapse:collapse;table-layout:fixed">'
            + "".join(rows) + "</table>")


def bullet_block(title, items, accent="#101820"):
    if not items:
        return ""
    lis = "".join(f'<li style="margin:6px 0;line-height:1.5">{inline(b)}</li>' for b in items)
    return (f'<h2 class="sec">{title}</h2>'
            f'<ul style="margin:8px 0 4px;padding-left:20px;font-size:14px;color:#2b3640">{lis}</ul>')


def build(report, ranks, current_week, metrics_by_lab=None, pricing_rows=None):
    metrics_by_lab = metrics_by_lab or {}
    pricing_rows = pricing_rows or []
    weeks = sorted({r["week"] for r in ranks}, key=week_key)
    if weeks and current_week not in weeks:
        current_week = weeks[-1]
    prev_week = None
    if current_week in weeks:
        i = weeks.index(current_week)
        prev_week = weeks[i - 1] if i > 0 else None
    cur = sorted([r for r in ranks if r["week"] == current_week], key=lambda r: r["rank"])
    prev_rank = {r["lab"]: r["rank"] for r in ranks if r["week"] == prev_week} if prev_week else {}
    score_by_lab = {r["lab"]: r["score"] for r in cur}
    breakdown_by_lab = {r["lab"]: r.get("destaque", "") for r in cur}

    # --- derived metrics ---
    changes = {lab: len(report["labs"].get(lab, {}).get("mudou", [])) for lab in LABS}
    total_changes = sum(changes.values())
    labs_with_news = sum(1 for v in changes.values() if v > 0)
    most_active = cur[0]["lab"] if cur else "—"
    # biggest climber
    climber, climb_val = None, 0
    for r in cur:
        if r["lab"] in prev_rank:
            d = prev_rank[r["lab"]] - r["rank"]
            if d > climb_val:
                climb_val, climber = d, r["lab"]
    climber_txt = f'{climber} ▲{climb_val}' if climber else "—"

    has_data = total_changes > 0 or any(s > 0 for s in score_by_lab.values())

    # --- citation coverage (trust signal) ---
    all_bullets = [b for lab in LABS for b in report["labs"].get(lab, {}).get("mudou", [])]
    cited = sum(1 for b in all_bullets if URL_RE.search(b))
    cite_total = len(all_bullets)

    # --- charts ---
    labs_present = [l for l in LABS if any(r["lab"] == l for r in ranks)]
    colors = [color_for(l) for l in labs_present]

    score_bar = chart_img({
        "type": "bar",
        "data": {"labels": labs_present,
                 "datasets": [{"label": "Score", "data": [score_by_lab.get(l, 0) for l in labs_present],
                               "backgroundColor": colors, "borderRadius": 6}]},
        "options": {"indexAxis": "y",
                    "plugins": {"legend": {"display": False},
                                "title": {"display": True, "text": "Score de atividade da semana (0-10)", "font": {"size": 13}}},
                    "scales": {"x": {"min": 0, "max": 10, "ticks": {"stepSize": 2}}}},
    }, w=300, h=230, alt="Score por lab", style="margin:0")

    donut = chart_img({
        "type": "doughnut",
        "data": {"labels": labs_present,
                 "datasets": [{"data": [changes.get(l, 0) for l in labs_present], "backgroundColor": colors}]},
        "options": {"plugins": {"legend": {"position": "right", "labels": {"boxWidth": 12, "font": {"size": 10}}},
                                "title": {"display": True, "text": "Quota de mudanças detetadas", "font": {"size": 13}}}},
    }, w=300, h=230, alt="Quota de mudanças", style="margin:0")

    line_datasets = []
    for lab in labs_present:
        per = {r["week"]: r["rank"] for r in ranks if r["lab"] == lab}
        line_datasets.append({"label": lab, "data": [per.get(w) for w in weeks],
                              "borderColor": color_for(lab), "backgroundColor": color_for(lab),
                              "fill": False, "spanGaps": True, "lineTension": 0.3,
                              "pointRadius": 4, "borderWidth": 3})
    rank_line = chart_img({
        "type": "line",
        "data": {"labels": weeks, "datasets": line_datasets},
        "options": {"plugins": {"legend": {"position": "bottom", "labels": {"boxWidth": 12, "font": {"size": 11}}},
                                "title": {"display": True, "text": "Evolução do ranking semanal (1 = mais ativo)", "font": {"size": 13}}},
                    "scales": {"y": {"reverse": True, "min": 1, "max": max(2, len(labs_present)),
                                      "ticks": {"stepSize": 1, "precision": 0}, "title": {"display": True, "text": "Rank"}}}},
    }, w=620, h=300, alt="Evolução do ranking semanal")

    # --- hero highlight: top lab's first bullet, else resumo[0] ---
    hero = ""
    if cur:
        top = cur[0]["lab"]
        tb = report["labs"].get(top, {}).get("mudou", [])
        headline = tb[0] if tb else (report["resumo"][0] if report["resumo"] else "")
        if headline:
            # Solid background first (Gmail/Outlook strip CSS gradients); gradient layered on top.
            hero = (f'<div style="background:#101820;'
                    f'background-image:linear-gradient(135deg,{color_for(top)} 0%,#101820 100%);'
                    f'color:#ffffff;border-radius:10px;padding:18px 22px;margin:0 0 18px">'
                    f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;opacity:.85">🔥 Destaque da semana · {html.escape(top)}</div>'
                    f'<div style="font-size:17px;font-weight:700;line-height:1.35;margin-top:6px">{inline(headline)}</div></div>')

    # --- KPI strip ---
    kpis = (
        '<table style="width:100%;border-collapse:collapse;margin:0 0 16px"><tr>'
        + kpi_tile(total_changes, "Mudanças detetadas", "#10a37f")
        + kpi_tile(html.escape(most_active.split(" / ")[0]), "Lab mais ativo", "#d97757")
        + kpi_tile(html.escape(climber_txt.split(" ")[0]) + (f' <span style="color:#1a9c52">▲{climb_val}</span>' if climber else ""), "Maior subida", "#4285f4")
        + kpi_tile(f"{labs_with_news}/{len(LABS)}", "Labs com novidades", "#7c3aed")
        + '</tr></table>')

    # --- data section: score bar + rank-evolution line ---
    if has_data:
        charts = (f'<div style="margin:4px 0 2px">{score_bar}</div>'
                  f'<div style="margin:8px 0">{rank_line}</div>')
    else:
        note = ('<p style="color:#9aa4af;font-size:12px;margin:4px 0 0">Execução de baseline — '
                'os gráficos de score ganham forma quando houver mudanças entre semanas.</p>')
        charts = f'<div style="margin:8px 0">{rank_line}</div>{note}'

    price_html = pricing_block(pricing_rows)
    heat_html = heatmap(metrics_by_lab)

    week_label = current_week or report["title"]
    title = report["title"] or "Briefing Semanal"

    parts = [f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ margin:0; padding:0; background:#eef1f4; color:#17202a; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:24px 14px; }}
  .card {{ background:#f8fafc; border:1px solid #dfe3e8; border-radius:12px; overflow:hidden; }}
  .hero {{ background:#101820; color:#fff; padding:26px 28px; }}
  .brand {{ font-size:13px; letter-spacing:3px; text-transform:uppercase; color:#7fd1b9; font-weight:700; }}
  .hero h1 {{ margin:8px 0 2px; font-size:25px; }}
  .hero .sub {{ color:#aab4be; font-size:13px; }}
  .content {{ padding:22px 26px 8px; }}
  .sec {{ font-size:16px; margin:24px 0 6px; padding-bottom:6px; border-bottom:2px solid #e7ebef; color:#101820; }}
  .foot {{ background:#101820; color:#cdd6df; padding:22px 28px; font-size:12px; line-height:1.6; }}
  .cta {{ display:inline-block; background:#10a37f; color:#fff !important; text-decoration:none; font-weight:700;
          padding:11px 20px; border-radius:8px; font-size:14px; margin:6px 0; }}
  a {{ color:#7fd1b9; }}
  @media only screen and (max-width:600px) {{
    .wrap {{ padding:12px 8px !important; }}
    .content {{ padding:16px 14px 6px !important; }}
    .hero {{ padding:20px 18px !important; }}
    .hero h1 {{ font-size:21px !important; }}
    .stack {{ display:block !important; width:100% !important; box-sizing:border-box; padding:4px 0 !important; }}
    .kpi {{ display:inline-block !important; width:48% !important; box-sizing:border-box; vertical-align:top; }}
    .lb {{ font-size:12px !important; }}
    .lb .hide-sm {{ display:none !important; }}
  }}
</style></head>
<body><div class="wrap"><div class="card">
  <div class="hero">
    <div class="brand">◆ intelagent · competitive intelligence</div>
    <h1>{html.escape(title)}</h1>
    <div class="sub">Frontier model labs · OpenAI · Anthropic · Google/Gemini · xAI</div>
  </div>
  <div class="content">
"""]
    parts.append(hero)
    parts.append(kpis)
    parts.append('<h2 class="sec">🏆 Leaderboard da semana</h2>')
    parts.append(leaderboard(cur, prev_rank))
    if price_html:
        parts.append('<h2 class="sec">💰 Comparador de preços</h2>')
        parts.append(price_html)
    if heat_html:
        parts.append('<h2 class="sec">🔥 Mapa de atividade</h2>')
        parts.append(heat_html)
    parts.append('<h2 class="sec">📊 Score & evolução</h2>')
    parts.append(charts)
    if any(report["labs"].get(l, {}).get("mudou") or report["labs"].get(l) for l in LABS):
        parts.append('<h2 class="sec">🔬 Por lab</h2>')
        parts.append(lab_cards(report, score_by_lab, breakdown_by_lab))
    parts.append(bullet_block("🔗 Sinais cruzados", report["sinais"]))
    parts.append('</div>')  # close content
    # footer
    fontes = ""
    if report["fontes"]:
        lis = "".join(f'<li style="margin:3px 0">{inline(f)}</li>' for f in report["fontes"][:12])
        fontes = f'<div style="margin:0 0 14px"><strong style="color:#fff">Fontes</strong><ul style="margin:6px 0;padding-left:18px">{lis}</ul></div>'
    if cite_total:
        pct = round(100 * cited / cite_total)
        col = "#7fd1b9" if pct >= 80 else ("#e8b84b" if pct >= 40 else "#e0795f")
        cite_badge = (f'<div style="margin:0 0 12px;font-size:12px"><span style="color:{col};font-weight:700">'
                      f'✓ Rastreabilidade {pct}%</span> <span style="color:#9aa4af">— {cited}/{cite_total} '
                      f'afirmações com fonte citada</span></div>')
    else:
        cite_badge = ""
    parts.append(
        '<div class="foot">'
        + cite_badge + fontes +
        '<div style="border-top:1px solid #2a3540;padding-top:14px;margin-top:4px">'
        '<div style="color:#fff;font-size:15px;font-weight:700;margin-bottom:4px">Gostas deste briefing?</div>'
        'Recebe a análise dos frontier model labs toda a segunda de manhã, com ranking, gráficos e os movimentos que interessam.'
        '<div style="margin:12px 0 4px"><a class="cta" href="#">Subscrever o briefing semanal →</a></div>'
        '<div style="color:#7c8794;margin-top:10px;font-size:11px">Metodologia: score 0-10 calculado de forma determinística a partir de '
        'snapshots públicos (models, pricing, blog, jobs) comparados semana a semana — '
        f'<strong style="color:#aab4be">{WEIGHTS_NOTE}</strong>. Análise qualitativa gerada e citada à fonte. Gerado pelo intelagent.</div>'
        '</div></div>')
    parts.append('</div></div></body></html>')
    return "\n".join(p for p in parts if p)


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: render-briefing-html.py <report.md> [ranks.csv]")
    report_path = Path(sys.argv[1])
    if not report_path.is_file():
        sys.exit(f"[render] report not found: {report_path}")
    csv_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else report_path.parent.parent / "data" / "ranks.csv"
    data_dir = csv_path.parent
    m = re.search(r"(\d{4}-W\d{1,2})", report_path.stem)
    current_week = m.group(1) if m else ""
    report = parse_report(report_path.read_text(encoding="utf-8"))
    ranks = load_ranks(csv_path)
    # Resolve the effective week the same way build() does (latest in ranks if mismatch).
    weeks = sorted({r["week"] for r in ranks}, key=week_key)
    eff_week = current_week if (current_week in weeks or not weeks) else weeks[-1]
    metrics_by_lab = load_metrics(data_dir / "metrics.csv", eff_week)
    pricing_rows = load_pricing(data_dir / "pricing.csv", eff_week)
    sys.stdout.write(build(report, ranks, current_week, metrics_by_lab, pricing_rows))


if __name__ == "__main__":
    main()
