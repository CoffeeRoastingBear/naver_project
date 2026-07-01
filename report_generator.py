import html
import base64
import json
from datetime import datetime
from pathlib import Path


REPORTS_DIR = Path("reports")
REPORT_META_PATH = REPORTS_DIR / "latest_report_meta.json"
FONT_PATH = Path("배달의민족글꼴모음") / "BMDOHYEON_ttf.ttf"


def _fmt_price(value):
    try:
        number = int(float(value or 0))
    except (TypeError, ValueError):
        number = 0
    return f"{number:,}원" if number else "-"


def _fmt_rate(value):
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "-"


def _font_face_css():
    if not FONT_PATH.exists():
        return ""
    data = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    return (
        "@font-face {"
        "font-family:'BMDoHyeon';"
        f"src:url(data:font/truetype;charset=utf-8;base64,{data}) format('truetype');"
        "font-weight:400;"
        "font-style:normal;"
        "}"
    )


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _price_link(item):
    if not item:
        return "<div>-</div>"
    price = _fmt_price(item.get("lprice") or item.get("price"))
    rate = _fmt_rate(item.get("discount_rate"))
    link = str(item.get("link") or "").strip()
    if link:
        return f'<div><strong><a href="{_esc(link)}">최저가 (클릭)</a></strong> <span>{price} · {rate}</span></div>'
    return f"<div><strong>{price}</strong> <span>{rate}</span><br><span>URL 없음</span></div>"


def _max_discount(rows):
    values = []
    for row in rows or []:
        for item in row.get("low_items") or []:
            try:
                values.append(float(item.get("discount_rate")))
            except (TypeError, ValueError):
                pass
    return min(values) if values else None


def _model_sidebar(rows):
    items = []
    for row in rows or []:
        items.append(
            "<div class=\"model-item\">"
            f"<strong>{_esc(row.get('own_sku'))}</strong>"
            f"<small>{_esc(row.get('competitor_sku'))}</small>"
            f"<span>기준가 {_fmt_price(row.get('base_price'))}</span>"
            "</div>"
        )
    return "".join(items) or "<div class=\"empty-side\">표시 모델 없음</div>"


def _price_position_html(row):
    stats = row.get("price_position_stats") or {}
    total = int(stats.get("total_count") or 0)
    lower_count = int(stats.get("lower_count") or 0)
    higher_count = int(stats.get("higher_count") or 0)
    lower_rate = float(stats.get("lower_rate") or 0)
    higher_rate = float(stats.get("higher_rate") or 0)
    if total <= 0:
        return '<div class="base-stats muted">수집 게시물 없음</div>'
    return (
        '<div class="base-stats">'
        f'<div class="stat-line down">기준가 대비 낮은 게시물 <strong>{lower_count:,}건({lower_rate:.1f}%)</strong></div>'
        f'<div class="stat-line up">기준가 대비 높은 게시물 <strong>{higher_count:,}건({higher_rate:.1f}%)</strong></div>'
        f'<div class="stat-note">수집 {total:,}건 기준</div>'
        '</div>'
    )


def _ai_summary_cards(summary_lines):
    icons = ["◆", "↓", "↗"]
    labels = ["저가 집중 모델", "최대 가격 차이", "상세 확인"]
    cards = []
    for index, line in enumerate((summary_lines or [])[:3]):
        cards.append(
            '<div class="ai-card">'
            f'<div class="ai-card-icon">{icons[index] if index < len(icons) else "AI"}</div>'
            '<div>'
            f'<div class="ai-card-label">{labels[index] if index < len(labels) else "AI 인사이트"}</div>'
            f'<div class="ai-card-text">{_esc(line)}</div>'
            '</div>'
            '</div>'
        )
    return "".join(cards) or '<div class="ai-card"><div class="ai-card-icon">AI</div><div class="ai-card-text">AI 요약 정보가 없습니다.</div></div>'


def _top20_panel(rows, side=None):
    items = []
    for row in rows or []:
        for item in (row.get("low_items") or [])[:20]:
            if side and item.get("side") != side:
                continue
            items.append((row, item))
    items = sorted(items, key=lambda pair: (int(pair[1].get("lprice") or pair[1].get("price") or 0), float(pair[1].get("discount_rate") or 0)))[:20]

    blocks = []
    for index, (row, item) in enumerate(items, start=1):
        title = _esc(item.get("title") or "-")
        link = str(item.get("link") or "").strip()
        image = str(item.get("image") or "").strip()
        image_html = f'<img class="item-image" src="{_esc(image)}" alt="">' if image else '<div class="item-image placeholder"></div>'
        title_html = f'<a class="item-title" href="{_esc(link)}">{index}. {title}</a>' if link else f'<div class="item-title">{index}. {title}</div>'
        side = "경쟁사" if item.get("side") == "competitor" else "당사"
        blocks.append(
            "<div class=\"top-item\">"
            f"{image_html}<div class=\"item-body\">{title_html}"
            f"<div class=\"item-meta\">{side} · {_esc(row.get('own_sku'))} / {_esc(row.get('competitor_sku'))} · "
            f"{_esc(item.get('mall_name') or '-')} · {_fmt_price(item.get('lprice') or item.get('price'))} · {_fmt_rate(item.get('discount_rate'))}</div>"
            "</div>"
            "</div>"
        )
    return "".join(blocks) or "<div class=\"empty\">기준가 대비 10% 이상 낮은 게시물이 없습니다.</div>"


def get_latest_report_meta():
    if not REPORT_META_PATH.exists():
        return {}
    try:
        return json.loads(REPORT_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_latest_report():
    """Return the newest generated HTML report path, or None.

    Mail automation must use this function and attach the returned file.
    It must not call Naver API or dashboard collection endpoints.
    """
    if not REPORTS_DIR.exists():
        return None
    reports = sorted(REPORTS_DIR.glob("price_report_*.html"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else None


def generate_price_report(rows, summary_lines=None, generated_at=None, stats=None, attachments=None):
    """Write a standalone HTML report from already-collected dashboard rows."""
    REPORTS_DIR.mkdir(exist_ok=True)
    generated_at = generated_at or datetime.now()
    summary_lines = (summary_lines or [])[:3]
    file_path = REPORTS_DIR / f"price_report_{generated_at.strftime('%Y%m%d_%H%M%S')}.html"
    sidebar_models = _model_sidebar(rows)
    own_top20_html = _top20_panel(rows, "own")
    competitor_top20_html = _top20_panel(rows, "competitor")
    summary_cards = _ai_summary_cards(summary_lines)
    font_face_css = _font_face_css()

    row_html = []
    for row in rows or []:
        row_html.append(
            "<tr>"
            f"<td><strong>{_esc(row.get('own_sku'))}</strong><br><small>경쟁사 {_esc(row.get('competitor_sku'))}</small></td>"
            f"<td class=\"price-cell\"><strong>{_fmt_price(row.get('base_price'))}</strong>{_price_position_html(row)}</td>"
            f"<td>{_price_link(row.get('own_lowest'))}</td>"
            f"<td>{_price_link(row.get('competitor_lowest'))}</td>"
            "</tr>"
        )

    summary_html = "".join(f"<li>{_esc(line)}</li>" for line in summary_lines)
    if not summary_html:
        summary_html = "<li>기준가 대비 10% 이상 낮은 게시물이 없습니다.</li>"

    table_body = "".join(row_html) or '<tr><td colspan="5" class="empty">표시할 게시물이 없습니다.</td></tr>'
    html_text = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>AI 요약 리포트</title>
  <style>
    {font_face_css}
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'BMDoHyeon', Arial, 'Malgun Gothic', sans-serif; margin: 0; background: #f3f6fa; color: #17202a; }}
    .layout {{ display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 100vh; }}
    .sidebar {{ background: #142235; color: #ffffff; padding: 22px 18px; }}
    .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 22px; }}
    .brand-mark {{ width: 34px; height: 34px; border-radius: 8px; background: #0bb15b; display: grid; place-items: center; font-weight: 800; }}
    .brand h1 {{ font-size: 20px; margin: 0; letter-spacing: 0; }}
    .brand p {{ color: #b9c5d2; margin: 3px 0 0; font-size: 12px; }}
    .panel {{ border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 14px; margin-bottom: 14px; background: rgba(255,255,255,0.04); }}
    .panel-title {{ font-size: 13px; font-weight: 700; color: #d7e2ef; margin-bottom: 10px; }}
    .category-pill {{ display: block; background: #ffffff; color: #142235; border-radius: 6px; padding: 9px 10px; font-weight: 700; }}
    .model-item {{ border-top: 1px solid rgba(255,255,255,0.12); padding: 10px 0; }}
    .model-item:first-of-type {{ border-top: 0; }}
    .model-item strong {{ display: block; font-size: 13px; }}
    .model-item small {{ display: block; color: #b9c5d2; line-height: 1.45; margin-top: 3px; }}
    .model-item span {{ display: block; color: #eef4fb; font-size: 12px; margin-top: 4px; white-space: nowrap; }}
    .empty-side {{ color: #b9c5d2; font-size: 13px; }}
    .main {{ padding: 24px; min-width: 0; }}
    .hero {{ position: relative; background: linear-gradient(135deg, #ffffff 0%, #f7fbff 100%); border: 1px solid #d9e0e8; padding: 22px; border-radius: 8px; margin-bottom: 16px; }}
    .ai-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }}
    .ai-badge {{ width: 44px; height: 44px; border-radius: 12px; background: #101828; color: #ffffff; display: grid; place-items: center; font-family: Arial, sans-serif; font-weight: 800; box-shadow: 0 8px 18px rgba(16,24,40,0.18); }}
    .ai-title {{ margin: 0; font-size: 26px; letter-spacing: 0; }}
    .ai-subtitle {{ color: #667085; font-size: 13px; margin-top: 4px; }}
    .meta {{ position: absolute; top: 12px; right: 16px; color: #98a2b3; font-size: 11px; }}
    .ai-card-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .ai-card {{ display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px; align-items: start; background: #ffffff; border: 1px solid #e5e9f0; border-radius: 8px; padding: 12px; }}
    .ai-card-icon {{ width: 34px; height: 34px; border-radius: 10px; background: #e8f2ff; color: #175cd3; display: grid; place-items: center; font-weight: 800; }}
    .ai-card-label {{ color: #667085; font-size: 11px; margin-bottom: 4px; }}
    .ai-card-text {{ line-height: 1.55; color: #243447; font-size: 13px; }}
    .card {{ background: #ffffff; border: 1px solid #d9e0e8; border-radius: 8px; overflow: hidden; margin-bottom: 16px; }}
    .card-title {{ padding: 14px 16px; border-bottom: 1px solid #d9e0e8; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #d9e0e8; padding: 12px; vertical-align: top; }}
    th {{ background: #eef3f8; text-align: left; }}
    a {{ color: #175cd3; word-break: break-all; }}
    .nowrap, .price-cell {{ white-space: nowrap; }}
    .price-cell strong {{ display: block; margin-bottom: 8px; }}
    .base-stats {{ white-space: normal; min-width: 260px; font-family: Arial, 'Malgun Gothic', sans-serif; }}
    .stat-line {{ font-size: 12px; line-height: 1.5; }}
    .stat-line strong {{ display: inline; margin: 0; }}
    .stat-line.down strong {{ color: #175cd3; }}
    .stat-line.up strong {{ color: #b42318; }}
    .stat-note {{ color: #667085; font-size: 11px; margin-top: 2px; }}
    ol {{ margin: 0; padding-left: 20px; }}
    li {{ margin-bottom: 8px; }}
    .lowest hr {{ border: 0; border-top: 1px solid #e5e9f0; margin: 10px 0; }}
    .empty {{ text-align: center; color: #667085; }}
    .top-list {{ padding: 8px 16px 16px; }}
    .top-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 16px; border-top: 1px solid #d9e0e8; }}
    .top-panel {{ border: 1px solid #e5e9f0; border-radius: 8px; overflow: hidden; }}
    .top-panel-title {{ padding: 12px 14px; background: #f7f9fc; font-weight: 700; border-bottom: 1px solid #e5e9f0; }}
    .top-item {{ display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 10px; border-top: 1px solid #edf1f5; padding: 10px 0; }}
    .top-item:first-child {{ border-top: 0; }}
    .item-image {{ width: 56px; height: 56px; object-fit: cover; border-radius: 6px; border: 1px solid #e5e9f0; background: #f3f6fa; }}
    .item-image.placeholder {{ display: block; }}
    .item-title {{ font-weight: 700; }}
    .item-meta {{ color: #667085; font-size: 12px; margin-top: 4px; }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ min-height: auto; }}
      .top-grid {{ grid-template-columns: 1fr; }}
      .ai-card-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">N</div>
        <div>
          <h1>가격 비교</h1>
          <p>모델코드 기반 정적 리포트</p>
        </div>
      </div>
      <section class="panel">
        <div class="panel-title">카테고리</div>
        <span class="category-pill">TV ({len(rows or [])})</span>
      </section>
      <section class="panel">
        <div class="panel-title">모델코드</div>
        {sidebar_models}
      </section>
    </aside>
    <main class="main">
    <section class="hero">
      <div class="ai-head">
        <div class="ai-badge">AI</div>
        <div>
          <h2 class="ai-title">&lt;&lt; AI 요약 &gt;&gt;</h2>
          <div class="ai-subtitle">수집된 가격 데이터를 기준으로 저가 게시물과 가격 차이를 자동 요약했습니다.</div>
        </div>
      </div>
      <div class="meta">생성일시: {_esc(generated_at.strftime('%Y-%m-%d %H:%M:%S'))}</div>
      <div class="ai-card-grid">{summary_cards}</div>
    </section>
    <section class="card">
      <div class="card-title">최신 가격 비교</div>
      <table>
        <thead>
          <tr>
            <th>모델</th>
            <th>기준가</th>
            <th>당사 최저가</th>
            <th>경쟁사 최저가</th>
          </tr>
        </thead>
        <tbody>{table_body}</tbody>
      </table>
      <div class="top-grid">
        <section class="top-panel">
          <div class="top-panel-title">최저가 상위 20개(당사)</div>
          <div class="top-list">{own_top20_html}</div>
        </section>
        <section class="top-panel">
          <div class="top-panel-title">최저가 상위 20개(X사)</div>
          <div class="top-list">{competitor_top20_html}</div>
        </section>
      </div>
    </section>
    </main>
  </div>
</body>
</html>
"""
    file_path.write_text(html_text, encoding="utf-8")
    REPORT_META_PATH.write_text(
        json.dumps(
            {
                "report_path": str(file_path),
                "generated_at": generated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "summary": summary_lines,
                "stats": stats or {},
                "attachments": attachments or {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(file_path)
