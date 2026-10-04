"""
rules/zone_intrusion_rule.py
─────────────────────────────
Detects when a person crosses into a restricted zone,
optionally only during configured active hours.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from shapely.geometry import Point, Polygon

from rules.base_rule import BaseRule, RuleResult

logger = logging.getLogger(__name__)


class ZoneIntrusionRule(BaseRule):
    """
    Fires when a person enters a restricted zone polygon.
    Supports active_hours to only monitor during certain times (e.g. "22:00-06:00").
    """

    @property
    def rule_type(self) -> str:
        return "intrusion"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results = []
        zones = config.get("zones", [])

        for zone in zones:
            intrusion_cfg = self._get_rule_config(zone, "intrusion")
            if not intrusion_cfg or not intrusion_cfg.get("enabled", True):
                continue

            active_hours = intrusion_cfg.get("active_hours")
            if active_hours and not self._is_active_now(active_hours):
                continue

            zone_id = zone.get("id", "unknown")
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
                if zone_poly.contains(Point(cx, cy)):
                    results.append(
                        RuleResult(
                            triggered=True,
                            confidence=0.85,
                            rule_type=self.rule_type,
                            track_ids=[track.track_id],
                            metadata={
                                "zone_id": zone_id,
                                "zone_name": zone.get("name", zone_id),
                                "centroid": [round(cx, 1), round(cy, 1)],
                                "polygon": polygon_pts,
                                "active_hours": active_hours,
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
    def _is_active_now(active_hours: str) -> bool:
        """
        Parse 'HH:MM-HH:MM' and return True if current time is within range.
        Handles overnight ranges like '22:00-06:00'.
        """
        try:
            start_str, end_str = active_hours.split("-")
            now = datetime.now().time()
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
            from datetime import time as dtime
            start = dtime(sh, sm)
            end   = dtime(eh, em)
            if start <= end:
                return start <= now <= end
            else:   # overnight window
                return now >= start or now <= end
        except Exception:
            return True  # if parse fails, default to always active
