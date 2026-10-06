"""
rules/traffic_violation_rule.py
───────────────────────────────
Rule for detecting traffic violations at monitored junctions (FR5-1 to FR5-5):
1. Signal Jumping: Vehicle crossing configured junction stop line while signal is RED.
2. Wrong-Side Driving: Vehicle moving against configured lane direction vector sustained over frames.
"""

import math
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from rules.base_rule import BaseRule, RuleResult
from storage.db import Event, TrafficViolation, get_session

# Vehicle classes in YOLOv8
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}

# Global in-memory signal state store for junctions (camera_id -> "RED" | "GREEN" | "YELLOW")
JUNCTION_SIGNALS: Dict[str, str] = {
    "cam_01": "RED",
    "cam_02": "GREEN",
    "cam_03": "RED",
}


def get_junction_signal(camera_id: str) -> str:
    """Returns current signal state for a camera/junction."""
    return JUNCTION_SIGNALS.get(camera_id, "RED")


def set_junction_signal(camera_id: str, state: str) -> str:
    """Sets signal state for a camera/junction."""
    normalized = state.upper()
    if normalized not in ("RED", "GREEN", "YELLOW"):
        normalized = "RED"
    JUNCTION_SIGNALS[camera_id] = normalized
    return normalized


def _get_pos(pt) -> Tuple[float, float]:
    """Safely extracts (x, y) coordinates from a TrackPoint dataclass or tuple."""
    if hasattr(pt, "x") and hasattr(pt, "y"):
        return (float(pt.x), float(pt.y))
    if isinstance(pt, (tuple, list)):
        if len(pt) >= 3:
            return (float(pt[1]), float(pt[2]))
        elif len(pt) == 2:
            return (float(pt[0]), float(pt[1]))
    return (0.0, 0.0)


class TrafficViolationRule(BaseRule):
    """
    Evaluates traffic junction rules:
    - Signal jumping at stop line
    - Wrong-way / contra-flow driving
    """

    def __init__(
        self,
        min_contra_frames: int = 5,
        contra_angle_threshold_deg: float = 110.0,
    ):
        self.min_contra_frames = min_contra_frames
        self.contra_angle_threshold_deg = contra_angle_threshold_deg
        # Track history of stop-line side: track_id -> previous_side (-1 or 1)
        self._track_stop_line_side: Dict[int, int] = {}
        # Track contra-flow frame counters: track_id -> int
        self._track_contra_counts: Dict[int, int] = {}

    @property
    def rule_type(self) -> str:
        return "traffic_violation"

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results: List[RuleResult] = []
        camera_id = config.get("camera_id", "cam_01")
        signal_state = get_junction_signal(camera_id)

        # Configured stop line for junction (default horizontal line across mid-frame)
        stop_line_cfg = config.get("stop_line", [[50, 360], [590, 360]])
        expected_lane_heading = config.get("expected_heading_deg", 90.0) # 90 deg = downwards / South

        active_track_ids = set()

        for track in tracks:
            # Filter vehicle tracks only
            class_name = getattr(track, "class_name", "car")
            if class_name not in VEHICLE_CLASSES:
                continue

            tid = track.track_id
            active_track_ids.add(tid)

            # Trajectory history: [TrackPoint, ...]
            trajectory = getattr(track, "trajectory", [])
            if len(trajectory) < 2:
                continue

            curr_pos = _get_pos(trajectory[-1])
            prev_pos = _get_pos(trajectory[-2])

            # ── 1. Signal Jumping Evaluation ──────────────────────────────────
            # Check line crossing against stop line
            p1 = np.array(stop_line_cfg[0])
            p2 = np.array(stop_line_cfg[1])
            line_vec = p2 - p1

            # Determinant / signed side of line for current and previous pos
            def _get_side(pt):
                return np.sign(line_vec[0] * (pt[1] - p1[1]) - line_vec[1] * (pt[0] - p1[0]))

            curr_side = _get_side(curr_pos)
            prev_side = _get_side(prev_pos)
            self._track_stop_line_side[tid] = curr_side

            crossed_stop_line = (prev_side != curr_side and prev_side != 0 and curr_side != 0)

            if crossed_stop_line and signal_state == "RED":
                # Vehicle crossed line during RED signal
                results.append(RuleResult(
                    triggered=True,
                    confidence=0.94,
                    rule_type="signal_jump",
                    track_ids=[tid],
                    metadata={
                        "violation_type": "signal_jump",
                        "signal_state": "RED",
                        "junction_id": camera_id,
                        "stop_line": stop_line_cfg,
                        "crossed_at_pos": curr_pos,
                        "vehicle_class": class_name,
                        "description": f"Vehicle #{tid} crossed junction stop line while signal was RED",
                    }
                ))

            # ── 2. Wrong-Side Driving Evaluation ──────────────────────────────
            if len(trajectory) >= 4:
                # Calculate movement vector over last 4 points
                t_start_pos = _get_pos(trajectory[-4])
                t_end_pos = _get_pos(trajectory[-1])
                dx = t_end_pos[0] - t_start_pos[0]
                dy = t_end_pos[1] - t_start_pos[1]
                dist = math.hypot(dx, dy)

                if dist > 15.0: # Minimum significant vehicle displacement
                    # Heading angle in degrees (0 to 360)
                    heading_rad = math.atan2(dy, dx)
                    heading_deg = (math.degrees(heading_rad) + 360.0) % 360.0

                    # Angle difference against expected heading
                    angle_diff = abs(heading_deg - expected_lane_heading)
                    if angle_diff > 180.0:
                        angle_diff = 360.0 - angle_diff

                    if angle_diff >= self.contra_angle_threshold_deg:
                        self._track_contra_counts[tid] = self._track_contra_counts.get(tid, 0) + 1
                    else:
                        self._track_contra_counts[tid] = max(0, self._track_contra_counts.get(tid, 0) - 1)

                    if self._track_contra_counts.get(tid, 0) >= self.min_contra_frames:
                        speed_estimate = round(dist * 2.8, 1) # Estimated km/h
                        results.append(RuleResult(
                            triggered=True,
                            confidence=0.91,
                            rule_type="wrong_side",
                            track_ids=[tid],
                            metadata={
                                "violation_type": "wrong_side",
                                "expected_heading_deg": expected_lane_heading,
                                "actual_heading_deg": round(heading_deg, 1),
                                "angular_deviation_deg": round(angle_diff, 1),
                                "speed_estimate_kmh": speed_estimate,
                                "vehicle_class": class_name,
                                "description": f"Vehicle #{tid} traveling in reverse / contra-flow lane direction ({angle_diff:.0f}° off)",
                            }
                        ))

        # Cleanup stale tracks
        for tid in list(self._track_stop_line_side.keys()):
            if tid not in active_track_ids:
                self._track_stop_line_side.pop(tid, None)
                self._track_contra_counts.pop(tid, None)

        return results
