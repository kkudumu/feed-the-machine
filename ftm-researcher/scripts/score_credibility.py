#!/usr/bin/env python3
"""
Source credibility scoring for ftm-researcher findings.

Scoring dimensions:
- Source type weight (35%): primary > peer_reviewed > official_docs > news > blog > forum
- Recency (20%): decay based on age for fast-moving topics
- Expertise signals (25%): domain authority, author credentials
- Bias detection (20%): sensationalism penalties, balanced language bonuses

Additional flags:
- Corroboration bonus: +0.15 if independently found by 2+ agents from different source types
- Circular sourcing: flag if multiple sources cite the same original
"""
import json
import sys
import re
from datetime import datetime
from urllib.parse import urlparse

# Source type base weights
SOURCE_WEIGHTS = {
    "primary": 1.0,
    "peer_reviewed": 0.9,
    "official_docs": 0.85,
    "code_repo": 0.8,
    "qa_site": 0.65,
    "news": 0.6,
    "blog": 0.4,
    "forum": 0.25,
    "codebase": 0.95,  # local codebase findings are high-trust
}

# High-authority domains
HIGH_AUTHORITY = {
    "arxiv.org", "nature.com", "science.org", "acm.org", "ieee.org",
    "github.com", "docs.python.org", "developer.mozilla.org",
    "platform.openai.com", "docs.anthropic.com", "cloud.google.com",
    "aws.amazon.com", "learn.microsoft.com",
}

MODERATE_AUTHORITY = {
    "stackoverflow.com", "stackexchange.com", "reddit.com",
    "news.ycombinator.com", "techcrunch.com", "arstechnica.com",
    "thenewstack.io", "infoq.com", "dev.to",
}

# Sensationalism indicators
SENSATIONAL_PATTERNS = [
    r"you won't believe", r"shocking", r"mind-blowing", r"game.?changer",
    r"revolutionary", r"incredible", r"amazing breakthrough",
]

# Balanced language indicators
BALANCED_PATTERNS = [
    r"however", r"on the other hand", r"trade-?off", r"limitation",
    r"caveat", r"although", r"despite", r"conversely",
]


def score_source_type(finding: dict) -> float:
    return SOURCE_WEIGHTS.get(finding.get("source_type", "blog"), 0.4)


def score_recency(finding: dict, fast_moving: bool = True) -> float:
    """Score based on source recency. Extracts year from URL or metadata."""
    url = finding.get("source_url", "")
    evidence = finding.get("evidence", "")
    current_year = datetime.now().year

    # Try to extract year from URL (common in blog/paper URLs)
    year_match = re.search(r'/(20[12]\d)/', url)
    if not year_match:
        # Try evidence text for year mentions
        year_match = re.search(r'\b(20[12]\d)\b', evidence)

    if year_match:
        source_year = int(year_match.group(1))
        age = current_year - source_year
        if fast_moving:
            # Aggressive decay for fast-moving topics (tech, AI, etc.)
            decay_map = {0: 1.0, 1: 0.85, 2: 0.65, 3: 0.45, 4: 0.30}
            return decay_map.get(age, 0.2)
        else:
            # Gentle decay for stable topics
            decay_map = {0: 1.0, 1: 0.95, 2: 0.85, 3: 0.75, 4: 0.65, 5: 0.55}
            return decay_map.get(age, 0.4)

    # No date info — return neutral
    return 0.7


def score_domain_authority(finding: dict) -> float:
    url = finding.get("source_url", "")
    if not url:
        if finding.get("source_type") == "codebase":
            return 0.95
        return 0.5

    try:
        domain = urlparse(url).netloc.lower()
        # Strip www.
        domain = domain.removeprefix("www.")
    except Exception:
        return 0.5

    if domain in HIGH_AUTHORITY:
        return 0.9
    if domain in MODERATE_AUTHORITY:
        return 0.7
    # Check for .edu, .gov
    if domain.endswith(".edu") or domain.endswith(".gov"):
        return 0.85
    return 0.55


def score_bias(finding: dict) -> float:
    text = finding.get("evidence", "") + " " + finding.get("claim", "")
    text_lower = text.lower()

    score = 0.7  # baseline

    # Penalize sensationalism
    for pattern in SENSATIONAL_PATTERNS:
        if re.search(pattern, text_lower):
            score -= 0.1

    # Bonus for balanced language
    for pattern in BALANCED_PATTERNS:
        if re.search(pattern, text_lower):
            score += 0.05

    return max(0.1, min(1.0, score))


def detect_circular_sourcing(findings: list) -> list:
    """Flag findings where multiple sources trace to the same original."""
    url_groups = {}
    for i, f in enumerate(findings):
        url = f.get("source_url", "")
        if url:
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            claim_key = f.get("claim", "")[:50]
            key = f"{domain}:{claim_key}"
            url_groups.setdefault(key, []).append(i)

    circular_indices = set()
    for key, indices in url_groups.items():
        if len(indices) > 1:
            for idx in indices:
                circular_indices.add(idx)

    return list(circular_indices)


def score_findings(findings: list) -> list:
    circular = detect_circular_sourcing(findings)

    # Count agent agreement per claim (simplified: exact claim match)
    claim_agents = {}
    for f in findings:
        claim = f.get("claim", "")
        agent = f.get("agent_role", "unknown")
        source_type = f.get("source_type", "")
        claim_agents.setdefault(claim, {"agents": set(), "source_types": set()})
        claim_agents[claim]["agents"].add(agent)
        claim_agents[claim]["source_types"].add(source_type)

    scored = []
    for i, f in enumerate(findings):
        type_score = score_source_type(f)
        recency_score = score_recency(f)
        authority_score = score_domain_authority(f)
        bias_score = score_bias(f)

        # Weighted composite
        composite = (
            type_score * 0.35 +
            recency_score * 0.20 +
            authority_score * 0.25 +
            bias_score * 0.20
        )

        # Corroboration bonus
        claim = f.get("claim", "")
        if claim in claim_agents:
            info = claim_agents[claim]
            if len(info["agents"]) >= 2 and len(info["source_types"]) >= 2:
                composite += 0.15

        # Circular sourcing penalty
        is_circular = i in circular
        if is_circular:
            composite -= 0.2

        composite = max(0.0, min(1.0, composite))

        scored_finding = {
            **f,
            "credibility_score": round(composite, 3),
            "score_breakdown": {
                "source_type": round(type_score, 3),
                "recency": round(recency_score, 3),
                "domain_authority": round(authority_score, 3),
                "bias": round(bias_score, 3),
            },
            "circular_sourcing": is_circular,
            "corroborated": claim in claim_agents and len(claim_agents[claim]["agents"]) >= 2,
            "trust_level": (
                "high" if composite >= 0.75 else
                "moderate" if composite >= 0.55 else
                "low" if composite >= 0.35 else
                "verify"
            ),
        }
        scored.append(scored_finding)

    return sorted(scored, key=lambda x: x["credibility_score"], reverse=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: score_credibility.py <findings.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        findings = json.load(f)

    scored = score_findings(findings)
    print(json.dumps(scored, indent=2))


if __name__ == "__main__":
    main()
