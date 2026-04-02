#!/usr/bin/env python3
"""
Validates ftm-researcher output for completeness and quality.

Checks:
1. All required fields present in each finding
2. Source URLs are non-empty for non-codebase findings
3. Confidence scores in valid range
4. Disagreement map has all 4 tiers
5. No placeholder text (TBD, TODO, FIXME)
6. Minimum finding count per mode (quick: 3, standard: 10, deep: 15)
7. Source diversity: at least 3 different source types represented
8. No duplicate claims (exact match)
"""
import json
import sys

REQUIRED_FINDING_FIELDS = ["claim", "source_type", "confidence", "agent_role"]
REQUIRED_MAP_TIERS = ["consensus", "contested", "unique_insights", "refuted"]
PLACEHOLDER_PATTERNS = ["TBD", "TODO", "FIXME", "placeholder", "lorem ipsum"]
MIN_FINDINGS = {"quick": 3, "standard": 10, "deep": 15}


def validate(output: dict) -> dict:
    errors = []
    warnings = []

    mode = output.get("mode", "standard")
    findings = output.get("findings", [])
    disagreement_map = output.get("disagreement_map", {})

    # Check minimum findings
    min_count = MIN_FINDINGS.get(mode, 10)
    if len(findings) < min_count:
        warnings.append(f"Only {len(findings)} findings for {mode} mode (expected >= {min_count})")

    # Check required fields
    for i, f in enumerate(findings):
        for field in REQUIRED_FINDING_FIELDS:
            if field not in f or not f[field]:
                errors.append(f"Finding {i}: missing required field '{field}'")

        # Source URL required for non-codebase
        if f.get("source_type") != "codebase" and not f.get("source_url"):
            warnings.append(f"Finding {i}: no source_url for {f.get('source_type')} source")

        # Confidence range
        conf = f.get("confidence", 0)
        if not (0.0 <= conf <= 1.0):
            errors.append(f"Finding {i}: confidence {conf} out of range [0, 1]")

        # Placeholder detection
        text = json.dumps(f).lower()
        for p in PLACEHOLDER_PATTERNS:
            if p.lower() in text:
                errors.append(f"Finding {i}: contains placeholder text '{p}'")

    # Source diversity
    source_types = set(f.get("source_type", "") for f in findings)
    if len(source_types) < 3:
        warnings.append(f"Only {len(source_types)} source types (expected >= 3)")

    # Duplicate detection
    claims = [f.get("claim", "") for f in findings]
    dupes = [c for c in claims if claims.count(c) > 1]
    if dupes:
        errors.append(f"Duplicate claims found: {set(dupes)}")

    # Disagreement map tiers
    if mode in ("standard", "deep"):
        for tier in REQUIRED_MAP_TIERS:
            if tier not in disagreement_map:
                errors.append(f"Disagreement map missing tier: {tier}")

    return {"errors": errors, "warnings": warnings, "valid": len(errors) == 0}


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_research.py <output.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        output = json.load(f)

    result = validate(output)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
