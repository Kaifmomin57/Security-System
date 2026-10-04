"""
rules/base_rule.py
──────────────────
Abstract base class for all behavior rules.
Every rule implements evaluate() and returns a RuleResult.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


@dataclass
class RuleResult:
    """Output from a single rule evaluation."""
    triggered: bool
    confidence: float                 # 0.0 – 1.0
    rule_type: str
    track_ids: List[int]
    metadata: Dict[str, Any] = field(default_factory=dict)
    # metadata carries rule-specific info for the Explainability Panel
    # e.g. {"dwell_time": 72.3, "zone_id": "zone_atm", "trajectory_points": [...]}

    @property
    def is_valid(self) -> bool:
        return self.triggered and 0.0 < self.confidence <= 1.0


class BaseRule(ABC):
    """
    Abstract base for all SentryEye behavior rules.

    Subclasses must implement:
        - rule_type  (str property)
        - evaluate() (returns RuleResult)
    """

    @property
    @abstractmethod
    def rule_type(self) -> str:
        """Unique string identifier for this rule, e.g. 'loitering'."""
        ...

    @abstractmethod
    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        """
        Evaluate the rule against the current set of active tracks.

        Args:
            tracks : list of Track objects from tracker.py
            config : rule configuration dict (thresholds, zone polygons, etc.)

        Returns:
            List of RuleResult — one per triggering track/pair.
        """
        ...

    def _clamp_confidence(self, value: float) -> float:
        return max(0.0, min(1.0, value))
