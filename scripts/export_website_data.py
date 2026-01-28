#!/usr/bin/env python3
"""
Export paper data for website consumption.

Combines paper_state.json (S2 enrichment) with classifications_claude.json
to create per-category JSON files with all the rich data.
"""

import json
from pathlib import Path
from datetime import datetime

# Category definitions
CATEGORIES = {
    "ML01": "Input Manipulation Attack",
    "ML02": "Data Poisoning Attack",
    "ML03": "Model Inversion Attack",
    "ML04": "Membership Inference Attack",
    "ML05": "Model Theft",
    "ML06": "AI Supply Chain Attacks",
    "ML07": "Transfer Learning Attack",
    "ML08": "Model Skewing",
    "ML09": "Output Integrity Attack",
    "ML10": "Model Poisoning"
}


def load_data():
    """Load paper state and classifications."""
    data_dir = Path(__file__).parent.parent / "data"

    with open(data_dir / "paper_state.json") as f:
        state = json.load(f)

    with open(data_dir / "classifications_claude.json") as f:
        classifications = json.load(f)

    return state["papers"], classifications["papers"]


def build_title_index(papers):
    """Build index of papers by title for lookup."""
    index = {}
    for paper_id, paper in papers.items():
        title = paper.get("title", "").lower().strip()
        if title:
            index[title] = paper_id
    return index


def format_paper_for_website(paper, classification):
    """Format a paper with all enriched data for the website."""
    s2 = paper.get("s2", {})

    # Get the best citation count (prefer S2)
    citation_count = s2.get("citation_count") or paper.get("cited_by_count", 0)

    # Get the best venue
    venue = s2.get("venue") or paper.get("venue")

    # Get publication date
    pub_date = s2.get("publication_date") or paper.get("publication_date")

    # Get authors with h-index from S2 if available
    s2_authors = s2.get("authors", [])
    if s2_authors:
        authors = []
        author_details = []
        for a in s2_authors:
            authors.append(a.get("name", "Unknown"))
            author_details.append({
                "name": a.get("name"),
                "h_index": a.get("h_index"),
                "citation_count": a.get("citation_count"),
                "affiliations": a.get("affiliations", [])
            })
    else:
        authors = paper.get("authors", [])
        author_details = []

    # Get max h-index among authors
    max_h_index = 0
    if author_details:
        h_indices = [a.get("h_index", 0) for a in author_details if a.get("h_index")]
        max_h_index = max(h_indices) if h_indices else 0

    # Build the output
    result = {
        "paper_id": paper.get("paper_id"),
        "title": paper.get("title"),
        "abstract": paper.get("abstract"),
        "year": paper.get("year"),
        "venue": venue,
        "authors": authors,
        "author_details": author_details if author_details else None,
        "max_h_index": max_h_index,

        # URLs
        "url": paper.get("url") or paper.get("openalex_id"),
        "pdf_url": paper.get("pdf_url"),
        "doi": paper.get("doi"),

        # S2 enrichment
        "citation_count": citation_count,
        "influential_citation_count": s2.get("influential_citation_count", 0),
        "reference_count": s2.get("reference_count"),
        "is_open_access": s2.get("is_open_access", False),
        "publication_date": pub_date,

        # TLDR summary
        "tldr": s2.get("tldr", {}).get("text") if s2.get("tldr") else None,

        # S2 fields of study
        "fields_of_study": s2.get("fields_of_study"),
        "publication_types": s2.get("publication_types"),

        # Classification data
        "paper_type": classification.get("type"),
        "domains": classification.get("domains", []),
        "model_types": classification.get("models", []),
        "tags": classification.get("tags", []),

        # Open access PDF
        "open_access_pdf": s2.get("open_access_pdf", {}).get("url") if s2.get("open_access_pdf") else None,
    }

    # Clean up None values
    result = {k: v for k, v in result.items() if v is not None}

    return result


def main():
    print("Loading data...")
    papers, classifications = load_data()
    title_index = build_title_index(papers)

    print(f"Papers in state: {len(papers)}")
    print(f"Classifications: {len(classifications)}")

    # Build category paper lists
    category_papers = {cat: [] for cat in CATEGORIES}
    matched = 0
    unmatched = []

    for cls in classifications:
        title = cls.get("title", "").lower().strip()
        paper_id = title_index.get(title)

        if not paper_id:
            unmatched.append(cls.get("title", ""))[:50]
            continue

        paper = papers[paper_id]
        formatted = format_paper_for_website(paper, cls)

        # Add to each category it belongs to
        owasp_labels = cls.get("owasp", [])
        for label in owasp_labels:
            if label in category_papers:
                category_papers[label].append(formatted)
                matched += 1

    print(f"Matched: {matched} paper-category assignments")
    if unmatched:
        print(f"Unmatched: {len(unmatched)} classifications")

    # Export per-category files
    data_dir = Path(__file__).parent.parent / "data"
    today = datetime.now().strftime("%Y-%m-%d")

    for cat_id, cat_name in CATEGORIES.items():
        papers_list = category_papers[cat_id]

        # Sort by citation count (most cited first)
        papers_list.sort(key=lambda p: p.get("citation_count", 0), reverse=True)

        output = {
            "owasp_id": cat_id,
            "owasp_name": cat_name,
            "total": len(papers_list),
            "updated": today,
            "papers": papers_list
        }

        output_path = data_dir / f"{cat_id.lower()}_papers.json"
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"  {cat_id}: {len(papers_list)} papers -> {output_path.name}")

    # Update manifest
    manifest = {
        "version": 2,
        "updated": today,
        "total_papers": len(papers),
        "categories": {}
    }

    for cat_id in CATEGORIES:
        manifest["categories"][cat_id] = {
            "file": f"{cat_id.lower()}_papers.json",
            "count": len(category_papers[cat_id])
        }

    manifest_path = data_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest updated: {manifest_path.name}")
    print("Done!")


if __name__ == "__main__":
    main()
