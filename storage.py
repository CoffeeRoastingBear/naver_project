import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from naver_api import make_item_id, strip_html


DATA_DIR = Path("data")
KEYWORD_MASTER_PATH = Path("keyword_master.t1")
DEFAULT_KEYWORDS = {
    "냉장고": ["삼성냉장고", "비스포크냉장고", "양문형냉장고", "김치냉장고"],
    "세탁기": ["삼성세탁기", "비스포크세탁기", "드럼세탁기", "통돌이세탁기"],
    "에어컨": ["삼성에어컨", "무풍에어컨", "벽걸이에어컨", "스탠드에어컨"],
    "TV": ["삼성TV", "OLED TV", "QLED TV", "스마트TV"],
}


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def snapshot_name(dt=None):
    return (dt or datetime.now()).strftime("%Y%m%d_%H%M%S.t1")


def safe_part(value):
    value = str(value).strip()
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    return value[:80] or "unknown"


def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)


def ensure_keyword_master():
    if KEYWORD_MASTER_PATH.exists():
        return
    rows = []
    created_at = now_text()
    for category, keywords in DEFAULT_KEYWORDS.items():
        for keyword in keywords:
            rows.append(
                {
                    "category": category,
                    "keyword": keyword,
                    "is_default": "Y",
                    "created_at": created_at,
                }
            )
    pd.DataFrame(rows).to_csv(KEYWORD_MASTER_PATH, index=False, encoding="utf-8-sig")


def read_keyword_master():
    ensure_keyword_master()
    return pd.read_csv(KEYWORD_MASTER_PATH, encoding="utf-8-sig").fillna("")


def save_keyword_master(df):
    df.to_csv(KEYWORD_MASTER_PATH, index=False, encoding="utf-8-sig")


def add_keyword(category, keyword, is_default="N"):
    category = category.strip()
    keyword = keyword.strip()
    if not category or not keyword:
        raise ValueError("카테고리와 키워드를 입력해주세요.")

    df = read_keyword_master()
    exists = ((df["category"] == category) & (df["keyword"] == keyword)).any()
    if not exists:
        next_row = pd.DataFrame(
            [
                {
                    "category": category,
                    "keyword": keyword,
                    "is_default": is_default,
                    "created_at": now_text(),
                }
            ]
        )
        df = pd.concat([df, next_row], ignore_index=True)
        save_keyword_master(df)


def categories_payload():
    df = read_keyword_master()
    result = {}
    for category, group in df.groupby("category", sort=False):
        result[category] = group[["keyword", "is_default", "created_at"]].to_dict("records")
    return result


def keyword_dir(category, keyword):
    return DATA_DIR / safe_part(category) / safe_part(keyword)


def latest_file(category, keyword):
    folder = keyword_dir(category, keyword)
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.t1"), reverse=True)
    return files[0] if files else None


def parse_file_time(path):
    return datetime.strptime(path.stem, "%Y%m%d_%H%M%S")


def read_snapshot(path):
    return pd.read_csv(path, encoding="utf-8-sig").fillna("")


def write_snapshot(category, keyword, items, total, snapshot_time=None):
    ensure_dirs()
    snapshot_time = snapshot_time or datetime.now()
    folder = keyword_dir(category, keyword)
    folder.mkdir(parents=True, exist_ok=True)

    rows = []
    for rank, item in enumerate(items, start=1):
        rows.append(
            {
                "snapshot_time": snapshot_time.strftime("%Y-%m-%d %H:%M:%S"),
                "category": category,
                "keyword": keyword,
                "rank": rank,
                "item_id": make_item_id(item),
                "title": strip_html(item.get("title")),
                "link": item.get("link", ""),
                "mall_name": item.get("mallName", ""),
                "price": int(item.get("lprice") or 0),
                "brand": item.get("brand", ""),
                "maker": item.get("maker", ""),
                "product_type": item.get("productType", ""),
                "search_total": int(total or 0),
                "raw_json": json.dumps(item, ensure_ascii=False),
            }
        )

    df = pd.DataFrame(rows)
    file_path = folder / snapshot_name(snapshot_time)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path, df


def df_summary(df):
    if df.empty:
        return {
            "avg_price": 0,
            "min_price": 0,
            "max_price": 0,
            "count": 0,
            "search_total": 0,
        }
    prices = pd.to_numeric(df["price"], errors="coerce").dropna()
    return {
        "avg_price": int(prices.mean()) if not prices.empty else 0,
        "min_price": int(prices.min()) if not prices.empty else 0,
        "max_price": int(prices.max()) if not prices.empty else 0,
        "count": int(len(df)),
        "search_total": int(df["search_total"].iloc[0]) if "search_total" in df.columns and len(df) else 0,
    }


def latest_summary_for_keyword(category, keyword):
    path = latest_file(category, keyword)
    if not path:
        return None
    df = read_snapshot(path)
    summary = df_summary(df)
    summary.update(
        {
            "category": category,
            "keyword": keyword,
            "file": str(path),
            "snapshot_time": df["snapshot_time"].iloc[0] if len(df) else parse_file_time(path).strftime("%Y-%m-%d %H:%M:%S"),
            "items": df.head(20).to_dict("records"),
        }
    )
    return summary


def previous_summary_for_keyword(category, keyword, current_file):
    folder = keyword_dir(category, keyword)
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.t1"), reverse=True)
    previous = [path for path in files if path != current_file]
    if not previous:
        return None
    return df_summary(read_snapshot(previous[0]))


def keyword_trend(category, keyword):
    folder = keyword_dir(category, keyword)
    if not folder.exists():
        return []

    rows = []
    for path in sorted(folder.glob("*.t1")):
        df = read_snapshot(path)
        summary = df_summary(df)
        rows.append(
            {
                "snapshot_time": df["snapshot_time"].iloc[0] if len(df) else parse_file_time(path).strftime("%Y-%m-%d %H:%M:%S"),
                **summary,
            }
        )
    return rows

