#!/usr/bin/env python3
"""
Fetch ML security papers from Semantic Scholar API.

Usage:
    python fetch_papers.py [--output papers.json]
    python fetch_papers.py -c configs/ml01a_prompt_injection.yaml -o data/prompt_injection_raw.json
"""

import argparse
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import requests

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# API key from environment variable (optional, but recommended for higher rate limits)
API_KEY = os.environ.get("S2_API_KEY")


# Seed papers for citation crawling (seminal works in model stealing)
# Format: (paper_id, short_name) - paper_id is from Semantic Scholar
SEED_PAPERS = [
    # Foundational query-based attacks
    ("8a95423d0059f7c5b1422f0ef1aa60b9e26aab7e", "Tramèr 2016 - Stealing ML Models"),
    ("089c6224cfbcf5c18b63564eb65001c7c42a7acf", "Knockoff Nets 2018"),
    ("ac713aebdcc06f15f8ea61e1140bb360341fdf27", "Thieves on Sesame Street 2019"),
    ("4d548fd21aad60e3052455e22b7a57cc1f06e3c3", "CloudLeak 2020"),
    ("d8f64187b447d1b64f69f541dbbaec71bd79d205", "ActiveThief 2020"),

    # Cryptanalytic / side-channel attacks
    ("186377b9098efc726b8f1bda7e4f8aa2ed7bafa5", "Cryptanalytic Extraction 2020"),
    ("109ad71af2ffce01b60852f8141ea91be6eed9e1", "DeepSniffer 2020"),
    ("f5014e34ed13191082cd20cc279ca4cc9adee84f", "Stealing via Timing Side Channels 2018"),

    # Defenses
    ("4582e2350e4822834dcf266522690722dd4430d4", "PRADA 2018"),
    ("abbb0fd559ade70265f4f528df094fbbd8ae2040", "Entangled Watermarks 2020"),
    ("da10f79f983fd4fbd589ed7ffa68d33964841443", "Prediction Poisoning 2019"),

    # Surveys
    ("d405b58a8f465d5ba2e91f9541e09760904c11a8", "Survey: Stealing ML Models 2022"),
]

# Keywords to search for (expanded with shorter/variant terms)
KEYWORDS = [
    # Core terms - shorter for better matching
    "model stealing",
    "model extraction",
    "model theft",
    "steal model",
    "stealing model",
    "extract model",

    # With "attack" suffix
    "model stealing attack",
    "model extraction attack",
    "neural network extraction attack",

    # Specific attack names
    "knockoff nets",
    "knockoff net",
    "copycat CNN",
    "copycat model",
    "imitation attack",
    "clone model",
    "cloning attack",

    # ML/DNN specific
    "stealing machine learning",
    "steal ML model",
    "steal ML models",
    "steal neural network",
    "DNN model stealing",
    "DNN extraction",
    "stealing deep learning",
    "LLM stealing",
    "LLM extraction",
    "stealing language model",

    # Functionality/black-box
    "stealing functionality",
    "functionality stealing",
    "black-box model stealing",
    "blackbox model extraction",

    # Defense terms
    "model stealing defense",
    "model extraction defense",
    "prevent model stealing",
    "protect model extraction",

    # Side-channel approaches
    "side-channel model extraction",
    "side-channel neural network",
    "timing attack neural network",
    "cache attack DNN",
    "power analysis neural network",
    "electromagnetic neural network",
    "DNN weights leakage",
    "neural network weight extraction",

    # Reverse engineering
    "reverse engineer neural network",
    "reverse engineering DNN",
    "cryptanalytic extraction neural",

    # API/query-based
    "API model extraction",
    "query-based model stealing",
    "prediction API stealing",
]

# Venues to exclude (not related to ML security)
EXCLUDED_VENUES = [
    "IEEE transactions on microwave theory and techniques",
    "IEEE Transactions on Microwave Theory and Techniques",
]


def load_keywords_from_config(config_path: str) -> tuple[list[str], str]:
    """
    Load keywords from a YAML config file.

    Returns:
        Tuple of (keywords list, domain name)
    """
    if not YAML_AVAILABLE:
        raise ImportError("PyYAML is required to use config files. Install with: pip install pyyaml")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Combine all keyword types into a single list
    keywords = []
    keywords.extend(config.get("high_quality_keywords", []))
    keywords.extend(config.get("core_keywords", []))
    keywords.extend(config.get("defense_keywords", []))

    domain_name = config.get("domain", {}).get("name", "unknown")
    owasp_id = config.get("domain", {}).get("owasp_id", "")

    if owasp_id:
        domain_name = f"{owasp_id} - {domain_name}"

    return keywords, domain_name

# Fields to request from the API
FIELDS = "title,abstract,year,venue,authors,citationCount,url,openAccessPdf,publicationDate"

# API endpoint
SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


@dataclass
class Paper:
    paper_id: str
    title: str
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    authors: list[str]
    citation_count: int
    url: str
    pdf_url: Optional[str]
    publication_date: Optional[str]
    keywords_matched: list[str]  # which search keywords matched this paper
    first_seen: Optional[str] = None  # when this paper was first added


def search_papers(query: str, limit: int = 100) -> list[dict]:
    """Search for papers matching a query."""
    papers = []
    offset = 0

    # Add API key header if available
    headers = {}
    if API_KEY:
        headers["x-api-key"] = API_KEY

    while True:
        params = {
            "query": query,
            "fields": FIELDS,
            "limit": min(limit - len(papers), 100),  # API max is 100 per request
            "offset": offset,
        }

        response = requests.get(SEARCH_URL, params=params, headers=headers)

        if response.status_code == 429:
            # Rate limited, wait and retry
            print(f"  Rate limited, waiting 5 seconds...")
            time.sleep(5)
            continue

        response.raise_for_status()
        data = response.json()

        batch = data.get("data", [])
        if not batch:
            break

        papers.extend(batch)
        print(f"  Fetched {len(papers)} papers...")

        if len(papers) >= limit or "next" not in data:
            break

        offset += len(batch)
        time.sleep(0.5)  # Be nice to the API

    return papers[:limit]


def fetch_citations(paper_id: str, limit: Optional[int] = None) -> list[dict]:
    """Fetch papers that cite a given paper. If limit is None, fetch all."""
    citations_url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
    papers = []
    offset = 0

    headers = {}
    if API_KEY:
        headers["x-api-key"] = API_KEY

    while limit is None or len(papers) < limit:
        batch_size = 100 if limit is None else min(limit - len(papers), 100)
        params = {
            "fields": FIELDS,
            "limit": batch_size,
            "offset": offset,
        }

        response = requests.get(citations_url, params=params, headers=headers)

        if response.status_code == 429:
            print(f"  Rate limited, waiting 5 seconds...")
            time.sleep(5)
            continue

        if response.status_code == 404:
            print(f"  Paper {paper_id} not found")
            break

        response.raise_for_status()
        data = response.json()

        batch = data.get("data", [])
        if not batch:
            break

        # Extract the citing paper from each citation entry
        for entry in batch:
            citing_paper = entry.get("citingPaper", {})
            if citing_paper.get("paperId"):
                papers.append(citing_paper)

        print(f"  Fetched {len(papers)} citations...")

        if "next" not in data:
            break
        if limit is not None and len(papers) >= limit:
            break

        offset += len(batch)
        time.sleep(0.5)

    return papers if limit is None else papers[:limit]


def fetch_citations_from_seeds(seed_papers: list[tuple], limit_per_seed: Optional[int] = None) -> list[dict]:
    """Fetch citations from all seed papers."""
    all_citations = []
    seen_ids = set()

    for paper_id, name in seed_papers:
        print(f"Fetching citations for: {name}")
        citations = fetch_citations(paper_id, limit=limit_per_seed)

        for paper in citations:
            pid = paper.get("paperId")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_citations.append(paper)

        print(f"  Total unique citations so far: {len(all_citations)}")
        time.sleep(1)  # Be nice between seed papers

    return all_citations


def is_relevant(paper: dict, keywords: list[str]) -> bool:
    """Check if paper is relevant based on keyword occurrence in title/abstract."""
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    text = title + " " + abstract

    # Must have at least one keyword in title or abstract
    for kw in keywords:
        if kw.lower() in text:
            return True

    # Additional title patterns for side-channel/hardware attacks on ML
    title_patterns = [
        "leak" in title and ("dnn" in title or "neural" in title or "weight" in title),
        "side-channel" in title and ("neural" in title or "dnn" in title or "ml" in title),
        "electromagnetic" in title and "neural" in title,
        "power analysis" in title and ("neural" in title or "dnn" in title),
    ]
    if any(title_patterns):
        return True

    return False


def get_matched_keywords(paper: dict, keywords: list[str]) -> list[str]:
    """Get list of keywords that matched this paper."""
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    text = title + " " + abstract

    matched = []
    for kw in keywords:
        if kw.lower() in text:
            matched.append(kw)

    # Check title patterns for side-channel attacks and model stealing
    if not matched:
        if "leak" in title and ("dnn" in title or "neural" in title or "weight" in title):
            matched.append("DNN weights leakage (title)")
        elif "side-channel" in title and ("neural" in title or "dnn" in title or "ml" in title):
            matched.append("side-channel attack (title)")
        elif "electromagnetic" in title and "neural" in title:
            matched.append("electromagnetic analysis (title)")
        elif "power analysis" in title and ("neural" in title or "dnn" in title):
            matched.append("power analysis (title)")
        elif "stealing" in title and ("model" in title or "neural" in title or "llm" in title or "language model" in title):
            matched.append("model stealing (title)")

    return matched


def parse_paper(raw: dict, keywords_matched: list[str]) -> Paper:
    """Parse raw API response into Paper object."""
    authors = [a.get("name", "") for a in raw.get("authors", [])]

    pdf_url = None
    if raw.get("openAccessPdf"):
        pdf_url = raw["openAccessPdf"].get("url")

    return Paper(
        paper_id=raw.get("paperId", ""),
        title=raw.get("title", ""),
        abstract=raw.get("abstract"),
        year=raw.get("year"),
        venue=raw.get("venue"),
        authors=authors,
        citation_count=raw.get("citationCount", 0),
        url=raw.get("url", ""),
        pdf_url=pdf_url,
        publication_date=raw.get("publicationDate"),
        keywords_matched=keywords_matched,
    )


def fetch_papers_by_keywords(keywords: list[str], limit_per_keyword: int = 100) -> list[Paper]:
    """Fetch papers for all keywords and deduplicate."""
    seen_ids = set()
    papers = []

    for keyword in keywords:
        print(f"Searching for: {keyword}")
        results = search_papers(keyword, limit=limit_per_keyword)

        for raw in results:
            paper_id = raw.get("paperId")
            if not paper_id or paper_id in seen_ids:
                continue

            # Skip excluded venues
            venue = raw.get("venue") or ""
            if venue in EXCLUDED_VENUES:
                continue

            # Check relevance
            matched = get_matched_keywords(raw, keywords)
            if not matched:
                continue

            seen_ids.add(paper_id)
            papers.append(parse_paper(raw, matched))

    print(f"\nTotal unique relevant papers from keywords: {len(papers)}")
    return papers


def fetch_papers_by_citations(
    seed_papers: list[tuple],
    keywords: list[str],
    limit_per_seed: Optional[int] = None,
) -> list[Paper]:
    """Fetch papers by crawling citations from seed papers, filtered by keywords."""
    print("\n=== Citation Crawling ===")

    # Fetch all citations from seed papers
    raw_citations = fetch_citations_from_seeds(seed_papers, limit_per_seed=limit_per_seed)
    print(f"Total raw citations fetched: {len(raw_citations)}")

    # Filter and parse
    seen_ids = set()
    papers = []

    for raw in raw_citations:
        paper_id = raw.get("paperId")
        if not paper_id or paper_id in seen_ids:
            continue

        # Skip excluded venues
        venue = raw.get("venue") or ""
        if venue in EXCLUDED_VENUES:
            continue

        # Check relevance using keywords
        matched = get_matched_keywords(raw, keywords)
        if not matched:
            continue

        seen_ids.add(paper_id)
        # Mark that this came from citation crawling
        matched.append("(via citation)")
        papers.append(parse_paper(raw, matched))

    print(f"Relevant papers from citations: {len(papers)}")
    return papers


def fetch_all_papers(
    keywords: list[str],
    seed_papers: list[tuple],
    limit_per_keyword: int = 100,
    limit_per_seed: Optional[int] = None,
) -> list[Paper]:
    """Fetch papers using both keyword search and citation crawling."""

    # 1. Keyword-based search
    print("=== Keyword Search ===")
    keyword_papers = fetch_papers_by_keywords(keywords, limit_per_keyword)

    # 2. Citation-based crawling
    citation_papers = fetch_papers_by_citations(seed_papers, keywords, limit_per_seed)

    # 3. Combine and deduplicate
    seen_ids = set()
    combined = []

    # Add keyword papers first (they have cleaner keyword matches)
    for paper in keyword_papers:
        if paper.paper_id not in seen_ids:
            seen_ids.add(paper.paper_id)
            combined.append(paper)

    # Add citation papers that aren't duplicates
    added_from_citations = 0
    for paper in citation_papers:
        if paper.paper_id not in seen_ids:
            seen_ids.add(paper.paper_id)
            combined.append(paper)
            added_from_citations += 1

    print(f"\n=== Combined Results ===")
    print(f"From keywords: {len(keyword_papers)}")
    print(f"New from citations: {added_from_citations}")
    print(f"Total unique: {len(combined)}")

    return combined


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    import re
    # Lowercase, remove punctuation, collapse whitespace
    t = title.lower()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def titles_are_similar(t1: str, t2: str) -> bool:
    """Check if two normalized titles are similar enough to be duplicates."""
    # Exact match
    if t1 == t2:
        return True
    # One is prefix of the other (handles "Title" vs "Title: Extended")
    if t1.startswith(t2) or t2.startswith(t1):
        min_len = min(len(t1), len(t2))
        if min_len >= 20:  # Only if the common part is substantial
            return True
    # Check word overlap (handles minor word differences)
    words1 = set(t1.split())
    words2 = set(t2.split())
    if len(words1) >= 4 and len(words2) >= 4:
        intersection = words1 & words2
        union = words1 | words2
        jaccard = len(intersection) / len(union)
        if jaccard >= 0.8:  # 80% word overlap
            return True
    return False


def deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    """Remove duplicate papers, keeping the one with best metadata."""
    # Build groups of similar papers
    groups = []
    used = set()

    for i, p1 in enumerate(papers):
        if i in used:
            continue
        norm1 = normalize_title(p1.title)
        group = [p1]
        used.add(i)

        for j, p2 in enumerate(papers):
            if j in used:
                continue
            norm2 = normalize_title(p2.title)
            if titles_are_similar(norm1, norm2):
                group.append(p2)
                used.add(j)

        groups.append(group)

    # For each group, keep the best version
    deduped = []
    for group in groups:
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Score each paper: prefer venue > year > citations
            def score(p):
                return (
                    1 if p.venue else 0,  # Has venue
                    p.year or 0,          # Has year
                    p.citation_count,     # More citations
                )
            best = max(group, key=score)
            deduped.append(best)
            print(f"  Deduped: kept '{best.title}' ({best.venue or 'no venue'}), removed {len(group)-1} duplicate(s)")

    return deduped


def load_existing_papers(filepath: str) -> dict[str, Paper]:
    """Load existing papers from JSON file, indexed by paper_id."""
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath) as f:
            data = json.load(f)
        existing = {}
        for p in data.get("papers", []):
            paper = Paper(
                paper_id=p["paper_id"],
                title=p["title"],
                abstract=p.get("abstract"),
                year=p.get("year"),
                venue=p.get("venue"),
                authors=p.get("authors", []),
                citation_count=p.get("citation_count", 0),
                url=p.get("url", ""),
                pdf_url=p.get("pdf_url"),
                publication_date=p.get("publication_date"),
                keywords_matched=p.get("keywords_matched", []),
                first_seen=p.get("first_seen"),
            )
            existing[paper.paper_id] = paper
        print(f"Loaded {len(existing)} existing papers from {filepath}")
        return existing
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not load existing papers: {e}")
        return {}


def merge_papers(existing: dict[str, Paper], new_papers: list[Paper]) -> list[Paper]:
    """Merge new papers with existing ones. Never removes papers, only adds or updates."""
    today = time.strftime("%Y-%m-%d")
    merged = dict(existing)  # Start with all existing papers
    added = 0
    updated = 0

    # Set first_seen for existing papers that don't have it
    for paper_id, paper in merged.items():
        if not paper.first_seen:
            paper.first_seen = today

    for paper in new_papers:
        if paper.paper_id in merged:
            # Update metadata but preserve first_seen
            old = merged[paper.paper_id]
            paper.first_seen = old.first_seen or today
            merged[paper.paper_id] = paper
            updated += 1
        else:
            # New paper - set first_seen
            paper.first_seen = today
            merged[paper.paper_id] = paper
            added += 1

    print(f"Merge result: {added} new papers, {updated} updated, {len(merged)} total")
    return list(merged.values())


def main():
    parser = argparse.ArgumentParser(description="Fetch ML security papers from Semantic Scholar")
    parser.add_argument("--output", "-o", default="papers.json", help="Output JSON file")
    parser.add_argument("--config", "-c", help="YAML config file to load keywords from")
    parser.add_argument("--limit", "-l", type=int, default=100, help="Max papers per keyword search")
    parser.add_argument("--citation-limit", type=int, default=None, help="Max citations per seed (default: all)")
    parser.add_argument("--no-citations", action="store_true", help="Skip citation crawling")
    args = parser.parse_args()

    # Determine keywords to use
    if args.config:
        keywords, domain_name = load_keywords_from_config(args.config)
        print(f"Using config: {args.config}")
        print(f"Domain: {domain_name}")
        print(f"Keywords: {len(keywords)}")
        # When using config, default to no citations (config-based fetching is keyword-only)
        use_citations = False
        seed_papers = []
    else:
        keywords = KEYWORDS
        seed_papers = SEED_PAPERS
        use_citations = not args.no_citations
        print("Using default model stealing keywords")

    # Load existing papers (we never remove papers, only add)
    existing = load_existing_papers(args.output)

    # Fetch new papers
    if not use_citations or args.no_citations:
        # Keywords only mode
        print("Running in keywords-only mode (no citation crawling)")
        new_papers = fetch_papers_by_keywords(keywords, limit_per_keyword=args.limit)
    else:
        # Full hybrid mode - fetch ALL citations by default
        new_papers = fetch_all_papers(
            keywords=keywords,
            seed_papers=seed_papers,
            limit_per_keyword=args.limit,
            limit_per_seed=args.citation_limit,  # None = fetch all
        )

    # Deduplicate new papers
    new_papers = deduplicate_papers(new_papers)
    print(f"After deduplication: {len(new_papers)} new papers found")

    # Merge with existing (preserves all existing papers)
    papers = merge_papers(existing, new_papers)

    # Sort by year (newest first), then by citations
    papers.sort(key=lambda p: (-(p.year or 0), -p.citation_count))

    # Convert to JSON
    data = {
        "updated": time.strftime("%Y-%m-%d"),
        "total": len(papers),
        "keywords": keywords,
        "seed_papers": [name for _, name in seed_papers] if seed_papers else [],
        "papers": [asdict(p) for p in papers],
    }

    if args.config:
        data["config"] = args.config

    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(papers)} papers to {args.output}")


if __name__ == "__main__":
    main()
