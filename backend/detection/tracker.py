"""
detection/tracker.py
─────────────────────
DeepSORT wrapper — assigns persistent track_id to each detected person/object.
Maintains a rolling history of each track's trajectory for the rule engine.
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

from detection.detector import Detection

logger = logging.getLogger(__name__)

# Max trajectory history points per track
TRAJECTORY_MAX_LEN = 300


@dataclass
class TrackPoint:
    """A single position snapshot for a tracked entity."""
    timestamp: float
    x: float       # centroid x
    y: float       # centroid y
    frame_idx: int


@dataclass
class Track:
    """Represents a tracked entity with its full history."""
    track_id: int
    class_name: str
    bbox: List[float]          # [x1, y1, x2, y2] current frame
    confidence: float
    trajectory: deque = field(default_factory=lambda: deque(maxlen=TRAJECTORY_MAX_LEN))
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    is_confirmed: bool = False

    @property
    def centroid(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def dwell_time(self) -> float:
        """Seconds this track has been visible."""
        return self.last_seen - self.first_seen

    @property
    def recent_trajectory(self) -> List[TrackPoint]:
        """Return trajectory as a list."""
        return list(self.trajectory)

    def add_point(self, timestamp: float, frame_idx: int):
        cx, cy = self.centroid
        self.trajectory.append(TrackPoint(timestamp=timestamp, x=cx, y=cy, frame_idx=frame_idx))
        self.last_seen = timestamp


class Tracker:
    """
    DeepSORT tracker wrapper.
    Accepts raw detections per frame and returns Track objects
    with persistent IDs and trajectory history.

    Args:
        max_age          : frames a track can be lost before deletion
        n_init           : frames needed before a track is confirmed
        max_cosine_dist  : appearance embedding similarity threshold
        camera_id        : for logging only
    """

    def __init__(
        self,
        max_age: int = 75,             # increased so temporary occlusions don't lose the track ID
        n_init: int = 2,               # fast confirmation
        max_cosine_dist: float = 0.55, # robust against webcam lighting/angle shifts
        camera_id: str = "cam_01",
    ):
        self.camera_id = camera_id
        self._tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_cosine_distance=max_cosine_dist,
            max_iou_distance=0.7,
            nn_budget=200,
            override_track_class=None,
            embedder="mobilenet",          # lightweight ReID embedder
            half=True,                     # FP16 for GTX 1650 speed
            bgr=True,
            embedder_gpu=True,
        )
        self._tracks: Dict[int, Track] = {}   # track_id -> Track
        logger.info(f"[{camera_id}] DeepSORT tracker initialized (max_age={max_age}, n_init={n_init}, max_cosine={max_cosine_dist}).")

    # ─── Public API ───────────────────────────────────────────────────────────

    def update(
        self, detections: List[Detection], frame: np.ndarray, frame_idx: int, timestamp: float
    ) -> List[Track]:
        """
        Feed new detections → get updated Track list.

        Args:
            detections : list of Detection from detector.py
            frame      : current BGR frame (for ReID embedding)
            frame_idx  : current frame index
            timestamp  : unix timestamp

        Returns:
            List of active Track objects (only confirmed tracks)
        """
        # Format for deep_sort_realtime: ([x1,y1,w,h], confidence, class_name)
        raw = []
        for d in detections:
            x1, y1, x2, y2 = d.bbox
            w, h = x2 - x1, y2 - y1
            raw.append(([x1, y1, w, h], d.confidence, d.class_name))

        if not raw:
            # No detections — age out tracks
            ds_tracks = self._tracker.update_tracks([], frame=frame)
        else:
            ds_tracks = self._tracker.update_tracks(raw, frame=frame)

        active_ids = set()
        active_tracks = []

        for ds_track in ds_tracks:
            if not ds_track.is_confirmed():
                continue

            track_id = int(ds_track.track_id)
            ltrb = ds_track.to_ltrb()              # [x1, y1, x2, y2]
            class_name = ds_track.det_class or "person"
            conf = ds_track.det_conf or 0.5

            active_ids.add(track_id)

            # Create or update internal Track record
            if track_id not in self._tracks:
                self._tracks[track_id] = Track(
                    track_id=track_id,
                    class_name=class_name,
                    bbox=list(ltrb),
                    confidence=conf,
                    first_seen=timestamp,
                )

            t = self._tracks[track_id]
            t.bbox = list(ltrb)
            t.confidence = conf
            t.is_confirmed = True
            t.add_point(timestamp, frame_idx)
            active_tracks.append(t)

        # Clean up tracks gone for too long
        stale = [tid for tid in self._tracks if tid not in active_ids]
        for tid in stale:
            if time.time() - self._tracks[tid].last_seen > 60:
                del self._tracks[tid]

        return active_tracks

    @property
    def all_tracks(self) -> Dict[int, Track]:
        """Return all known tracks (including recently inactive)."""
        return self._tracks

    def get_track(self, track_id: int) -> Optional[Track]:
        return self._tracks.get(track_id)
