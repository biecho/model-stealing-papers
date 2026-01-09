#!/usr/bin/env python3
"""
Classify papers using LLM (Groq or Google AI).

Takes papers with status="fetched" and classifies them into OWASP categories:
- ML01-ML10: Relevant ML security categories
- NONE: Not related to ML security (paper gets discarded)

Papers with abstracts get HIGH confidence classification.
Papers without abstracts get LOW confidence (title-only).
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from state import PaperState

# API configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GOOGLE_MODEL = "gemini-2.0-flash"

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_MODEL = "llama-3.3-70b"

OWASP_CATEGORIES = """
ML01: Input Manipulation (adversarial examples, evasion attacks, input perturbation, prompt injection)
ML02: Data Poisoning (training data manipulation, backdoor attacks, trojan attacks)
ML03: Model Inversion & Data Reconstruction (privacy attacks, membership inference, attribute inference)
ML04: Model Theft & Extraction (model stealing, architecture extraction, knowledge distillation attacks)
ML05: Data Extraction & Leakage (training data extraction, memorization attacks, PII leakage)
ML06: Supply Chain (model supply chain, pretrained model attacks, model integrity, federated learning attacks)
ML07: Transfer Attacks (cross-domain attacks, transferability of adversarial examples)
ML08: Model Configuration & Deployment (misconfigurations, deployment security, model serving)
ML09: Output Integrity (output manipulation, prediction tampering, deepfakes, AI-generated content detection)
ML10: Model Manipulation & Corruption (weight manipulation, model modification attacks, fine-tuning attacks)
NONE: Not related to ML security (general ML, other security topics, AI FOR security rather than attacks ON ML)
"""

SYSTEM_PROMPT = f"""You are an expert ML security researcher. Classify the given paper into ONE of the OWASP ML Security Top 10 categories.

Categories:
{OWASP_CATEGORIES}

Important distinctions:
- Papers about ATTACKING ML systems → classify as ML01-ML10
- Papers about DEFENDING ML systems from attacks → classify based on the attack type they defend against
- Papers about using AI FOR security (malware detection, intrusion detection) → classify as NONE
- General ML papers without security focus → classify as NONE

Respond with ONLY the category code (ML01, ML02, ..., ML10, or NONE). No explanation."""


def validate_category(category: str) -> str:
    """Validate and extract category from LLM response."""
    category = category.strip().upper()
    valid = ["ML01", "ML02", "ML03", "ML04", "ML05", "ML06", "ML07", "ML08", "ML09", "ML10", "NONE"]
    if category in valid:
        return category
    # Try to extract valid category
    for v in valid:
        if v in category:
            return v
    return "NONE"


def classify_with_groq(title: str, abstract: str = None) -> tuple[str, str]:
    """Classify using Groq API."""
    if abstract:
        user_message = f"Title: {title}\n\nAbstract: {abstract[:2500]}"
        confidence = "HIGH"
    else:
        user_message = f"Title: {title}\n\n(No abstract available - classify based on title only)"
        confidence = "LOW"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1,
        "max_tokens": 10,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "ml-security-papers/1.0",
    }

    req = urllib.request.Request(
        GROQ_API_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode())
        category = data["choices"][0]["message"]["content"]
        return validate_category(category), confidence


def classify_with_google(title: str, abstract: str = None) -> tuple[str, str]:
    """Classify using Google AI (Gemini) API."""
    if abstract:
        user_message = f"Title: {title}\n\nAbstract: {abstract[:2500]}"
        confidence = "HIGH"
    else:
        user_message = f"Title: {title}\n\n(No abstract available - classify based on title only)"
        confidence = "LOW"

    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_message}"

    url = f"{GOOGLE_API_URL}/{GOOGLE_MODEL}:generateContent?key={GOOGLE_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 10,
        }
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ml-security-papers/1.0",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode())
        category = data["candidates"][0]["content"]["parts"][0]["text"]
        return validate_category(category), confidence


def classify_with_cerebras(title: str, abstract: str = None) -> tuple[str, str]:
    """Classify using Cerebras API (OpenAI-compatible)."""
    if abstract:
        user_message = f"Title: {title}\n\nAbstract: {abstract[:2500]}"
        confidence = "HIGH"
    else:
        user_message = f"Title: {title}\n\n(No abstract available - classify based on title only)"
        confidence = "LOW"

    payload = {
        "model": CEREBRAS_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1,
        "max_tokens": 10,
    }

    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "ml-security-papers/1.0",
    }

    req = urllib.request.Request(
        CEREBRAS_API_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode())
        category = data["choices"][0]["message"]["content"]
        return validate_category(category), confidence


def classify_with_llm(title: str, abstract: str = None, provider: str = "cerebras") -> tuple[str, str]:
    """
    Classify a paper using LLM.
    Returns (category, confidence).
    """
    if provider == "google":
        return classify_with_google(title, abstract)
    elif provider == "cerebras":
        return classify_with_cerebras(title, abstract)
    else:
        return classify_with_groq(title, abstract)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Classify papers with LLM")
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--limit", type=int, default=0, help="Limit papers to classify (0=all)")
    parser.add_argument("--rate-limit", type=float, default=1.5, help="Seconds between requests")
    parser.add_argument("--include-pending", action="store_true", help="Also classify pending papers (title-only)")
    parser.add_argument("--provider", type=str, default="cerebras", choices=["groq", "google", "cerebras"], help="LLM provider")
    args = parser.parse_args()

    if args.provider == "groq" and not GROQ_API_KEY:
        print("Error: GROQ_API_KEY environment variable not set", flush=True)
        return
    if args.provider == "google" and not GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY environment variable not set", flush=True)
        return
    if args.provider == "cerebras" and not CEREBRAS_API_KEY:
        print("Error: CEREBRAS_API_KEY environment variable not set", flush=True)
        print("Get a free API key at: https://cloud.cerebras.ai/", flush=True)
        return

    print(f"Using provider: {args.provider}", flush=True)

    state = PaperState(args.state_file)

    # Get papers to classify
    to_classify = state.get_papers_to_classify()  # status="fetched"

    if args.include_pending:
        # Also include pending papers for title-only classification
        to_classify.extend(state.get_pending_papers())

    print(f"Papers to classify: {len(to_classify)}", flush=True)

    if args.limit > 0:
        to_classify = to_classify[:args.limit]
        print(f"Limited to {len(to_classify)} papers", flush=True)

    if not to_classify:
        print("No papers to classify", flush=True)
        return

    classified = 0
    discarded = 0
    errors = 0

    for i, paper in enumerate(to_classify):
        paper_id = paper["paper_id"]
        title = paper["title"]
        abstract = paper.get("abstract")

        try:
            category, confidence = classify_with_llm(title, abstract, args.provider)

            state.set_classified(paper_id, category, confidence)

            if category == "NONE":
                discarded += 1
            else:
                classified += 1

            if (i + 1) % 10 == 0 or i == 0:
                status = "✓" if category != "NONE" else "✗"
                print(f"[{i+1}/{len(to_classify)}] {status} {category} ({confidence}): {title[:40]}...", flush=True)

            # Save checkpoint
            if (i + 1) % 25 == 0:
                state.save()
                print(f"  Checkpoint saved", flush=True)

            time.sleep(args.rate_limit)

        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"Rate limited, waiting 60s...", flush=True)
                time.sleep(60)
                continue
            else:
                print(f"Error: {e}", flush=True)
                errors += 1

        except Exception as e:
            print(f"Error classifying {title[:40]}: {e}", flush=True)
            errors += 1

    # Final save
    state.save()

    print(f"\nDone!", flush=True)
    print(f"  Classified (ML01-ML10): {classified}", flush=True)
    print(f"  Discarded (NONE): {discarded}", flush=True)
    print(f"  Errors: {errors}", flush=True)

    stats = state.stats()
    print(f"\nBy category:", flush=True)
    for cat, count in sorted(stats['by_category'].items()):
        print(f"  {cat}: {count}", flush=True)


if __name__ == "__main__":
    main()
