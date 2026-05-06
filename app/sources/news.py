"""News via Google News RSS."""

import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.config import REFRESH_NEWS, GOOGLE_NEWS_QUERIES, GOOGLE_NEWS_RSS_TEMPLATE
from app.sources.base import BaseSource, logger
from news_classification.classifier import KeywordWeighted
from news_classification import findings


def _load_best_classifier() -> KeywordWeighted:
    """Load KeywordWeighted with best-known params from findings, or defaults."""
    bests = findings.best_by_classifier()
    if "KeywordWeighted" in bests:
        params = bests["KeywordWeighted"].get("metadata", {}).get("params", {})
        return KeywordWeighted(**params)
    return KeywordWeighted()


class NewsSource(BaseSource):
    cache_key = "news_alerts"
    refresh_interval = REFRESH_NEWS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._classifier = _load_best_classifier()

    async def fetch(self) -> dict:
        items = await self._fetch_google_news()
        return {"items": items}

    async def _fetch_google_news(self) -> list[dict]:
        all_items = []
        seen_titles = set()

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for query in GOOGLE_NEWS_QUERIES:
                try:
                    url = GOOGLE_NEWS_RSS_TEMPLATE.format(query=query.replace(" ", "+"))
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "xml")
                    for entry in soup.find_all("item")[:5]:
                        title_el = entry.find("title")
                        link_el = entry.find("link")
                        pub_date_el = entry.find("pubDate")
                        source_el = entry.find("source")

                        if not title_el:
                            continue

                        title = title_el.text.strip()
                        title_key = re.sub(r'\s+', ' ', title.lower())[:80]
                        if title_key in seen_titles:
                            continue
                        seen_titles.add(title_key)

                        source = source_el.text.strip() if source_el else "Google News"
                        category, _confidence = self._classifier.classify(title)

                        all_items.append({
                            "headline": title,
                            "source": source,
                            "category": category,
                            "url": link_el.text.strip() if link_el else None,
                            "timestamp": pub_date_el.text.strip() if pub_date_el else datetime.now().isoformat(),
                        })
                except Exception as e:
                    logger.debug("Google News query '%s' failed: %s", query, e)

        all_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_items[:20]
