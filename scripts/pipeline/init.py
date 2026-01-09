#!/usr/bin/env python3
"""
Initialize the paper state with seed papers from Awesome-ML-SP-Papers.

This is the starting point for the pipeline:
1. Load curated papers from Awesome-ML-SP-Papers
2. Create initial paper_state.json with all papers as "pending"
3. Papers with arXiv metadata start as "fetched"
"""

import json
from pathlib import Path

from state import PaperState


def load_awesome_papers(path: Path) -> list[dict]:
    """Load papers from Awesome-ML-SP-Papers JSON."""
    with open(path) as f:
        return json.load(f)


def load_arxiv_metadata(path: Path) -> dict[str, dict]:
    """Load arXiv metadata keyed by title (normalized)."""
    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    result = {}
    for p in data.get("papers", []):
        title = p.get("title", "").lower().strip()
        result[title] = p
    return result


def normalize_title(title: str) -> str:
    """Normalize title for matching."""
    return title.lower().strip().replace("\n", " ").replace("  ", " ")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Initialize paper state from seeds")
    parser.add_argument("--awesome", type=Path, default=Path("data/awesome_ml_sp_papers.json"))
    parser.add_argument("--arxiv", type=Path, default=Path("data/arxiv_metadata.json"))
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--reset", action="store_true", help="Reset existing state")
    args = parser.parse_args()

    # Load or create state
    if args.reset and args.state_file.exists():
        args.state_file.unlink()
        print("Reset existing state")

    state = PaperState(args.state_file)
    existing_count = len(state.papers)

    if existing_count > 0 and not args.reset:
        print(f"State already has {existing_count} papers. Use --reset to start fresh.")
        print("Adding only new papers...")

    # Load seed papers
    awesome_papers = load_awesome_papers(args.awesome)
    print(f"Loaded {len(awesome_papers)} seed papers from Awesome-ML-SP-Papers")

    # Load arXiv metadata (for papers that have abstracts)
    arxiv_metadata = load_arxiv_metadata(args.arxiv)
    print(f"Loaded {len(arxiv_metadata)} arXiv metadata entries")

    # Add papers to state
    added = 0
    with_abstract = 0

    for paper in awesome_papers:
        title = paper["title"]
        norm_title = normalize_title(title)

        # Generate a temporary ID based on title (will be replaced with S2 ID later)
        paper_id = f"seed_{hash(norm_title) & 0xFFFFFFFF:08x}"

        # Check if we have arXiv metadata
        arxiv = arxiv_metadata.get(norm_title)

        if arxiv:
            # We have metadata from arXiv
            was_added = state.add_paper(
                paper_id=arxiv.get("arxiv_id", paper_id),
                title=title,
                source="seed",
                abstract=arxiv.get("abstract"),
                year=paper.get("year") or arxiv.get("year"),
                venue=paper.get("venue"),
                authors=arxiv.get("authors", []),
                url=arxiv.get("url"),
                depth=0,
            )
            if was_added and arxiv.get("abstract"):
                with_abstract += 1
        else:
            # No metadata yet, just add with title
            was_added = state.add_paper(
                paper_id=paper_id,
                title=title,
                source="seed",
                year=paper.get("year"),
                venue=paper.get("venue"),
                url=paper.get("pdf_url"),
                depth=0,
            )

        if was_added:
            added += 1

    # Save state
    state.save()

    # Print stats
    stats = state.stats()
    print(f"\nInitialization complete:")
    print(f"  Papers added: {added}")
    print(f"  With abstracts (fetched): {with_abstract}")
    print(f"  Total in state: {stats['total_papers']}")
    print(f"\nBy status:")
    for status, count in sorted(stats['by_status'].items()):
        print(f"  {status}: {count}")
    print(f"\nState saved to: {args.state_file}")


if __name__ == "__main__":
    main()
