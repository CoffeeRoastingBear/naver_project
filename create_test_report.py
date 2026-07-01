from report_generator import generate_price_report


def main():
    rows = [
        {
            "own_sku": "KQ85QNF80AFXKR",
            "competitor_sku": "86QNED80",
            "base_price": 3720790,
            "low_count": 3,
            "own_lowest": {
                "lprice": 3290000,
                "discount_rate": -11.56,
                "link": "https://shopping.naver.com/test/own-kq85",
            },
            "competitor_lowest": {
                "lprice": 3180000,
                "discount_rate": -14.52,
                "link": "https://shopping.naver.com/test/competitor-86qned80",
            },
            "low_items": [
                {
                    "side": "competitor",
                    "title": "86QNED80 테스트 최저가 게시물",
                    "mall_name": "Test Mall",
                    "lprice": 3180000,
                    "discount_rate": -14.52,
                    "link": "https://shopping.naver.com/test/competitor-86qned80",
                },
                {
                    "side": "own",
                    "title": "KQ85QNF80AFXKR 테스트 저가 게시물",
                    "mall_name": "Samsung Test Mall",
                    "lprice": 3290000,
                    "discount_rate": -11.56,
                    "link": "https://shopping.naver.com/test/own-kq85",
                },
            ],
        }
    ]
    summary = [
        "현재 기준가 대비 저가 게시물이 가장 많은 모델은 KQ85QNF80AFXKR이며 총 3건입니다.",
        "기준가 대비 가격 차이가 가장 큰 모델은 KQ85QNF80AFXKR이며 최대 14.5% 낮습니다.",
        "상세 게시물은 URL 클릭 시 확인 가능합니다.",
    ]
    report_path = generate_price_report(rows, summary)
    print(f"Created test report: {report_path}")


if __name__ == "__main__":
    main()
