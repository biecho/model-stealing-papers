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

SYSTEM_PROMPT = """You are an expert ML security researcher. Classify papers into OWASP ML Security Top 10 categories.

## Categories (based on OWASP ML Security Top 10 2023):

ML01 - Input Manipulation Attack
  Adversarial examples that fool models at INFERENCE time. Attacker crafts malicious inputs (images, text, audio) with imperceptible perturbations to cause misclassification.
  Examples: adversarial patches, evasion attacks, perturbation attacks, prompt injection, jailbreaking LLMs

ML02 - Data Poisoning Attack
  Corrupting TRAINING DATA to make the model learn wrong behavior. Attacker injects malicious samples or mislabels data before/during training.
  Examples: backdoor attacks, trojan attacks, label flipping, training data manipulation

ML03 - Model Inversion Attack
  RECONSTRUCTING training data or sensitive attributes by querying the model. Attacker reverse-engineers what data the model was trained on.
  Examples: attribute inference, training data reconstruction, facial reconstruction from face recognition models

ML04 - Membership Inference Attack
  Determining WHETHER a specific record was in the training set. Binary question: "Was this person's data used to train the model?"
  Examples: privacy attacks on ML, detecting if individual's data was used, GDPR/privacy violations

ML05 - Model Theft
  Stealing the MODEL ITSELF - its parameters, weights, or architecture. Creating a copy of the model.
  Examples: model extraction, model stealing, knowledge distillation attacks, API-based model copying

ML06 - AI Supply Chain Attacks
  Attacking the ML ECOSYSTEM - packages, platforms, model hubs, MLOps infrastructure.
  Examples: malicious PyPI packages, compromised pre-trained models on HuggingFace, MLOps platform vulnerabilities

ML07 - Transfer Learning Attack
  Exploiting TRANSFER LEARNING to inject malicious behavior. Attacker poisons a pre-trained model that others will fine-tune.
  Examples: backdoored foundation models, malicious fine-tuning, attacking models through transfer learning

ML08 - Model Skewing
  Manipulating FEEDBACK LOOPS in continuously learning systems to gradually skew model behavior over time.
  Examples: feedback loop exploitation, concept drift attacks, online learning manipulation

ML09 - Output Integrity Attack
  Tampering with model OUTPUTS after prediction. Attacker intercepts and modifies the results.
  Examples: prediction tampering, result manipulation, man-in-the-middle on model outputs

ML10 - Model Poisoning
  Directly manipulating MODEL PARAMETERS/WEIGHTS (not training data). Attacker modifies the model itself.
  Examples: weight manipulation, neural trojan insertion into weights, model file tampering

NONE - Not ML Security
  Use for: general ML without security focus, using AI FOR security (malware detection, intrusion detection, fraud detection), pure cryptography, non-ML security

## Key Distinctions:
- ML02 (data poisoning) vs ML10 (model poisoning): ML02 attacks training DATA, ML10 attacks model WEIGHTS directly
- ML03 (model inversion) vs ML04 (membership inference): ML03 reconstructs data content, ML04 only asks "was this in training set?"
- ML05 (model theft) vs ML03 (model inversion): ML05 steals the model itself, ML03 extracts info about training data
- ML01 (input manipulation) vs ML09 (output integrity): ML01 manipulates inputs, ML09 manipulates outputs
- ML02 (data poisoning) vs ML08 (model skewing): ML02 is initial training corruption, ML08 exploits feedback loops

## Classification Rules:
1. Papers about ATTACKING ML systems → ML01-ML10
2. Papers about DEFENDING against specific attacks → classify by the attack type defended against
3. Papers using AI FOR security tasks (not attacks ON AI) → NONE
4. General ML papers without adversarial/security focus → NONE
5. Adversarial robustness/certified defenses → ML01 (they defend against input manipulation)

Respond with ONLY the category code. No explanation."""


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
