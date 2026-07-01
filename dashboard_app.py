import json
import mimetypes
import sys
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from config_manager import cooldown_for_category, load_config, public_config, save_config, set_category_cooldown
from naver_api import fetch_shop_results
from report_generator import REPORTS_DIR, generate_price_report, get_latest_report
from storage import (
    add_keyword,
    ai_summary_for_rows,
    categories_payload,
    delete_keyword,
    empty_mapping_summary,
    ensure_dirs,
    ensure_keyword_master,
    generate_test_data,
    get_mapping,
    item_price_trend,
    latest_file,
    latest_summary_for_keyword,
    parse_file_time,
    previous_summary_for_keyword,
    read_keyword_master,
    write_mapping_snapshot,
)


BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765


def app_path(path):
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / path
    return BASE_DIR / path


def json_response(handler, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def error_response(handler, message, status=400):
    json_response(handler, {"ok": False, "error": message}, status=status)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def attach_previous(summary, previous):
    summary["previous_own_avg_price"] = previous["own"]["avg_price"] if previous else None
    summary["own_avg_change"] = summary["own"]["avg_price"] - previous["own"]["avg_price"] if previous else None
    summary["previous_competitor_avg_price"] = previous["competitor"]["avg_price"] if previous else None
    summary["competitor_avg_change"] = (
        summary["competitor"]["avg_price"] - previous["competitor"]["avg_price"] if previous else None
    )


def is_dashboard_row(summary):
    return (
        int(summary.get("base_price") or 0) > 0
        and bool(summary.get("has_competitor_price"))
        and int(summary.get("low_count") or 0) > 0
    )


def collect_keyword(category, keyword, top_n=None, product_type="all"):
    config = load_config()
    if not config.get("client_id") or not config.get("client_secret"):
        raise RuntimeError("네이버 API Key를 먼저 저장해주세요.")

    mapping = get_mapping(category, keyword)
    if not mapping:
        raise RuntimeError("등록된 모델코드 매핑을 찾을 수 없습니다.")

    top_n = int(top_n or config.get("top_n") or 100)
    cooldown_minutes = cooldown_for_category(category)
    current_latest = latest_file(category, keyword)
    now = datetime.now()

    if current_latest:
        latest_dt = parse_file_time(current_latest)
        if now - latest_dt < timedelta(minutes=cooldown_minutes):
            summary = latest_summary_for_keyword(category, keyword, product_type, mapping)
            summary["source"] = "cache"
            summary["cooldown_until"] = (latest_dt + timedelta(minutes=cooldown_minutes)).strftime("%Y-%m-%d %H:%M:%S")
            return summary

    own_items, own_total = fetch_shop_results(config["client_id"], config["client_secret"], mapping["own_sku"], limit=top_n)
    competitor_items, competitor_total = fetch_shop_results(
        config["client_id"], config["client_secret"], mapping["competitor_sku"], limit=top_n
    )
    file_path, _ = write_mapping_snapshot(category, keyword, own_items, competitor_items, own_total, competitor_total, mapping, now)
    summary = latest_summary_for_keyword(category, keyword, product_type, mapping)
    previous = previous_summary_for_keyword(category, keyword, file_path, product_type)
    summary["source"] = "api"
    attach_previous(summary, previous)
    return summary


def latest_category_rows(category, product_type="all"):
    df = read_keyword_master()
    if category:
        df = df[df["category"] == category]
    df = df[df["competitor_sku"].astype(str).str.strip() != ""]

    rows = []
    for _, row in df.iterrows():
        mapping = row.to_dict()
        summary = latest_summary_for_keyword(row["category"], row["keyword"], product_type, mapping)
        if not summary:
            summary = empty_mapping_summary(row["category"], mapping)
        current_file = latest_file(row["category"], row["keyword"])
        previous = previous_summary_for_keyword(row["category"], row["keyword"], current_file, product_type) if current_file else None
        summary["is_default"] = row.get("is_default", "")
        attach_previous(summary, previous)
        if is_dashboard_row(summary):
            rows.append(summary)
    return rows


def latest_rows_for_keywords(category, keywords, product_type="all"):
    rows = []
    for keyword in keywords:
        mapping = get_mapping(category, keyword) or {"keyword": keyword, "own_sku": keyword, "competitor_sku": "", "base_price": 0}
        summary = latest_summary_for_keyword(category, keyword, product_type, mapping)
        if not summary:
            summary = empty_mapping_summary(category, mapping)
        current_file = latest_file(category, keyword)
        previous = previous_summary_for_keyword(category, keyword, current_file, product_type) if current_file else None
        summary["is_default"] = mapping.get("is_default", "Y")
        attach_previous(summary, previous)
        if is_dashboard_row(summary):
            rows.append(summary)
    return rows


def rows_payload(rows):
    return {"rows": rows, "summary": ai_summary_for_rows(rows)}


def write_report_payload(rows):
    payload = rows_payload(rows)
    report_path = generate_price_report(rows, payload["summary"])
    return {**payload, "report": {"path": report_path}}


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        try:
            if path == "/api/config":
                return json_response(self, {"ok": True, "config": public_config()})
            if path == "/api/categories":
                return json_response(self, {"ok": True, "categories": categories_payload()})
            if path == "/api/latest":
                category = query.get("category", [""])[0]
                product_type = query.get("product_type", ["all"])[0]
                rows = latest_category_rows(category, product_type)
                return json_response(self, {"ok": True, **rows_payload(rows)})
            if path == "/api/report/latest":
                return json_response(self, {"ok": True, "report": {"path": get_latest_report()}})
            if path == "/api/trend":
                category = query.get("category", [""])[0]
                keyword = query.get("keyword", [""])[0]
                product_type = query.get("product_type", ["all"])[0]
                mapping = get_mapping(category, keyword)
                return json_response(self, {"ok": True, "mapping": mapping, "trend": item_price_trend(category, keyword, product_type)})
            return self.serve_static(path)
        except Exception as exc:
            return error_response(self, str(exc), status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            body = read_json_body(self)
            if path == "/api/config":
                save_config(
                    body.get("client_id", ""),
                    body.get("client_secret", ""),
                    body.get("top_n", 100),
                    body.get("cooldown_minutes", 30),
                    body.get("category_cooldowns"),
                )
                return json_response(self, {"ok": True, "config": public_config()})

            if path == "/api/category_cooldown":
                set_category_cooldown(body.get("category", ""), body.get("minutes", 30))
                return json_response(self, {"ok": True, "config": public_config()})

            if path == "/api/test_data":
                result = generate_test_data()
                rows = latest_rows_for_keywords(result["category"], result["keywords"], body.get("product_type") or "all")
                return json_response(
                    self,
                    {"ok": True, "result": result, "categories": categories_payload(), **write_report_payload(rows)},
                )

            if path == "/api/keyword":
                add_keyword(
                    body.get("category", ""),
                    is_default="N",
                    own_sku=body.get("own_sku", ""),
                    competitor_sku=body.get("competitor_sku", ""),
                    base_price=body.get("base_price", 0),
                )
                return json_response(self, {"ok": True, "categories": categories_payload()})

            if path == "/api/delete_keyword":
                delete_keyword(body.get("category", ""), body.get("keyword", ""))
                return json_response(self, {"ok": True, "categories": categories_payload()})

            if path == "/api/collect":
                category = body.get("category", "").strip()
                keywords = body.get("keywords") or []
                top_n = int(body.get("top_n") or 100)
                product_type = body.get("product_type") or "all"
                if not category or not keywords:
                    return error_response(self, "카테고리와 모델코드를 선택해주세요.")
                if len(keywords) > 10:
                    return error_response(self, "한 번에 최대 10개 모델까지만 조회할 수 있습니다.")

                results = [collect_keyword(category, keyword, top_n, product_type) for keyword in keywords]
                rows = latest_category_rows(category, product_type)
                return json_response(self, {"ok": True, "results": results, **write_report_payload(rows)})

            return error_response(self, "없는 API 경로입니다.", status=404)
        except Exception as exc:
            return error_response(self, str(exc), status=500)

    def serve_static(self, request_path):
        if request_path == "/":
            request_path = "/dashboard.html"
        if request_path.startswith("/reports/"):
            target = Path.cwd() / request_path.lstrip("/")
        else:
            target = app_path(request_path.lstrip("/"))
        if not target.exists() or not target.is_file():
            return error_response(self, "파일을 찾을 수 없습니다.", status=404)

        mime, _ = mimetypes.guess_type(str(target))
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run():
    ensure_dirs()
    REPORTS_DIR.mkdir(exist_ok=True)
    ensure_keyword_master()
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    url = f"http://{HOST}:{PORT}/"
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"Dashboard running: {url}")
    server.serve_forever()


if __name__ == "__main__":
    run()
