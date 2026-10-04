"""
ingestion/stream_reader.py
──────────────────────────
Reads from a video file or RTSP stream and yields frames with frame-skip support.
Handles reconnection for live RTSP streams.
"""

import cv2
import time
import logging
from typing import Generator, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class StreamReader:
    """
    Reads frames from a video source (file or RTSP).
    Yields (frame_index, timestamp, frame_numpy) tuples.

    Args:
        source     : path to video file OR rtsp:// URL
        frame_skip : process every Nth frame (1 = every frame, 2 = every other frame)
        width      : resize width (0 = no resize)
        height     : resize height (0 = no resize)
        camera_id  : identifier string for logging
    """

    def __init__(
        self,
        source: str,
        frame_skip: int = 2,
        width: int = 640,
        height: int = 640,
        camera_id: str = "cam_01",
        max_reconnect_attempts: int = 5,
    ):
        self.source = source
        self.frame_skip = max(1, frame_skip)
        self.width = width
        self.height = height
        self.camera_id = camera_id
        self.max_reconnect_attempts = max_reconnect_attempts

        self._cap: cv2.VideoCapture | None = None
        self._frame_index = 0
        self._is_file = not str(source).lower().startswith("rtsp")

    # ─── Public API ───────────────────────────────────────────────────────────

    def open(self) -> bool:
        """Open the video source. Returns True on success."""
        # If source is a digit string like "0", parse to int for webcam capture
        src = self.source
        if isinstance(src, str) and src.strip().isdigit():
            src = int(src.strip())
            self._is_file = False
            self._is_webcam = True
        else:
            self._is_webcam = False

        self._cap = cv2.VideoCapture(src)
        if not self._cap.isOpened():
            logger.error(f"[{self.camera_id}] Cannot open source: {self.source}")
            return False
        fps = self._cap.get(cv2.CAP_PROP_FPS) or 25
        total = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(
            f"[{self.camera_id}] Opened source — FPS: {fps:.1f}, "
            f"Frames: {total if total > 0 else 'live'}, "
            f"Frame-skip: every {self.frame_skip} frames"
        )
        return True

    def release(self):
        """Release the video capture."""
        if self._cap:
            self._cap.release()
            self._cap = None

    def stream(self) -> Generator[Tuple[int, float, np.ndarray], None, None]:
        """
        Generator that yields (frame_index, timestamp, frame).

        For video files: loops continuously (for demo long-run testing).
        For RTSP: attempts reconnection on failure.
        """
        if not self._cap and not self.open():
            return

        reconnect_attempts = 0
        raw_index = 0  # counts every frame from the capture

        while True:
            ret, frame = self._cap.read()

            # ── Handle end of file / stream failure ──────────────────────────
            if not ret:
                if self._is_file:
                    # Loop the file for continuous demo testing
                    logger.info(f"[{self.camera_id}] End of file — looping.")
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    raw_index = 0
                    self._frame_index = 0
                    continue
                else:
                    # RTSP reconnect logic
                    if reconnect_attempts >= self.max_reconnect_attempts:
                        logger.error(f"[{self.camera_id}] Max reconnect attempts reached. Stopping.")
                        break
                    reconnect_attempts += 1
                    logger.warning(
                        f"[{self.camera_id}] Stream lost. Reconnecting ({reconnect_attempts}/{self.max_reconnect_attempts})..."
                    )
                    self.release()
                    time.sleep(2)
                    if not self.open():
                        continue
                    raw_index = 0
                    continue

            reconnect_attempts = 0  # reset on successful read

            # ── Frame-skip: only yield every Nth frame ───────────────────────
            raw_index += 1
            if raw_index % self.frame_skip != 0:
                continue

            # ── Resize if configured ─────────────────────────────────────────
            if self.width > 0 and self.height > 0:
                frame = cv2.resize(frame, (self.width, self.height))

            timestamp = time.time()
            yield self._frame_index, timestamp, frame
            self._frame_index += 1

    @property
    def fps(self) -> float:
        """Return source FPS (0 if not opened)."""
        if self._cap:
            return self._cap.get(cv2.CAP_PROP_FPS) or 25.0
        return 25.0

    @property
    def effective_fps(self) -> float:
        """FPS after frame-skip is applied."""
        return self.fps / self.frame_skip

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.release()
