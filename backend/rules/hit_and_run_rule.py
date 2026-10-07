"""
rules/hit_and_run_rule.py
─────────────────────────
Rule for Hit-and-Run incident detection (FR6-1 to FR6-5):
1. Detects collision-pattern signature: sudden proximity with simultaneous sharp speed drop.
2. Post-collision phase: one track remains stationary/down while the other accelerates away and flees without stopping.
3. Triggers high-severity 'possible_hit_and_run' alert with involved track IDs.
"""

import math
from typing import Any, Dict, List, Tuple

from rules.base_rule import BaseRule, RuleResult
from storage.db import CollisionEvent, Event, get_session

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}


class CollisionCandidate:
    def __init__(
        self,
        track_1_id: int,
        track_2_id: int,
        timestamp: float,
        location: Tuple[float, float],
        positions: Dict[int, Tuple[float, float]],
    ):
        self.track_1_id = track_1_id
        self.track_2_id = track_2_id
        self.timestamp = timestamp
        self.location = location
        self.positions = positions


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


def _get_timestamp(pt) -> float:
    if hasattr(pt, "timestamp"):
        return float(pt.timestamp)
    if isinstance(pt, (tuple, list)) and len(pt) >= 3:
        return float(pt[0])
    return 0.0


class HitAndRunRule(BaseRule):
    def __init__(
        self,
        proximity_threshold_px: float = 100.0,
        speed_drop_ratio: float = 0.30,
        fleeing_speed_min_px: float = 20.0,
        observation_window_secs: float = 5.0,
        stationary_speed_max_px: float = 8.0,
        minimum_departure_px: float = 35.0,
    ):
        self.proximity_threshold = proximity_threshold_px
        self.speed_drop_ratio = speed_drop_ratio
        self.fleeing_speed_min = fleeing_speed_min_px
        self.observation_window = observation_window_secs
        self.stationary_speed_max = stationary_speed_max_px
        self.minimum_departure = minimum_departure_px

        # Active collision candidates: (t1, t2) -> CollisionCandidate
        self._candidates: Dict[Tuple[int, int], CollisionCandidate] = {}
        # Track speeds are in pixels per second, not pixels per frame.
        self._speed_history: Dict[int, List[float]] = {}

    @property
    def rule_type(self) -> str:
        return "possible_hit_and_run"

    def _calc_speed(self, trajectory: List[Any]) -> float:
        """Calculate instantaneous speed in pixels per second."""
        if len(trajectory) < 2:
            return 0.0
        p1 = _get_pos(trajectory[-2])
        p2 = _get_pos(trajectory[-1])
        elapsed = _get_timestamp(trajectory[-1]) - _get_timestamp(trajectory[-2])
        if elapsed <= 0:
            return 0.0
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / elapsed

    def evaluate(self, tracks: List[Any], config: Dict[str, Any]) -> List[RuleResult]:
        results: List[RuleResult] = []
        rule_config = config.get("hit_and_run", {})
        if not rule_config.get("enabled", True):
            return results

        # Build track map and update speeds
        track_map = {}
        active_ids = set()
        current_positions = {}
        current_timestamp = 0.0

        for t in tracks:
            tid = t.track_id
            active_ids.add(tid)
            track_map[tid] = t

            traj = getattr(t, "trajectory", [])
            if not traj:
                continue
            current_positions[tid] = _get_pos(traj[-1])
            current_timestamp = max(current_timestamp, _get_timestamp(traj[-1]))
            sp = self._calc_speed(traj)
            if tid not in self._speed_history:
                self._speed_history[tid] = []
            if len(traj) >= 2:
                speed_time = _get_timestamp(traj[-1])
                history = self._speed_history[tid]
                if not history or history[-1][0] != speed_time:
                    history.append((speed_time, sp))
                    if len(history) > 20:
                        history.pop(0)

        # ── Step 1: Detect Collision Pattern Signatures ────────────────────────
        track_list = list(track_map.values())
        for i in range(len(track_list)):
            for j in range(i + 1, len(track_list)):
                t1, t2 = track_list[i], track_list[j]
                c1 = getattr(t1, "class_name", "")
                c2 = getattr(t2, "class_name", "")

                # Require a vehicle-vehicle or vehicle-person interaction.
                if c1 not in VEHICLE_CLASSES and c2 not in VEHICLE_CLASSES:
                    continue

                traj1 = getattr(t1, "trajectory", [])
                traj2 = getattr(t2, "trajectory", [])
                if len(traj1) < 2 or len(traj2) < 2:
                    continue

                pos1 = current_positions.get(t1.track_id)
                pos2 = current_positions.get(t2.track_id)
                if pos1 is None or pos2 is None:
                    continue
                dist = math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])
                previous_pos1 = _get_pos(traj1[-2])
                previous_pos2 = _get_pos(traj2[-2])
                previous_dist = math.hypot(
                    previous_pos1[0] - previous_pos2[0],
                    previous_pos1[1] - previous_pos2[1],
                )

                pair_key = (min(t1.track_id, t2.track_id), max(t1.track_id, t2.track_id))

                if (
                    dist > self.proximity_threshold
                    or previous_dist - dist < rule_config.get("minimum_closing_px", 5.0)
                    or pair_key in self._candidates
                ):
                    continue

                # A pedestrian merely being near a vehicle is not a collision.
                # Require a fast-moving vehicle to decelerate sharply at close contact.
                impact_detected = False
                for vehicle in (t for t in (t1, t2) if getattr(t, "class_name", "") in VEHICLE_CLASSES):
                    speed_history = self._speed_history.get(vehicle.track_id, [])
                    if len(speed_history) < 2:
                        continue
                    prior_speeds = [speed for _, speed in speed_history[:-1][-3:]]
                    avg_prior_speed = sum(prior_speeds) / len(prior_speeds) if prior_speeds else 0.0
                    current_speed = speed_history[-1][1]
                    minimum_approach_speed = rule_config.get("minimum_approach_speed_px", 30.0)
                    if (
                        avg_prior_speed >= minimum_approach_speed
                        and current_speed <= avg_prior_speed * self.speed_drop_ratio
                    ):
                        impact_detected = True
                        break

                if impact_detected:
                    collision_loc = ((pos1[0] + pos2[0]) / 2.0, (pos1[1] + pos2[1]) / 2.0)
                    self._candidates[pair_key] = CollisionCandidate(
                        track_1_id=t1.track_id,
                        track_2_id=t2.track_id,
                        timestamp=current_timestamp,
                        location=collision_loc,
                        positions={t1.track_id: pos1, t2.track_id: pos2},
                    )

        # ── Step 2: Post-Collision Fleeing Assessment ──────────────────────────
        expired_keys = []
        for pair_key, cand in self._candidates.items():
            t1_id, t2_id = cand.track_1_id, cand.track_2_id
            elapsed = current_timestamp - cand.timestamp

            if elapsed > self.observation_window:
                expired_keys.append(pair_key)
                continue

            if elapsed <= 0:
                continue

            fleeing_id, stationary_id = None, None
            for possible_fleeing_id, possible_stationary_id in ((t1_id, t2_id), (t2_id, t1_id)):
                fleeing_track = track_map.get(possible_fleeing_id)
                if getattr(fleeing_track, "class_name", "") not in VEHICLE_CLASSES:
                    continue

                fleeing_speed_history = self._speed_history.get(possible_fleeing_id, [])
                stationary_speed_history = self._speed_history.get(possible_stationary_id, [])
                if not fleeing_speed_history or not stationary_speed_history:
                    continue

                fleeing_speed = fleeing_speed_history[-1][1]
                stationary_speed = stationary_speed_history[-1][1]
                fleeing_pos = current_positions.get(possible_fleeing_id)
                stationary_pos = current_positions.get(possible_stationary_id)
                fleeing_start = cand.positions[possible_fleeing_id]
                stationary_start = cand.positions[possible_stationary_id]
                if fleeing_pos is None or stationary_pos is None:
                    continue

                departure_distance = math.hypot(
                    fleeing_pos[0] - fleeing_start[0],
                    fleeing_pos[1] - fleeing_start[1],
                )
                stationary_drift = math.hypot(
                    stationary_pos[0] - stationary_start[0],
                    stationary_pos[1] - stationary_start[1],
                )
                if (
                    fleeing_speed >= self.fleeing_speed_min
                    and departure_distance >= self.minimum_departure
                    and stationary_speed <= self.stationary_speed_max
                    and stationary_drift <= rule_config.get("stationary_radius_px", 35.0)
                ):
                    fleeing_id, stationary_id = possible_fleeing_id, possible_stationary_id
                    break

            if fleeing_id and stationary_id:
                fleeing_track = track_map.get(fleeing_id)
                stat_track = track_map.get(stationary_id)
                fleeing_speed = self._speed_history[fleeing_id][-1][1]

                results.append(RuleResult(
                    triggered=True,
                    confidence=0.92,
                    rule_type="possible_hit_and_run",
                    track_ids=[fleeing_id, stationary_id],
                    metadata={
                        "violation_type": "hit_and_run",
                        "track_id_fleeing": fleeing_id,
                        "track_id_stationary": stationary_id,
                        "fleeing_class": getattr(fleeing_track, "class_name", "vehicle"),
                        "victim_class": getattr(stat_track, "class_name", "person"),
                        "collision_location": cand.location,
                        "fleeing_velocity_px": round(fleeing_speed, 1),
                        "observation_seconds": round(elapsed, 2),
                        "description": (
                            f"Possible collision at {cand.location}: vehicle #{fleeing_id} "
                            f"decelerated at close contact, then moved away while "
                            f"track #{stationary_id} remained at the scene."
                        ),
                    }
                ))
                expired_keys.append(pair_key)

        for k in expired_keys:
            self._candidates.pop(k, None)

        # Cleanup speed history
        for tid in list(self._speed_history.keys()):
            if tid not in active_ids:
                self._speed_history.pop(tid, None)

        return results
