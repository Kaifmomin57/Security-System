"""
privacy/face_blur.py
─────────────────────
Lightweight face detection + blur for stored clips (Differentiator F19).
Uses OpenCV Haar Cascade — CPU-only, no extra VRAM required.

Faces are blurred in all STORED clips/snapshots by default.
"""

import cv2
import logging
import numpy as np
import os

logger = logging.getLogger(__name__)

# Search order for Haar Cascade XML
_LOCAL_CASCADE = os.path.join(os.path.dirname(__file__), "haarcascade_frontalface_default.xml")
_CV2_DATA_DIR = getattr(cv2, "data", None)
_CV2_CASCADE = (
    os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    if _CV2_DATA_DIR and hasattr(cv2.data, "haarcascades")
    else ""
)

if os.path.exists(_LOCAL_CASCADE):
    CASCADE_PATH = _LOCAL_CASCADE
elif _CV2_CASCADE and os.path.exists(_CV2_CASCADE):
    CASCADE_PATH = _CV2_CASCADE
else:
    CASCADE_PATH = _LOCAL_CASCADE


class FaceBlur:
    """
    Detects and blurs faces in frames using Haar Cascade.
    Applied to saved media (clips/snapshots), not to live display.
    """

    def __init__(self, scale_factor: float = 1.1, min_neighbors: int = 5):
        self.detector = cv2.CascadeClassifier(CASCADE_PATH)
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        if self.detector.empty():
            logger.error(f"Failed to load Haar cascade for face detection from {CASCADE_PATH}!")
        else:
            logger.info(f"FaceBlur initialized successfully from {CASCADE_PATH}")

    def blur_frame(self, frame: np.ndarray) -> np.ndarray:
        """Detect and blur all faces in a single frame. Returns modified frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=(30, 30),
        )
        for (x, y, w, h) in faces:
            roi = frame[y:y + h, x:x + w]
            # Heavy blur — kernel size relative to face size
            ksize = max(15, w // 4) | 1   # ensure odd kernel
            frame[y:y + h, x:x + w] = cv2.GaussianBlur(roi, (ksize, ksize), 30)
        return frame

    def blur_image_file(self, path: str) -> bool:
        """Apply face blur to a saved image file (in-place)."""
        frame = cv2.imread(path)
        if frame is None:
            logger.warning(f"Could not read image: {path}")
            return False
        blurred = self.blur_frame(frame)
        cv2.imwrite(path, blurred)
        return True

    def blur_video_file(self, input_path: str, output_path: str = None) -> str:
        """
        Apply face blur to every frame of a video clip.
        Writes to output_path (or overwrites input if not specified).
        Returns the output path.
        """
        if output_path is None:
            output_path = input_path  # overwrite

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            logger.warning(f"Cannot open video: {input_path}")
            return input_path

        fps    = cap.get(cv2.CAP_PROP_FPS) or 15.0
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        tmp_path = output_path + ".tmp.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(self.blur_frame(frame))

        cap.release()
        writer.release()

        os.replace(tmp_path, output_path)
        logger.info(f"Face blur applied to clip: {output_path}")
        return output_path
