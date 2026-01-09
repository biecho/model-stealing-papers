#!/usr/bin/env python3
"""
Paper state management for the ML Security Papers pipeline.

Central state tracking for all papers:
- Status: pending → fetched → classified → expanded (or discarded)
- Classification: ML01-ML10 or NONE
- Timestamps: when each operation was performed
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

# Status types
Status = Literal["pending", "fetched", "classified", "expanded", "discarded"]
Source = Literal["seed", "citation", "reference"]
Category = Literal["ML01", "ML02", "ML03", "ML04", "ML05", "ML06", "ML07", "ML08", "ML09", "ML10", "NONE"]


class PaperState:
    """Manages the state of all papers in the pipeline."""

    def __init__(self, state_file: Path = Path("data/paper_state.json")):
        self.state_file = state_file
        self.papers: dict[str, dict] = {}
        self.metadata: dict = {
            "total_papers": 0,
            "by_status": {},
            "by_category": {},
            "last_updated": None,
        }
        self._load()

    def _load(self):
        """Load state from file."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                self.papers = data.get("papers", {})
                self.metadata = data.get("metadata", self.metadata)

    def save(self):
        """Save state to file."""
        self._update_metadata()
        data = {
            "papers": self.papers,
            "metadata": self.metadata,
        }
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

    def _update_metadata(self):
        """Update metadata stats."""
        self.metadata["total_papers"] = len(self.papers)
        self.metadata["last_updated"] = datetime.now().isoformat()

        # Count by status
        by_status = {}
        for p in self.papers.values():
            status = p.get("status", "pending")
            by_status[status] = by_status.get(status, 0) + 1
        self.metadata["by_status"] = by_status

        # Count by category
        by_category = {}
        for p in self.papers.values():
            cat = p.get("classification")
            if cat:
                by_category[cat] = by_category.get(cat, 0) + 1
        self.metadata["by_category"] = by_category

    def add_paper(
        self,
        paper_id: str,
        title: str,
        source: Source,
        source_paper_id: str = None,
        abstract: str = None,
        year: int = None,
        venue: str = None,
        authors: list[str] = None,
        url: str = None,
        depth: int = 0,
    ) -> bool:
        """
        Add a new paper to the state.
        Returns True if paper was added, False if already exists.
        """
        if paper_id in self.papers:
            return False

        self.papers[paper_id] = {
            "paper_id": paper_id,
            "title": title,
            "abstract": abstract,
            "year": year,
            "venue": venue,
            "authors": authors or [],
            "url": url,
            "source": source,
            "source_paper_id": source_paper_id,
            "depth": depth,  # Distance from seed papers
            "status": "fetched" if abstract else "pending",
            "classification": None,
            "classification_confidence": None,
            "added_at": datetime.now().isoformat(),
            "fetched_at": datetime.now().isoformat() if abstract else None,
            "classified_at": None,
            "expanded_at": None,
            "citations_checked_at": None,
        }
        return True

    def get_paper(self, paper_id: str) -> dict | None:
        """Get a paper by ID."""
        return self.papers.get(paper_id)

    def has_paper(self, paper_id: str) -> bool:
        """Check if paper exists in state."""
        return paper_id in self.papers

    def update_paper(self, paper_id: str, **kwargs):
        """Update paper fields."""
        if paper_id in self.papers:
            self.papers[paper_id].update(kwargs)

    def set_fetched(self, paper_id: str, abstract: str = None, **metadata):
        """Mark paper as fetched with metadata."""
        if paper_id in self.papers:
            self.papers[paper_id].update({
                "status": "fetched",
                "abstract": abstract,
                "fetched_at": datetime.now().isoformat(),
                **metadata,
            })

    def set_classified(self, paper_id: str, category: Category, confidence: str = "HIGH"):
        """Mark paper as classified."""
        if paper_id in self.papers:
            if category == "NONE":
                status = "discarded"
            else:
                status = "classified"

            self.papers[paper_id].update({
                "status": status,
                "classification": category,
                "classification_confidence": confidence,
                "classified_at": datetime.now().isoformat(),
            })

    def set_expanded(self, paper_id: str):
        """Mark paper as expanded (citations/references fetched)."""
        if paper_id in self.papers:
            self.papers[paper_id].update({
                "status": "expanded",
                "expanded_at": datetime.now().isoformat(),
            })

    def set_citations_checked(self, paper_id: str):
        """Update when citations were last checked."""
        if paper_id in self.papers:
            self.papers[paper_id]["citations_checked_at"] = datetime.now().isoformat()

    def get_papers_by_status(self, status: Status) -> list[dict]:
        """Get all papers with a given status."""
        return [p for p in self.papers.values() if p.get("status") == status]

    def get_pending_papers(self) -> list[dict]:
        """Get papers that need metadata fetching."""
        return self.get_papers_by_status("pending")

    def get_papers_to_classify(self) -> list[dict]:
        """Get papers that have metadata but need classification."""
        return self.get_papers_by_status("fetched")

    def get_papers_to_expand(self) -> list[dict]:
        """Get classified papers that haven't been expanded yet."""
        return self.get_papers_by_status("classified")

    def get_papers_for_discovery(self, days_since_check: int = 7) -> list[dict]:
        """Get papers that need citation checking (for daily discovery)."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days_since_check)).isoformat()

        result = []
        for p in self.papers.values():
            if p.get("status") in ("classified", "expanded"):
                last_check = p.get("citations_checked_at")
                if not last_check or last_check < cutoff:
                    result.append(p)
        return result

    def get_classified_papers(self, category: Category = None) -> list[dict]:
        """Get all classified papers, optionally filtered by category."""
        result = []
        for p in self.papers.values():
            if p.get("status") in ("classified", "expanded"):
                if category is None or p.get("classification") == category:
                    result.append(p)
        return result

    def stats(self) -> dict:
        """Get current statistics."""
        self._update_metadata()
        return self.metadata


def main():
    """CLI for inspecting state."""
    import argparse

    parser = argparse.ArgumentParser(description="Paper state management")
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--status", type=str, help="List papers by status")
    parser.add_argument("--category", type=str, help="List papers by category")
    args = parser.parse_args()

    state = PaperState(args.state_file)

    if args.stats:
        stats = state.stats()
        print(f"Total papers: {stats['total_papers']}")
        print(f"\nBy status:")
        for status, count in sorted(stats['by_status'].items()):
            print(f"  {status}: {count}")
        print(f"\nBy category:")
        for cat, count in sorted(stats['by_category'].items()):
            print(f"  {cat}: {count}")

    elif args.status:
        papers = state.get_papers_by_status(args.status)
        print(f"Papers with status '{args.status}': {len(papers)}")
        for p in papers[:10]:
            print(f"  - {p['title'][:60]}...")

    elif args.category:
        papers = state.get_classified_papers(args.category)
        print(f"Papers classified as '{args.category}': {len(papers)}")
        for p in papers[:10]:
            print(f"  - {p['title'][:60]}...")


if __name__ == "__main__":
    main()
