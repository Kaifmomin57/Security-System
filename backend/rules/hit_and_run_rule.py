"""
rules/hit_and_run_rule.py
─────────────────────────
Rule for Hit-and-Run incident detection (FR6-1 to FR6-5):
1. Detects collision-pattern signature: sudden proximity with simultaneous sharp speed drop.
2. Post-collision phase: one track remains stationary/down while the other accelerates away and flees without stopping.
3. Triggers high-severity 'possible_hit_and_run' alert with involved track IDs.
"""

import math
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from rules.base_rule import BaseRule, RuleResult
from storage.db import CollisionEvent, Event, get_session

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}


class CollisionCandidate:
    def __init__(self, track_1_id: int, track_2_id: int, timestamp: float, location: Tuple[float, float]):
        self.track_1_id = track_1_id
        self.track_2_id = track_2_id
        self.timestamp = timestamp
        self.location = location
        self.confirmed = False
        self.alerted = False


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


class HitAndRunRule(BaseRule):
    def __init__(
        self,
        proximity_threshold_px: float = 160.0,
        speed_drop_ratio: float = 0.70,
        fleeing_speed_min_px: float = 3.0,
        observation_window_secs: float = 2.0,
    ):
        self.proximity_threshold = proximity_threshold_px
        self.speed_drop_ratio = speed_drop_ratio
        self.fleeing_speed_min = fleeing_speed_min_px
        self.observation_window = observation_window_secs

        # Active collision candidate incidents: (t1, t2) -> CollisionCandidate
        self._candidates: Dict[Tuple[int, int], CollisionCandidate] = {}
        # Track speed history: track_id -> List[speed]
        self._speed_history: Dict[int, List[float]] = {}

    @property
    def rule_type(self) -> str:
        return "possible_hit_and_run"

    def _calc_speed(self, trajectory: List[Any]) -> float:
        """Calculates instantaneous speed (pixels/frame) from trajectory tail."""
        if len(trajectory) < 2:
            return 0.0
        p1 = _get_pos(trajectory[-2])
        p2 = _get_pos(trajectory[-1])
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results: List[RuleResult] = []
        now = time.time()

        # Build track map and update speeds
        track_map = {}
        active_ids = set()

        for t in tracks:
            tid = t.track_id
            active_ids.add(tid)
            track_map[tid] = t

            traj = getattr(t, "trajectory", [])
            sp = self._calc_speed(traj)
            if tid not in self._speed_history:
                self._speed_history[tid] = []
            self._speed_history[tid].append(sp)
            if len(self._speed_history[tid]) > 20:
                self._speed_history[tid].pop(0)

        # ── Step 1: Detect Collision Pattern Signatures ────────────────────────
        track_list = list(track_map.values())
        for i in range(len(track_list)):
            for j in range(i + 1, len(track_list)):
                t1, t2 = track_list[i], track_list[j]
                c1 = getattr(t1, "class_name", "")
                c2 = getattr(t2, "class_name", "")

                # Must involve at least one vehicle (vehicle-vehicle or vehicle-person)
                if c1 not in VEHICLE_CLASSES and c2 not in VEHICLE_CLASSES:
                    continue

                traj1 = getattr(t1, "trajectory", [])
                traj2 = getattr(t2, "trajectory", [])
                if len(traj1) < 4 or len(traj2) < 4:
                    continue

                pos1 = _get_pos(traj1[-1])
                pos2 = _get_pos(traj2[-1])
                dist = math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])

                pair_key = (min(t1.track_id, t2.track_id), max(t1.track_id, t2.track_id))

                # Check proximity contact
                if dist <= self.proximity_threshold:
                    speeds1 = self._speed_history.get(t1.track_id, [])
                    speeds2 = self._speed_history.get(t2.track_id, [])

                    if len(speeds1) >= 4 and len(speeds2) >= 4:
                        avg_prior_1 = np.mean(speeds1[-4:-1])
                        avg_prior_2 = np.mean(speeds2[-4:-1])
                        curr_1 = speeds1[-1]
                        curr_2 = speeds2[-1]

                        # Sudden sharp drop in speed at moment of impact or close contact with vulnerable subject
                        impact_drop = (
                            (avg_prior_1 > 5.0 and curr_1 < avg_prior_1 * self.speed_drop_ratio) or
                            (avg_prior_2 > 5.0 and curr_2 < avg_prior_2 * self.speed_drop_ratio) or
                            (curr_1 <= 4.0 and avg_prior_1 >= 5.0) or
                            (curr_2 <= 4.0 and avg_prior_2 >= 5.0) or
                            (c1 == "person" or c2 == "person") # Vehicle in immediate collision zone with pedestrian
                        )

                        if impact_drop and pair_key not in self._candidates:
                            collision_loc = ((pos1[0] + pos2[0]) / 2.0, (pos1[1] + pos2[1]) / 2.0)
                            self._candidates[pair_key] = CollisionCandidate(
                                track_1_id=t1.track_id,
                                track_2_id=t2.track_id,
                                timestamp=now,
                                location=collision_loc,
                            )

        # ── Step 2: Post-Collision Fleeing Assessment ──────────────────────────
        expired_keys = []
        for pair_key, cand in self._candidates.items():
            t1_id, t2_id = cand.track_1_id, cand.track_2_id
            elapsed = now - cand.timestamp

            if elapsed > self.observation_window:
                expired_keys.append(pair_key)
                continue

            if cand.alerted:
                continue

            # Check if one is stationary/down and the other is fleeing rapidly
            sp1_hist = self._speed_history.get(t1_id, [])
            sp2_hist = self._speed_history.get(t2_id, [])

            cur_sp1 = sp1_hist[-1] if sp1_hist else 0.0
            cur_sp2 = sp2_hist[-1] if sp2_hist else 0.0

            fleeing_id, stationary_id = None, None

            # Case A: Track 1 fleeing, Track 2 stationary
            if cur_sp1 >= self.fleeing_speed_min and cur_sp2 <= 3.0:
                fleeing_id, stationary_id = t1_id, t2_id
            # Case B: Track 2 fleeing, Track 1 stationary
            elif cur_sp2 >= self.fleeing_speed_min and cur_sp1 <= 3.0:
                fleeing_id, stationary_id = t2_id, t1_id

            if fleeing_id and stationary_id:
                cand.alerted = True
                fleeing_track = track_map.get(fleeing_id)
                stat_track = track_map.get(stationary_id)

                results.append(RuleResult(
                    triggered=True,
                    confidence=0.93,
                    rule_type="possible_hit_and_run",
                    track_ids=[fleeing_id, stationary_id],
                    metadata={
                        "violation_type": "hit_and_run",
                        "track_id_fleeing": fleeing_id,
                        "track_id_stationary": stationary_id,
                        "fleeing_class": getattr(fleeing_track, "class_name", "vehicle"),
                        "victim_class": getattr(stat_track, "class_name", "person"),
                        "collision_location": cand.location,
                        "fleeing_velocity_px": round(max(cur_sp1, cur_sp2), 1),
                        "description": (
                            f"Collision signature detected at {cand.location}; Track #{fleeing_id} "
                            f"fleeing at high speed while Track #{stationary_id} is stationary/down."
                        ),
                    }
                ))

        for k in expired_keys:
            self._candidates.pop(k, None)

        # Cleanup speed history
        for tid in list(self._speed_history.keys()):
            if tid not in active_ids:
                self._speed_history.pop(tid, None)

        return results
