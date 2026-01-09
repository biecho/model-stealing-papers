# ML Security Papers Pipeline Architecture

## Overview

A graph-based paper discovery system that:
1. Starts from curated seed papers (Awesome-ML-SP-Papers)
2. Expands via citation network (BFS-style)
3. Classifies with LLM (OWASP ML Security Top 10)
4. Discovers new papers daily

## Data Model

### Paper State (`data/paper_state.json`)

```json
{
  "papers": {
    "<paper_id>": {
      "paper_id": "abc123",
      "title": "...",
      "abstract": "...",
      "year": 2024,
      "venue": "...",
      "authors": ["..."],
      "url": "...",

      "source": "seed | citation | reference",
      "source_paper_id": "xyz789",  // Paper that led us here (if not seed)

      "status": "pending | fetched | classified | expanded | discarded",
      "classification": "ML01 | ML02 | ... | ML10 | NONE | null",
      "classification_confidence": "HIGH | LOW",

      "added_at": "2026-01-09",
      "fetched_at": "2026-01-09",
      "classified_at": "2026-01-09",
      "expanded_at": "2026-01-09",
      "citations_checked_at": "2026-01-09"
    }
  },
  "metadata": {
    "total_papers": 1000,
    "by_status": {"pending": 100, "classified": 800, ...},
    "by_category": {"ML01": 200, "ML02": 150, ...},
    "last_updated": "2026-01-09"
  }
}
```

### Status Flow

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
┌─────────┐    ┌─────────┐    ┌────────────┐    ┌────────────┐
│ pending │───▶│ fetched │───▶│ classified │───▶│  expanded  │
└─────────┘    └─────────┘    └────────────┘    └────────────┘
                                   │
                                   │ (if NONE)
                                   ▼
                              ┌───────────┐
                              │ discarded │
                              └───────────┘
```

- **pending**: Paper ID known, needs metadata
- **fetched**: Has metadata (title, abstract), ready for classification
- **classified**: LLM assigned category (ML01-10 or NONE)
- **expanded**: Citations/references fetched, added to queue
- **discarded**: Classified as NONE (not ML security)

## Pipeline Scripts

### 1. Initialize (`scripts/pipeline/init.py`)
```
Load seed papers from Awesome-ML-SP-Papers
Create initial paper_state.json with status="pending"
```

### 2. Fetch Metadata (`scripts/pipeline/fetch.py`)
```
For each paper with status="pending":
  - Try Semantic Scholar API (by title or ID)
  - Try arXiv API (if has arXiv link)
  - Update status to "fetched" (or stay "pending" if no abstract)
```

### 3. Classify (`scripts/pipeline/classify.py`)
```
For each paper with status="fetched":
  - Call LLM with title + abstract
  - If ML01-ML10: status="classified"
  - If NONE: status="discarded"
  - Save classification result
```

### 4. Expand (`scripts/pipeline/expand.py`)
```
For each paper with status="classified" (not yet expanded):
  - Fetch citations (papers that cite this)
  - Fetch references (papers this cites)
  - For each new paper:
    - If not in state: add with status="pending", source="citation|reference"
  - Update status to "expanded"
```

### 5. Daily Discovery (`scripts/pipeline/discover.py`)
```
For each paper in pool (classified, not discarded):
  - If citations_checked_at is old (or null):
    - Check for NEW citations since last check
    - Add new citing papers with status="pending"
    - Update citations_checked_at
```

## Graph Traversal Strategy

### BFS Expansion (Breadth-First)
```
Queue: [seed papers]
Visited: {}

while Queue not empty:
    paper = Queue.pop()
    if paper.id in Visited: continue

    classify(paper)
    if paper.classification == NONE:
        Visited[paper.id] = "discarded"
        continue

    Visited[paper.id] = "expanded"

    for cited_paper in get_citations(paper):
        if cited_paper.id not in Visited:
            Queue.append(cited_paper)

    for ref_paper in get_references(paper):
        if ref_paper.id not in Visited:
            Queue.append(ref_paper)
```

### Depth Limits
- **Max depth from seed**: 2-3 levels (avoid going too far from ML security)
- **Max papers per expansion**: 100 citations + 50 references
- **Relevance filter**: Only expand papers classified as ML security

## API Rate Limits & Efficiency

### Semantic Scholar
- Public: 100 requests / 5 minutes
- With API key: 1 request / second
- **Strategy**: Batch where possible, cache responses

### Groq (LLM)
- Free tier: ~30 requests / minute (then rate limited)
- **Strategy**: Process in batches, save checkpoints

### Avoiding Duplicate Work
- Check `status` before any operation
- Check `expanded_at` before re-expanding
- Check `citations_checked_at` for daily discovery

## Daily Cron Job

```bash
#!/bin/bash
# Run daily at 2 AM

cd /path/to/ml-security-papers

# 1. Check for new citations to our papers
python scripts/pipeline/discover.py

# 2. Fetch metadata for any new pending papers
python scripts/pipeline/fetch.py --limit 100

# 3. Classify newly fetched papers
python scripts/pipeline/classify.py --limit 100

# 4. Expand newly classified papers (optional, can run weekly)
# python scripts/pipeline/expand.py --limit 50

# 5. Generate updated output files
python scripts/pipeline/export.py
```

## Output Files

After pipeline runs, generate clean output files:

```
data/
  paper_state.json      # Full state (internal)

  # Public outputs
  ml01_papers.json      # Papers classified as ML01
  ml02_papers.json      # Papers classified as ML02
  ...
  ml10_papers.json      # Papers classified as ML10

  manifest.json         # Summary stats
```
