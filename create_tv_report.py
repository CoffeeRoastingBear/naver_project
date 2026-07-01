import os
from datetime import datetime

import pandas as pd

from config_manager import load_config
from naver_api import fetch_shop_results
from report_generator import REPORTS_DIR, generate_price_report
from storage import (
    add_discount_columns,
    ai_summary_for_rows,
    latest_summary_for_keyword,
    read_keyword_master,
    write_mapping_snapshot,
)


CATEGORY = "TV"
TOP_N = 100


def naver_credentials():
    client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        return client_id, client_secret

    config = load_config()
    client_id = config.get("client_id", "").strip()
    client_secret = config.get("client_secret", "").strip()
    if client_id and client_secret:
        return client_id, client_secret

    raise RuntimeError("NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 또는 로컬 config.json API Key가 필요합니다.")


def tv_default_mappings():
    df = read_keyword_master()
    df = df[
        (df["category"] == CATEGORY)
        & (df["is_default"].astype(str).str.upper() == "Y")
        & (df["own_sku"].astype(str).str.strip() != "")
        & (df["competitor_sku"].astype(str).str.strip() != "")
        & (df["base_price"].astype(int) > 0)
    ].copy()
    if df.empty:
        raise RuntimeError("TV 기본 모델 7개를 찾을 수 없습니다. keyword_master.t1을 확인해주세요.")
    return [row.to_dict() for _, row in df.iterrows()]


def create_tv_report():
    client_id, client_secret = naver_credentials()
    snapshot_time = datetime.now()
    mappings = tv_default_mappings()
    rows = []
    collected_frames = []
    model_stats = []

    for mapping in mappings:
        own_sku = mapping["own_sku"]
        competitor_sku = mapping["competitor_sku"]
        keyword = mapping["keyword"]
        print(f"Collecting {own_sku} / {competitor_sku}")

        own_items, own_total = fetch_shop_results(client_id, client_secret, own_sku, limit=TOP_N)
        competitor_items, competitor_total = fetch_shop_results(client_id, client_secret, competitor_sku, limit=TOP_N)
        _, snapshot_df = write_mapping_snapshot(
            CATEGORY,
            keyword,
            own_items,
            competitor_items,
            own_total,
            competitor_total,
            mapping,
            snapshot_time,
        )
        snapshot_df = add_discount_columns(snapshot_df, mapping["base_price"])
        snapshot_df["own_sku"] = own_sku
        snapshot_df["competitor_sku"] = competitor_sku
        snapshot_df["base_price"] = int(mapping["base_price"] or 0)
        collected_frames.append(snapshot_df)
        model_stats.append(
            {
                "own_sku": own_sku,
                "competitor_sku": competitor_sku,
                "own_total": int(own_total or 0),
                "competitor_total": int(competitor_total or 0),
                "total": int(own_total or 0) + int(competitor_total or 0),
            }
        )

        summary = latest_summary_for_keyword(CATEGORY, keyword, "all", mapping)
        if (
            summary
            and int(summary.get("base_price") or 0) > 0
            and bool(summary.get("has_competitor_price"))
            and int(summary.get("low_count") or 0) > 0
        ):
            rows.append(summary)

    summary_lines = ai_summary_for_rows(rows)
    REPORTS_DIR.mkdir(exist_ok=True)
    data_path = REPORTS_DIR / f"price_data_{snapshot_time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    all_data = pd.concat(collected_frames, ignore_index=True) if collected_frames else pd.DataFrame()
    with pd.ExcelWriter(data_path, engine="openpyxl") as writer:
        pd.DataFrame(model_stats).to_excel(writer, sheet_name="keyword_summary", index=False)
        all_data.to_excel(writer, sheet_name="naver_raw_data", index=False)
        pd.DataFrame(rows).drop(columns=["low_items", "items"], errors="ignore").to_excel(writer, sheet_name="dashboard_summary", index=False)

    stats = {
        "category": CATEGORY,
        "keyword_count": len(mappings),
        "displayed_model_count": len(rows),
        "total_search_count": sum(item["total"] for item in model_stats),
        "model_stats": model_stats,
    }
    report_path = generate_price_report(
        rows,
        summary_lines,
        generated_at=snapshot_time,
        stats=stats,
        attachments={"xlsx": str(data_path)},
    )
    print(f"Created TV report: {report_path}")
    print(f"Created XLSX data: {data_path}")
    print(f"Dashboard rows: {len(rows)}")
    return report_path


if __name__ == "__main__":
    create_tv_report()
