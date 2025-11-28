#!/usr/bin/env python3
"""
Fetch model stealing papers from Semantic Scholar API.

Usage:
    python fetch_papers.py [--output papers.json]
"""

import argparse
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional
import requests

# API key from environment variable (optional, but recommended for higher rate limits)
API_KEY = os.environ.get("S2_API_KEY")


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
    "DNN weights leakage",
    "neural network weight extraction",
    "side-channel model extraction",
    "recover parameters neural network",
    "electromagnetic analysis neural network",
    "extract parameters neural network",
    "side-channel attack deep learning",
    "power analysis neural network weights",
    "GPU leak DNN weights",
]

# Venues to exclude (not related to ML security)
EXCLUDED_VENUES = [
    "IEEE transactions on microwave theory and techniques",
    "IEEE Transactions on Microwave Theory and Techniques",
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

    # Add API key header if available
    headers = {}
    if API_KEY:
        headers["x-api-key"] = API_KEY

    while True:
        params = {
            "query": query,
            "fields": FIELDS,
            "limit": min(limit - len(papers), 100),  # API max is 100 per request
            "offset": offset,
        }

        response = requests.get(SEARCH_URL, params=params, headers=headers)

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

    # Additional title patterns for side-channel/hardware attacks on ML
    title_patterns = [
        "leak" in title and ("dnn" in title or "neural" in title or "weight" in title),
        "side-channel" in title and ("neural" in title or "dnn" in title or "ml" in title),
        "electromagnetic" in title and "neural" in title,
        "power analysis" in title and ("neural" in title or "dnn" in title),
    ]
    if any(title_patterns):
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

    # Check title patterns for side-channel attacks
    if not matched:
        if "leak" in title and ("dnn" in title or "neural" in title or "weight" in title):
            matched.append("DNN weights leakage (title)")
        elif "side-channel" in title and ("neural" in title or "dnn" in title or "ml" in title):
            matched.append("side-channel attack (title)")
        elif "electromagnetic" in title and "neural" in title:
            matched.append("electromagnetic analysis (title)")
        elif "power analysis" in title and ("neural" in title or "dnn" in title):
            matched.append("power analysis (title)")

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

            # Skip excluded venues
            venue = raw.get("venue") or ""
            if venue in EXCLUDED_VENUES:
                continue

            # Check relevance
            matched = get_matched_keywords(raw, keywords)
            if not matched:
                continue

            seen_ids.add(paper_id)
            papers.append(parse_paper(raw, matched))

    print(f"\nTotal unique relevant papers: {len(papers)}")
    return papers


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    import re
    # Lowercase, remove punctuation, collapse whitespace
    t = title.lower()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def titles_are_similar(t1: str, t2: str) -> bool:
    """Check if two normalized titles are similar enough to be duplicates."""
    # Exact match
    if t1 == t2:
        return True
    # One is prefix of the other (handles "Title" vs "Title: Extended")
    if t1.startswith(t2) or t2.startswith(t1):
        min_len = min(len(t1), len(t2))
        if min_len >= 20:  # Only if the common part is substantial
            return True
    # Check word overlap (handles minor word differences)
    words1 = set(t1.split())
    words2 = set(t2.split())
    if len(words1) >= 4 and len(words2) >= 4:
        intersection = words1 & words2
        union = words1 | words2
        jaccard = len(intersection) / len(union)
        if jaccard >= 0.8:  # 80% word overlap
            return True
    return False


def deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    """Remove duplicate papers, keeping the one with best metadata."""
    # Build groups of similar papers
    groups = []
    used = set()

    for i, p1 in enumerate(papers):
        if i in used:
            continue
        norm1 = normalize_title(p1.title)
        group = [p1]
        used.add(i)

        for j, p2 in enumerate(papers):
            if j in used:
                continue
            norm2 = normalize_title(p2.title)
            if titles_are_similar(norm1, norm2):
                group.append(p2)
                used.add(j)

        groups.append(group)

    # For each group, keep the best version
    deduped = []
    for group in groups:
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Score each paper: prefer venue > year > citations
            def score(p):
                return (
                    1 if p.venue else 0,  # Has venue
                    p.year or 0,          # Has year
                    p.citation_count,     # More citations
                )
            best = max(group, key=score)
            deduped.append(best)
            print(f"  Deduped: kept '{best.title}' ({best.venue or 'no venue'}), removed {len(group)-1} duplicate(s)")

    return deduped


def main():
    parser = argparse.ArgumentParser(description="Fetch model stealing papers")
    parser.add_argument("--output", "-o", default="papers.json", help="Output JSON file")
    parser.add_argument("--limit", "-l", type=int, default=100, help="Max papers per keyword")
    args = parser.parse_args()

    papers = fetch_all_papers(KEYWORDS, limit_per_keyword=args.limit)

    # Deduplicate papers with similar titles
    papers = deduplicate_papers(papers)
    print(f"After deduplication: {len(papers)} papers")

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
