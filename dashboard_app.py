import json
import mimetypes
import sys
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from config_manager import load_config, public_config, save_config
from naver_api import fetch_shop_results
from storage import (
    add_keyword,
    categories_payload,
    ensure_dirs,
    ensure_keyword_master,
    keyword_trend,
    latest_file,
    latest_summary_for_keyword,
    parse_file_time,
    previous_summary_for_keyword,
    read_keyword_master,
    read_snapshot,
    write_snapshot,
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


def collect_keyword(category, keyword, top_n=None):
    config = load_config()
    if not config.get("client_id") or not config.get("client_secret"):
        raise RuntimeError("네이버 API Key를 먼저 저장해주세요.")

    top_n = int(top_n or config.get("top_n") or 100)
    cooldown_minutes = int(config.get("cooldown_minutes") or 30)
    current_latest = latest_file(category, keyword)
    now = datetime.now()

    if current_latest:
        latest_dt = parse_file_time(current_latest)
        if now - latest_dt < timedelta(minutes=cooldown_minutes):
            df = read_snapshot(current_latest)
            summary = latest_summary_for_keyword(category, keyword)
            summary["source"] = "cache"
            summary["cooldown_until"] = (latest_dt + timedelta(minutes=cooldown_minutes)).strftime("%Y-%m-%d %H:%M:%S")
            return summary

    items, total = fetch_shop_results(
        config["client_id"],
        config["client_secret"],
        keyword,
        limit=top_n,
    )
    file_path, df = write_snapshot(category, keyword, items, total, now)
    summary = latest_summary_for_keyword(category, keyword)
    previous = previous_summary_for_keyword(category, keyword, file_path)
    summary["source"] = "api"
    summary["previous_avg_price"] = previous["avg_price"] if previous else None
    summary["avg_change"] = summary["avg_price"] - previous["avg_price"] if previous else None
    return summary


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
                return json_response(self, {"ok": True, "rows": latest_category_rows(category)})
            if path == "/api/trend":
                category = query.get("category", [""])[0]
                keyword = query.get("keyword", [""])[0]
                return json_response(self, {"ok": True, "trend": keyword_trend(category, keyword)})
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
                )
                return json_response(self, {"ok": True, "config": public_config()})

            if path == "/api/keyword":
                add_keyword(body.get("category", ""), body.get("keyword", ""), "N")
                return json_response(self, {"ok": True, "categories": categories_payload()})

            if path == "/api/collect":
                category = body.get("category", "").strip()
                keywords = body.get("keywords") or []
                top_n = int(body.get("top_n") or 100)
                if not category or not keywords:
                    return error_response(self, "카테고리와 키워드를 선택해주세요.")
                if len(keywords) > 10:
                    return error_response(self, "한 번에 최대 10개 키워드까지만 조회할 수 있습니다.")

                results = [collect_keyword(category, keyword, top_n) for keyword in keywords]
                return json_response(self, {"ok": True, "results": results, "rows": latest_category_rows(category)})

            return error_response(self, "알 수 없는 API 경로입니다.", status=404)
        except Exception as exc:
            return error_response(self, str(exc), status=500)

    def serve_static(self, request_path):
        if request_path == "/":
            request_path = "/dashboard.html"
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


def latest_category_rows(category):
    df = read_keyword_master()
    if category:
        df = df[df["category"] == category]

    rows = []
    for _, row in df.iterrows():
        summary = latest_summary_for_keyword(row["category"], row["keyword"])
        if not summary:
            summary = {
                "category": row["category"],
                "keyword": row["keyword"],
                "snapshot_time": "",
                "avg_price": 0,
                "min_price": 0,
                "max_price": 0,
                "count": 0,
                "search_total": 0,
                "items": [],
            }
        current_file = latest_file(row["category"], row["keyword"])
        previous = previous_summary_for_keyword(row["category"], row["keyword"], current_file) if current_file else None
        summary["is_default"] = row.get("is_default", "")
        summary["previous_avg_price"] = previous["avg_price"] if previous else None
        summary["avg_change"] = summary["avg_price"] - previous["avg_price"] if previous else None
        rows.append(summary)
    return rows


def run():
    ensure_dirs()
    ensure_keyword_master()
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    url = f"http://{HOST}:{PORT}/"
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"Dashboard running: {url}")
    server.serve_forever()


if __name__ == "__main__":
    run()
