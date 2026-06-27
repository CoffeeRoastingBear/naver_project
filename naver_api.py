import hashlib
import json
import time
import urllib.parse
import urllib.request


NAVER_SHOP_SEARCH_URL = "https://openapi.naver.com/v1/search/shop.json"


def strip_html(value):
    return (value or "").replace("<b>", "").replace("</b>", "")


def make_item_id(item):
    item_id = item.get("productId") or item.get("product_id")
    if item_id:
        return str(item_id)

    link = item.get("link")
    if link:
        return str(link)

    raw = "|".join(
        [
            item.get("title", ""),
            item.get("link", ""),
            item.get("mallName", ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def fetch_shop_results(client_id, client_secret, keyword, limit=100, sleep_seconds=0.4):
    limit = max(1, min(int(limit), 300))
    display = min(100, limit)
    items = []
    total = 0

    for start in range(1, limit + 1, display):
        params = urllib.parse.urlencode(
            {
                "query": keyword,
                "display": min(display, limit - len(items)),
                "start": start,
                "sort": "sim",
            }
        )
        request = urllib.request.Request(f"{NAVER_SHOP_SEARCH_URL}?{params}")
        request.add_header("X-Naver-Client-Id", client_id)
        request.add_header("X-Naver-Client-Secret", client_secret)

        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body)

        total = int(payload.get("total") or 0)
        page_items = payload.get("items") or []
        items.extend(page_items)

        if len(items) >= limit or not page_items:
            break

        time.sleep(float(sleep_seconds))

    return items[:limit], total

