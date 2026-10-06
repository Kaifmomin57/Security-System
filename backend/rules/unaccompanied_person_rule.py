"""
rules/unaccompanied_person_rule.py
───────────────────────────────────
Feature A (PRD): Abandoned / Lost / Unaccompanied Person Detection.

Detects when a small-stature individual (heuristic proxy for a child/vulnerable person)
remains in a monitored area without a consistently associated adult-sized companion
for longer than a configurable threshold.
"""

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from rules.base_rule import BaseRule, RuleResult
from storage.db import get_session, TrackClassification, UnaccompaniedEvent

logger = logging.getLogger(__name__)


class StatureClassifier:
    """
    Heuristic classifier that determines whether a person bounding box
    corresponds to a 'small' (child/vulnerable proxy), 'adult', or 'ambiguous' stature.
    """

    def __init__(
        self,
        adult_height_ref: float = 160.0,       # default reference adult pixel height at standard depth
        small_stature_ratio: float = 0.68,     # < 68% of adult height = small stature
        min_aspect_ratio: float = 1.4,         # height / width ratio for upright person
    ):
        self.adult_height_ref = adult_height_ref
        self.small_stature_ratio = small_stature_ratio
        self.min_aspect_ratio = min_aspect_ratio

    def classify(self, track: Any, all_tracks: List[Any], calib_config: Dict[str, Any]) -> Tuple[str, float]:
        """
        Classifies track stature into ('small', 'adult', 'ambiguous') with a confidence score.
        """
        x1, y1, x2, y2 = track.bbox
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        aspect = h / w

        # Retrieve camera calibration if provided
        ref_h = calib_config.get("adult_height_px", self.adult_height_ref)
        small_ratio = calib_config.get("small_stature_ratio", self.small_stature_ratio)

        # Dynamic comparison against other visible adults in frame if available
        adult_heights = [
            (t.bbox[3] - t.bbox[1]) for t in all_tracks
            if t.track_id != track.track_id and t.class_name == "person" and (t.bbox[3] - t.bbox[1]) > ref_h * 0.75
        ]
        if adult_heights:
            effective_adult_h = sum(adult_heights) / len(adult_heights)
        else:
            effective_adult_h = ref_h

        ratio = h / effective_adult_h

        if ratio <= small_ratio:
            confidence = min(1.0, max(0.5, 1.0 - (ratio / small_ratio) * 0.4))
            return "small", confidence
        elif ratio >= 0.85:
            confidence = min(1.0, max(0.5, (ratio - 0.85) / 0.3 + 0.5))
            return "adult", confidence
        else:
            return "ambiguous", 0.4


class UnaccompaniedPersonRule(BaseRule):
    """
    Fires when a small-stature individual is unaccompanied by any adult
    within a configured proximity radius for longer than threshold_seconds.

    Config keys:
        threshold_seconds   : int (default 60s)
        proximity_radius_px : float (default 140px)
        adult_height_px     : float (default 160px)
        small_stature_ratio : float (default 0.68)
    """

    def __init__(self):
        self.classifier = StatureClassifier()
        # track_id -> {
        #   "stature": str,
        #   "alone_since": float,
        #   "last_adult_seen_at": Optional[float],
        #   "recorded_db": bool
        # }
        self._state: Dict[int, dict] = {}

    @property
    def rule_type(self) -> str:
        return "unaccompanied_person"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results = []
        now = time.time()

        # Extract camera/zone unaccompanied rule config
        unaccompanied_cfg = self._extract_config(config)
        if not unaccompanied_cfg.get("enabled", True):
            return results

        threshold = unaccompanied_cfg.get("threshold_seconds", 60)
        proximity_radius = unaccompanied_cfg.get("proximity_radius_px", 140.0)

        # Filter only active person tracks
        person_tracks = [t for t in tracks if getattr(t, "class_name", "person") == "person"]
        if not person_tracks:
            return results

        # 1. Classify statures for all person tracks in this frame
        classified = {}
        adult_tracks = []
        small_tracks = []

        for t in person_tracks:
            stature, conf = self.classifier.classify(t, person_tracks, unaccompanied_cfg)
            classified[t.track_id] = (stature, conf)
            if stature == "adult":
                adult_tracks.append(t)
            elif stature == "small":
                small_tracks.append(t)

        # 2. Check each small-stature track for proximity to any adult track
        active_ids = {t.track_id for t in person_tracks}

        for small_track in small_tracks:
            tid = small_track.track_id
            stature, conf = classified[tid]

            if tid not in self._state:
                self._state[tid] = {
                    "stature": stature,
                    "alone_since": now,
                    "last_adult_seen_at": None,
                    "nearest_adult_dist": None,
                }

            state = self._state[tid]
            sx, sy = small_track.centroid

            # Find nearest adult
            min_dist = float("inf")
            nearest_adult_id = None
            for adult in adult_tracks:
                ax, ay = adult.centroid
                dist = math.hypot(sx - ax, sy - ay)
                if dist < min_dist:
                    min_dist = dist
                    nearest_adult_id = adult.track_id

            is_accompanied = min_dist <= proximity_radius

            if is_accompanied:
                # Reset alone counter
                state["last_adult_seen_at"] = now
                state["alone_since"] = now
                state["nearest_adult_dist"] = min_dist
            else:
                # Person is currently alone
                state["nearest_adult_dist"] = min_dist if min_dist != float("inf") else None
                duration_alone = now - state["alone_since"]

                if duration_alone >= threshold:
                    confidence = self._score_confidence(duration_alone, threshold, conf)
                    last_adult_ts = state["last_adult_seen_at"]
                    last_adult_dt_str = (
                        datetime.utcfromtimestamp(last_adult_ts).isoformat()
                        if last_adult_ts else "None (never observed nearby)"
                    )

                    results.append(
                        RuleResult(
                            triggered=True,
                            confidence=confidence,
                            rule_type=self.rule_type,
                            track_ids=[tid],
                            metadata={
                                "stature_class": "small-stature (child/vulnerable proxy)",
                                "stature_confidence": round(conf, 2),
                                "duration_alone_seconds": int(duration_alone),
                                "threshold_seconds": threshold,
                                "last_adult_seen_at": last_adult_dt_str,
                                "nearest_adult_distance_px": round(min_dist, 1) if min_dist != float("inf") else "None",
                                "centroid": [round(sx, 1), round(sy, 1)],
                                "explanation": (
                                    f"Small-stature person (Track #{tid}) has been alone without an adult "
                                    f"companion for {int(duration_alone)}s (threshold: {threshold}s)."
                                ),
                            },
                        )
                    )

        # Cleanup disappeared tracks from state
        stale_keys = [k for k in self._state if k not in active_ids]
        for k in stale_keys:
            if now - self._state[k].get("alone_since", now) > 120:
                del self._state[k]

        return results

    def _extract_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract unaccompanied rule config from zones config or camera root config."""
        if "unaccompanied_person" in config:
            return config["unaccompanied_person"]
        if "unaccompanied" in config:
            return config["unaccompanied"]
        # Check zone rules
        for zone in config.get("zones", []):
            for r in zone.get("rules", []):
                if r.get("type") in ("unaccompanied_person", "unaccompanied"):
                    return r
        # Direct configuration in root dict
        if "threshold_seconds" in config or "unaccompanied_threshold_seconds" in config:
            return {
                "enabled": config.get("enabled", True),
                "threshold_seconds": config.get("threshold_seconds", config.get("unaccompanied_threshold_seconds", 60)),
                "proximity_radius_px": config.get("proximity_radius_px", 140.0),
                "adult_height_px": config.get("adult_height_px", 160.0),
                "small_stature_ratio": config.get("small_stature_ratio", 0.68),
            }
        # Default configuration
        return {
            "enabled": True,
            "threshold_seconds": 60,
            "proximity_radius_px": 140.0,
            "adult_height_px": 160.0,
            "small_stature_ratio": 0.68,
        }

    def _score_confidence(self, duration_alone: float, threshold: float, stature_conf: float) -> float:
        ratio = (duration_alone - threshold) / (2.0 * threshold + 1e-9)
        time_score = 0.5 + 0.5 * min(ratio, 1.0)
        final_conf = 0.7 * time_score + 0.3 * stature_conf
        return self._clamp_confidence(final_conf)
