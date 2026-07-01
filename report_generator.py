import html
from datetime import datetime
from pathlib import Path


REPORTS_DIR = Path("reports")


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


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _price_link(item):
    if not item:
        return "<div>-</div>"
    price = _fmt_price(item.get("lprice") or item.get("price"))
    rate = _fmt_rate(item.get("discount_rate"))
    link = str(item.get("link") or "").strip()
    if link:
        return f'<div><strong>{price}</strong> <span>{rate}</span><br><a href="{_esc(link)}">{_esc(link)}</a></div>'
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
            f"<small>{_esc(row.get('competitor_sku'))} · 기준가 {_fmt_price(row.get('base_price'))}</small>"
            "</div>"
        )
    return "".join(items) or "<div class=\"empty-side\">표시 모델 없음</div>"


def _top20_panel(rows):
    items = []
    for row in rows or []:
        for item in (row.get("low_items") or [])[:20]:
            items.append((row, item))
    items = sorted(items, key=lambda pair: (int(pair[1].get("lprice") or pair[1].get("price") or 0), float(pair[1].get("discount_rate") or 0)))[:20]

    blocks = []
    for index, (row, item) in enumerate(items, start=1):
        title = _esc(item.get("title") or "-")
        link = str(item.get("link") or "").strip()
        title_html = f'<a class="item-title" href="{_esc(link)}">{index}. {title}</a>' if link else f'<div class="item-title">{index}. {title}</div>'
        side = "경쟁사" if item.get("side") == "competitor" else "당사"
        blocks.append(
            "<div class=\"top-item\">"
            f"{title_html}"
            f"<div class=\"item-meta\">{side} · {_esc(row.get('own_sku'))} / {_esc(row.get('competitor_sku'))} · "
            f"{_esc(item.get('mall_name') or '-')} · {_fmt_price(item.get('lprice') or item.get('price'))} · {_fmt_rate(item.get('discount_rate'))}</div>"
            "</div>"
        )
    return "".join(blocks) or "<div class=\"empty\">기준가 대비 10% 이상 낮은 게시물이 없습니다.</div>"


def get_latest_report():
    """Return the newest generated HTML report path, or None.

    Mail automation must use this function and attach the returned file.
    It must not call Naver API or dashboard collection endpoints.
    """
    if not REPORTS_DIR.exists():
        return None
    reports = sorted(REPORTS_DIR.glob("price_report_*.html"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else None


def generate_price_report(rows, summary_lines=None, generated_at=None):
    """Write a standalone HTML report from already-collected dashboard rows."""
    REPORTS_DIR.mkdir(exist_ok=True)
    generated_at = generated_at or datetime.now()
    summary_lines = (summary_lines or [])[:3]
    file_path = REPORTS_DIR / f"price_report_{generated_at.strftime('%Y%m%d_%H%M%S')}.html"
    total_low_count = sum(int(row.get("low_count") or 0) for row in rows or [])
    max_discount = _max_discount(rows)
    sidebar_models = _model_sidebar(rows)
    top20_html = _top20_panel(rows)

    row_html = []
    for row in rows or []:
        top_items = []
        for index, item in enumerate((row.get("low_items") or [])[:20], start=1):
            title = _esc(item.get("title") or "-")
            link = str(item.get("link") or "").strip()
            title_html = f'<a href="{_esc(link)}">{title}</a>' if link else title
            top_items.append(
                "<li>"
                f"{title_html}<br>"
                f"<small>{'경쟁사' if item.get('side') == 'competitor' else '당사'} · {_esc(item.get('mall_name') or '-')} · "
                f"{_fmt_price(item.get('lprice') or item.get('price'))} · {_fmt_rate(item.get('discount_rate'))}</small>"
                "</li>"
            )

        row_html.append(
            "<tr>"
            f"<td><strong>{_esc(row.get('own_sku'))}</strong><br><small>경쟁사 {_esc(row.get('competitor_sku'))}</small></td>"
            f"<td>{_fmt_price(row.get('base_price'))}</td>"
            f"<td><div class=\"lowest\"><div>당사 최저가</div>{_price_link(row.get('own_lowest'))}"
            f"<hr><div>경쟁사 최저가</div>{_price_link(row.get('competitor_lowest'))}</div></td>"
            f"<td>{int(row.get('low_count') or 0):,}건</td>"
            f"<td><ol>{''.join(top_items)}</ol></td>"
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
  <title>TV 가격 비교 AI 요약 리포트</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: Arial, 'Malgun Gothic', sans-serif; margin: 0; background: #f3f6fa; color: #17202a; }}
    .layout {{ display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 100vh; }}
    .sidebar {{ background: #142235; color: #ffffff; padding: 22px 18px; }}
    .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 22px; }}
    .brand-mark {{ width: 34px; height: 34px; border-radius: 8px; background: #0bb15b; display: grid; place-items: center; font-weight: 800; }}
    .brand h1 {{ font-size: 19px; margin: 0; }}
    .brand p {{ color: #b9c5d2; margin: 3px 0 0; font-size: 12px; }}
    .panel {{ border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 14px; margin-bottom: 14px; background: rgba(255,255,255,0.04); }}
    .panel-title {{ font-size: 13px; font-weight: 700; color: #d7e2ef; margin-bottom: 10px; }}
    .category-pill {{ display: block; background: #ffffff; color: #142235; border-radius: 6px; padding: 9px 10px; font-weight: 700; }}
    .model-item {{ border-top: 1px solid rgba(255,255,255,0.12); padding: 10px 0; }}
    .model-item:first-of-type {{ border-top: 0; }}
    .model-item strong {{ display: block; font-size: 13px; }}
    .model-item small {{ display: block; color: #b9c5d2; line-height: 1.45; margin-top: 3px; }}
    .empty-side {{ color: #b9c5d2; font-size: 13px; }}
    .main {{ padding: 24px; min-width: 0; }}
    .hero {{ background: #ffffff; border: 1px solid #d9e0e8; padding: 20px 22px; border-radius: 8px; }}
    h2 {{ font-size: 24px; margin: 0 0 8px; }}
    .meta {{ color: #667085; margin-bottom: 14px; }}
    .summary ol {{ margin: 0; padding-left: 22px; color: #243447; }}
    .summary li {{ margin-bottom: 6px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 14px 0 18px; }}
    .metric {{ background: #ffffff; border: 1px solid #d9e0e8; border-radius: 8px; padding: 14px; }}
    .metric span {{ display: block; color: #667085; font-size: 12px; margin-bottom: 6px; }}
    .metric strong {{ font-size: 20px; }}
    .card {{ background: #ffffff; border: 1px solid #d9e0e8; border-radius: 8px; overflow: hidden; margin-bottom: 16px; }}
    .card-title {{ padding: 14px 16px; border-bottom: 1px solid #d9e0e8; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #d9e0e8; padding: 12px; vertical-align: top; }}
    th {{ background: #eef3f8; text-align: left; }}
    a {{ color: #175cd3; word-break: break-all; }}
    ol {{ margin: 0; padding-left: 20px; }}
    li {{ margin-bottom: 8px; }}
    .lowest hr {{ border: 0; border-top: 1px solid #e5e9f0; margin: 10px 0; }}
    .empty {{ text-align: center; color: #667085; }}
    .top-list {{ padding: 8px 16px 16px; }}
    .top-item {{ border-top: 1px solid #edf1f5; padding: 10px 0; }}
    .top-item:first-child {{ border-top: 0; }}
    .item-title {{ font-weight: 700; }}
    .item-meta {{ color: #667085; font-size: 12px; margin-top: 4px; }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ min-height: auto; }}
      .metrics {{ grid-template-columns: 1fr; }}
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
      <h2>TV 가격 비교 * AI 요약</h2>
      <div class="meta">기준가 대비 10% 이상 낮은 게시물 기준 · 생성일시: {_esc(generated_at.strftime('%Y-%m-%d %H:%M:%S'))}</div>
      <div class="summary"><ol>{summary_html}</ol></div>
    </section>
    <section class="metrics">
      <div class="metric"><span>표시 모델</span><strong>{len(rows or [])}</strong></div>
      <div class="metric"><span>저가 게시물 수</span><strong>{total_low_count:,}건</strong></div>
      <div class="metric"><span>최대 할인율</span><strong>{_fmt_rate(max_discount)}</strong></div>
    </section>
    <section class="card">
      <div class="card-title">최신 가격 비교</div>
      <table>
        <thead>
          <tr>
            <th>모델</th>
            <th>기준가</th>
            <th>최저가 게시물</th>
            <th>저가 게시물 수</th>
            <th>TOP20 게시물</th>
          </tr>
        </thead>
        <tbody>{table_body}</tbody>
      </table>
    </section>
    <section class="card">
      <div class="card-title">저가 게시물 TOP20</div>
      <div class="top-list">{top20_html}</div>
    </section>
    </main>
  </div>
</body>
</html>
"""
    file_path.write_text(html_text, encoding="utf-8")
    return str(file_path)
