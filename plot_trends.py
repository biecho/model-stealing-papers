#!/usr/bin/env python3
"""Plot research trends for model stealing papers."""

import json
from collections import Counter
import matplotlib.pyplot as plt
import numpy as np


def plot_papers_per_year(papers, ax):
    """Bar chart of papers per year."""
    years = Counter(p["year"] for p in papers if p["year"])
    years_sorted = sorted(years.items())

    years_list = [y for y, _ in years_sorted]
    counts = [c for _, c in years_sorted]

    ax.bar(years_list, counts, color="#2563eb", edgecolor="black", linewidth=0.5)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Papers per Year")

    for x, y in zip(years_list, counts):
        ax.annotate(str(y), (x, y + 0.5), ha="center", fontsize=9)

    ax.set_xticks(years_list)
    ax.set_ylim(0, max(counts) + 5)


def plot_cumulative(papers, ax):
    """Cumulative papers over time."""
    years = Counter(p["year"] for p in papers if p["year"])
    years_sorted = sorted(years.items())

    years_list = [y for y, _ in years_sorted]
    counts = [c for _, c in years_sorted]
    cumulative = np.cumsum(counts)

    ax.plot(years_list, cumulative, marker="o", color="#2563eb", linewidth=2)
    ax.fill_between(years_list, cumulative, alpha=0.3, color="#2563eb")
    ax.set_xlabel("Year")
    ax.set_ylabel("Cumulative Papers")
    ax.set_title("Cumulative Growth")
    ax.set_xticks(years_list)

    for x, y in zip(years_list, cumulative):
        ax.annotate(str(y), (x, y + 3), ha="center", fontsize=9)


def plot_attack_vs_defense(papers, ax):
    """Attack vs defense papers per year."""
    defense_keywords = ["defense", "defence", "protect", "defend", "detection", "watermark"]

    attacks = Counter()
    defenses = Counter()

    for p in papers:
        if not p["year"]:
            continue
        title = (p["title"] or "").lower()
        abstract = (p["abstract"] or "").lower()
        text = title + " " + abstract

        is_defense = any(kw in text for kw in defense_keywords)
        if is_defense:
            defenses[p["year"]] += 1
        else:
            attacks[p["year"]] += 1

    all_years = sorted(set(attacks.keys()) | set(defenses.keys()))
    attack_counts = [attacks.get(y, 0) for y in all_years]
    defense_counts = [defenses.get(y, 0) for y in all_years]

    x = np.arange(len(all_years))
    width = 0.35

    ax.bar(x - width/2, attack_counts, width, label="Attack", color="#ef4444")
    ax.bar(x + width/2, defense_counts, width, label="Defense", color="#22c55e")

    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Attack vs Defense Papers")
    ax.set_xticks(x)
    ax.set_xticklabels(all_years)
    ax.legend()


def plot_top_venues(papers, ax):
    """Top publication venues."""
    # Map long venue names to short abbreviations
    venue_abbrev = {
        "arXiv.org": "arXiv",
        "AAAI Conference on Artificial Intelligence": "AAAI",
        "Neural Information Processing Systems": "NeurIPS",
        "Computer Vision and Pattern Recognition": "CVPR",
        "IEEE Transactions on Dependable and Secure Computing": "IEEE TDSC",
        "IEEE Symposium on Security and Privacy": "IEEE S&P",
        "IEEE Transactions on Information Forensics and Security": "IEEE TIFS",
        "International Conference on Machine Learning": "ICML",
        "ACM Asia Conference on Computer and Communications Security": "ACM ASIACCS",
        "IEEE International Joint Conference on Neural Network": "IJCNN",
        "ACM Conference on Computer and Communications Security": "ACM CCS",
        "USENIX Security Symposium": "USENIX Security",
        "International Conference on Learning Representations": "ICLR",
        "European Conference on Computer Vision": "ECCV",
        "IEEE Access": "IEEE Access",
        "ACM Multimedia": "ACM MM",
    }

    venues = Counter()
    for p in papers:
        venue = p.get("venue")
        if venue and venue.strip():
            venues[venue] += 1

    top = venues.most_common(10)
    venue_names = [venue_abbrev.get(v, v[:25] + "..." if len(v) > 25 else v) for v, _ in top]
    counts = [c for _, c in top]

    y_pos = np.arange(len(venue_names))
    ax.barh(y_pos, counts, color="#8b5cf6")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(venue_names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Number of Papers")
    ax.set_title("Top 10 Venues")

    for i, c in enumerate(counts):
        ax.annotate(str(c), (c + 0.2, i), va="center", fontsize=9)


def plot_citation_distribution(papers, ax):
    """Citation count distribution."""
    citations = [p["citation_count"] for p in papers if p["citation_count"] > 0]

    # Log scale bins for better visualization
    bins = [0, 1, 5, 10, 25, 50, 100, 250, 500, 2000]
    hist, _ = np.histogram(citations, bins=bins)

    labels = ["1", "2-5", "6-10", "11-25", "26-50", "51-100", "101-250", "251-500", "500+"]
    x = np.arange(len(labels))

    ax.bar(x, hist, color="#f59e0b", edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xlabel("Citation Count")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Citation Distribution")

    for i, h in enumerate(hist):
        if h > 0:
            ax.annotate(str(h), (i, h + 0.5), ha="center", fontsize=9)


def plot_top_cited(papers, ax):
    """Top cited papers."""
    top = sorted(papers, key=lambda p: -p["citation_count"])[:10]

    titles = []
    for p in top:
        t = p["title"]
        if len(t) > 45:
            t = t[:42] + "..."
        titles.append(f"{t} ({p['year']})")

    citations = [p["citation_count"] for p in top]

    y_pos = np.arange(len(titles))
    ax.barh(y_pos, citations, color="#ec4899")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(titles, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Citations")
    ax.set_title("Top 10 Most Cited Papers")


def main():
    with open("papers.json") as f:
        data = json.load(f)

    papers = data["papers"]

    # Papers per year
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_papers_per_year(papers, ax)
    plt.tight_layout()
    plt.savefig("trends_papers_per_year.png", dpi=150)
    plt.close()
    print("Saved trends_papers_per_year.png")

    # Cumulative growth
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_cumulative(papers, ax)
    plt.tight_layout()
    plt.savefig("trends_cumulative.png", dpi=150)
    plt.close()
    print("Saved trends_cumulative.png")

    # Attack vs defense
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_attack_vs_defense(papers, ax)
    plt.tight_layout()
    plt.savefig("trends_attack_vs_defense.png", dpi=150)
    plt.close()
    print("Saved trends_attack_vs_defense.png")

    # Top venues
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_top_venues(papers, ax)
    plt.tight_layout()
    plt.savefig("trends_top_venues.png", dpi=150)
    plt.close()
    print("Saved trends_top_venues.png")

    # Citation distribution
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_citation_distribution(papers, ax)
    plt.tight_layout()
    plt.savefig("trends_citations.png", dpi=150)
    plt.close()
    print("Saved trends_citations.png")

    # Top cited papers
    fig, ax = plt.subplots(figsize=(14, 8))
    plot_top_cited(papers, ax)
    plt.tight_layout()
    plt.savefig("trends_top_cited.png", dpi=150)
    plt.close()
    print("Saved trends_top_cited.png")


if __name__ == "__main__":
    main()
