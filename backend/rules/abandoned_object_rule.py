"""
rules/abandoned_object_rule.py
──────────────────────────────
Rule for Abandoned & Unattended Suspicious Object Detection (FR5-4 to FR5-6):
1. Detects stationary luggage/objects (backpack, suitcase, handbag).
2. Monitors proximity of person tracks over time.
3. If unattended for > threshold_seconds, raises 'abandoned_object' alert.
"""

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from rules.base_rule import BaseRule, RuleResult
from storage.db import AbandonedObjectEvent, Event, get_session

logger = logging.getLogger("sentryeye.abandoned_object")

OBJECT_CLASSES = {"backpack", "suitcase", "handbag"}


class AbandonedObjectRule(BaseRule):
    def __init__(
        self,
        proximity_radius_px: float = 120.0,
        unattended_threshold_seconds: float = 30.0, # default 30s for demo responsiveness (configurable up to 120s)
    ):
        self.proximity_radius = proximity_radius_px
        self.unattended_threshold = unattended_threshold_seconds
        # Track unattended timestamps: track_id -> first_unattended_timestamp
        self._unattended_start_times: Dict[int, float] = {}
        self._alerted_objects: set = set()

    @property
    def rule_type(self) -> str:
        return "abandoned_object"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results: List[RuleResult] = []
        now = time.time()
        camera_id = config.get("camera_id", "cam_01")
        cfg_threshold = config.get("abandoned_threshold_seconds", self.unattended_threshold)

        # Separate object tracks from person tracks
        object_tracks = [t for t in tracks if getattr(t, "class_name", "") in OBJECT_CLASSES]
        person_tracks = [t for t in tracks if getattr(t, "class_name", "") == "person"]

        active_object_ids = set()

        for obj in object_tracks:
            obj_id = obj.track_id
            active_object_ids.add(obj_id)
            obj_cx, obj_cy = getattr(obj, "centroid", (0, 0))

            # Check if any person is within proximity radius
            has_nearby_person = False
            nearest_person_dist = float("inf")

            for p in person_tracks:
                p_cx, p_cy = getattr(p, "centroid", (0, 0))
                dist = math.hypot(obj_cx - p_cx, obj_cy - p_cy)
                if dist < nearest_person_dist:
                    nearest_person_dist = dist
                if dist <= self.proximity_radius:
                    has_nearby_person = True
                    break

            if has_nearby_person:
                # Owner / person present: reset unattended timer
                self._unattended_start_times.pop(obj_id, None)
                self._alerted_objects.discard(obj_id)
            else:
                # No person nearby
                if obj_id not in self._unattended_start_times:
                    self._unattended_start_times[obj_id] = now

                duration_unattended = now - self._unattended_start_times[obj_id]

                if duration_unattended >= cfg_threshold and obj_id not in self._alerted_objects:
                    self._alerted_objects.add(obj_id)
                    confidence = min(0.95, 0.70 + (duration_unattended - cfg_threshold) * 0.01)

                    results.append(RuleResult(
                        triggered=True,
                        confidence=round(confidence, 2),
                        rule_type=self.rule_type,
                        track_ids=[obj_id],
                        metadata={
                            "object_class": obj.class_name,
                            "object_track_id": obj_id,
                            "duration_unattended_seconds": round(duration_unattended, 1),
                            "nearest_person_dist_px": round(nearest_person_dist, 1) if nearest_person_dist != float("inf") else 999,
                            "location": [round(obj_cx, 1), round(obj_cy, 1)],
                            "description": (
                                f"Unattended {obj.class_name} left stationary with no owner nearby for "
                                f"{int(duration_unattended)} seconds."
                            ),
                        }
                    ))

        # Cleanup disappeared objects
        for oid in list(self._unattended_start_times.keys()):
            if oid not in active_object_ids:
                self._unattended_start_times.pop(oid, None)
                self._alerted_objects.discard(oid)

        return results
