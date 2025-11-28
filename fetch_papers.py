#!/usr/bin/env python3
"""
Fetch model stealing papers from Semantic Scholar API.

Usage:
    python fetch_papers.py [--output papers.json]
"""

import argparse
import json
import time
from dataclasses import dataclass, asdict
from typing import Optional
import requests


# Keywords to search for
KEYWORDS = [
    "model stealing attack",
    "model extraction attack",
    "neural network extraction attack",
    "stealing machine learning model",
    "model stealing defense",
    "model extraction",
    "LoRA extraction attack",
    "LLM model stealing",
    "knockoff nets",
    "stealing functionality black-box",
    "DNN model stealing",
]

# Fields to request from the API
FIELDS = "title,abstract,year,venue,authors,citationCount,url,openAccessPdf,publicationDate"

# API endpoint
SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


@dataclass
class Paper:
    paper_id: str
    title: str
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    authors: list[str]
    citation_count: int
    url: str
    pdf_url: Optional[str]
    publication_date: Optional[str]
    keywords_matched: list[str]  # which search keywords matched this paper


def search_papers(query: str, limit: int = 100) -> list[dict]:
    """Search for papers matching a query."""
    papers = []
    offset = 0

    while True:
        params = {
            "query": query,
            "fields": FIELDS,
            "limit": min(limit - len(papers), 100),  # API max is 100 per request
            "offset": offset,
        }

        response = requests.get(SEARCH_URL, params=params)

        if response.status_code == 429:
            # Rate limited, wait and retry
            print(f"  Rate limited, waiting 5 seconds...")
            time.sleep(5)
            continue

        response.raise_for_status()
        data = response.json()

        batch = data.get("data", [])
        if not batch:
            break

        papers.extend(batch)
        print(f"  Fetched {len(papers)} papers...")

        if len(papers) >= limit or "next" not in data:
            break

        offset += len(batch)
        time.sleep(0.5)  # Be nice to the API

    return papers[:limit]


def is_relevant(paper: dict, keywords: list[str]) -> bool:
    """Check if paper is relevant based on keyword occurrence in title/abstract."""
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    text = title + " " + abstract

    # Must have at least one keyword in title or abstract
    for kw in keywords:
        if kw.lower() in text:
            return True

    return False


def get_matched_keywords(paper: dict, keywords: list[str]) -> list[str]:
    """Get list of keywords that matched this paper."""
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    text = title + " " + abstract

    matched = []
    for kw in keywords:
        if kw.lower() in text:
            matched.append(kw)
    return matched


def parse_paper(raw: dict, keywords_matched: list[str]) -> Paper:
    """Parse raw API response into Paper object."""
    authors = [a.get("name", "") for a in raw.get("authors", [])]

    pdf_url = None
    if raw.get("openAccessPdf"):
        pdf_url = raw["openAccessPdf"].get("url")

    return Paper(
        paper_id=raw.get("paperId", ""),
        title=raw.get("title", ""),
        abstract=raw.get("abstract"),
        year=raw.get("year"),
        venue=raw.get("venue"),
        authors=authors,
        citation_count=raw.get("citationCount", 0),
        url=raw.get("url", ""),
        pdf_url=pdf_url,
        publication_date=raw.get("publicationDate"),
        keywords_matched=keywords_matched,
    )


def fetch_all_papers(keywords: list[str], limit_per_keyword: int = 100) -> list[Paper]:
    """Fetch papers for all keywords and deduplicate."""
    seen_ids = set()
    papers = []

    for keyword in keywords:
        print(f"Searching for: {keyword}")
        results = search_papers(keyword, limit=limit_per_keyword)

        for raw in results:
            paper_id = raw.get("paperId")
            if not paper_id or paper_id in seen_ids:
                continue

            # Check relevance
            matched = get_matched_keywords(raw, keywords)
            if not matched:
                continue

            seen_ids.add(paper_id)
            papers.append(parse_paper(raw, matched))

    print(f"\nTotal unique relevant papers: {len(papers)}")
    return papers


def main():
    parser = argparse.ArgumentParser(description="Fetch model stealing papers")
    parser.add_argument("--output", "-o", default="papers.json", help="Output JSON file")
    parser.add_argument("--limit", "-l", type=int, default=100, help="Max papers per keyword")
    args = parser.parse_args()

    papers = fetch_all_papers(KEYWORDS, limit_per_keyword=args.limit)

    # Sort by year (newest first), then by citations
    papers.sort(key=lambda p: (-(p.year or 0), -p.citation_count))

    # Convert to JSON
    data = {
        "updated": time.strftime("%Y-%m-%d"),
        "total": len(papers),
        "keywords": KEYWORDS,
        "papers": [asdict(p) for p in papers],
    }

    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(papers)} papers to {args.output}")


if __name__ == "__main__":
    main()
