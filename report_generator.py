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
                f"<small>{_esc(item.get('side') or '')} · {_esc(item.get('mall_name') or '-')} · "
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
    body {{ font-family: Arial, 'Malgun Gothic', sans-serif; margin: 24px; color: #17202a; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    .meta {{ color: #667085; margin-bottom: 20px; }}
    .summary {{ background: #f4f7fb; border: 1px solid #dce4ef; padding: 14px 18px; margin-bottom: 20px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e0e8; padding: 10px; vertical-align: top; }}
    th {{ background: #eef3f8; text-align: left; }}
    a {{ color: #175cd3; word-break: break-all; }}
    ol {{ margin: 0; padding-left: 20px; }}
    li {{ margin-bottom: 8px; }}
    .lowest hr {{ border: 0; border-top: 1px solid #e5e9f0; margin: 10px 0; }}
    .empty {{ text-align: center; color: #667085; }}
  </style>
</head>
<body>
  <h1>TV 가격 비교 * AI 요약</h1>
  <div class="meta">생성일시: {_esc(generated_at.strftime('%Y-%m-%d %H:%M:%S'))}</div>
  <section class="summary">
    <ol>{summary_html}</ol>
  </section>
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
</body>
</html>
"""
    file_path.write_text(html_text, encoding="utf-8")
    return str(file_path)
