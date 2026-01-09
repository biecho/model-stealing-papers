#!/usr/bin/env python3
"""
Expand the paper graph via citations and references.

For each classified paper (ML01-ML10):
1. Fetch papers that cite it (citations)
2. Fetch papers it references (references)
3. Add new papers to the queue with status="pending"
4. Mark original paper as "expanded"

This implements BFS-style graph traversal.
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from state import PaperState

# Semantic Scholar API
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("S2_API_KEY")
PAPER_FIELDS = "paperId,title,abstract,year,venue,authors,url"


def get_citations(paper_id: str, limit: int = 100) -> list[dict]:
    """Get papers that cite this paper."""
    url = f"{S2_API_BASE}/paper/{paper_id}/citations?fields={PAPER_FIELDS}&limit={limit}"

    headers = {"User-Agent": "ml-security-papers/1.0"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            # Citations are nested under "citingPaper"
            return [item.get("citingPaper") for item in data.get("data", []) if item.get("citingPaper")]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise
        if e.code != 404:
            print(f"  Citations HTTP Error {e.code}", flush=True)
    except Exception as e:
        print(f"  Citations Error: {e}", flush=True)

    return []


def get_references(paper_id: str, limit: int = 50) -> list[dict]:
    """Get papers that this paper references."""
    url = f"{S2_API_BASE}/paper/{paper_id}/references?fields={PAPER_FIELDS}&limit={limit}"

    headers = {"User-Agent": "ml-security-papers/1.0"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            # References are nested under "citedPaper"
            return [item.get("citedPaper") for item in data.get("data", []) if item.get("citedPaper")]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise
        if e.code != 404:
            print(f"  References HTTP Error {e.code}", flush=True)
    except Exception as e:
        print(f"  References Error: {e}", flush=True)

    return []


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Expand paper graph via citations")
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--limit", type=int, default=0, help="Limit papers to expand (0=all)")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum depth from seed papers")
    parser.add_argument("--max-citations", type=int, default=100, help="Max citations per paper")
    parser.add_argument("--max-references", type=int, default=50, help="Max references per paper")
    parser.add_argument("--rate-limit", type=float, default=3.0, help="Seconds between requests")
    args = parser.parse_args()

    state = PaperState(args.state_file)

    # Get papers to expand (classified but not yet expanded)
    to_expand = state.get_papers_to_expand()

    # Filter by depth
    to_expand = [p for p in to_expand if p.get("depth", 0) < args.max_depth]

    print(f"Papers to expand: {len(to_expand)}", flush=True)

    if args.limit > 0:
        to_expand = to_expand[:args.limit]
        print(f"Limited to {len(to_expand)} papers", flush=True)

    if not to_expand:
        print("No papers to expand", flush=True)
        return

    total_citations_added = 0
    total_references_added = 0
    expanded_count = 0

    for i, paper in enumerate(to_expand):
        paper_id = paper["paper_id"]
        title = paper["title"]
        depth = paper.get("depth", 0)

        # We need an S2 paper ID for expansion
        s2_id = paper.get("s2_paper_id") or paper_id
        if s2_id.startswith("seed_"):
            # Can't expand without S2 ID
            print(f"[{i+1}/{len(to_expand)}] ⊘ No S2 ID: {title[:40]}...", flush=True)
            continue

        try:
            # Fetch citations
            citations = get_citations(s2_id, args.max_citations)
            time.sleep(args.rate_limit)

            # Fetch references
            references = get_references(s2_id, args.max_references)
            time.sleep(args.rate_limit)

            citations_added = 0
            references_added = 0

            # Add citing papers
            for citing in citations:
                if not citing or not citing.get("paperId"):
                    continue

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
                    depth=depth + 1,
                )
                if was_added:
                    citations_added += 1

            # Add referenced papers
            for ref in references:
                if not ref or not ref.get("paperId"):
                    continue

                was_added = state.add_paper(
                    paper_id=ref["paperId"],
                    title=ref.get("title", "Unknown"),
                    source="reference",
                    source_paper_id=paper_id,
                    abstract=ref.get("abstract"),
                    year=ref.get("year"),
                    venue=ref.get("venue"),
                    authors=[a.get("name") for a in ref.get("authors", [])],
                    url=ref.get("url"),
                    depth=depth + 1,
                )
                if was_added:
                    references_added += 1

            # Mark as expanded
            state.set_expanded(paper_id)
            expanded_count += 1

            total_citations_added += citations_added
            total_references_added += references_added

            if (i + 1) % 5 == 0 or i == 0:
                print(f"[{i+1}/{len(to_expand)}] ✓ +{citations_added} cit, +{references_added} ref: {title[:35]}...", flush=True)

            # Save checkpoint
            if (i + 1) % 10 == 0:
                state.save()
                print(f"  Checkpoint saved", flush=True)

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
    print(f"  Papers expanded: {expanded_count}", flush=True)
    print(f"  Citations added: {total_citations_added}", flush=True)
    print(f"  References added: {total_references_added}", flush=True)

    stats = state.stats()
    print(f"\nCurrent state:", flush=True)
    print(f"  Total papers: {stats['total_papers']}", flush=True)
    for status, count in sorted(stats['by_status'].items()):
        print(f"  {status}: {count}", flush=True)


if __name__ == "__main__":
    main()
