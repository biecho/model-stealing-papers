#!/usr/bin/env python3
"""
Enrich paper metadata using Semantic Scholar API.

Fetches comprehensive data including:
- Citation counts (total + influential)
- TLDR summaries
- SPECTER embeddings (768-dim vectors)
- Author details (h-index, affiliations)
- Publication metadata
- Fields of study
"""

import json
import time
import re
import sys
from pathlib import Path
from typing import Optional
import requests

# Configuration
S2_API_KEY = "MdCu6FrIBMThj6CBX4Hy2hqx64ABeev5UHbgGhJ3"
S2_BATCH_SIZE = 100  # S2 allows up to 500, but be conservative
S2_RATE_LIMIT_DELAY = 1.0  # seconds between batches

# S2 API endpoints
S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# Fields to fetch from S2
S2_PAPER_FIELDS = ",".join([
    "paperId",
    "externalIds",
    "title",
    "abstract",
    "year",
    "venue",
    "citationCount",
    "referenceCount",
    "influentialCitationCount",
    "isOpenAccess",
    "openAccessPdf",
    "fieldsOfStudy",
    "s2FieldsOfStudy",
    "publicationTypes",
    "publicationDate",
    "journal",
    "tldr",
    "authors",
    "authors.authorId",
    "authors.name",
    "authors.hIndex",
    "authors.citationCount",
    "authors.paperCount",
    "authors.affiliations",
])

# Embedding field (separate due to size)
S2_EMBEDDING_FIELDS = "paperId,embedding"


def extract_s2_id(paper: dict) -> Optional[str]:
    """Extract the best S2-compatible ID from a paper."""
    doi = (paper.get('doi') or '').lower()
    url = (paper.get('url') or '').lower()
    pdf_url = (paper.get('pdf_url') or '').lower()

    # Check for arXiv ID in various places
    arxiv_patterns = [
        r'arxiv[:/](\d{4}\.\d{4,5})',
        r'arxiv\.org/abs/(\d{4}\.\d{4,5})',
        r'arxiv\.org/pdf/(\d{4}\.\d{4,5})',
    ]

    for pattern in arxiv_patterns:
        for source in [doi, url, pdf_url]:
            match = re.search(pattern, source)
            if match:
                return f"arXiv:{match.group(1)}"

    # Check for regular DOI
    if doi and 'doi.org/' in doi:
        doi_id = doi.replace('https://doi.org/', '').replace('http://doi.org/', '')
        if not 'arxiv' in doi_id.lower():
            return f"DOI:{doi_id}"

    return None


def search_paper_by_title(title: str, headers: dict) -> Optional[dict]:
    """Search for a paper by title in S2."""
    params = {
        "query": title,
        "fields": S2_PAPER_FIELDS,
        "limit": 1
    }

    try:
        response = requests.get(S2_SEARCH_URL, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                result = data['data'][0]
                # Verify title similarity
                result_title = result.get('title', '').lower()
                search_title = title.lower()
                # Simple check - first 50 chars should match
                if result_title[:50] == search_title[:50]:
                    return result
        return None
    except Exception as e:
        print(f"  Search error: {e}")
        return None


def fetch_batch(paper_ids: list, headers: dict, include_embeddings: bool = False) -> list:
    """Fetch a batch of papers from S2."""
    fields = S2_PAPER_FIELDS
    if include_embeddings:
        fields += ",embedding"

    params = {"fields": fields}

    try:
        response = requests.post(
            S2_BATCH_URL,
            params=params,
            headers=headers,
            json={"ids": paper_ids},
            timeout=60
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print("  Rate limited, waiting 60s...")
            time.sleep(60)
            return fetch_batch(paper_ids, headers, include_embeddings)
        else:
            print(f"  Batch error: {response.status_code} - {response.text[:200]}")
            return [None] * len(paper_ids)
    except Exception as e:
        print(f"  Batch exception: {e}")
        return [None] * len(paper_ids)


def process_s2_result(s2_data: dict) -> dict:
    """Process S2 API result into our schema."""
    if not s2_data:
        return None

    result = {
        "paper_id": s2_data.get("paperId"),
        "external_ids": s2_data.get("externalIds"),
        "citation_count": s2_data.get("citationCount"),
        "reference_count": s2_data.get("referenceCount"),
        "influential_citation_count": s2_data.get("influentialCitationCount"),
        "is_open_access": s2_data.get("isOpenAccess"),
        "open_access_pdf": s2_data.get("openAccessPdf"),
        "fields_of_study": s2_data.get("fieldsOfStudy"),
        "s2_fields_of_study": s2_data.get("s2FieldsOfStudy"),
        "publication_types": s2_data.get("publicationTypes"),
        "publication_date": s2_data.get("publicationDate"),
        "journal": s2_data.get("journal"),
        "venue": s2_data.get("venue"),
    }

    # Process TLDR
    tldr = s2_data.get("tldr")
    if tldr:
        result["tldr"] = {
            "text": tldr.get("text"),
            "model": tldr.get("model")
        }

    # Process authors with details
    authors = s2_data.get("authors", [])
    if authors:
        result["authors"] = []
        for a in authors:
            author_data = {
                "author_id": a.get("authorId"),
                "name": a.get("name"),
            }
            if a.get("hIndex") is not None:
                author_data["h_index"] = a.get("hIndex")
            if a.get("citationCount") is not None:
                author_data["citation_count"] = a.get("citationCount")
            if a.get("paperCount") is not None:
                author_data["paper_count"] = a.get("paperCount")
            if a.get("affiliations"):
                author_data["affiliations"] = a.get("affiliations")
            result["authors"].append(author_data)

    # Process embedding
    embedding = s2_data.get("embedding")
    if embedding:
        result["embedding"] = {
            "model": embedding.get("model"),
            "vector": embedding.get("vector")
        }

    return result


def main():
    # Load current state
    state_path = Path("data/paper_state.json")
    with open(state_path) as f:
        state = json.load(f)

    papers = state["papers"]
    headers = {"x-api-key": S2_API_KEY}

    # Prepare batches
    print("Preparing paper lookups...")

    # Group papers by lookup method
    batch_lookups = []  # (paper_id, s2_id)
    title_lookups = []  # (paper_id, title)
    already_have = 0

    for paper_id, paper in papers.items():
        # Skip if already have S2 data
        if paper.get("s2") and paper["s2"].get("paper_id"):
            already_have += 1
            continue

        s2_id = extract_s2_id(paper)
        if s2_id:
            batch_lookups.append((paper_id, s2_id))
        else:
            title_lookups.append((paper_id, paper.get("title", "")))

    print(f"  Already enriched: {already_have}")
    print(f"  Batch lookups (arXiv/DOI): {len(batch_lookups)}")
    print(f"  Title searches needed: {len(title_lookups)}")

    # Process batch lookups
    print(f"\nProcessing batch lookups...")
    enriched = 0
    failed = 0

    for i in range(0, len(batch_lookups), S2_BATCH_SIZE):
        batch = batch_lookups[i:i + S2_BATCH_SIZE]
        s2_ids = [b[1] for b in batch]
        paper_ids = [b[0] for b in batch]

        print(f"  Batch {i//S2_BATCH_SIZE + 1}/{(len(batch_lookups) + S2_BATCH_SIZE - 1)//S2_BATCH_SIZE}: {len(batch)} papers...")

        results = fetch_batch(s2_ids, headers, include_embeddings=True)

        for paper_id, s2_data in zip(paper_ids, results):
            if s2_data:
                processed = process_s2_result(s2_data)
                if processed:
                    papers[paper_id]["s2"] = processed
                    enriched += 1
                else:
                    failed += 1
            else:
                failed += 1

        print(f"    Enriched: {enriched}, Failed: {failed}")
        time.sleep(S2_RATE_LIMIT_DELAY)

    # Process title lookups
    if title_lookups:
        print(f"\nProcessing title searches...")
        for paper_id, title in title_lookups:
            print(f"  Searching: {title[:50]}...")
            result = search_paper_by_title(title, headers)
            if result:
                processed = process_s2_result(result)
                if processed:
                    papers[paper_id]["s2"] = processed
                    enriched += 1
                    print(f"    Found!")
                else:
                    failed += 1
                    print(f"    Processing failed")
            else:
                failed += 1
                print(f"    Not found")
            time.sleep(S2_RATE_LIMIT_DELAY)

    # Save results
    print(f"\nSaving results...")
    state["papers"] = papers

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\nDone!")
    print(f"  Total enriched: {enriched}")
    print(f"  Total failed: {failed}")
    print(f"  Already had S2 data: {already_have}")


if __name__ == "__main__":
    main()
