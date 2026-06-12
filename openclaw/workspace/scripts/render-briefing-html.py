#!/usr/bin/env python3
"""Render the AI Model & Provider Radar as a compact executive dashboard."""
from __future__ import annotations

import csv
import base64
import html
import json
import os
import re
import struct
import sys
import urllib.parse
import zlib
from pathlib import Path

INK = "#111827"
MUTED = "#64748b"
HAIR = "#e5e7eb"
BG = "#f3f4f6"
BLUE = "#2563eb"
GREEN = "#16a34a"
YELLOW = "#ca8a04"
RED = "#dc2626"
SLATE = "#475569"

SOURCE_LABELS = {
    "OpenAI": "OpenAI Docs",
    "Anthropic": "Anthropic Docs",
    "Google / Gemini": "Gemini Docs",
    "xAI": "xAI Docs",
    "Mistral AI": "Mistral Docs",
}

FULL_SOURCES = {
    "OpenAI": ["https://openai.com/api/pricing/", "https://platform.openai.com/docs/models", "https://developers.openai.com/api/docs/changelog"],
    "Anthropic": ["https://docs.anthropic.com/en/docs/about-claude/pricing", "https://docs.anthropic.com/en/docs/about-claude/models/overview", "https://www.anthropic.com/news"],
    "Google / Gemini": ["https://ai.google.dev/gemini-api/docs/pricing", "https://ai.google.dev/gemini-api/docs/models", "https://ai.google.dev/gemini-api/docs/changelog"],
    "xAI": ["https://docs.x.ai/developers/models", "https://docs.x.ai/developers/pricing", "https://docs.x.ai/docs/release-notes"],
    "Mistral AI": ["https://mistral.ai/pricing/", "https://docs.mistral.ai/models/", "https://docs.mistral.ai/resources/changelogs"],
    "Benchmarks": ["https://artificialanalysis.ai/leaderboards/models/", "https://lmarena.ai/leaderboard", "https://www.swebench.com/", "https://aider.chat/docs/leaderboards/"],
}

AA_INTELLIGENCE = {
    "Claude Fable 5": 64.9,
    "GPT-5.5": 60.2,
    "Gemini 3.5 Flash": 55.3,
    "Grok 4.3": 53.2,
    "Mistral Medium 3.5": 39.2,
}


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def money(value: object) -> str:
    return f"${num(value):g}"


def ctx(value: object) -> str:
    n = int(num(value))
    if n >= 1_000_000:
        return f"{n / 1_000_000:g}M"
    if n >= 1000:
        return f"{n // 1000}k"
    return str(n)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda r: num(r.get("model_score")), reverse=True)
    return rows


def week_from_report(path: Path, md: str) -> str:
    match = re.search(r"(\d{4}-W\d{2})", md) or re.search(r"(\d{4}-W\d{2})", path.name)
    return match.group(1) if match else ""


def badge(label: str, color: str = BLUE) -> str:
    return (
        f'<span style="display:inline-block;padding:4px 8px;border-radius:999px;'
        f'font-size:10px;font-weight:800;letter-spacing:.04em;color:{color};'
        f'background:{color}14;border:1px solid {color}35;white-space:nowrap">{esc(label)}</span>'
    )


def model_badges(r: dict[str, str]) -> str:
    labels: list[tuple[str, str]] = []
    status = (r.get("status") or "").upper()
    labels.append((status or "N/D", GREEN if status == "STABLE" else YELLOW if status == "PREVIEW" else RED))
    if num(r.get("output_price_per_1m")) <= 3:
        labels.append(("LOW COST", GREEN))
    if num(r.get("context_window")) >= 1_000_000:
        labels.append(("HIGH CONTEXT", BLUE))
    if any(x in (r.get("modalities") or "") for x in ("image", "audio", "video")):
        labels.append(("MULTIMODAL", BLUE))
    if "Mistral" in r.get("provider", ""):
        labels.append(("EU OPEN WEIGHT", GREEN))
    if num(r.get("output_price_per_1m")) >= 25:
        labels.append(("HIGH OUTPUT COST", RED))
    return " ".join(badge(label, color) for label, color in labels[:4])


def status_color(r: dict[str, str]) -> str:
    status = (r.get("status") or "").upper()
    if status == "STABLE":
        return GREEN
    if status == "PREVIEW":
        return YELLOW
    return RED


def production_score(r: dict[str, str]) -> float:
    status = (r.get("status") or "").lower()
    score = num(r.get("model_score"))
    if status == "stable":
        return score
    if status == "preview":
        return score - 18
    return score - 100


def intelligence_score(r: dict[str, str]) -> float:
    return AA_INTELLIGENCE.get(r.get("model_name", ""), num(r.get("model_score")))


def kpi_card(title: str, value: str, note: str, color: str = BLUE) -> str:
    return (
        '<td style="width:25%;padding:6px;vertical-align:top">'
        f'<div style="background:#fff;border:1px solid {HAIR};border-radius:16px;padding:14px;min-height:84px">'
        f'<div style="font-size:26px;font-weight:900;color:{color};line-height:1.05">{esc(value)}</div>'
        f'<div style="font-size:11px;color:{MUTED};font-weight:800;text-transform:uppercase;letter-spacing:.07em;margin-top:8px">{esc(title)}</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:6px;line-height:1.3">{esc(note)}</div>'
        '</div></td>'
    )


def decision_card(label: str, title: str, r: dict[str, str], reason: str, color: str) -> str:
    return (
        '<td style="width:25%;padding:6px;vertical-align:top">'
        f'<div style="background:#fff;border:1px solid {color}33;border-radius:16px;padding:14px;min-height:118px">'
        f'<div style="font-size:11px;font-weight:900;color:{color};text-transform:uppercase;letter-spacing:.06em">{esc(label)}</div>'
        f'<div style="font-size:13px;font-weight:900;color:{color};margin-top:3px">{esc(title)}</div>'
        f'<div style="font-size:15px;font-weight:900;color:{INK};margin-top:8px;line-height:1.2">{esc(r.get("model_name"))}</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:2px">{esc(r.get("provider"))}</div>'
        f'<div style="font-size:12px;color:{INK};margin-top:9px;line-height:1.35">{esc(reason)}</div>'
        '</div></td>'
    )


def bar_row(prefix: str, label: str, value: float, max_value: float, suffix: str, color: str) -> str:
    width = max(5, min(100, round(value / max_value * 100))) if max_value else 5
    return (
        '<tr>'
        f'<td style="width:245px;padding:7px 10px 7px 0;font-size:13px;color:{INK};white-space:nowrap"><strong>{esc(prefix)}</strong> {esc(label)}</td>'
        '<td style="padding:7px 0;width:100%">'
        f'<div style="height:12px;background:#e2e8f0;border-radius:999px;overflow:hidden">'
        f'<div style="height:12px;width:{width}%;background:{color};border-radius:999px"></div>'
        '</div></td>'
        f'<td style="width:56px;padding:7px 0 7px 10px;font-size:13px;font-weight:900;color:{INK};white-space:nowrap">{esc(suffix)}</td>'
        '</tr>'
    )


def score_bar_row(prefix: str, r: dict[str, str], value: float, max_value: float, suffix: str) -> str:
    width = max(5, min(100, round(value / max_value * 100))) if max_value else 5
    return (
        '<tr>'
        f'<td style="width:255px;padding:7px 10px 7px 0;font-size:13px;color:{INK};white-space:nowrap"><strong>{esc(prefix)}</strong> {esc(r.get("model_name"))}</td>'
        '<td style="padding:7px 0;width:100%">'
        f'<div style="height:12px;background:#e2e8f0;border-radius:999px;overflow:hidden">'
        f'<div style="height:12px;width:{width}%;background:{status_color(r)};border-radius:999px"></div>'
        '</div></td>'
        f'<td style="width:58px;padding:7px 0 7px 10px;font-size:13px;font-weight:900;color:{INK};white-space:nowrap">{esc(suffix)}</td>'
        f'<td style="width:78px;padding:7px 0 7px 8px">{badge((r.get("status") or "").upper(), status_color(r))}</td>'
        '</tr>'
    )


def pick(rows: list[dict[str, str]], pred, default: dict[str, str]) -> dict[str, str]:
    return next((r for r in rows if pred(r)), default)


def top_pick(label: str, r: dict[str, str], metric: str) -> str:
    return (
        '<td style="width:50%;padding:6px;vertical-align:top">'
        f'<div style="background:#fff;border:1px solid {HAIR};border-radius:14px;padding:12px">'
        f'<div style="font-size:10px;color:{MUTED};font-weight:900;text-transform:uppercase;letter-spacing:.06em">{esc(label)}</div>'
        f'<div style="font-size:14px;font-weight:900;color:{INK};margin-top:6px">{esc(r.get("model_name"))}</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:2px">{esc(r.get("provider"))}</div>'
        f'<div style="margin-top:8px">{badge(metric, BLUE)} {badge((r.get("status") or "").upper(), status_color(r))}</div>'
        '</div></td>'
    )


def compact_row(r: dict[str, str]) -> str:
    return (
        f'<div style="background:#fff;border:1px solid {HAIR};border-radius:14px;padding:12px;margin-top:8px">'
        f'<strong>{esc(r.get("model_name"))}</strong> <span style="color:{MUTED}">· {esc(r.get("provider"))}</span>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:5px">{money(r.get("input_price_per_1m"))} input · {money(r.get("output_price_per_1m"))} output · {ctx(r.get("context_window"))} context · {esc((r.get("status") or "").lower())} · {esc(short_use(r))}</div>'
        '</div>'
    )


def short_use(r: dict[str, str]) -> str:
    text = (r.get("best_use_case") or "").lower()
    if "open-weight" in text or "europeia" in text:
        return "EU open weight"
    if "custo" in text:
        return "cost/context"
    if "multimodal" in text:
        return "multimodal"
    if "coding" in text or "código" in text:
        return "coding"
    return "premium"


def ranking_cards(rows: list[dict[str, str]], score_key: str = "model_score") -> str:
    cards = []
    for idx, r in enumerate(rows, 1):
        if score_key == "production":
            score = production_score(r)
        elif score_key == "intelligence":
            score = intelligence_score(r)
        else:
            score = num(r.get("model_score"))
        cards.append(
            '<td style="width:50%;padding:6px;vertical-align:top">'
            f'<div style="background:#fff;border:1px solid {HAIR};border-radius:14px;padding:13px">'
            f'<div style="font-size:12px;color:{MUTED};font-weight:900">#{idx}</div>'
            f'<div style="font-size:15px;font-weight:900;color:{INK};margin-top:3px">{esc(r.get("model_name"))}</div>'
            f'<div style="font-size:12px;color:{MUTED};margin-top:4px">{esc(r.get("provider"))} · {score:g} · {money(r.get("input_price_per_1m"))}/{money(r.get("output_price_per_1m"))} · {ctx(r.get("context_window"))} · {badge((r.get("status") or "").upper(), status_color(r))}</div>'
            f'<div style="font-size:12px;color:{INK};margin-top:8px">Uso: {esc(short_use(r))}</div>'
            '</div></td>'
        )
    return '<table role="presentation" width="100%" cellspacing="0" cellpadding="0">' + "".join(
        "<tr>" + "".join(cards[i:i + 2]) + "</tr>" for i in range(0, len(cards), 2)
    ) + "</table>"


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def png_bytes(width: int, height: int, pixels: bytearray) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    stride = width * 3
    raw = b"".join(b"\x00" + bytes(pixels[y * stride:(y + 1) * stride]) for y in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def draw_rect(pixels: bytearray, width: int, height: int, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(width - 1, x1), min(height - 1, y1)
    for y in range(y0, y1 + 1):
        row = y * width * 3
        for x in range(x0, x1 + 1):
            i = row + x * 3
            pixels[i:i + 3] = bytes(color)


def draw_circle(pixels: bytearray, width: int, height: int, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
    r2 = radius * radius
    for y in range(max(0, cy - radius), min(height - 1, cy + radius) + 1):
        row = y * width * 3
        for x in range(max(0, cx - radius), min(width - 1, cx + radius) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                i = row + x * 3
                pixels[i:i + 3] = bytes(color)


def scatter_png(rows: list[dict[str, str]]) -> bytes:
    width, height = 1080, 560
    left, top, right, bottom = 88, 44, 48, 82
    plot_w = width - left - right
    plot_h = height - top - bottom
    pixels = bytearray(hex_rgb("#ffffff") * (width * height))
    draw_rect(pixels, width, height, left, top, width - right, height - bottom, hex_rgb("#f8fafc"))

    grid = hex_rgb("#e2e8f0")
    axis = hex_rgb("#64748b")
    for i in range(6):
        y = top + round(i * plot_h / 5)
        draw_rect(pixels, width, height, left, y, width - right, y + 1, grid)
    for i in range(6):
        x = left + round(i * plot_w / 5)
        draw_rect(pixels, width, height, x, top, x + 1, height - bottom, grid)
    draw_rect(pixels, width, height, left, height - bottom, width - right, height - bottom + 3, axis)
    draw_rect(pixels, width, height, left, top, left + 3, height - bottom, axis)

    costs = [num(r.get("output_price_per_1m")) for r in rows]
    scores = [num(r.get("model_score")) for r in rows]
    min_cost, max_cost = 0, max(costs) if costs else 1
    min_score = max(0, min(scores) - 5) if scores else 70
    max_score = min(100, max(scores) + 3) if scores else 95
    if max_score <= min_score:
        max_score = min_score + 1
    palette = ["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#dc2626", "#0f766e"]
    points: list[tuple[int, int, str]] = []
    for idx, r in enumerate(rows):
        cost = num(r.get("output_price_per_1m"))
        score = num(r.get("model_score"))
        x = left + round((cost - min_cost) / max(1, max_cost - min_cost) * plot_w)
        y = top + round((max_score - score) / (max_score - min_score) * plot_h)
        color = hex_rgb(palette[idx % len(palette)])
        draw_circle(pixels, width, height, x, y, 18, hex_rgb("#ffffff"))
        draw_circle(pixels, width, height, x, y, 13, color)
        points.append((x, y, palette[idx % len(palette)]))

    # Larger corner marks make it clear which direction is better even without text rendering.
    draw_rect(pixels, width, height, left + 8, top + 8, left + 34, top + 34, hex_rgb("#dcfce7"))
    draw_rect(pixels, width, height, width - right - 34, height - bottom - 34, width - right - 8, height - bottom - 8, hex_rgb("#fee2e2"))
    return png_bytes(width, height, pixels)


def scatter_png_data_uri(rows: list[dict[str, str]]) -> str:
    data = scatter_png(rows)
    out = os.environ.get("AI_RADAR_CHART_OUT")
    if out:
        Path(out).write_bytes(data)
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def scatter(rows: list[dict[str, str]]) -> str:
    palette = ["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#dc2626", "#0f766e"]
    datasets = []
    legend = []
    for idx, r in enumerate(rows, 1):
        cost = num(r.get("output_price_per_1m"))
        score = intelligence_score(r)
        color = palette[(idx - 1) % len(palette)]
        datasets.append({
            "label": r.get("model_name", ""),
            "data": [{"x": cost, "y": score}],
            "pointRadius": 8,
            "pointHoverRadius": 10,
            "backgroundColor": color,
            "borderColor": "#ffffff",
            "borderWidth": 2,
        })
        hover = (
            f"{r.get('model_name')} | Provider: {r.get('provider')} | "
            f"Intelligence Index: {score:g} | Output: {money(cost)}/M | "
            f"Contexto: {ctx(r.get('context_window'))} | Estado: {(r.get('status') or '').upper()}"
        )
        legend.append(
            f'<tr title="{esc(hover)}"><td style="width:16px;padding:4px 6px 4px 0">'
            f'<span style="display:inline-block;width:11px;height:11px;border-radius:99px;background:{color}"></span></td>'
            f'<td style="font-size:12px;color:{INK};padding:4px 10px 4px 0"><strong>{esc(r.get("model_name"))}</strong></td>'
            f'<td style="font-size:12px;color:{MUTED};padding:4px 10px 4px 0">{score:g} intelligence</td>'
            f'<td style="font-size:12px;color:{MUTED};padding:4px 0">{money(cost)}/M output</td></tr>'
        )
    y_min = max(30, min(intelligence_score(r) for r in rows) - 4)
    y_max = min(70, max(intelligence_score(r) for r in rows) + 4)
    chart_config = (
        "{"
        "type:'scatter',"
        f"data:{{datasets:{json.dumps(datasets, separators=(',', ':'))}}},"
        "options:{"
        "backgroundColor:'white',"
        "layout:{padding:{top:28,right:28,bottom:12,left:12}},"
        "plugins:{"
        "legend:{position:'bottom',labels:{boxWidth:10,font:{size:11}}},"
        "title:{display:false},"
        "datalabels:{align:'top',anchor:'end',offset:4,color:'#111827',font:{size:10,weight:'bold'},formatter:function(value,ctx){return ctx.dataset.label;}}"
        "},"
        "scales:{"
        "x:{type:'linear',min:0,title:{display:true,text:'Preço output / 1M tokens (USD)',font:{size:12,weight:'bold'}},grid:{color:'#e2e8f0'},ticks:{callback:function(v){return '$'+v;}}},"
        f"y:{{min:{y_min:g},max:{y_max:g},title:{{display:true,text:'Artificial Analysis Intelligence Index',font:{{size:12,weight:'bold'}}}},grid:{{color:'#e2e8f0'}}}}"
        "}"
        "}"
        "}"
    )
    uri = "https://quickchart.io/chart?width=900&height=520&version=4&format=png&backgroundColor=white&c=" + urllib.parse.quote(chart_config)
    hover_summary = " | ".join(f"{r.get('model_name')}: intelligence {intelligence_score(r):g}, output {money(r.get('output_price_per_1m'))}/M" for r in rows)
    return (
        f'<div style="background:#fff;border:1px solid {HAIR};border-radius:14px;padding:12px">'
        f'<div style="font-size:11px;color:{MUTED};font-weight:900;margin-bottom:4px">Y: Intelligence Index · X: preço output / 1M tokens</div>'
        f'<div style="font-size:12px;color:{INK};margin-bottom:8px"><strong>Melhor zona:</strong> topo esquerdo = maior inteligência com menor custo.</div>'
        f'<img src="{uri}" title="{esc(hover_summary)}" alt="Custo vs capacidade: scatter plot por modelo" width="100%" style="display:block;width:100%;max-width:760px;border:1px solid #e2e8f0;border-radius:12px;margin:0 auto" />'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px">{"".join(legend)}</table>'
        f'</div>'
    )


def intelligence_chart(rows: list[dict[str, str]]) -> str:
    chart_rows = sorted(rows, key=intelligence_score, reverse=True)
    labels = [r.get("model_name", "") for r in chart_rows]
    scores = [round(intelligence_score(r), 1) for r in chart_rows]
    colors = ["#111827", "#2563eb", "#0f766e", "#7c3aed", "#ca8a04"]
    chart_config = (
        "{"
        "type:'bar',"
        f"data:{{labels:{json.dumps(labels, separators=(',', ':'))},datasets:[{{label:'Intelligence Index',data:{json.dumps(scores, separators=(',', ':'))},backgroundColor:{json.dumps(colors[:len(scores)], separators=(',', ':'))},borderRadius:8,barPercentage:.72}}]}},"
        "options:{"
        "indexAxis:'y',"
        "backgroundColor:'white',"
        "layout:{padding:{top:12,right:44,bottom:8,left:8}},"
        "plugins:{legend:{display:false},title:{display:false},datalabels:{anchor:'end',align:'right',color:'#111827',font:{weight:'bold',size:12},formatter:function(v){return v.toFixed(1);}}},"
        "scales:{x:{min:0,max:70,grid:{color:'#e2e8f0'},title:{display:true,text:'Artificial Analysis Intelligence Index',font:{size:12,weight:'bold'}}},y:{grid:{display:false},ticks:{font:{size:12,weight:'bold'},color:'#111827'}}}"
        "}"
        "}"
    )
    uri = "https://quickchart.io/chart?width=900&height=420&version=4&format=png&backgroundColor=white&c=" + urllib.parse.quote(chart_config)
    hover = " | ".join(f"{r.get('model_name')}: {intelligence_score(r):g}" for r in chart_rows)
    return (
        f'<div style="background:#fff;border:1px solid {HAIR};border-radius:14px;padding:12px">'
        f'<div style="font-size:11px;color:{MUTED};font-weight:900;margin-bottom:8px">Fonte: Artificial Analysis Intelligence Index v4.0</div>'
        f'<img src="{uri}" title="{esc(hover)}" alt="Nível de inteligência por modelo" width="100%" style="display:block;width:100%;max-width:760px;border:1px solid #e2e8f0;border-radius:12px;margin:0 auto" />'
        f'</div>'
    )


def output_price_chart(rows: list[dict[str, str]]) -> str:
    chart_rows = sorted(rows, key=lambda r: num(r.get("output_price_per_1m")))
    labels = [r.get("model_name", "") for r in chart_rows]
    prices = [round(num(r.get("output_price_per_1m")), 2) for r in chart_rows]
    colors = ["#16a34a", "#0f766e", "#ca8a04", "#f59e0b", "#dc2626"]
    max_price = max(prices) if prices else 50
    chart_config = (
        "{"
        "type:'bar',"
        f"data:{{labels:{json.dumps(labels, separators=(',', ':'))},datasets:[{{label:'Output price / 1M tokens',data:{json.dumps(prices, separators=(',', ':'))},backgroundColor:{json.dumps(colors[:len(prices)], separators=(',', ':'))},borderRadius:8,barPercentage:.72}}]}},"
        "options:{"
        "indexAxis:'y',"
        "backgroundColor:'white',"
        "layout:{padding:{top:12,right:52,bottom:8,left:8}},"
        "plugins:{legend:{display:false},title:{display:false},datalabels:{anchor:'end',align:'right',color:'#111827',font:{weight:'bold',size:12},formatter:function(v){return '$'+v.toString();}}},"
        f"scales:{{x:{{min:0,max:{max_price:g},grid:{{color:'#e2e8f0'}},title:{{display:true,text:'USD por 1M output tokens',font:{{size:12,weight:'bold'}}}},ticks:{{callback:function(v){{return '$'+v;}}}}}},y:{{grid:{{display:false}},ticks:{{font:{{size:12,weight:'bold'}},color:'#111827'}}}}}}"
        "}"
        "}"
    )
    uri = "https://quickchart.io/chart?width=900&height=420&version=4&format=png&backgroundColor=white&c=" + urllib.parse.quote(chart_config)
    hover = " | ".join(f"{r.get('model_name')}: {money(r.get('output_price_per_1m'))}/M output" for r in chart_rows)
    return (
        f'<div style="background:#fff;border:1px solid {HAIR};border-radius:14px;padding:12px">'
        f'<div style="font-size:11px;color:{MUTED};font-weight:900;margin-bottom:8px">Ordenado do menor para o maior custo de output</div>'
        f'<img src="{uri}" title="{esc(hover)}" alt="Preço output por 1M tokens" width="100%" style="display:block;width:100%;max-width:760px;border:1px solid #e2e8f0;border-radius:12px;margin:0 auto" />'
        f'</div>'
    )


def governance() -> str:
    items = [
        "Preços e contexto só contam quando vêm de documentação oficial.",
        "Claims de qualidade exigem benchmark independente ou interno.",
        "Modelos preview/deprecated/removed não entram como recomendação de produção.",
    ]
    return '<ul style="margin:0 0 0 18px;padding:0">' + "".join(
        f'<li style="margin:7px 0;color:{INK};font-size:13px;line-height:1.45">{esc(item)}</li>' for item in items
    ) + "</ul>"


def source_footer() -> str:
    lines = []
    for provider, urls in FULL_SOURCES.items():
        links = " · ".join(f'<a href="{esc(u)}" style="color:{BLUE}">{esc(u)}</a>' for u in urls)
        lines.append(f'<div style="margin:4px 0"><strong>{esc(provider)}:</strong> {links}</div>')
    return "".join(lines)


def render(report_path: Path, md: str, rows: list[dict[str, str]]) -> str:
    week = week_from_report(report_path, md)
    stable = [r for r in rows if (r.get("status") or "").lower() == "stable"]
    risks = [r for r in rows if (r.get("status") or "").lower() != "stable"]
    intelligence_rows = sorted(rows, key=intelligence_score, reverse=True)
    premium = pick(rows, lambda r: r.get("provider") == "Anthropic", stable[0] if stable else rows[0])
    test = pick(rows, lambda r: "Mistral" in r.get("provider", ""), rows[0])
    cheap = min(rows, key=lambda r: num(r.get("output_price_per_1m")))
    avoid = risks[0] if risks else max(rows, key=lambda r: num(r.get("output_price_per_1m")))
    avoid_reason = "Preview: sem produção direta." if risks else "Custo alto: validar ROI antes de escala."
    multimodal = pick(rows, lambda r: any(x in (r.get("modalities") or "") for x in ("audio", "video")), rows[0])
    long_ctx = max(rows, key=lambda r: num(r.get("context_window")))
    enterprise = max(stable or rows, key=lambda r: num(r.get("provider_score")))

    top_grid = [
        top_pick("Geral premium", premium, f'{premium.get("model_score")}/100'),
        top_pick("Código", premium, "coding"),
        top_pick("Custo/output", cheap, f'{money(cheap.get("output_price_per_1m"))}/M output'),
        top_pick("Docs longos/RAG", long_ctx, f'{ctx(long_ctx.get("context_window"))} context'),
        top_pick("Multimodal", multimodal, "image/audio/video"),
        top_pick("Enterprise", enterprise, "high confidence"),
        top_pick("Europa open weight", test, "EU open weight"),
        top_pick("Acompanhar", test, "WATCH"),
    ]
    top_rows = "".join("<tr>" + "".join(top_grid[i:i + 2]) + "</tr>" for i in range(0, len(top_grid), 2))

    changes = [
        ("Anthropic", "NOVO MODELO", "Claude Fable 5 passa a liderar capacidade premium.", GREEN),
        ("Google/Gemini", "STABLE", "Gemini 3.5 Flash substitui o preview como opção recomendável.", GREEN),
        ("Mistral", "OPEN WEIGHT", "Mistral Medium 3.5 atualiza a opção europeia para agentes e código.", GREEN),
    ]
    change_html = "".join(
        f'<li style="margin:8px 0;color:{INK};line-height:1.4"><strong>{esc(provider)}</strong> · {badge(label, color)} · {esc(text)}</li>'
        for provider, label, text, color in changes
    )

    preview_risk_model = risks[0] if risks else {"model_name": "Sem preview ativo", "provider": "Radar", "status": "stable"}
    preview_risk_text = "Não usar em produção sem fallback." if risks else "Sem modelos preview nesta versão."
    risk_cards = (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>'
        + decision_card("RISCO", "Preview", preview_risk_model, preview_risk_text, YELLOW)
        + decision_card("CUSTO", "Custo alto", max(rows, key=lambda r: num(r.get("output_price_per_1m"))), "Output acima de $25/M exige validação de ROI.", RED)
        + decision_card("VALIDAÇÃO", "Benchmark interno", test, "Validar qualidade no teu dataset antes de adoção.", BLUE)
        + "</tr></table>"
    )
    investments = [
        ("OpenAI", "raciocínio, código e integração de produto."),
        ("Anthropic", "modelos premium para agentes e trabalho empresarial."),
        ("Google/Gemini", "multimodalidade, contexto longo e tooling para agentes."),
        ("xAI", "custo/contexto, voz e ferramentas dentro do ecossistema Grok."),
        ("Mistral", "modelos europeus open weight e agentes para empresas."),
    ]
    investment_html = "".join(
        f'<div style="font-size:13px;color:{INK};line-height:1.45;margin:7px 0"><strong>{esc(provider)}:</strong> {esc(text)}</div>'
        for provider, text in investments
    )
    conclusion = (
        "A leitura simples é esta: Claude Fable 5 lidera em inteligência bruta, mas é caro. "
        "Para produção equilibrada, Grok 4.3 e Gemini 3.5 Flash são mais fáceis de justificar; Mistral Medium 3.5 fica como aposta europeia open weight a validar internamente."
    )

    return f'''<!doctype html>
<html><body style="margin:0;background:{BG};font-family:Arial,Helvetica,sans-serif;color:{INK}">
<div style="max-width:960px;margin:0 auto;padding:22px">
  <div style="background:linear-gradient(135deg,#0f172a,#1d4ed8);border-radius:22px;padding:28px;color:white">
    <h1 style="margin:0;font-size:30px;line-height:1.1">AI Model & Provider Radar {esc(week)}</h1>
  </div>

  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:12px -6px 4px"><tr>
    {kpi_card("Mudanças críticas", "3", "modelo/preço/risco", BLUE)}
    {kpi_card("Risco ativo", str(len(risks)), "preview em avaliação", RED if risks else GREEN)}
    {kpi_card("Modelos avaliados", str(len(rows)), "inteligência + custo", SLATE)}
    {kpi_card("Top oportunidade", cheap.get("model_name", ""), "baixo custo, stable", GREEN)}
  </tr></table>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Mudanças críticas</h2>
    <ul style="margin:0 0 0 18px;padding:0">{change_html}</ul>
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Decisão recomendada</h2>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
      {decision_card("DECISÃO", "Manter", premium, "Stable para código e agentes premium.", GREEN)}
      {decision_card("AVALIAÇÃO", "Testar", test, "EU open weight para agentes e código.", BLUE)}
      {decision_card("OTIMIZAÇÃO", "Avaliar custo", cheap, "Menor custo de output no radar.", GREEN)}
      {decision_card("RISCO", "Rever/Evitar", avoid, avoid_reason, YELLOW)}
    </tr></table>
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Top picks por cenário</h2>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{top_rows}</table>
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Nível de inteligência</h2>
    {intelligence_chart(rows)}
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Preço output / 1M tokens</h2>
    {output_price_chart(rows)}
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Custo vs capacidade</h2>
    {scatter(rows)}
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Onde estão a investir mais</h2>
    {investment_html}
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Riscos</h2>
    {risk_cards}
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Governança</h2>
    {governance()}
  </div>

  <div style="background:#fff;border:1px solid {HAIR};border-radius:18px;padding:18px;margin-top:14px">
    <h2 style="margin:0 0 10px;font-size:18px">Conclusão</h2>
    <p style="margin:0;color:{INK};font-size:13px;line-height:1.55">{esc(conclusion)}</p>
  </div>

  <div style="font-size:12px;color:{MUTED};line-height:1.45;margin:16px 4px">
    <strong>Fontes no corpo:</strong> OpenAI Docs · Anthropic Docs · Gemini Docs · xAI Docs · Mistral Docs · Artificial Analysis.
    <div style="height:8px"></div>
    <strong>Metodologia:</strong> O nível de inteligência usa Artificial Analysis Intelligence Index. Preços e contexto vêm da documentação oficial de cada provider. Provider Score mede adoção empresarial.
    <div style="height:8px"></div>
    {source_footer()}
  </div>
</div>
</body></html>'''


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: render-briefing-html.py <report.md> [model-radar.csv]")
    report = Path(sys.argv[1])
    csv_path = Path(sys.argv[2]) if len(sys.argv) > 2 else report.parent.parent / "data" / "model-radar.csv"
    print(render(report, report.read_text(encoding="utf-8"), read_rows(csv_path)))


if __name__ == "__main__":
    main()
