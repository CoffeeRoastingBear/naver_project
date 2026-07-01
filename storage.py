import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from naver_api import make_item_id, strip_html


DATA_DIR = Path("data")
KEYWORD_MASTER_PATH = Path("keyword_master.t1")
LOW_DISCOUNT_RATE = -10.0

MASTER_COLUMNS = ["category", "keyword", "own_sku", "competitor_sku", "base_price", "is_default", "created_at"]
LEGACY_COLUMNS = ["category", "keyword", "is_default", "created_at"]
MASTER_EXPORT_COLUMNS = {
    "category": "카테고리",
    "keyword": "매핑키",
    "own_sku": "당사 모델코드",
    "competitor_sku": "경쟁사 모델코드",
    "base_price": "기준가",
    "is_default": "기본여부",
    "created_at": "등록일시",
}
MASTER_IMPORT_COLUMNS = {label: key for key, label in MASTER_EXPORT_COLUMNS.items()}

CATEGORY_NAMES = [
    "TV",
    "모니터",
    "오디오",
    "냉장고",
    "냉동고",
    "와인 냉장고",
    "김치냉장고",
    "정수기",
    "세탁기",
    "건조기",
    "에어드레서(슈드레서 포함)",
    "인덕션",
    "식기세척기",
    "오븐",
    "전자레인지",
    "후드",
    "청소기",
    "에어컨",
    "가정용 환기시스템",
    "공기청정기",
    "제습기",
    "선풍기",
    "LED 조명",
    "프린터(A3 복합기 제외)",
    "갤럭시 스마트폰(이동통신사)",
    "갤럭시 스마트폰(자급제)",
    "갤럭시 탭(이동통신사)",
    "PC(갤럭시 북, 데스크탑)",
    "갤럭시 워치",
    "갤럭시 버즈",
    "갤럭시 링",
    "갤럭시 핏",
    "갤럭시 XR",
    "갤럭시 탭(자급제)",
]


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def snapshot_name(dt=None):
    return (dt or datetime.now()).strftime("%Y%m%d_%H%M%S.t1")


def mapping_key(own_sku, competitor_sku):
    own_sku = str(own_sku or "").strip().upper()
    competitor_sku = str(competitor_sku or "").strip().upper()
    return f"{own_sku}__{competitor_sku}"


def display_name(row):
    own_sku = str(row.get("own_sku") or row.get("keyword") or "").strip()
    competitor_sku = str(row.get("competitor_sku") or "").strip()
    return f"{own_sku} / {competitor_sku}" if competitor_sku else own_sku


def safe_part(value):
    value = str(value).strip()
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    return value[:120] or "unknown"


def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)


def ensure_keyword_master():
    if KEYWORD_MASTER_PATH.exists():
        return
    save_keyword_master(pd.DataFrame(columns=MASTER_COLUMNS))


def read_keyword_master():
    ensure_keyword_master()
    skiprows = 0
    for encoding in ("utf-8-sig", "cp949"):
        try:
            with KEYWORD_MASTER_PATH.open("r", encoding=encoding) as file:
                if file.readline().strip().lower().startswith("sep="):
                    skiprows = 1
            break
        except UnicodeDecodeError:
            continue

    try:
        df = pd.read_csv(KEYWORD_MASTER_PATH, encoding="utf-8-sig", sep=None, engine="python", skiprows=skiprows).fillna("")
    except UnicodeDecodeError:
        df = pd.read_csv(KEYWORD_MASTER_PATH, encoding="cp949", sep=None, engine="python", skiprows=skiprows).fillna("")
    df = df.rename(columns=MASTER_IMPORT_COLUMNS)

    for column in LEGACY_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    if "own_sku" not in df.columns:
        df["own_sku"] = df["keyword"]
    if "competitor_sku" not in df.columns:
        df["competitor_sku"] = ""
    if "base_price" not in df.columns:
        df["base_price"] = 0

    df["own_sku"] = df["own_sku"].astype(str).str.strip().str.upper()
    df["competitor_sku"] = df["competitor_sku"].astype(str).str.strip().str.upper()
    if not df.empty:
        df["keyword"] = df.apply(
            lambda row: mapping_key(row["own_sku"], row["competitor_sku"]) if row["competitor_sku"] else str(row["keyword"]).strip(),
            axis=1,
        )
    df["base_price"] = pd.to_numeric(df["base_price"], errors="coerce").fillna(0).astype(int)
    return df[MASTER_COLUMNS]


def save_keyword_master(df):
    df = df.copy()
    for column in MASTER_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    export_df = df[MASTER_COLUMNS].rename(columns=MASTER_EXPORT_COLUMNS)
    csv_text = export_df.to_csv(index=False)
    with KEYWORD_MASTER_PATH.open("w", encoding="cp949", newline="") as file:
        file.write("sep=,\n")
        file.write(csv_text)


def add_keyword(category, keyword=None, is_default="N", own_sku=None, competitor_sku=None, base_price=0):
    category = str(category or "").strip()
    own_sku = str(own_sku or keyword or "").strip().upper()
    competitor_sku = str(competitor_sku or "").strip().upper()
    if not category or not own_sku or not competitor_sku:
        raise ValueError("카테고리, 당사 모델코드, 경쟁사 모델코드를 모두 입력해주세요.")

    keyword = mapping_key(own_sku, competitor_sku)
    base_price = int(float(base_price or 0))
    df = read_keyword_master()
    exists = ((df["category"] == category) & (df["keyword"] == keyword)).any()
    if not exists:
        next_row = pd.DataFrame(
            [
                {
                    "category": category,
                    "keyword": keyword,
                    "own_sku": own_sku,
                    "competitor_sku": competitor_sku,
                    "base_price": base_price,
                    "is_default": is_default,
                    "created_at": now_text(),
                }
            ]
        )
        df = pd.concat([df, next_row], ignore_index=True)
        save_keyword_master(df)


def delete_keyword(category, keyword):
    df = read_keyword_master()
    mask = (df["category"] == category) & (df["keyword"] == keyword)
    if mask.any():
        save_keyword_master(df[~mask])


def categories_payload():
    df = read_keyword_master()
    result = {category: [] for category in CATEGORY_NAMES}
    df = df[df["competitor_sku"].astype(str).str.strip() != ""]
    for category, group in df.groupby("category", sort=False):
        result.setdefault(category, [])
        records = []
        for _, row in group.iterrows():
            item = row.to_dict()
            item["display_name"] = display_name(row)
            records.append(item)
        result[category] = records
    return result


def get_mapping(category, keyword):
    df = read_keyword_master()
    match = df[(df["category"] == category) & (df["keyword"] == keyword)]
    if match.empty:
        return None
    row = match.iloc[0].to_dict()
    row["display_name"] = display_name(row)
    return row


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
    df = pd.read_csv(path, encoding="utf-8-sig").fillna("")
    if "price" not in df.columns and "lprice" in df.columns:
        df["price"] = df["lprice"]
    if "lprice" not in df.columns and "price" in df.columns:
        df["lprice"] = df["price"]
    if "hprice" not in df.columns:
        df["hprice"] = ""
    if "product_id" not in df.columns:
        df["product_id"] = df.get("item_id", "")
    if "product_type" not in df.columns and "productType" in df.columns:
        df["product_type"] = df["productType"]
    if "product_type" not in df.columns:
        df["product_type"] = ""
    if "side" not in df.columns:
        df["side"] = "own"
    if "sku" not in df.columns:
        df["sku"] = df.get("keyword", "")
    return df


def normalize_product_type(value):
    value = str(value or "all")
    return "all" if value == "all" else value


def filter_product_type(df, product_type="all"):
    product_type = normalize_product_type(product_type)
    if product_type == "all" or "product_type" not in df.columns:
        return df
    return df[df["product_type"].astype(str) == product_type]


def write_snapshot(category, keyword, items, total, snapshot_time=None, side="own", sku=None):
    ensure_dirs()
    snapshot_time = snapshot_time or datetime.now()
    folder = keyword_dir(category, keyword)
    folder.mkdir(parents=True, exist_ok=True)

    rows = []
    for rank, item in enumerate(items, start=1):
        product_id = str(item.get("productId") or "")
        item_id = make_item_id(item)
        lprice = int(item.get("lprice") or 0)
        rows.append(
            {
                "snapshot_time": snapshot_time.strftime("%Y-%m-%d %H:%M:%S"),
                "category": category,
                "keyword": keyword,
                "side": side,
                "sku": sku or item.get("sku", ""),
                "rank": rank,
                "item_id": item_id,
                "product_id": product_id or item_id,
                "product_type": str(item.get("productType", "")),
                "title": strip_html(item.get("title")),
                "mall_name": item.get("mallName", ""),
                "lprice": lprice,
                "hprice": int(item.get("hprice") or 0),
                "price": lprice,
                "link": item.get("link", ""),
                "brand": item.get("brand", ""),
                "maker": item.get("maker", ""),
                "search_total": int(total or 0),
                "raw_json": json.dumps(item, ensure_ascii=False),
            }
        )

    df = pd.DataFrame(rows)
    file_path = folder / snapshot_name(snapshot_time)
    if file_path.exists():
        existing = read_snapshot(file_path)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path, df


def write_mapping_snapshot(category, keyword, own_items, competitor_items, own_total, competitor_total, mapping, snapshot_time=None):
    snapshot_time = snapshot_time or datetime.now()
    file_path, _ = write_snapshot(category, keyword, own_items, own_total, snapshot_time, "own", mapping["own_sku"])
    file_path, df = write_snapshot(category, keyword, competitor_items, competitor_total, snapshot_time, "competitor", mapping["competitor_sku"])
    return file_path, df


def _price_series(df):
    return pd.to_numeric(df.get("lprice", df.get("price")), errors="coerce").dropna()


def df_summary(df, product_type="all"):
    df = filter_product_type(df, product_type)
    if df.empty:
        return {"avg_price": 0, "min_price": 0, "max_price": 0, "count": 0, "search_total": 0, "min_url": "", "max_url": ""}

    prices = _price_series(df)
    if prices.empty:
        return {"avg_price": 0, "min_price": 0, "max_price": 0, "count": int(len(df)), "search_total": 0, "min_url": "", "max_url": ""}

    min_index = prices.idxmin()
    max_index = prices.idxmax()
    return {
        "avg_price": int(prices.mean()),
        "min_price": int(prices.min()),
        "max_price": int(prices.max()),
        "count": int(len(df)),
        "search_total": int(df["search_total"].iloc[0]) if "search_total" in df.columns and len(df) else 0,
        "min_url": str(df.loc[min_index].get("link", "")),
        "max_url": str(df.loc[max_index].get("link", "")),
    }


def side_summary(df, side, product_type="all"):
    return df_summary(df[df["side"].astype(str) == side], product_type)


def discount_rate(price, base_price):
    try:
        base_price = float(base_price or 0)
        price = float(price or 0)
    except (TypeError, ValueError):
        return None
    if base_price <= 0 or price <= 0:
        return None
    return ((price - base_price) / base_price) * 100


def add_discount_columns(df, base_price):
    df = df.copy()
    if df.empty:
        df["discount_rate"] = []
        df["discount_percent"] = []
        return df
    df["lprice"] = pd.to_numeric(df.get("lprice", df.get("price")), errors="coerce")
    df["discount_rate"] = df["lprice"].apply(lambda price: discount_rate(price, base_price))
    df["discount_percent"] = df["discount_rate"].apply(lambda value: abs(float(value)) if value is not None and value <= 0 else 0)
    return df


def low_price_items(df, base_price, side=None):
    df = add_discount_columns(df, base_price)
    if side:
        df = df[df["side"].astype(str) == side]
    if df.empty:
        return df
    return df[df["discount_rate"].apply(lambda value: value is not None and value <= LOW_DISCOUNT_RATE)]


def item_record(row):
    value = row.to_dict()
    value["lprice"] = int(value.get("lprice") or value.get("price") or 0)
    value["price"] = int(value.get("price") or value.get("lprice") or 0)
    rate = value.get("discount_rate")
    value["discount_rate"] = round(float(rate), 2) if rate is not None and not pd.isna(rate) else None
    value["discount_percent"] = round(abs(value["discount_rate"]), 2) if value["discount_rate"] is not None else 0
    return value


def lowest_item_payload(df):
    if df.empty:
        return None
    sorted_df = df.sort_values(["lprice", "discount_percent"], ascending=[True, False])
    return item_record(sorted_df.iloc[0])


def top_low_items(df, limit=20):
    if df.empty:
        return []
    sorted_df = df.sort_values(["lprice", "discount_percent"], ascending=[True, False])
    return [item_record(row) for _, row in sorted_df.head(limit).iterrows()]


def empty_mapping_summary(category, mapping):
    return {
        "category": category,
        "keyword": mapping["keyword"],
        "display_name": mapping.get("display_name") or display_name(mapping),
        "own_sku": mapping.get("own_sku", ""),
        "competitor_sku": mapping.get("competitor_sku", ""),
        "base_price": int(mapping.get("base_price") or 0),
        "snapshot_time": "",
        "own": df_summary(pd.DataFrame()),
        "competitor": df_summary(pd.DataFrame()),
        "own_lowest": None,
        "competitor_lowest": None,
        "low_count": 0,
        "low_items": [],
        "items": [],
    }


def latest_summary_for_keyword(category, keyword, product_type="all", mapping=None):
    mapping = mapping or get_mapping(category, keyword) or {"keyword": keyword, "own_sku": keyword, "competitor_sku": "", "base_price": 0}
    base_price = int(mapping.get("base_price") or 0)
    path = latest_file(category, keyword)
    if not path:
        return None

    df = filter_product_type(read_snapshot(path), product_type)
    own_df = df[df["side"].astype(str) == "own"]
    competitor_df = df[df["side"].astype(str) == "competitor"]
    low_df = low_price_items(df, base_price)
    own_low_df = low_price_items(df, base_price, "own")
    competitor_low_df = low_price_items(df, base_price, "competitor")
    snapshot_time = df["snapshot_time"].iloc[0] if len(df) and "snapshot_time" in df.columns else parse_file_time(path).strftime("%Y-%m-%d %H:%M:%S")

    summary = {
        **df_summary(low_df, "all"),
        "category": category,
        "keyword": keyword,
        "display_name": mapping.get("display_name") or display_name(mapping),
        "own_sku": mapping.get("own_sku", ""),
        "competitor_sku": mapping.get("competitor_sku", ""),
        "base_price": base_price,
        "file": str(path),
        "snapshot_time": snapshot_time,
        "own": df_summary(own_df, "all"),
        "competitor": df_summary(competitor_df, "all"),
        "own_low": df_summary(own_low_df, "all"),
        "competitor_low": df_summary(competitor_low_df, "all"),
        "own_lowest": lowest_item_payload(own_low_df),
        "competitor_lowest": lowest_item_payload(competitor_low_df),
        "low_count": int(len(low_df)),
        "low_items": top_low_items(low_df, 20),
        "items": top_low_items(low_df, 20),
        "has_competitor_price": bool(len(_price_series(competitor_df))),
    }
    return summary


def previous_summary_for_keyword(category, keyword, current_file, product_type="all"):
    folder = keyword_dir(category, keyword)
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.t1"), reverse=True)
    previous = [path for path in files if path != current_file]
    if not previous:
        return None
    df = read_snapshot(previous[0])
    return {"own": side_summary(df, "own", product_type), "competitor": side_summary(df, "competitor", product_type), **df_summary(df, product_type)}


def item_price_trend(category, keyword, product_type="all", target_count=8):
    folder = keyword_dir(category, keyword)
    if not folder.exists():
        return {"snapshots": [], "own": {"series": []}, "competitor": {"series": []}}

    files = sorted(folder.glob("*.t1"))
    snapshots = []
    latest_by_side = {"own": None, "competitor": None}
    for path in files:
        df = filter_product_type(read_snapshot(path), product_type).copy()
        snapshot_time = parse_file_time(path).strftime("%Y-%m-%d %H:%M:%S")
        if not df.empty:
            df["lprice"] = pd.to_numeric(df["lprice"], errors="coerce")
            df["item_key"] = df["product_id"].astype(str).where(df["product_id"].astype(str) != "", df["item_id"].astype(str))
            snapshot_time = df["snapshot_time"].iloc[0] if "snapshot_time" in df.columns else snapshot_time
            for side in latest_by_side:
                side_df = df[df["side"].astype(str) == side]
                if not side_df.empty:
                    latest_by_side[side] = side_df
        snapshots.append({"time": snapshot_time, "df": df})

    def build_side(side):
        latest_df = latest_by_side[side]
        if latest_df is None or latest_df.empty:
            return {"series": []}
        threshold = max(1, math.ceil(len(snapshots) * 0.45))
        by_key = {}
        for snap in snapshots:
            side_df = snap["df"][snap["df"]["side"].astype(str) == side]
            for _, row in side_df.iterrows():
                key = str(row.get("item_key", ""))
                if not key:
                    continue
                by_key.setdefault(
                    key,
                    {
                        "item_id": str(row.get("item_id", "")),
                        "product_id": str(row.get("product_id", "")),
                        "title": str(row.get("title", "")),
                        "mall_name": str(row.get("mall_name", "")),
                        "link": str(row.get("link", "")),
                        "points": {},
                    },
                )
                by_key[key]["points"][snap["time"]] = int(row.get("lprice") or 0)

        latest_candidates = [str(row.get("item_key", "")) for _, row in latest_df.sort_values("rank").iterrows()]
        selected = []
        for key in latest_candidates:
            if len(selected) >= target_count:
                break
            if key in by_key and len(by_key[key]["points"]) >= threshold:
                selected.append(key)
        for key in latest_candidates:
            if len(selected) >= target_count:
                break
            if key in by_key and key not in selected:
                selected.append(key)
        return {"threshold": threshold, "series": [{**by_key[key], "visible_count": len(by_key[key]["points"])} for key in selected]}

    return {
        "snapshots": [item["time"] for item in snapshots],
        "own": build_side("own"),
        "competitor": build_side("competitor"),
    }


def ai_summary_for_rows(rows):
    active = [row for row in rows if int(row.get("low_count") or 0) > 0]
    if not active:
        return [
            "현재 기준가 대비 10% 이상 낮은 게시물이 있는 모델이 없습니다.",
            "기준가 또는 경쟁사 가격이 없는 모델은 요약에서 제외했습니다.",
            "상세 게시물은 URL 클릭 시 확인 가능합니다.",
        ]

    most_count = max(active, key=lambda row: int(row.get("low_count") or 0))
    all_items = []
    for row in active:
        for item in row.get("low_items") or []:
            all_items.append((row, item))
    biggest = min(all_items, key=lambda pair: pair[1].get("discount_rate", 0)) if all_items else None
    if biggest:
        biggest_model, biggest_item = biggest
        biggest_text = (
            f"기준가 대비 가격 차이가 가장 큰 모델은 {biggest_model.get('own_sku')}이며 "
            f"최대 {abs(float(biggest_item.get('discount_rate') or 0)):.1f}% 낮습니다."
        )
    else:
        biggest_text = "기준가 대비 가격 차이가 가장 큰 모델을 계산할 수 없습니다."

    return [
        f"현재 기준가 대비 저가 게시물이 가장 많은 모델은 {most_count.get('own_sku')}이며 총 {int(most_count.get('low_count') or 0)}건입니다.",
        biggest_text,
        "상세 게시물은 URL 클릭 시 확인 가능합니다.",
    ]


def generate_test_data():
    category = "TV - test 시안"
    mappings = [
        {"own_sku": "KQ85QD80AFXKR", "competitor_sku": "OLED85C5KNA", "base_price": 4590000},
        {"own_sku": "KQ75QD80AFXKR", "competitor_sku": "OLED77C5KNA", "base_price": 3290000},
        {"own_sku": "KQ65QD80AFXKR", "competitor_sku": "OLED65C5KNA", "base_price": 2190000},
        {"own_sku": "KQ85QND90AFXKR", "competitor_sku": "OLED83G5KNA", "base_price": 6290000},
        {"own_sku": "KQ55QD80AFXKR", "competitor_sku": "OLED55C5KNA", "base_price": 1590000},
    ]
    created_at = now_text()
    existing = read_keyword_master()
    test_keywords = [mapping_key(item["own_sku"], item["competitor_sku"]) for item in mappings]
    existing = existing[~((existing["keyword"].isin(test_keywords)) & (existing["category"].isin(["TV", category])))]
    master_rows = []
    base_time = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=6)
    own_malls = ["삼성공식스토어", "삼성전자파트너", "하이마트", "전자랜드"]
    competitor_malls = ["LG공식스토어", "베스트샵", "온라인가전몰", "프리미엄TV샵"]

    for mapping_index, mapping in enumerate(mappings):
        keyword = mapping_key(mapping["own_sku"], mapping["competitor_sku"])
        master_rows.append({**mapping, "category": category, "keyword": keyword, "is_default": "Y", "created_at": created_at})
        for snap_index in range(12):
            snapshot_time = base_time + timedelta(minutes=snap_index * 30)
            own_items = []
            competitor_items = []
            for rank in range(1, 9):
                own_base = mapping["base_price"] * 0.88 + rank * 18000 + mapping_index * 25000
                competitor_base = mapping["base_price"] * 0.84 + rank * 22000 + mapping_index * 30000
                own_wave = ((snap_index % 4) - 1.5) * 26000
                competitor_wave = ((snap_index % 5) - 2) * 36000
                own_trend = -snap_index * (9000 + rank * 500)
                competitor_trend = -snap_index * (11000 + rank * 650)
                own_price = max(450000, int(own_base + own_wave + own_trend + ((rank * 11 + snap_index) % 5) * 9000))
                competitor_price = max(450000, int(competitor_base + competitor_wave + competitor_trend + ((rank * 7 + snap_index) % 6) * 11000))
                own_id = f"OWN-{mapping_index + 1:02d}-{rank:02d}"
                comp_id = f"COMP-{mapping_index + 1:02d}-{rank:02d}"
                own_items.append(
                    {
                        "productId": own_id,
                        "productType": "1",
                        "title": f"삼성 {mapping['own_sku']} Neo QLED TV 패키지 {rank}",
                        "link": f"https://shopping.naver.com/test/{own_id}",
                        "mallName": own_malls[(rank + mapping_index) % len(own_malls)],
                        "lprice": str(own_price),
                        "hprice": str(own_price + 55000),
                        "brand": "Samsung",
                        "maker": "Samsung Electronics",
                    }
                )
                competitor_items.append(
                    {
                        "productId": comp_id,
                        "productType": "1",
                        "title": f"경쟁사 {mapping['competitor_sku']} OLED TV 패키지 {rank}",
                        "link": f"https://shopping.naver.com/test/{comp_id}",
                        "mallName": competitor_malls[(rank + mapping_index) % len(competitor_malls)],
                        "lprice": str(competitor_price),
                        "hprice": str(competitor_price + 65000),
                        "brand": "Competitor",
                        "maker": "Competitor Electronics",
                    }
                )
            write_mapping_snapshot(
                category,
                keyword,
                own_items,
                competitor_items,
                own_total=850 + mapping_index * 70,
                competitor_total=780 + mapping_index * 65,
                mapping={**mapping, "keyword": keyword},
                snapshot_time=snapshot_time,
            )

    merged = pd.concat([existing, pd.DataFrame(master_rows, columns=MASTER_COLUMNS)], ignore_index=True)
    save_keyword_master(merged)
    return {"category": category, "keywords": [row["keyword"] for row in master_rows], "snapshots": 12}
