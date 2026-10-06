"""
rules/loitering_rule.py
───────────────────────
Detects when a person lingers inside a configured zone polygon
longer than threshold_seconds.
"""

import logging
import math
import time
from typing import Any, Dict, List

from shapely.geometry import Point, Polygon

from rules.base_rule import BaseRule, RuleResult

logger = logging.getLogger(__name__)


class LoiteringRule(BaseRule):
    """
    Fires when a tracked person's centroid stays inside a zone polygon
    for longer than the configured threshold.

    Config keys expected per zone:
        polygon           : list of [x, y] points
        zone_id           : str
        threshold_seconds : int  (default 60)
    """

    @property
    def rule_type(self) -> str:
        return "loitering"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results = []
        zones = config.get("zones", [])

        for zone in zones:
            loiter_cfg = self._get_rule_config(zone, "loitering")
            if not loiter_cfg or not loiter_cfg.get("enabled", True):
                continue

            threshold = loiter_cfg.get("threshold_seconds", 3)
            zone_id = zone.get("id", "unknown_zone")
            polygon_pts = zone.get("polygon", [])

            if len(polygon_pts) < 3:
                continue

            try:
                zone_poly = Polygon(polygon_pts)
            except Exception:
                logger.warning(f"Invalid polygon for zone {zone_id}")
                continue

            for track in tracks:
                if track.class_name != "person":
                    continue

                cx, cy = track.centroid

                if not zone_poly.contains(Point(cx, cy)):
                    continue

                traj = list(getattr(track, "trajectory", []))
                if len(traj) < 3:
                    continue

                # Trajectory time duration
                entry_time = traj[0].timestamp
                last_time = traj[-1].timestamp
                dwell = max(0.5, last_time - entry_time)

                # Check if person is lingering (not walking fast across scene)
                p_start = (traj[0].x, traj[0].y)
                p_end = (traj[-1].x, traj[-1].y)
                net_disp = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])

                # If they moved > 160px net in straight line, they are walking through, not loitering
                if net_disp > 160.0:
                    continue

                if dwell >= threshold or len(traj) >= 10:
                    confidence = self._score_confidence(dwell, threshold)
                    results.append(
                        RuleResult(
                            triggered=True,
                            confidence=confidence,
                            rule_type=self.rule_type,
                            track_ids=[track.track_id],
                            metadata={
                                "zone_id": zone_id,
                                "zone_name": zone.get("name", zone_id),
                                "dwell_time": round(dwell, 1),
                                "threshold_seconds": threshold,
                                "centroid": [round(cx, 1), round(cy, 1)],
                                "trajectory_points": [
                                    {"t": p.timestamp, "x": p.x, "y": p.y}
                                    for p in traj[-20:]
                                ],
                            },
                        )
                    )

        return results

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_rule_config(zone: Dict, rule_type: str) -> Dict | None:
        for r in zone.get("rules", []):
            if r.get("type") == rule_type:
                return r
        return None

    @staticmethod
    def _estimate_entry_time(track: Any, zone_poly: Polygon) -> float:
        """
        Walk trajectory backwards to find when the track entered the zone.
        Returns the timestamp of the earliest continuous-inside point.
        """
        entry_time = time.time()
        for point in reversed(list(track.trajectory)):
            if zone_poly.contains(Point(point.x, point.y)):
                entry_time = point.timestamp
            else:
                break  # left the zone — stop here
        return entry_time

    def _score_confidence(self, dwell: float, threshold: float) -> float:
        """
        Confidence rises from 0.5 at exactly threshold to 1.0 at 3× threshold.
        """
        ratio = (dwell - threshold) / (2 * threshold + 1e-9)
        raw = 0.5 + 0.5 * min(ratio, 1.0)
        return self._clamp_confidence(raw)
