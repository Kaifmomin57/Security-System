"""
detection/weapon_detector.py
─────────────────────────────
Dedicated weapon detection engine using a specialized YOLO model (best.pt).
Runs as a secondary detector alongside the main object detector.

Detects: gun (0), knife (1)
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import torch
from ultralytics import YOLO

logger = logging.getLogger("sentryeye.weapon_detector")

WEAPON_MODEL_PATH = os.getenv("WEAPON_MODEL", "best.pt")


@dataclass
class WeaponDetection:
    """Single weapon detection result."""
    bbox: List[float]       # [x1, y1, x2, y2]
    class_id: int
    class_name: str         # 'gun' or 'knife'
    confidence: float

    @property
    def centroid(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)


class WeaponDetector:
    """
    Specialized YOLO weapon detector (best.pt — 2-class: gun, knife).
    Runs at lower frequency than main detector to save GPU budget.
    """

    def __init__(
        self,
        model_path: str = WEAPON_MODEL_PATH,
        device: str = "cuda",
        confidence: float = 0.40,
    ):
        self.confidence = confidence
        self.device = self._resolve_device(device)

        logger.info(f"WeaponDetector: Loading {model_path} on {self.device}...")
        try:
            self.model = YOLO(model_path)
            self.model.to(self.device)
            # Warm-up
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self.model(dummy, verbose=False)
            self.class_names = self.model.names  # {0: 'gun', 1: 'knife'}
            logger.info(
                f"WeaponDetector: Ready — classes: {self.class_names}, "
                f"conf: {confidence}, device: {self.device}"
            )
        except Exception as e:
            logger.error(f"WeaponDetector: Failed to load {model_path}: {e}")
            self.model = None
            self.class_names = {}

    def detect(self, frame: np.ndarray) -> List[WeaponDetection]:
        """
        Run weapon inference on a single frame.
        Returns list of WeaponDetection objects (empty if model not loaded).
        """
        if self.model is None or frame is None or frame.size == 0:
            return []

        try:
            results = self.model(
                frame,
                verbose=False,
                conf=self.confidence,
                device=self.device,
            )

            detections = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = self.class_names.get(cls_id, str(cls_id))
                    conf = float(box.conf[0].item())
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append(WeaponDetection(
                        bbox=[x1, y1, x2, y2],
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf,
                    ))
            return detections

        except Exception as e:
            logger.debug(f"WeaponDetector inference error: {e}")
            return []

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "cuda":
            if torch.cuda.is_available():
                return "cuda"
            logger.warning("WeaponDetector: CUDA not available — using CPU.")
            return "cpu"
        return device


# Global singleton — imported by pipeline.py and weapon_rule.py
weapon_detector = WeaponDetector()
