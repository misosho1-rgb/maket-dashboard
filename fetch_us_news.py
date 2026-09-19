"""
미국 정치·경제 Top10 뉴스 수집 스크립트

- knews-rss(한국 언론사 RSS 모음)의 국제/경제 카테고리 피드를 가져와
  미국 관련 키워드가 제목에 포함된 기사만 걸러서 최신순 Top10을 뽑는다.
- 매일 새벽 cron(또는 GitHub Actions)으로 실행하는 것을 전제로 작성.
- 실행 결과는 us_news_top10.json 으로 저장된다.

실행:
    pip install feedparser
    python fetch_us_news.py
"""

import json
import re
from datetime import datetime, timezone

import feedparser

# knews-rss가 모아주는 카테고리별 RSS (여러 한국 언론사 기사를 합쳐서 제공)
FEED_URLS = [
    "https://akngs.github.io/knews-rss/categories/international.xml",
    "https://akngs.github.io/knews-rss/categories/economy.xml",
]

# 제목에 이 중 하나라도 포함되면 "미국 관련"으로 간주
KEYWORDS = [
    "미국", "트럼프", "연준", "백악관", "FOMC", "관세",
    "나스닥", "S&P", "뉴욕증시", "월가", "워시", "베센트",
]

TOP_N = 10
OUTPUT_PATH = "us_news_top10.json"


def matches_keyword(title: str) -> bool:
    return any(keyword.lower() in title.lower() for keyword in KEYWORDS)


def parse_pubdate(entry) -> datetime:
    """feedparser가 파싱한 published_parsed(struct_time)를 datetime으로 변환.
    없는 경우 아주 과거 시각을 반환해 정렬 시 뒤로 밀리게 한다."""
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def clean_title(title: str) -> str:
    # 언론사 태그, 괄호로 된 접두어 등 최소한의 정리만 수행
    return re.sub(r"\s+", " ", title).strip()


def collect_articles():
    articles = []
    for url in FEED_URLS:
        feed = feedparser.parse(url)
        source_title = feed.feed.get("title", url)
        for entry in feed.entries:
            title = clean_title(entry.get("title", ""))
            if not title or not matches_keyword(title):
                continue
            articles.append(
                {
                    "title": title,
                    "link": entry.get("link", ""),
                    "source": source_title,
                    "published_at": parse_pubdate(entry).isoformat(),
                    "_sort_key": parse_pubdate(entry),
                }
            )
    return articles


def dedupe(articles):
    """같은 제목이 여러 언론사에서 중복 수집되는 경우 첫 번째만 남긴다."""
    seen = set()
    unique = []
    for a in articles:
        if a["title"] in seen:
            continue
        seen.add(a["title"])
        unique.append(a)
    return unique


def main():
    articles = collect_articles()
    articles = dedupe(articles)
    articles.sort(key=lambda a: a["_sort_key"], reverse=True)
    top10 = articles[:TOP_N]

    for a in top10:
        del a["_sort_key"]

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(top10),
        "articles": top10,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"{len(top10)}건 저장 완료 -> {OUTPUT_PATH}")
    for i, a in enumerate(top10, 1):
        print(f"{i:2d}. [{a['source']}] {a['title']}")


if __name__ == "__main__":
    main()
