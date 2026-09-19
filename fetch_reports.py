"""
증권사 리포트 수집 스크립트 (네이버 금융 '종목분석 리포트' 목록 페이지 스크래핑)

- https://finance.naver.com/research/company_list.naver 의 표를 읽어서
  최신 리포트 상위 10개를 뽑아낸다.
- 이 목록에는 목표주가·투자의견이 표에 직접 나오지 않아서(PDF 안에만 있음),
  종목명 / 리포트 제목 / 증권사 / 작성일 / 원문 링크만 가져온다.
- 공식 API가 아닌 일반 HTML 표 스크래핑이라 네이버가 페이지 구조를 바꾸면
  이 스크립트도 같이 고쳐야 한다.
- 실패 시 진단 정보(응답 코드, 표 개수, 앞부분 텍스트)를 로그에 찍어서
  다음에 어디를 고쳐야 할지 바로 알 수 있게 해둠.

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
    "Accept-Language": "ko-KR,ko;q=0.9",
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


def diagnose(res, soup):
    """실패 원인을 좁히기 위한 진단 로그."""
    print(f"[진단] HTTP 상태코드: {res.status_code}, 응답 길이: {len(res.text)}자")
    tables = soup.find_all("table")
    print(f"[진단] 페이지 안 <table> 개수: {len(tables)}")
    all_links = soup.find_all("a")
    print(f"[진단] 페이지 안 <a> 개수: {len(all_links)}")
    # 응답이 정상 페이지가 아니라 캡차/차단 페이지일 가능성 체크
    lowered = res.text.lower()
    if "captcha" in lowered or "비정상적인 접근" in res.text:
        print("[진단] 캡차/접근 차단 페이지로 리다이렉트된 것으로 보임")
    print("[진단] 응답 앞부분 500자:")
    print(res.text[:500].replace("\n", " "))


def fetch_reports():
    res = requests.get(URL, headers=HEADERS, timeout=15)
    res.raise_for_status()
    res.encoding = "euc-kr"
    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("table tr")
    reports = [parse_row(tr) for tr in rows]
    reports = [r for r in reports if r]

    if not reports:
        diagnose(res, soup)

    return reports


def main():
    reports = fetch_reports()
    top = reports[:TOP_N]
    generated_at = datetime.now(timezone.utc).isoformat()

    if not top:
        print("경고: 리포트를 하나도 못 읽었어요. 위 [진단] 로그를 확인하세요.")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": generated_at, "items": top}, f, ensure_ascii=False, indent=2)

    print(f"{len(top)}건 저장 완료 -> {OUTPUT_PATH}")
    for r in top[:3]:
        print(f"  - [{r['firm']}] {r['stock']} - {r['title']}")


if __name__ == "__main__":
    main()
