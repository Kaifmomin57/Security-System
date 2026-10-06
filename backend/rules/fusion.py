"""
rules/fusion.py
───────────────
Multi-signal fusion + temporal smoothing layer.

Before an alert is raised, a rule must:
  1. Fire on >= N of the last M evaluations  (temporal smoothing)
  2. Optionally combine >= 2 independent rule signals  (multi-signal fusion)

This is the primary false-alarm reduction mechanism.
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from rules.base_rule import RuleResult

logger = logging.getLogger(__name__)


@dataclass
class SmoothingBuffer:
    """Sliding window of recent rule results for one (track_id, rule_type) pair."""
    window: deque = field(default_factory=lambda: deque(maxlen=8))  # last M=8 evaluations
    last_confirmed_at: float = 0.0
    confirmed_count: int = 0

    def push(self, triggered: bool, confidence: float):
        self.window.append((triggered, confidence))

    @property
    def trigger_count(self) -> int:
        return sum(1 for (t, _) in self.window if t)

    @property
    def avg_confidence(self) -> float:
        confs = [c for (t, c) in self.window if t]
        return sum(confs) / len(confs) if confs else 0.0


class FusionEngine:
    """
    Temporal smoothing + multi-signal fusion gate.

    Args:
        n_required    : rule must fire at least N times out of last M evaluations
        m_window      : rolling window size (M)
        cooldown_secs : min seconds between confirmed alerts for same track+rule
    """

    def __init__(
        self,
        n_required: int = 2,
        m_window: int = 4,
        cooldown_secs: int = 10,
    ):
        self.n_required = n_required
        self.m_window = m_window
        self.cooldown_secs = cooldown_secs

        # Key: (camera_id, track_ids_tuple, rule_type) -> SmoothingBuffer
        self._buffers: Dict[Tuple, SmoothingBuffer] = defaultdict(
            lambda: SmoothingBuffer(window=deque(maxlen=m_window))
        )

    def process(
        self,
        raw_results: List[RuleResult],
        camera_id: str,
    ) -> List[RuleResult]:
        """
        Feed raw rule results → return only temporally-confirmed results.

        Args:
            raw_results : list of RuleResult from all rules this frame
            camera_id   : for keying the smoothing buffer

        Returns:
            Confirmed RuleResult objects ready for the alert layer.
        """
        confirmed = []

        for result in raw_results:
            if not result.triggered:
                continue

            key = (camera_id, tuple(sorted(result.track_ids)), result.rule_type)
            buf = self._buffers[key]
            buf.push(result.triggered, result.confidence)

            # ── Temporal smoothing check ──────────────────────────────────────
            if buf.trigger_count < self.n_required:
                logger.debug(
                    f"Smoothing: {result.rule_type} for tracks {result.track_ids} "
                    f"— {buf.trigger_count}/{self.n_required} required. Suppressed."
                )
                continue

            # ── Cooldown check ────────────────────────────────────────────────
            now = time.time()
            if now - buf.last_confirmed_at < self.cooldown_secs:
                continue

            # ── Confirmed — pass through with smoothed confidence ─────────────
            buf.last_confirmed_at = now
            buf.confirmed_count += 1

            smoothed_result = RuleResult(
                triggered=True,
                confidence=buf.avg_confidence,
                rule_type=result.rule_type,
                track_ids=result.track_ids,
                metadata={
                    **result.metadata,
                    "smoothing_trigger_count": buf.trigger_count,
                    "smoothing_window": self.m_window,
                    "confirmed_count": buf.confirmed_count,
                },
            )
            confirmed.append(smoothed_result)
            logger.info(
                f"✅ CONFIRMED [{camera_id}] {result.rule_type} "
                f"tracks={result.track_ids} conf={buf.avg_confidence:.2f}"
            )

        return confirmed

    def reset_track(self, camera_id: str, track_id: int):
        """Clear buffers for a specific track (e.g. when track is lost)."""
        keys_to_delete = [
            k for k in self._buffers
            if k[0] == camera_id and track_id in k[1]
        ]
        for k in keys_to_delete:
            del self._buffers[k]
