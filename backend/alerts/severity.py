"""
alerts/severity.py
───────────────────
Maps rule type + confidence → severity tier (low / medium / high).
"""

from rules.base_rule import RuleResult

# Base severity thresholds per rule type
RULE_BASE_SEVERITY = {
    "intrusion":  "high",    # zone violation is immediately high
    "loitering":  "medium",
    "trailing":   "medium",
    "crowd":      "low",
    "abandoned":  "medium",
}


def score_severity(result: RuleResult) -> str:
    """
    Return 'low' | 'medium' | 'high' based on rule type + confidence.

    Logic:
      - Start with rule's base severity
      - Upgrade if confidence >= 0.85
      - Downgrade if confidence < 0.55
    """
    base = RULE_BASE_SEVERITY.get(result.rule_type, "low")
    conf = result.confidence

    tiers = ["low", "medium", "high"]
    idx = tiers.index(base)

    if conf >= 0.85 and idx < 2:
        idx += 1   # upgrade severity
    elif conf < 0.55 and idx > 0:
        idx -= 1   # downgrade severity

    return tiers[idx]
