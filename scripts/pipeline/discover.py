#!/usr/bin/env python3
"""
Daily discovery: find new papers citing our pool.

For papers that haven't been checked recently:
1. Query Semantic Scholar for new citations
2. Add new citing papers to the queue
3. Update citations_checked_at timestamp

This finds newly published papers that reference known ML security papers.
"""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from state import PaperState

# Semantic Scholar API
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("S2_API_KEY")
PAPER_FIELDS = "paperId,title,abstract,year,venue,authors,url"


def get_recent_citations(paper_id: str, limit: int = 50) -> list[dict]:
    """Get papers that cite this paper, sorted by recency."""
    # Note: S2 API doesn't have a "since" filter, so we fetch recent ones
    # and filter client-side
    url = f"{S2_API_BASE}/paper/{paper_id}/citations?fields={PAPER_FIELDS}&limit={limit}"

    headers = {"User-Agent": "ml-security-papers/1.0"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            return [item.get("citingPaper") for item in data.get("data", []) if item.get("citingPaper")]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise
        if e.code != 404:
            print(f"  HTTP Error {e.code}", flush=True)
    except Exception as e:
        print(f"  Error: {e}", flush=True)

    return []


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Discover new papers citing our pool")
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--days", type=int, default=7, help="Check papers not checked in N days")
    parser.add_argument("--limit", type=int, default=0, help="Limit papers to check (0=all)")
    parser.add_argument("--rate-limit", type=float, default=3.0, help="Seconds between requests")
    args = parser.parse_args()

    state = PaperState(args.state_file)

    # Get papers that need citation checking
    to_check = state.get_papers_for_discovery(days_since_check=args.days)

    print(f"Papers to check for new citations: {len(to_check)}", flush=True)

    if args.limit > 0:
        to_check = to_check[:args.limit]
        print(f"Limited to {len(to_check)} papers", flush=True)

    if not to_check:
        print("No papers to check", flush=True)
        return

    total_new_papers = 0
    checked_count = 0

    for i, paper in enumerate(to_check):
        paper_id = paper["paper_id"]
        title = paper["title"]

        # We need an S2 paper ID
        s2_id = paper.get("s2_paper_id") or paper_id
        if s2_id.startswith("seed_"):
            continue

        try:
            citations = get_recent_citations(s2_id)

            new_papers = 0
            for citing in citations:
                if not citing or not citing.get("paperId"):
                    continue

                # Check if this is a new paper
                if not state.has_paper(citing["paperId"]):
                    # Check if it's recent (published in last 2 years)
                    year = citing.get("year")
                    current_year = datetime.now().year
                    if year and year >= current_year - 1:
                        was_added = state.add_paper(
                            paper_id=citing["paperId"],
                            title=citing.get("title", "Unknown"),
                            source="citation",
                            source_paper_id=paper_id,
                            abstract=citing.get("abstract"),
                            year=citing.get("year"),
                            venue=citing.get("venue"),
                            authors=[a.get("name") for a in citing.get("authors", [])],
                            url=citing.get("url"),
                            depth=paper.get("depth", 0) + 1,
                        )
                        if was_added:
                            new_papers += 1

            # Update checked timestamp
            state.set_citations_checked(paper_id)
            checked_count += 1
            total_new_papers += new_papers

            if new_papers > 0:
                print(f"[{i+1}/{len(to_check)}] +{new_papers} new: {title[:40]}...", flush=True)
            elif (i + 1) % 20 == 0:
                print(f"[{i+1}/{len(to_check)}] checked: {title[:40]}...", flush=True)

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

    # Final save
    state.save()

    print(f"\nDone!", flush=True)
    print(f"  Papers checked: {checked_count}", flush=True)
    print(f"  New papers discovered: {total_new_papers}", flush=True)

    stats = state.stats()
    print(f"\nCurrent state:", flush=True)
    print(f"  Total papers: {stats['total_papers']}", flush=True)
    for status, count in sorted(stats['by_status'].items()):
        print(f"  {status}: {count}", flush=True)


if __name__ == "__main__":
    main()
