"""
증권사 리포트 수집 스크립트 (네이버 금융 '종목분석 리포트' 목록 페이지 스크래핑)

- https://finance.naver.com/research/company_list.naver 의 표를 읽어서
  최신 리포트 상위 10개를 뽑아낸다.
- 이 목록에는 목표주가·투자의견이 표에 직접 나오지 않아서(PDF 안에만 있음),
  종목명 / 리포트 제목 / 증권사 / 작성일 / 원문 링크만 가져온다.
- 공식 API가 아닌 일반 HTML 표 스크래핑이라 네이버가 페이지 구조를 바꾸면
  이 스크립트도 같이 고쳐야 한다.

실행:
    pip install requests beautifulsoup4
    python fetch_reports.py
"""

import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://finance.naver.com/research/company_list.naver"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
}

OUTPUT_PATH = "reports_top10.json"
TOP_N = 10


def parse_row(tr):
    """<tr> 하나에서 리포트 한 건을 뽑는다. 실패하면 None."""
    links = tr.find_all("a")
    if len(links) < 2:
        return None

    stock_link, report_link = links[0], links[1]
    tds = tr.find_all("td")
    if len(tds) < 4:
        return None

    # 증권사 / 작성일은 표의 뒤쪽 td에 텍스트로만 들어있음
    texts = [td.get_text(strip=True) for td in tds]
    firm = texts[2] if len(texts) > 2 else ""
    date = texts[-1] if texts else ""

    href = report_link.get("href", "")
    if href.startswith("/"):
        href = "https://finance.naver.com" + href

    title = report_link.get_text(strip=True)
    if not title or not stock_link.get_text(strip=True):
        return None

    return {
        "stock": stock_link.get_text(strip=True),
        "title": title,
        "firm": firm,
        "date": date,
        "link": href,
    }


def fetch_reports():
    res = requests.get(URL, headers=HEADERS, timeout=15)
    res.raise_for_status()
    res.encoding = "euc-kr"
    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("table tr")
    reports = [parse_row(tr) for tr in rows]
    reports = [r for r in reports if r]
    return reports


def main():
    reports = fetch_reports()
    top = reports[:TOP_N]
    generated_at = datetime.now(timezone.utc).isoformat()

    if not top:
        print("경고: 리포트를 하나도 못 읽었어요. 페이지 구조가 바뀌었을 수 있어요.")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": generated_at, "items": top}, f, ensure_ascii=False, indent=2)

    print(f"{len(top)}건 저장 완료 -> {OUTPUT_PATH}")
    for r in top[:3]:
        print(f"  - [{r['firm']}] {r['stock']} - {r['title']}")


if __name__ == "__main__":
    main()
