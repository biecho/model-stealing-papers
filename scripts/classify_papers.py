#!/usr/bin/env python3
"""
Classify papers into OWASP ML Security categories using embeddings.

Usage:
    python scripts/classify_papers.py                    # Classify all papers
    python scripts/classify_papers.py --regenerate       # Regenerate category files
    python scripts/classify_papers.py --evaluate         # Evaluate accuracy
    python scripts/classify_papers.py --sample 10        # Classify sample papers
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from ml_security.classifier import EmbeddingsClassifier, CATEGORY_DESCRIPTIONS
from ml_security.utils import load_papers, save_papers


def classify_all(input_file: Path, output_file: Path, top_k: int = 3):
    """Classify all papers and save results."""
    print(f"Loading papers from {input_file}...")
    papers, metadata = load_papers(input_file)
    print(f"Loaded {len(papers)} papers")

    print("\nInitializing classifier...")
    classifier = EmbeddingsClassifier()

    print("\nClassifying papers...")
    # Convert Paper objects to dicts
    paper_dicts = [
        {"id": p.paper_id, "title": p.title, "abstract": p.abstract}
        for p in papers
    ]
    results = classifier.classify_batch(paper_dicts, top_k=top_k)

    # Build output with classifications
    output = {
        "metadata": {
            "total_papers": len(results),
            "categories": list(CATEGORY_DESCRIPTIONS.keys()),
        },
        "classifications": [r.to_dict() for r in results],
    }

    # Save results
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved classifications to {output_file}")

    # Print summary
    print("\n" + "=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)

    category_counts = {}
    for r in results:
        top_cat = r.top_category()[0]
        category_counts[top_cat] = category_counts.get(top_cat, 0) + 1

    for cat_id in sorted(category_counts.keys()):
        name = CATEGORY_DESCRIPTIONS.get(cat_id, {}).get("name", cat_id)
        count = category_counts[cat_id]
        print(f"{cat_id}: {name:<30} {count:>5} papers")


def evaluate_accuracy(data_dir: Path):
    """Evaluate classifier accuracy using existing filtered papers."""
    print("Initializing classifier...")
    classifier = EmbeddingsClassifier()

    print("\nEvaluating accuracy on filtered category papers...")
    print("=" * 60)

    for cat_id in sorted(CATEGORY_DESCRIPTIONS.keys()):
        cat_file = data_dir / f"{cat_id.lower()}_papers.json"
        if not cat_file.exists():
            print(f"{cat_id}: No data file found")
            continue

        papers, _ = load_papers(cat_file)
        if not papers:
            print(f"{cat_id}: No papers")
            continue

        paper_dicts = [
            {"id": p.paper_id, "title": p.title, "abstract": p.abstract}
            for p in papers
        ]

        metrics = classifier.evaluate_accuracy(paper_dicts, cat_id)

        name = CATEGORY_DESCRIPTIONS[cat_id]["name"]
        print(f"{cat_id}: {name}")
        print(f"  Papers: {metrics['total']}")
        print(f"  Top-1 Accuracy: {metrics['top1_accuracy']:.1%}")
        print(f"  Top-3 Accuracy: {metrics['top3_accuracy']:.1%}")
        print()


def sample_classify(input_file: Path, n: int = 10):
    """Classify a sample of papers and show detailed results."""
    print(f"Loading papers from {input_file}...")
    papers, _ = load_papers(input_file)

    # Take a sample
    import random
    sample = random.sample(papers, min(n, len(papers)))

    print(f"\nClassifying {len(sample)} sample papers...")
    classifier = EmbeddingsClassifier()

    print("\n" + "=" * 70)
    for paper in sample:
        result = classifier.classify(
            paper_id=paper.paper_id,
            title=paper.title,
            abstract=paper.abstract,
            top_k=3
        )

        print(f"\nTitle: {paper.title[:80]}...")
        print(f"Top categories:")
        for cat_id, conf in result.categories:
            name = CATEGORY_DESCRIPTIONS.get(cat_id, {}).get("name", cat_id)
            print(f"  {cat_id}: {name} ({conf:.3f})")
        print("-" * 70)


def regenerate_categories(input_file: Path, output_dir: Path, threshold: float = 0.3):
    """Regenerate category files using embeddings classification."""
    print(f"Loading papers from {input_file}...")
    papers, metadata = load_papers(input_file)
    print(f"Loaded {len(papers)} papers")

    print("\nInitializing classifier...")
    classifier = EmbeddingsClassifier()

    print("\nClassifying papers...")
    paper_dicts = [
        {"id": p.paper_id, "title": p.title, "abstract": p.abstract}
        for p in papers
    ]
    results = classifier.classify_batch(paper_dicts, top_k=3)

    # Build paper lookup
    paper_lookup = {p.paper_id: p for p in papers}

    # Group papers by top category
    category_papers = {cat_id: [] for cat_id in CATEGORY_DESCRIPTIONS}

    for result in results:
        top_cat, confidence = result.top_category()
        if confidence >= threshold and top_cat in category_papers:
            paper = paper_lookup.get(result.paper_id)
            if paper:
                category_papers[top_cat].append(paper)

    # Save category files
    print("\n" + "=" * 60)
    print("REGENERATING CATEGORY FILES")
    print("=" * 60)

    manifest_categories = []

    for cat_id in sorted(CATEGORY_DESCRIPTIONS.keys()):
        cat_info = CATEGORY_DESCRIPTIONS[cat_id]
        papers_list = category_papers[cat_id]

        output_file = output_dir / f"{cat_id.lower()}_papers.json"
        save_papers(
            papers_list,
            output_file,
            metadata={
                "owasp_id": cat_id,
                "owasp_name": cat_info["name"],
                "description": cat_info["description"].strip(),
            },
            note=f"Classified by embeddings (threshold={threshold})",
        )

        print(f"{cat_id}: {cat_info['name']:<30} {len(papers_list):>5} papers")

        manifest_categories.append({
            "owasp_id": cat_id,
            "owasp_name": cat_info["name"],
            "total": len(papers),
            "relevant": len(papers_list),
            "excluded": len(papers) - len(papers_list),
            "output_file": f"data/{cat_id.lower()}_papers.json",
        })

    # Save manifest
    manifest = {
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "categories": manifest_categories,
        "subcategories": [],  # No subcategories for now
    }
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved to: {manifest_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Classify papers using embeddings"
    )
    parser.add_argument(
        "-i", "--input",
        default="data/papers.json",
        help="Input papers JSON file",
    )
    parser.add_argument(
        "-o", "--output",
        default="data/classifications.json",
        help="Output classifications file",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output directory for category files (default: data)",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate category files using embeddings classification",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Evaluate accuracy on existing filtered papers",
    )
    parser.add_argument(
        "--sample",
        type=int,
        metavar="N",
        help="Classify N sample papers with detailed output",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top categories to return (default: 3)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Minimum confidence threshold for classification (default: 0.3)",
    )

    args = parser.parse_args()

    if args.evaluate:
        evaluate_accuracy(Path("data"))
    elif args.sample:
        sample_classify(Path(args.input), args.sample)
    elif args.regenerate:
        regenerate_categories(Path(args.input), Path(args.output_dir), args.threshold)
    else:
        classify_all(Path(args.input), Path(args.output), args.top_k)


if __name__ == "__main__":
    main()
