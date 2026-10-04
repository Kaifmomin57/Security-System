"""
alerts/trust_adjuster.py
─────────────────────────
Self-correcting alert trust (Differentiator F18).

Tracks dismiss-rate per (camera_id, rule_type).
If dismiss-rate exceeds threshold over a rolling window,
the rule's confirmation threshold is automatically raised for that camera.
"""

import logging
from collections import defaultdict, deque
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# If dismiss rate exceeds this, raise the confidence threshold
DISMISS_RATE_TRIGGER = 0.60   # 60% dismissed = suppression
DISMISS_WINDOW_SIZE  = 20     # look at last 20 alerts


class TrustAdjuster:
    """
    Per (camera_id, rule_type) dismiss-rate tracker.
    Returns whether an alert should be suppressed based on historical dismiss rate.
    """

    def __init__(self):
        # (camera_id, rule_type) -> deque of "dismissed" booleans
        self._history: Dict[Tuple[str, str], deque] = defaultdict(
            lambda: deque(maxlen=DISMISS_WINDOW_SIZE)
        )

    def record_outcome(self, camera_id: str, rule_type: str, dismissed: bool):
        """
        Record an alert outcome (dismissed or confirmed by operator).
        Call this when a PATCH /alerts/{id} changes status to 'dismissed' or 'resolved'.
        """
        key = (camera_id, rule_type)
        self._history[key].append(dismissed)
        rate = self.dismiss_rate(camera_id, rule_type)
        if rate >= DISMISS_RATE_TRIGGER:
            logger.warning(
                f"⚠️  High dismiss rate for [{camera_id}] {rule_type}: "
                f"{rate:.0%} — auto-raising confirmation threshold."
            )

    def should_suppress(self, camera_id: str, rule_type: str) -> bool:
        """
        Returns True if this rule+camera combo should be suppressed
        due to a high dismiss rate.
        """
        rate = self.dismiss_rate(camera_id, rule_type)
        if rate >= DISMISS_RATE_TRIGGER:
            logger.info(f"Suppressing [{camera_id}] {rule_type} (dismiss rate: {rate:.0%})")
            return True
        return False

    def dismiss_rate(self, camera_id: str, rule_type: str) -> float:
        history = self._history.get((camera_id, rule_type))
        if not history or len(history) < 5:
            return 0.0
        return sum(history) / len(history)

    def stats(self) -> Dict:
        return {
            f"{k[0]}:{k[1]}": {
                "dismiss_rate": f"{self.dismiss_rate(k[0], k[1]):.0%}",
                "sample_count": len(v),
            }
            for k, v in self._history.items()
        }


# Singleton instance shared across the pipeline
trust_adjuster = TrustAdjuster()
