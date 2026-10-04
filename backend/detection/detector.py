"""
detection/detector.py
─────────────────────
YOLOv8 wrapper for person + object detection.
Runs on CUDA (GTX 1650) by default.
"""

import logging
import numpy as np
import torch
from dataclasses import dataclass, field
from typing import List
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# Classes we care about from COCO dataset
COCO_CLASSES_OF_INTEREST = {
    0:  "person",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
    39: "bottle",
    67: "cell phone",
    73: "laptop",
}


@dataclass
class Detection:
    """Single detection result from one frame."""
    bbox: List[float]       # [x1, y1, x2, y2] in pixels
    class_id: int
    class_name: str
    confidence: float

    @property
    def centroid(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def area(self):
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


class Detector:
    """
    YOLOv8 inference wrapper.

    Args:
        model_name : e.g. 'yolov8s.pt' (auto-downloaded on first run)
        device     : 'cuda' for GPU, 'cpu' for fallback
        confidence : minimum detection confidence threshold
        classes    : list of COCO class IDs to detect (None = all)
    """

    def __init__(
        self,
        model_name: str = "yolov8s.pt",
        device: str = "cuda",
        confidence: float = 0.45,
        classes: List[int] = None,
    ):
        self.device = self._resolve_device(device)
        self.confidence = confidence
        self.classes = classes or list(COCO_CLASSES_OF_INTEREST.keys())

        logger.info(f"Loading YOLO model: {model_name} on {self.device}")
        self.model = YOLO(model_name)
        self.model.to(self.device)

        # Warm-up pass (avoids slow first frame)
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        self.model(dummy, verbose=False)
        logger.info(f"Detector ready — device: {self.device}, confidence threshold: {confidence}")

    # ─── Public API ───────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a single frame.

        Args:
            frame: BGR numpy array (H, W, 3)

        Returns:
            List of Detection objects
        """
        results = self.model(
            frame,
            verbose=False,
            conf=self.confidence,
            classes=self.classes,
            device=self.device,
        )

        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0].item())
                cls_name = self.model.names.get(cls_id, str(cls_id))
                conf = float(box.conf[0].item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        bbox=[x1, y1, x2, y2],
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf,
                    )
                )
        return detections

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "cuda":
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                logger.info(f"GPU detected: {name}")
                return "cuda"
            else:
                logger.warning("CUDA not available — falling back to CPU.")
                return "cpu"
        return device

    @staticmethod
    def verify_gpu():
        """Print GPU status. Call once at startup."""
        if torch.cuda.is_available():
            print(f"✅ CUDA available — GPU: {torch.cuda.get_device_name(0)}")
            print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        else:
            print("❌ CUDA not available — running on CPU")
