"""
ETF 시세 수집 스크립트 (네이버 금융 ETF 목록 JSON API 사용)

- finance.naver.com의 ETF 페이지가 내부적으로 호출하는 JSON API를 직접 호출.
  https://finance.naver.com/api/sise/etfItemList.nhn
- HTML 표를 긁는 것보다 안정적이지만, 이 역시 공식 문서화된 API가 아니라
  네이버가 응답 형식을 바꾸면 깨질 수 있음.
- 응답 필드 이름이 바뀌었을 가능성에 대비해, 여러 후보 키 이름을 순서대로 시도함.

실행:
    pip install requests
    python fetch_etf.py
"""

import json
from datetime import datetime, timezone

import requests

URL = "https://finance.naver.com/api/sise/etfItemList.nhn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://finance.naver.com/sise/etf.naver",
    "Accept": "application/json, text/plain, */*",
}

VOLUME_OUTPUT = "etf_volume_top10.json"
GAINERS_OUTPUT = "etf_gainers_top4.json"


def pick(d: dict, *keys, default=None):
    """d에서 keys 중 실제로 존재하는 첫 번째 키의 값을 반환."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def normalize(raw: dict):
    """API 응답의 한 항목을 우리 포맷으로 변환. 필수 필드가 없으면 None."""
    code = pick(raw, "itemcode", "code", "itemCode")
    name = pick(raw, "itemname", "name", "itemName")
    if not code or not name:
        return None
    return {
        "code": code,
        "name": name,
        "price": float(pick(raw, "nowVal", "now_val", "price", default=0) or 0),
        "change_rate": float(pick(raw, "changeRate", "change_rate", "fluctuationsRatio", default=0) or 0),
        "three_month_return": float(pick(raw, "threeMonthEarnRate", "three_month_earn_rate", default=0) or 0),
        "volume": int(pick(raw, "quant", "volume", "quantity", default=0) or 0),
    }


def fetch_all_etfs():
    res = requests.get(URL, headers=HEADERS, timeout=15)
    res.raise_for_status()
    data = res.json()

    # 응답 구조 후보 몇 가지를 순서대로 시도
    candidates = [
        data.get("result", {}).get("etfItemList") if isinstance(data, dict) else None,
        data.get("etfItemList") if isinstance(data, dict) else None,
        data.get("result") if isinstance(data, dict) else None,
        data if isinstance(data, list) else None,
    ]
    raw_list = next((c for c in candidates if isinstance(c, list) and c), [])

    if not raw_list:
        print("경고: 응답에서 ETF 목록을 못 찾았어요. 실제 응답 키:",
              list(data.keys()) if isinstance(data, dict) else type(data))
        return []

    items = [normalize(r) for r in raw_list]
    return [i for i in items if i]


def main():
    etfs = fetch_all_etfs()
    generated_at = datetime.now(timezone.utc).isoformat()

    if not etfs:
        print("경고: ETF 데이터를 하나도 못 읽었어요. API 응답 형식이 바뀌었을 수 있어요.")

    by_volume = sorted(etfs, key=lambda e: e["volume"], reverse=True)[:10]
    by_gain = sorted(etfs, key=lambda e: e["change_rate"], reverse=True)[:4]

    with open(VOLUME_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"generated_at": generated_at, "items": by_volume}, f, ensure_ascii=False, indent=2)

    with open(GAINERS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"generated_at": generated_at, "items": by_gain}, f, ensure_ascii=False, indent=2)

    print(f"거래량 TOP10: {len(by_volume)}건, 등락률 TOP4: {len(by_gain)}건 저장 완료")
    for e in by_volume[:3]:
        print(f"  - {e['name']} ({e['code']}) 거래량 {e['volume']:,}")


if __name__ == "__main__":
    main()
