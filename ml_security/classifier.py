"""
Embeddings-based paper classifier for OWASP ML Security categories.

Uses sentence-transformers to embed paper abstracts and compare
against category descriptions for classification.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError(
        "sentence-transformers required. Install with: pip install -e '.[classify]'"
    )


# OWASP ML Security Top 10 category descriptions for embedding
CATEGORY_DESCRIPTIONS = {
    "ML01": {
        "name": "Input Manipulation Attack",
        "description": """
        Adversarial attacks on machine learning model inputs. This includes
        adversarial examples, evasion attacks, perturbation attacks, and any
        technique that manipulates input data to cause misclassification or
        incorrect model behavior. Covers both white-box and black-box adversarial
        attacks, robustness evaluation, and input perturbation methods.
        """,
    },
    "ML02": {
        "name": "Data Poisoning Attack",
        "description": """
        Attacks that manipulate training data to compromise machine learning models.
        This includes data poisoning, training data manipulation, backdoor insertion
        during training, label flipping attacks, and any technique that corrupts
        the training process by modifying the dataset.
        """,
    },
    "ML03": {
        "name": "Model Inversion Attack",
        "description": """
        Attacks that reconstruct or recover private training data from machine learning
        models. This includes model inversion attacks that recover input features,
        gradient leakage attacks, training data reconstruction, attribute inference,
        and techniques to extract sensitive information about training samples from
        model outputs or gradients. Focus is on privacy of TRAINING DATA, not the model.
        """,
    },
    "ML04": {
        "name": "Membership Inference Attack",
        "description": """
        Attacks that determine whether specific data points were used to train a
        machine learning model. This includes membership inference attacks, privacy
        attacks that reveal training set membership, and techniques to distinguish
        training data from non-training data based on model behavior.
        """,
    },
    "ML05": {
        "name": "Model Theft",
        "description": """
        Attacks that steal, copy, or clone machine learning models themselves.
        This includes model extraction attacks, model stealing attacks, knockoff
        networks, functionality stealing, query-based model cloning, surrogate
        model training, and techniques to replicate or steal model weights,
        architecture, or behavior through API queries. The goal is stealing the
        MODEL, not the training data.
        """,
    },
    "ML06": {
        "name": "AI Supply Chain Attacks",
        "description": """
        Attacks on the machine learning supply chain, including pre-trained models,
        model repositories, ML pipelines, and dependencies. This includes trojaned
        pre-trained models, malicious model hubs, compromised ML libraries, and
        attacks on the infrastructure used to develop and deploy ML systems.
        """,
    },
    "ML07": {
        "name": "Transfer Learning Attack",
        "description": """
        Attacks that exploit transfer learning and pre-trained models. This includes
        attacks on fine-tuning, exploiting pre-trained representations, transferability
        of adversarial examples across models, and vulnerabilities introduced by
        using pre-trained models as feature extractors or starting points.
        """,
    },
    "ML08": {
        "name": "Model Skewing",
        "description": """
        Attacks that manipulate model behavior over time or cause concept drift.
        This includes online learning attacks, model drift exploitation, feedback
        loop manipulation, and techniques to gradually shift model behavior through
        strategic inputs or data manipulation over time.
        """,
    },
    "ML09": {
        "name": "Output Integrity Attack",
        "description": """
        Attacks that manipulate or corrupt model outputs. This includes output
        manipulation, prediction tampering, confidence score manipulation, and
        techniques to alter model responses after inference. Also covers attacks
        on model explanations and interpretability outputs.
        """,
    },
    "ML10": {
        "name": "Model Poisoning",
        "description": """
        Attacks that embed backdoors or trojans in machine learning models. This
        includes neural trojans, backdoor attacks, trigger-based attacks, and
        techniques to insert hidden malicious behavior that activates on specific
        inputs while maintaining normal performance on clean data.
        """,
    },
}



@dataclass
class ClassificationResult:
    """Result of classifying a paper."""
    paper_id: str
    title: str
    categories: list[tuple[str, float]]  # (category_id, confidence)

    def top_category(self) -> tuple[str, float]:
        """Return the top category and its confidence."""
        return self.categories[0] if self.categories else ("unknown", 0.0)

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "categories": [{"id": cat, "confidence": round(conf, 4)} for cat, conf in self.categories],
        }


class EmbeddingsClassifier:
    """Classify papers using sentence embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the classifier.

        Args:
            model_name: Sentence transformer model to use
        """
        self.model = SentenceTransformer(model_name)
        self.category_embeddings = {}
        self.category_info = {}
        self._embed_categories()

    def _embed_categories(self):
        """Pre-compute embeddings for all category descriptions."""
        for cat_id, info in CATEGORY_DESCRIPTIONS.items():
            text = f"{info['name']}: {info['description']}"
            self.category_embeddings[cat_id] = self.model.encode(text, normalize_embeddings=True)
            self.category_info[cat_id] = info["name"]

    def classify(
        self,
        paper_id: str,
        title: str,
        abstract: str | None = None,
        top_k: int = 3,
        threshold: float = 0.0
    ) -> ClassificationResult:
        """
        Classify a paper into OWASP categories.

        Args:
            paper_id: Unique identifier for the paper
            title: Paper title
            abstract: Paper abstract (optional but recommended)
            top_k: Number of top categories to return
            threshold: Minimum confidence threshold

        Returns:
            ClassificationResult with ranked categories
        """
        # Create paper text for embedding
        text = title
        if abstract:
            text = f"{title}. {abstract}"

        # Embed the paper
        paper_embedding = self.model.encode(text, normalize_embeddings=True)

        # Compute similarities to all categories
        similarities = []
        for cat_id, cat_embedding in self.category_embeddings.items():
            sim = float(np.dot(paper_embedding, cat_embedding))
            if sim >= threshold:
                similarities.append((cat_id, sim))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return ClassificationResult(
            paper_id=paper_id,
            title=title,
            categories=similarities[:top_k]
        )

    def classify_batch(
        self,
        papers: list[dict],
        top_k: int = 3,
        threshold: float = 0.0,
        show_progress: bool = True
    ) -> list[ClassificationResult]:
        """
        Classify multiple papers.

        Args:
            papers: List of paper dicts with 'id', 'title', and optionally 'abstract'
            top_k: Number of top categories to return per paper
            threshold: Minimum confidence threshold
            show_progress: Whether to show progress

        Returns:
            List of ClassificationResult objects
        """
        results = []
        total = len(papers)

        for i, paper in enumerate(papers):
            if show_progress and (i + 1) % 100 == 0:
                print(f"  Classified {i + 1}/{total} papers...")

            result = self.classify(
                paper_id=paper.get("id", str(i)),
                title=paper.get("title", ""),
                abstract=paper.get("abstract"),
                top_k=top_k,
                threshold=threshold
            )
            results.append(result)

        return results

    def evaluate_accuracy(
        self,
        papers: list[dict],
        expected_category: str
    ) -> dict:
        """
        Evaluate classification accuracy against expected category.

        Args:
            papers: List of papers that should belong to expected_category
            expected_category: The category these papers should be classified as

        Returns:
            Dict with accuracy metrics
        """
        results = self.classify_batch(papers, top_k=3, show_progress=False)

        top1_correct = 0
        top3_correct = 0

        for result in results:
            categories = [cat for cat, _ in result.categories]
            if categories and categories[0] == expected_category:
                top1_correct += 1
            if expected_category in categories:
                top3_correct += 1

        total = len(results)
        return {
            "total": total,
            "top1_accuracy": top1_correct / total if total > 0 else 0,
            "top3_accuracy": top3_correct / total if total > 0 else 0,
            "top1_correct": top1_correct,
            "top3_correct": top3_correct,
        }
