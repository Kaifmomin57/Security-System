"""
rules/weapon_rule.py
────────────────────
Rule for Weapon & Threatening Object Detection (FR5-1 to FR5-3):
1. Uses dedicated best.pt weapon model (gun, knife) via WeaponDetector.
2. Falls back to main detector raw_detections if weapon_detector unavailable.
3. Raises high-severity 'possible_weapon' alert explicitly flagged for human review.
"""

import logging
from typing import Any, Dict, List

from rules.base_rule import BaseRule, RuleResult

logger = logging.getLogger("sentryeye.weapon")

# Fallback classes if best.pt weapon_detector is not used
WEAPON_CLASSES_FALLBACK = {"knife", "scissors", "baseball bat"}


class WeaponDetectionRule(BaseRule):
    """
    Uses best.pt specialized weapon detector (gun + knife).
    Runs weapon inference per frame and associates detections to nearest person track.
    """

    def __init__(self, confidence_threshold: float = 0.55):
        self.conf_threshold = confidence_threshold
        # Import dedicated weapon detector (best.pt)
        try:
            from detection.weapon_detector import weapon_detector
            self._weapon_detector = weapon_detector
            logger.info("WeaponDetectionRule: Using dedicated best.pt weapon detector.")
        except Exception as e:
            self._weapon_detector = None
            logger.warning(f"WeaponDetectionRule: best.pt detector unavailable, using fallback: {e}")

    @property
    def rule_type(self) -> str:
        return "possible_weapon"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results: List[RuleResult] = []
        camera_id = config.get("camera_id", "cam_01")

        # ── Primary: Run best.pt weapon model on current frame ────────────────
        weapon_detections = []
        frame = config.get("current_frame")

        if self._weapon_detector is not None and frame is not None:
            weapon_detections = self._weapon_detector.detect(frame)

        # ── Fallback: Use main detector's raw_detections ──────────────────────
        if not weapon_detections:
            raw_detections = config.get("raw_detections", [])
            for det in raw_detections:
                cls_name = getattr(det, "class_name", "").lower()
                conf = getattr(det, "confidence", 0.0)
                if cls_name in WEAPON_CLASSES_FALLBACK and conf >= self.conf_threshold:
                    weapon_detections.append(det)

        # ── Associate each weapon detection with nearest person track ─────────
        person_tracks = [t for t in tracks if getattr(t, "class_name", "") == "person"]

        for det in weapon_detections:
            cls_name = getattr(det, "class_name", "weapon").lower()
            conf = getattr(det, "confidence", 0.0)

            if conf < self.conf_threshold:
                continue

            bbox = getattr(det, "bbox", [0, 0, 0, 0])
            x1, y1, x2, y2 = bbox
            w_cx, w_cy = (x1 + x2) / 2, (y1 + y2) / 2

            # Find nearest person track within 200px
            associated_track_id = None
            min_dist = float("inf")
            for t in person_tracks:
                t_cx, t_cy = getattr(t, "centroid", (0, 0))
                dist = ((w_cx - t_cx) ** 2 + (w_cy - t_cy) ** 2) ** 0.5
                if dist < min_dist and dist < 200:
                    min_dist = dist
                    associated_track_id = t.track_id

            # Severity escalation: gun > knife > other
            severity_flag = "IMMEDIATE" if cls_name == "gun" else "HIGH"

            results.append(RuleResult(
                triggered=True,
                confidence=round(conf, 2),
                rule_type=self.rule_type,
                track_ids=[associated_track_id] if associated_track_id else [],
                metadata={
                    "weapon_class": cls_name,
                    "confidence": round(conf, 2),
                    "associated_track_id": associated_track_id,
                    "location": [round(w_cx, 1), round(w_cy, 1)],
                    "severity_flag": severity_flag,
                    "detector": "best.pt" if self._weapon_detector else "fallback",
                    "description": (
                        f"⚠️ {cls_name.upper()} detected ({int(conf * 100)}% conf) "
                        f"[{severity_flag}] — flagged for mandatory human review"
                    ),
                }
            ))

        return results
