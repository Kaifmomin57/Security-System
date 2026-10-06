"""
rules/gesture_rule.py
─────────────────────
Rule for Signal-for-Help Hand Gesture Detection (FR3-1 to FR3-4).
Evaluates active person tracks using keypoint analysis and raises immediate high-priority alerts.
"""

from typing import Any, Dict, List
import numpy as np

from rules.base_rule import BaseRule, RuleResult
from detection.gesture_detector import gesture_detector


class DistressGestureRule(BaseRule):
    @property
    def rule_type(self) -> str:
        return "signal_for_help"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results: List[RuleResult] = []
        # Current frame image passed via config context if available
        frame = config.get("current_frame")
        if frame is None:
            return []

        h, w = frame.shape[:2]

        for track in tracks:
            if getattr(track, "class_name", "") != "person":
                continue

            bbox = getattr(track, "bbox", None)
            if not bbox:
                continue

            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 - x1 < 30 or y2 - y1 < 50:
                continue

            person_crop = frame[y1:y2, x1:x2]
            confirmed, confidence, desc = gesture_detector.process_person_crop(person_crop, track.track_id)

            if confirmed:
                results.append(RuleResult(
                    triggered=True,
                    confidence=confidence,
                    rule_type=self.rule_type,
                    track_ids=[track.track_id],
                    metadata={
                        "gesture_type": "signal_for_help",
                        "description": desc or "Signal-for-Help universal distress gesture detected",
                        "centroid": [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                        "bbox": [x1, y1, x2, y2],
                        "priority": "IMMEDIATE_DISPATCH",
                    }
                ))

        return results
