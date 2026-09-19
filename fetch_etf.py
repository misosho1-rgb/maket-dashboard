"""
ETF 시세 수집 스크립트 (네이버 금융 ETF 전체 시세 페이지 스크래핑)

- https://finance.naver.com/sise/etf.naver 의 표를 읽어서
  거래량 TOP10, 등락률(오늘 수익률) TOP4를 뽑아낸다.
- 이 페이지는 공식 API가 아니라 일반 HTML 표라서, 네이버가 페이지 구조를
  바꾸면 이 스크립트도 같이 고쳐야 한다. (뉴스 RSS보다 훨씬 깨지기 쉬움)
- 표 컬럼 순서(현재 기준): 종목명 | 현재가 | 전일비 | 등락률 | NAV | 3개월수익률 | 거래량 | 거래대금 | 시가총액
  -> 순서가 바뀌면 parse_row()의 인덱스만 조정하면 됨.

실행:
    pip install requests beautifulsoup4
    python fetch_etf.py
"""

import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://finance.naver.com/sise/etf.naver"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
}

VOLUME_OUTPUT = "etf_volume_top10.json"
GAINERS_OUTPUT = "etf_gainers_top4.json"


def to_number(text: str) -> float:
    """'1,234' / '+1.23%' / '-0.45' 같은 문자열에서 숫자만 뽑아 float으로."""
    if not text:
        return 0.0
    cleaned = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    try:
        return float(cleaned) if cleaned not in ("", "-", ".") else 0.0
    except ValueError:
        return 0.0


def parse_row(tr):
    """<tr> 하나에서 ETF 한 종목의 정보를 뽑는다. 실패하면 None."""
    link = tr.select_one("a")
    if not link or "code=" not in link.get("href", ""):
        return None

    tds = tr.find_all("td")
    if len(tds) < 8:
        return None

    texts = [td.get_text(strip=True) for td in tds]
    code_match = re.search(r"code=(\d+)", link["href"])

    try:
        return {
            "name": link.get_text(strip=True),
            "code": code_match.group(1) if code_match else "",
            "price": to_number(texts[1]),
            "change_rate": to_number(texts[3]),          # 오늘 등락률(%)
            "three_month_return": to_number(texts[5]),   # 3개월 수익률(%)
            "volume": int(to_number(texts[6])),           # 거래량
        }
    except (IndexError, ValueError):
        return None


def fetch_all_etfs():
    res = requests.get(URL, headers=HEADERS, timeout=15)
    res.raise_for_status()
    res.encoding = "euc-kr"
    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("table tr")
    etfs = [parse_row(tr) for tr in rows]
    etfs = [e for e in etfs if e]
    return etfs


def main():
    etfs = fetch_all_etfs()
    generated_at = datetime.now(timezone.utc).isoformat()

    if not etfs:
        print("경고: ETF 데이터를 하나도 못 읽었어요. 페이지 구조가 바뀌었을 수 있어요.")

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
