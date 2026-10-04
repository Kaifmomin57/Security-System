"""
rules/trailing_rule.py
───────────────────────
Detects when Person B follows Person A at a roughly consistent
distance for longer than duration_threshold seconds.

IMPORTANT: Uses trajectory and timing ONLY — zero demographic attributes.
"""

import logging
import math
import time
from typing import Any, Dict, List, Tuple

from rules.base_rule import BaseRule, RuleResult

logger = logging.getLogger(__name__)


class TrailingRule(BaseRule):
    """
    Stalking/trailing detector.

    Fires when:
    1. Track B's centroid is within [min_dist, max_dist] pixels of Track A
    2. This following distance is maintained for >= duration_threshold seconds
    3. The total number of persons in the scene is <= max_ambient_persons
       (avoids false positives in crowds)

    All logic is identity-agnostic (no gender/age/appearance).
    """

    @property
    def rule_type(self) -> str:
        return "trailing"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results = []
        trailing_cfg = config.get("trailing", {})

        min_dist   = trailing_cfg.get("min_follow_distance", 40)
        max_dist   = trailing_cfg.get("max_follow_distance", 200)
        duration   = trailing_cfg.get("duration_threshold", 45)
        max_people = trailing_cfg.get("max_ambient_persons", 4)

        # Filter to persons only
        persons = [t for t in tracks if t.class_name == "person"]

        # Low-activity check — don't flag in crowds
        if len(persons) > max_people:
            return []

        # Check every ordered pair (A, B) where B might be following A
        for i, track_a in enumerate(persons):
            for j, track_b in enumerate(persons):
                if i == j:
                    continue

                result = self._check_pair(
                    track_a, track_b, min_dist, max_dist, duration
                )
                if result:
                    results.append(result)

        return results

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _check_pair(
        self,
        track_a: Any,
        track_b: Any,
        min_dist: float,
        max_dist: float,
        duration_threshold: float,
    ) -> RuleResult | None:
        """
        Check if track_b is consistently following track_a.
        Returns a RuleResult if trailing is confirmed, else None.
        """
        traj_a = list(track_a.trajectory)
        traj_b = list(track_b.trajectory)

        if len(traj_a) < 10 or len(traj_b) < 10:
            return None  # Not enough history yet

        # Align trajectories by timestamp
        aligned = self._align_trajectories(traj_a, traj_b)
        if len(aligned) < 5:
            return None

        # Measure following distance at each aligned time point
        distances = [
            self._euclidean(ax, ay, bx, by)
            for (ax, ay), (bx, by) in aligned
        ]

        # Count how many points are within the following distance range
        in_range_count = sum(1 for d in distances if min_dist <= d <= max_dist)
        in_range_ratio = in_range_count / len(distances)

        # Require at least 70% of aligned points to be in range
        if in_range_ratio < 0.70:
            return None

        # Check if this condition has been sustained for long enough
        duration_covered = aligned[-1][0][0]  # last timestamp proxy via traj_a
        # Use actual timestamps from trajectory points
        first_ts = traj_a[0].timestamp if hasattr(traj_a[0], "timestamp") else time.time() - 60
        last_ts  = traj_a[-1].timestamp if hasattr(traj_a[-1], "timestamp") else time.time()
        sustained_seconds = last_ts - first_ts

        if sustained_seconds < duration_threshold:
            return None

        confidence = self._score_confidence(sustained_seconds, duration_threshold, in_range_ratio)

        return RuleResult(
            triggered=True,
            confidence=confidence,
            rule_type=self.rule_type,
            track_ids=[track_a.track_id, track_b.track_id],
            metadata={
                "leader_id": track_a.track_id,
                "follower_id": track_b.track_id,
                "sustained_seconds": round(sustained_seconds, 1),
                "avg_distance_px": round(sum(distances) / len(distances), 1),
                "in_range_ratio": round(in_range_ratio, 2),
                "trajectory_a": [
                    {"t": p.timestamp, "x": p.x, "y": p.y}
                    for p in traj_a[-20:]
                ],
                "trajectory_b": [
                    {"t": p.timestamp, "x": p.x, "y": p.y}
                    for p in traj_b[-20:]
                ],
            },
        )

    @staticmethod
    def _align_trajectories(
        traj_a: List[Any], traj_b: List[Any]
    ) -> List[Tuple[Tuple, Tuple]]:
        """
        Pair up trajectory points from A and B by nearest timestamp.
        Returns list of ((ax, ay), (bx, by)).
        """
        aligned = []
        b_times = [(p.timestamp, p.x, p.y) for p in traj_b]

        for pa in traj_a:
            # Find closest B point in time
            closest = min(b_times, key=lambda pb: abs(pb[0] - pa.timestamp), default=None)
            if closest and abs(closest[0] - pa.timestamp) < 2.0:  # within 2 seconds
                aligned.append(((pa.x, pa.y), (closest[1], closest[2])))

        return aligned

    @staticmethod
    def _euclidean(ax, ay, bx, by) -> float:
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)

    def _score_confidence(
        self, duration: float, threshold: float, ratio: float
    ) -> float:
        duration_score = min((duration - threshold) / threshold, 1.0) * 0.5
        ratio_score = (ratio - 0.70) / 0.30 * 0.5
        return self._clamp_confidence(0.4 + duration_score + ratio_score)
