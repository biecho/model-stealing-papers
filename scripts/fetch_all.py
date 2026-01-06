#!/usr/bin/env python3
"""
Fetch ML security papers for ALL OWASP categories.

This script fetches papers from Semantic Scholar using keywords from each
category config, then combines them into a single papers.json file.

Usage:
    python scripts/fetch_all.py                    # Fetch all categories
    python scripts/fetch_all.py --category ML01   # Fetch single category
    python scripts/fetch_all.py --limit 50        # Limit per keyword
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

API_KEY = os.environ.get("S2_API_KEY")
BASE_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS = "paperId,title,abstract,year,venue,authors,citationCount,openAccessPdf,publicationDate,externalIds"


def get_headers():
    """Get API headers with optional API key."""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["x-api-key"] = API_KEY
    return headers


def search_papers(query: str, limit: int = 100, offset: int = 0) -> list:
    """Search for papers using keyword query."""
    url = f"{BASE_URL}/paper/search"
    params = {
        "query": query,
        "limit": min(limit, 100),
        "offset": offset,
        "fields": FIELDS,
    }

    try:
        response = requests.get(url, params=params, headers=get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except requests.RequestException as e:
        print(f"  Error searching '{query}': {e}")
        return []


def get_paper_citations(paper_id: str, limit: int = 100) -> list:
    """Get papers that cite a given paper."""
    url = f"{BASE_URL}/paper/{paper_id}/citations"
    params = {"limit": limit, "fields": FIELDS}

    try:
        response = requests.get(url, params=params, headers=get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        return [c.get("citingPaper", {}) for c in data.get("data", [])]
    except requests.RequestException as e:
        print(f"  Error getting citations: {e}")
        return []


def get_paper_references(paper_id: str, limit: int = 100) -> list:
    """Get papers referenced by a given paper."""
    url = f"{BASE_URL}/paper/{paper_id}/references"
    params = {"limit": limit, "fields": FIELDS}

    try:
        response = requests.get(url, params=params, headers=get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        return [r.get("citedPaper", {}) for r in data.get("data", [])]
    except requests.RequestException as e:
        print(f"  Error getting references: {e}")
        return []


def normalize_paper(paper: dict, source: str = "search") -> dict:
    """Normalize paper data to consistent format."""
    if not paper or not paper.get("paperId"):
        return None

    authors = paper.get("authors", [])
    author_names = [a.get("name", "") for a in authors if a]

    pdf_url = ""
    if paper.get("openAccessPdf"):
        pdf_url = paper["openAccessPdf"].get("url", "")

    return {
        "paper_id": paper.get("paperId", ""),
        "title": paper.get("title", ""),
        "abstract": paper.get("abstract"),
        "year": paper.get("year") or 0,
        "venue": paper.get("venue", ""),
        "authors": author_names,
        "citation_count": paper.get("citationCount", 0) or 0,
        "url": f"https://www.semanticscholar.org/paper/{paper.get('paperId', '')}",
        "pdf_url": pdf_url,
        "publication_date": paper.get("publicationDate"),
        "source": source,
        "first_seen": datetime.now().strftime("%Y-%m-%d"),
    }


def load_config(config_path: Path) -> dict:
    """Load a YAML config file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_keywords_from_config(config: dict) -> list:
    """Extract all keywords from a config."""
    keywords = []
    keywords.extend(config.get("high_quality_keywords", []))
    keywords.extend(config.get("core_keywords", []))
    keywords.extend(config.get("defense_keywords", []))
    return keywords


def fetch_for_category(config_path: Path, limit_per_keyword: int = 100) -> dict:
    """Fetch papers for a single category."""
    config = load_config(config_path)
    domain = config.get("domain", {})
    owasp_id = domain.get("owasp_id", "unknown")
    owasp_name = domain.get("owasp_name", "Unknown")

    print(f"\n{'='*60}")
    print(f"{owasp_id}: {owasp_name}")
    print(f"{'='*60}")

    keywords = get_keywords_from_config(config)
    print(f"Keywords: {len(keywords)}")

    papers = {}
    rate_limit_delay = 1.0 if API_KEY else 3.0

    # Search by keywords
    for i, keyword in enumerate(keywords):
        print(f"  [{i+1}/{len(keywords)}] Searching: {keyword}")
        results = search_papers(keyword, limit=limit_per_keyword)

        for paper in results:
            normalized = normalize_paper(paper, f"search:{owasp_id}")
            if normalized and normalized["paper_id"] not in papers:
                normalized["keywords_matched"] = [keyword]
                papers[normalized["paper_id"]] = normalized
            elif normalized:
                papers[normalized["paper_id"]]["keywords_matched"].append(keyword)

        time.sleep(rate_limit_delay)

    # Get seed papers if defined
    seed_papers = config.get("seed_papers", [])
    for seed_id in seed_papers:
        print(f"  Fetching seed paper: {seed_id[:20]}...")
        url = f"{BASE_URL}/paper/{seed_id}"
        params = {"fields": FIELDS}
        try:
            response = requests.get(url, params=params, headers=get_headers(), timeout=30)
            response.raise_for_status()
            paper = response.json()
            normalized = normalize_paper(paper, f"seed:{owasp_id}")
            if normalized and normalized["paper_id"] not in papers:
                papers[normalized["paper_id"]] = normalized

            # Get citations of seed papers
            citations = get_paper_citations(seed_id, limit=50)
            for cited in citations:
                normalized = normalize_paper(cited, f"citation:{owasp_id}")
                if normalized and normalized["paper_id"] not in papers:
                    papers[normalized["paper_id"]] = normalized

            time.sleep(rate_limit_delay)
        except Exception as e:
            print(f"    Error: {e}")

    print(f"  Total papers for {owasp_id}: {len(papers)}")
    return papers


def fetch_all_categories(configs_dir: Path, limit_per_keyword: int = 100) -> dict:
    """Fetch papers for all category configs."""
    all_papers = {}

    config_files = sorted(configs_dir.glob("ml*.yaml"))
    print(f"Found {len(config_files)} category configs")

    for config_path in config_files:
        papers = fetch_for_category(config_path, limit_per_keyword)

        # Merge papers
        for paper_id, paper in papers.items():
            if paper_id not in all_papers:
                all_papers[paper_id] = paper
            else:
                # Merge keywords
                existing = all_papers[paper_id]
                existing["keywords_matched"] = list(set(
                    existing.get("keywords_matched", []) +
                    paper.get("keywords_matched", [])
                ))

    return all_papers


def main():
    parser = argparse.ArgumentParser(
        description="Fetch ML security papers for all OWASP categories"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/papers.json",
        help="Output JSON file",
    )
    parser.add_argument(
        "-c", "--configs-dir",
        default="configs",
        help="Directory with category configs",
    )
    parser.add_argument(
        "--category",
        help="Fetch single category only (e.g., ML01)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max papers per keyword search (default: 100)",
    )

    args = parser.parse_args()
    configs_dir = Path(args.configs_dir)
    output_file = Path(args.output)

    if args.category:
        # Single category
        config_path = configs_dir / f"{args.category.lower()}*.yaml"
        matches = list(configs_dir.glob(f"{args.category.lower()}*.yaml"))
        if not matches:
            print(f"Config not found for {args.category}")
            return 1
        papers = fetch_for_category(matches[0], args.limit)
    else:
        # All categories
        papers = fetch_all_categories(configs_dir, args.limit)

    # Save results
    output_data = {
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "total": len(papers),
        "papers": list(papers.values()),
    }

    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n{'='*60}")
    print(f"TOTAL: {len(papers)} papers saved to {output_file}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    exit(main())
