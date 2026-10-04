"""
storage/clip_saver.py
──────────────────────
Rolling buffer that saves pre/post-event video clips when an alert fires.
Keeps the last N seconds in memory (deque of frames), then writes on trigger.
"""

import logging
import os
import time
from collections import deque
from datetime import datetime
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ClipSaver:
    """
    Maintains a circular in-memory buffer of recent frames.
    On trigger, saves a clip containing PRE + POST event seconds.

    Args:
        output_dir      : directory to write clips and snapshots
        fps             : effective FPS of the video pipeline
        pre_seconds     : seconds of footage before the trigger to include
        post_seconds    : seconds of footage after the trigger to include
        camera_id       : for file naming
    """

    def __init__(
        self,
        output_dir: str = "./media",
        fps: float = 15.0,
        pre_seconds: int = 10,
        post_seconds: int = 5,
        camera_id: str = "cam_01",
    ):
        self.output_dir = output_dir
        self.fps = fps
        self.pre_seconds = pre_seconds
        self.post_seconds = post_seconds
        self.camera_id = camera_id

        self._clips_dir = os.path.join(output_dir, "clips")
        self._snapshots_dir = os.path.join(output_dir, "snapshots")
        os.makedirs(self._clips_dir, exist_ok=True)
        os.makedirs(self._snapshots_dir, exist_ok=True)

        # Rolling pre-event buffer
        pre_buffer_frames = int(fps * pre_seconds)
        self._pre_buffer: deque[np.ndarray] = deque(maxlen=pre_buffer_frames)

        # Post-event collection
        self._post_buffer: list[np.ndarray] = []
        self._post_frames_needed = int(fps * post_seconds)
        self._collecting_post = False
        self._pending_event_id: Optional[str] = None

        logger.info(
            f"[{camera_id}] ClipSaver ready — "
            f"pre={pre_seconds}s, post={post_seconds}s, buffer={pre_buffer_frames} frames"
        )

    # ─── Public API ───────────────────────────────────────────────────────────

    def push_frame(self, frame: np.ndarray):
        """Call this every processed frame to feed the rolling buffer."""
        self._pre_buffer.append(frame.copy())

        if self._collecting_post:
            self._post_buffer.append(frame.copy())
            if len(self._post_buffer) >= self._post_frames_needed:
                self._collecting_post = False
                self._flush_clip()

    def trigger(self, event_id: str, frame: np.ndarray) -> Tuple[str, str]:
        """
        Called when an alert is confirmed.

        Args:
            event_id : e.g. "evt_abc123"
            frame    : the frame at trigger time (for snapshot)

        Returns:
            (snapshot_path, clip_path) — written to disk.
        """
        # Save snapshot immediately
        snapshot_path = self._save_snapshot(event_id, frame)

        # Start collecting post-event frames
        self._pending_event_id = event_id
        self._post_buffer = []
        self._collecting_post = True

        logger.info(f"[{self.camera_id}] Clip trigger for {event_id} — collecting post-event frames...")

        return snapshot_path, ""

    def get_clip_path(self, event_id: str) -> str:
        """Return the expected clip path for an event (may not exist yet)."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self._clips_dir, f"{event_id}_{self.camera_id}.mp4")

    # ─── Internals ────────────────────────────────────────────────────────────

    def _save_snapshot(self, event_id: str, frame: np.ndarray) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{event_id}_{self.camera_id}_{ts}.jpg"
        path = os.path.join(self._snapshots_dir, filename)
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        logger.info(f"Snapshot saved: {path}")
        return path

    def _flush_clip(self):
        """Write pre + post frames to an MP4 file."""
        if not self._pending_event_id:
            return

        all_frames = list(self._pre_buffer) + self._post_buffer
        if not all_frames:
            return

        clip_path = self.get_clip_path(self._pending_event_id)
        h, w = all_frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(clip_path, fourcc, self.fps, (w, h))

        for f in all_frames:
            writer.write(f)
        writer.release()

        logger.info(
            f"[{self.camera_id}] Clip saved: {clip_path} "
            f"({len(all_frames)} frames, {len(all_frames)/self.fps:.1f}s)"
        )
        self._pending_event_id = None
        self._post_buffer = []
