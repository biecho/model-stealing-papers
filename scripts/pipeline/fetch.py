#!/usr/bin/env python3
"""
Fetch metadata for papers that are in "pending" status.

Sources (in order of preference):
1. Semantic Scholar API (by paper ID or title search)
2. arXiv API (if URL contains arxiv.org)

Updates paper status to "fetched" when successful.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from state import PaperState

# API configuration
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("S2_API_KEY")
S2_FIELDS = "paperId,title,abstract,year,venue,authors,citationCount,referenceCount,url,externalIds"

ARXIV_API = "http://export.arxiv.org/api/query"


def search_semantic_scholar(title: str) -> dict | None:
    """Search for a paper by title in Semantic Scholar."""
    query = urllib.parse.quote(title)
    url = f"{S2_API_BASE}/paper/search?query={query}&fields={S2_FIELDS}&limit=1"

    headers = {"User-Agent": "ml-security-papers/1.0"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            if data.get("data"):
                return data["data"][0]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise  # Re-raise rate limit
        print(f"  S2 HTTP Error {e.code}", flush=True)
    except Exception as e:
        print(f"  S2 Error: {e}", flush=True)

    return None


def get_semantic_scholar_by_id(paper_id: str) -> dict | None:
    """Get paper by Semantic Scholar ID."""
    url = f"{S2_API_BASE}/paper/{paper_id}?fields={S2_FIELDS}"

    headers = {"User-Agent": "ml-security-papers/1.0"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise
        if e.code != 404:
            print(f"  S2 HTTP Error {e.code}", flush=True)
    except Exception as e:
        print(f"  S2 Error: {e}", flush=True)

    return None


def extract_arxiv_id(url: str) -> str | None:
    """Extract arXiv ID from URL."""
    if not url:
        return None
    patterns = [
        r'arxiv.org/(?:abs|pdf)/(\d+\.\d+)',
        r'arxiv.org/(?:abs|pdf)/([a-z-]+/\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_arxiv(arxiv_id: str) -> dict | None:
    """Fetch metadata from arXiv API."""
    url = f"{ARXIV_API}?id_list={arxiv_id}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ml-security-papers/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            xml_data = response.read().decode()

        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        entry = root.find('atom:entry', ns)
        if entry is None:
            return None

        title_el = entry.find('atom:title', ns)
        if title_el is not None and 'Error' in (title_el.text or ''):
            return None

        return {
            'arxiv_id': arxiv_id,
            'title': title_el.text.strip().replace('\n', ' ') if title_el is not None else None,
            'abstract': entry.find('atom:summary', ns).text.strip().replace('\n', ' ') if entry.find('atom:summary', ns) is not None else None,
            'authors': [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)],
            'published': entry.find('atom:published', ns).text[:10] if entry.find('atom:published', ns) is not None else None,
            'url': f"https://arxiv.org/abs/{arxiv_id}",
        }
    except Exception as e:
        print(f"  arXiv Error: {e}", flush=True)
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch metadata for pending papers")
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--limit", type=int, default=0, help="Limit papers to fetch (0=all)")
    parser.add_argument("--rate-limit", type=float, default=3.0, help="Seconds between requests")
    args = parser.parse_args()

    state = PaperState(args.state_file)

    # Get pending papers
    pending = state.get_pending_papers()
    print(f"Papers pending metadata: {len(pending)}", flush=True)

    if args.limit > 0:
        pending = pending[:args.limit]
        print(f"Limited to {len(pending)} papers", flush=True)

    if not pending:
        print("No papers to fetch", flush=True)
        return

    fetched = 0
    failed = 0

    for i, paper in enumerate(pending):
        paper_id = paper["paper_id"]
        title = paper["title"]

        try:
            result = None

            # Try arXiv first if we have an arXiv URL
            arxiv_id = extract_arxiv_id(paper.get("url"))
            if arxiv_id:
                result = fetch_arxiv(arxiv_id)
                if result:
                    state.set_fetched(
                        paper_id,
                        abstract=result.get("abstract"),
                        authors=result.get("authors"),
                        year=int(result["published"][:4]) if result.get("published") else paper.get("year"),
                        url=result.get("url"),
                    )
                    # Update paper_id to arXiv ID if different
                    if arxiv_id != paper_id:
                        state.papers[paper_id]["arxiv_id"] = arxiv_id

            # Fall back to Semantic Scholar
            if not result:
                # Try by ID first if it looks like an S2 ID
                if not paper_id.startswith("seed_"):
                    result = get_semantic_scholar_by_id(paper_id)

                # Try by title search
                if not result:
                    result = search_semantic_scholar(title)

                if result:
                    state.set_fetched(
                        paper_id,
                        abstract=result.get("abstract"),
                        authors=[a.get("name") for a in result.get("authors", [])],
                        year=result.get("year"),
                        venue=result.get("venue"),
                        url=result.get("url"),
                    )
                    # Store S2 paper ID
                    if result.get("paperId"):
                        state.papers[paper_id]["s2_paper_id"] = result["paperId"]
                        state.papers[paper_id]["external_ids"] = result.get("externalIds", {})

            if result and result.get("abstract"):
                fetched += 1
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"[{i+1}/{len(pending)}] ✓ {title[:50]}...", flush=True)
            else:
                failed += 1
                if (i + 1) % 20 == 0:
                    print(f"[{i+1}/{len(pending)}] ✗ No abstract: {title[:40]}...", flush=True)

            # Save checkpoint
            if (i + 1) % 25 == 0:
                state.save()
                print(f"  Checkpoint saved", flush=True)

            time.sleep(args.rate_limit)

        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"Rate limited, waiting 120s...", flush=True)
                time.sleep(120)
                continue
            else:
                print(f"Error: {e}", flush=True)
                failed += 1

    # Final save
    state.save()

    print(f"\nDone!", flush=True)
    print(f"  Fetched with abstract: {fetched}", flush=True)
    print(f"  Failed/no abstract: {failed}", flush=True)

    stats = state.stats()
    print(f"\nCurrent state:", flush=True)
    for status, count in sorted(stats['by_status'].items()):
        print(f"  {status}: {count}", flush=True)


if __name__ == "__main__":
    main()
