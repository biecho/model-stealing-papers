#!/usr/bin/env python3
"""
Run paper filtering for all OWASP ML Security Top 10 categories.

Usage:
    python run_all.py                    # Filter all categories
    python run_all.py --list             # List available configs
    python run_all.py --category ML05    # Filter specific category
    python run_all.py --stats            # Show stats for all categories
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.config import Config, set_config
from src.pipeline import FilterPipeline, FilterStats
from src.utils import load_papers, save_papers


def list_configs() -> None:
    """List all available OWASP category configurations."""
    main_configs = Config.list_main_configs()

    print("=" * 70)
    print("OWASP ML Security Top 10 - Available Configurations")
    print("=" * 70)

    for config in main_configs:
        print(f"\n{config.owasp_id}: {config.owasp_name}")
        print(f"  Config: {config.config_path}")
        print(f"  Description: {config.short_description}")

        # Show subcategories
        subcats = Config.list_subcategories(config.owasp_id)
        for sub in subcats:
            print(f"  └─ {sub.owasp_id}: {sub.owasp_name}")
            print(f"       {sub.short_description}")


def filter_category(
    config: Config, input_file: Path, output_dir: Path, verbose: bool = True
) -> dict:
    """
    Filter papers for a single category.

    Returns:
        Dictionary with filtering results
    """
    set_config(config)

    if verbose:
        print(f"\n{'='*70}")
        print(f"{config.owasp_id}: {config.owasp_name}")
        print(f"{'='*70}")

    # Load papers
    papers, metadata = load_papers(input_file)
    if verbose:
        print(f"Loaded {len(papers)} papers")

    # Run pipeline
    pipeline = FilterPipeline()
    results = pipeline.process_batch(papers)

    # Calculate stats
    stats = FilterStats(results)
    relevant_count = len([r for r in results if r.is_relevant])
    excluded_count = len([r for r in results if not r.is_relevant])

    if verbose:
        print(f"  Relevant: {relevant_count}")
        print(f"  Excluded: {excluded_count}")

    # Save results
    output_file = output_dir / f"{config.owasp_id.lower()}_papers.json"
    relevant_papers = [r.paper for r in results if r.is_relevant]

    save_papers(
        relevant_papers,
        output_file,
        metadata={
            "owasp_id": config.owasp_id,
            "owasp_name": config.owasp_name,
            "description": config.short_description,
            "keywords": metadata.get("keywords"),
        },
        note=f"Filtered for {config.owasp_name}",
    )

    if verbose:
        print(f"  Saved to: {output_file}")

    result = {
        "owasp_id": config.owasp_id,
        "owasp_name": config.owasp_name,
        "total": len(papers),
        "relevant": relevant_count,
        "excluded": excluded_count,
        "output_file": str(output_file),
    }
    if config.parent_id:
        result["parent_id"] = config.parent_id
    return result


def filter_all(input_file: Path, output_dir: Path) -> list[dict]:
    """Filter papers for all categories and subcategories."""
    all_configs = Config.list_configs()
    main_results = []
    sub_results = []

    print("=" * 70)
    print("OWASP ML Security Top 10 - Filtering All Categories")
    print("=" * 70)
    print(f"Input: {input_file}")
    print(f"Output directory: {output_dir}")

    for config in all_configs:
        result = filter_category(config, input_file, output_dir)
        if config.is_subcategory:
            sub_results.append(result)
        else:
            main_results.append(result)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Category':<10} {'Name':<30} {'Papers':>8}")
    print("-" * 52)
    for r in main_results:
        print(f"{r['owasp_id']:<10} {r['owasp_name'][:30]:<30} {r['relevant']:>8}")
        # Show subcategories
        for s in sub_results:
            if s.get('parent_id') == r['owasp_id']:
                print(f"  └─{s['owasp_id']:<6} {s['owasp_name'][:28]:<28} {s['relevant']:>8}")

    # Save manifest with structured hierarchy
    manifest = {
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "categories": main_results,
        "subcategories": sub_results,
    }
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved to: {manifest_file}")

    return main_results + sub_results


def show_stats(output_dir: Path) -> None:
    """Show statistics for all filtered categories."""
    manifest_file = output_dir / "manifest.json"

    if not manifest_file.exists():
        print("No manifest found. Run filtering first.")
        return

    with open(manifest_file) as f:
        manifest = json.load(f)

    print("=" * 70)
    print("OWASP ML Security Top 10 - Statistics")
    print("=" * 70)
    print(f"Last updated: {manifest['updated']}")
    print()

    total_papers = 0
    for cat in manifest["categories"]:
        print(f"{cat['owasp_id']}: {cat['owasp_name']}")
        print(f"  Papers: {cat['relevant']}")
        total_papers += cat["relevant"]

    print("-" * 70)
    print(f"Total papers across categories: {total_papers}")
    print("(Note: Papers may appear in multiple categories)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter papers for OWASP ML Security Top 10 categories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-i", "--input",
        default="papers.json",
        help="Input papers JSON file (default: papers.json)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="data",
        help="Output directory for filtered papers (default: data)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available category configurations",
    )
    parser.add_argument(
        "--category",
        help="Filter specific category only (e.g., ML05)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics for all categories",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_dir = Path(args.output_dir)

    if args.list:
        list_configs()
        return 0

    if args.stats:
        show_stats(output_dir)
        return 0

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

    if args.category:
        # Filter single category
        configs = Config.list_configs()
        matching = [c for c in configs if c.owasp_id.upper() == args.category.upper()]
        if not matching:
            print(f"Category not found: {args.category}")
            print("Use --list to see available categories")
            return 1
        filter_category(matching[0], input_file, output_dir)
    else:
        # Filter all categories
        filter_all(input_file, output_dir)

    return 0


if __name__ == "__main__":
    exit(main())
