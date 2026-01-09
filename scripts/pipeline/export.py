#!/usr/bin/env python3
"""
Export classified papers to category-specific JSON files.

Generates:
- data/ml01_papers.json through ml10_papers.json
- data/manifest.json with summary statistics
"""

import json
from datetime import datetime
from pathlib import Path

from state import PaperState

CATEGORY_NAMES = {
    "ML01": "Input Manipulation Attack",
    "ML02": "Data Poisoning Attack",
    "ML03": "Model Inversion Attack",
    "ML04": "Membership Inference Attack",
    "ML05": "Model Theft",
    "ML06": "AI Supply Chain Attacks",
    "ML07": "Transfer Learning Attack",
    "ML08": "Model Skewing",
    "ML09": "Output Integrity Attack",
    "ML10": "Model Poisoning",
}


def export_category(papers: list[dict], category: str, output_dir: Path):
    """Export papers for a single category."""
    output_file = output_dir / f"{category.lower()}_papers.json"

    # Clean up paper data for export
    export_papers = []
    for p in papers:
        export_papers.append({
            "paper_id": p.get("openalex_id") or p.get("paper_id"),
            "title": p["title"],
            "abstract": p.get("abstract"),
            "year": p.get("year"),
            "venue": p.get("venue"),
            "authors": p.get("authors", []),
            "url": p.get("url"),
            "pdf_url": p.get("pdf_url"),
            "cited_by_count": p.get("cited_by_count"),
            "classification_confidence": p.get("classification_confidence"),
        })

    data = {
        "owasp_id": category,
        "owasp_name": CATEGORY_NAMES.get(category, category),
        "total": len(export_papers),
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "papers": export_papers,
    }

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    return len(export_papers)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Export papers to category files")
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    state = PaperState(args.state_file)

    print("Exporting papers by category...", flush=True)

    manifest_categories = []
    total_exported = 0

    for category in ["ML01", "ML02", "ML03", "ML04", "ML05", "ML06", "ML07", "ML08", "ML09", "ML10"]:
        papers = state.get_classified_papers(category)
        count = export_category(papers, category, args.output_dir)
        total_exported += count

        manifest_categories.append({
            "owasp_id": category,
            "owasp_name": CATEGORY_NAMES[category],
            "total": count,
            "file": f"{category.lower()}_papers.json",
        })

        print(f"  {category}: {count} papers", flush=True)

    # Generate manifest
    stats = state.stats()
    manifest = {
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "total_papers": stats["total_papers"],
        "total_classified": total_exported,
        "total_discarded": stats["by_status"].get("discarded", 0),
        "categories": manifest_categories,
        "pipeline_stats": {
            "by_status": stats["by_status"],
            "by_category": stats["by_category"],
        },
    }

    manifest_file = args.output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to: {manifest_file}", flush=True)
    print(f"Total exported: {total_exported} papers", flush=True)


if __name__ == "__main__":
    main()
