"""
증권사 리포트 수집 스크립트 v2 (m.stock.naver.com 비공식 JSON API 사용)

- 예전 finance.naver.com/research/company_list.naver 는 리액트로 새로 만들어져서
  더 이상 서버가 완성된 HTML 표를 안 줌 (자바스크립트가 나중에 채움) -> 스크래핑 불가.
- 대신 종목 상세 정보를 주는 비공식 API를 대형주 여러 개에 대해 호출해서,
  그 안에 들어있는 리서치(애널리스트 리포트) 정보를 모아 최신순으로 합친다.
  GET https://m.stock.naver.com/api/stock/{종목코드}/integration
- 이 API의 리서치 필드가 정확히 어떤 구조인지 100% 확인된 게 아니라서,
  실패하면 실제 JSON 구조를 로그에 통째로 찍어서 다음에 바로 고칠 수 있게 해둠.

실행:
    pip install requests
    python fetch_reports.py
"""

import json
from datetime import datetime, timezone

import requests

# 시가총액 상위 종목 위주로 구성 (필요하면 자유롭게 추가/삭제 가능)
STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("373220", "LG에너지솔루션"),
    ("207940", "삼성바이오로직스"),
    ("005380", "현대차"),
    ("035420", "NAVER"),
    ("005490", "POSCO홀딩스"),
    ("000270", "기아"),
    ("035720", "카카오"),
    ("068270", "셀트리온"),
    ("051910", "LG화학"),
    ("006400", "삼성SDI"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json, text/plain, */*",
}

OUTPUT_PATH = "reports_top10.json"
TOP_N = 10
DEBUG_DUMPED = False  # 진단 로그를 한 번만 찍기 위한 플래그


def find_research_list(obj, path=""):
    """JSON 안에서 '리포트 목록처럼 생긴 리스트'를 재귀적으로 찾는다.
    키 이름이 research/consensus 등을 포함하는 list[dict]를 우선적으로 찾음."""
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_lower = k.lower()
            if isinstance(v, list) and v and isinstance(v[0], dict):
                if "research" in key_lower or "consensus" in key_lower or "report" in key_lower:
                    results.append((f"{path}.{k}", v))
            results.extend(find_research_list(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(find_research_list(item, f"{path}[{i}]"))
    return results


def extract_report_fields(item: dict, stock_name: str):
    """리포트 dict 하나에서 제목/증권사/날짜/링크를 뽑는다.
    실제 확인된 필드명: tit(제목), bnm(증권사), wdt(작성일 YYYYMMDD), cd(종목코드), nm(종목명)"""
    def first_key(*candidates):
        for c in candidates:
            if c in item and item[c]:
                return item[c]
        return None

    title = first_key("tit", "title", "reportTitle", "stockOpinion", "name")
    firm = first_key("bnm", "secuFirmName", "writerFirmName", "brokerName", "firmName")
    raw_date = first_key("wdt", "date", "regDt", "writeDate", "registerDate")
    name = first_key("nm") or stock_name
    report_id = first_key("id")

    if not title:
        return None

    # wdt는 "20260907" 같은 8자리 문자열 -> "2026.09.07"로 보기 좋게 변환
    date = str(raw_date) if raw_date else ""
    if len(date) == 8 and date.isdigit():
        date = f"{date[:4]}.{date[4:6]}.{date[6:]}"

    # 이 API 응답엔 원문 링크가 없어서, 예전 리포트 상세 페이지 주소 패턴으로 추정해서 넣음.
    # 실제로 연결되는지 확인된 건 아님 -> 깨져 있으면 이 줄만 고치면 됨.
    link = f"https://finance.naver.com/research/company_read.naver?nid={report_id}&page=1" if report_id else ""

    return {
        "stock": str(name),
        "title": str(title),
        "firm": str(firm) if firm else "",
        "date": date,
        "link": link,
        "_sort_key": str(raw_date) if raw_date else "",
    }


def fetch_reports_for_stock(code: str, name: str, debug: bool):
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"  [{name}] 요청 실패: {e}")
        return []

    candidates = find_research_list(data)

    if not candidates:
        if debug:
            print(f"  [진단:{name}] 'research/consensus/report' 관련 리스트를 못 찾음.")
            print(f"  [진단:{name}] 최상위 키 목록: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        return []

    if debug:
        print(f"  [진단:{name}] 후보 리스트 발견: {[c[0] for c in candidates]}")
        # 첫 후보의 첫 항목 구조를 통째로 찍어서 필드명 확인
        first_path, first_list = candidates[0]
        print(f"  [진단:{name}] '{first_path}'의 첫 항목 예시: {json.dumps(first_list[0], ensure_ascii=False)[:400]}")

    items = []
    for _, lst in candidates:
        for raw in lst:
            parsed = extract_report_fields(raw, name)
            if parsed:
                items.append(parsed)
    return items


def main():
    all_reports = []
    debug_used = False

    for code, name in STOCKS:
        reports = fetch_reports_for_stock(code, name, debug=not debug_used)
        if reports:
            all_reports.extend(reports)
        elif not debug_used:
            debug_used = True  # 첫 실패 종목에서만 자세한 진단 로그를 찍음

    generated_at = datetime.now(timezone.utc).isoformat()

    # 여러 종목에서 모은 리포트를 최신순으로 정렬 후 상위 N개
    all_reports.sort(key=lambda r: r["_sort_key"], reverse=True)
    seen_titles = set()
    deduped = []
    for r in all_reports:
        if r["title"] in seen_titles:
            continue
        seen_titles.add(r["title"])
        deduped.append(r)

    top = deduped[:TOP_N]
    for r in top:
        del r["_sort_key"]

    if not top:
        print("경고: 리포트를 하나도 못 읽었어요. 위 [진단] 로그를 확인하세요.")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": generated_at, "items": top}, f, ensure_ascii=False, indent=2)

    print(f"{len(top)}건 저장 완료 -> {OUTPUT_PATH}")
    for r in top[:3]:
        print(f"  - [{r['firm']}] {r['stock']} - {r['title']}")


if __name__ == "__main__":
    main()
