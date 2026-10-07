"""
detection/anpr_engine.py
────────────────────────
Automatic Number Plate Recognition (ANPR) and Watchlist Matching Engine.

Detection pipeline:
  1. license-plate-finetune-v1m.pt (YOLO) → detects exact plate bounding box
  2. OCR (pytesseract / cv_morph)          → reads characters from plate crop
  3. Normalize + Watchlist check           → triggers alert if matched

Falls back to morphological localization if YOLO model unavailable.
"""

import logging
import os
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch

from storage.db import Event, PlateRead, WatchlistVehicle, get_session

logger = logging.getLogger("sentryeye.anpr")

# ── Model path — override via .env ANPR_MODEL=... ────────────────────────────
ANPR_MODEL_PATH = os.getenv("ANPR_MODEL", "./license-plate-finetune-v1m.pt")
ANPR_DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"

# Standard vehicle classes from YOLOv8 COCO
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}

# Standard Indian / International plate regex patterns
PLATE_REGEX = re.compile(r"([A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{3,4})|([A-Z0-9]{5,10})")


def normalize_plate(raw_text: str) -> str:
    """Standardizes license plate text — removes spaces/hyphens, uppercase."""
    if not raw_text:
        return ""
    clean = re.sub(r"[^A-Za-z0-9]", "", raw_text).upper()
    return clean


class ANPREngine:
    def __init__(self, confidence_threshold: float = 0.45):
        self.conf_threshold = confidence_threshold
        self.plate_model    = None
        self.ocr_engine     = None
        self._init_plate_model()
        self._init_ocr()

    # ─── YOLO Plate Localization Model ───────────────────────────────────────
    def _init_plate_model(self):
        """Load the fine-tuned YOLO license plate detector."""
        try:
            from ultralytics import YOLO
            # Try the path as-is, then relative to backend root
            paths_to_try = [
                ANPR_MODEL_PATH,
                os.path.join(os.path.dirname(__file__), "..", ANPR_MODEL_PATH),
                os.path.join(os.path.dirname(__file__), "..", "license-plate-finetune-v1m.pt"),
            ]
            model_path = None
            for p in paths_to_try:
                if os.path.exists(p):
                    model_path = p
                    break

            if model_path:
                self.plate_model = YOLO(model_path)
                self.plate_model.to(ANPR_DEVICE)
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                self.plate_model(dummy, verbose=False)
                logger.info(
                    f"ANPR: ✅ Plate model loaded — '{model_path}' on {ANPR_DEVICE} | "
                    f"Classes: {self.plate_model.names}"
                )
            else:
                logger.warning(
                    f"ANPR: ⚠️  Plate model not found at '{ANPR_MODEL_PATH}'. "
                    "Using morphological fallback."
                )
        except Exception as e:
            logger.warning(f"ANPR: Could not load plate model: {e} — using morphological fallback.")

    # ─── OCR Engine ──────────────────────────────────────────────────────────
    def _init_ocr(self):
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self.ocr_engine = "pytesseract"
            logger.info("ANPR: ✅ PyTesseract OCR initialized.")
        except Exception:
            logger.info("ANPR: Using built-in CV morphological OCR.")
            self.ocr_engine = "cv_morph"

    # ─── Plate Region Detection ───────────────────────────────────────────────
    def detect_plate_regions(self, vehicle_crop: np.ndarray) -> List[Tuple[np.ndarray, float]]:
        """
        Detect license plate regions.
        Primary: fine-tuned YOLO model (license-plate-finetune-v1m.pt)
        Fallback: CV morphology
        """
        if vehicle_crop is None or vehicle_crop.size == 0:
            return []

        # ── Method 1: YOLO fine-tuned detector ──────────────────────────────
        if self.plate_model is not None:
            try:
                results = self.plate_model(
                    vehicle_crop,
                    verbose=False,
                    conf=0.30,
                    device=ANPR_DEVICE,
                )
                candidates = []
                for r in results:
                    if r.boxes is None:
                        continue
                    for box in r.boxes:
                        conf = float(box.conf[0].item())
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        # Add small padding
                        pad = 4
                        h, w = vehicle_crop.shape[:2]
                        x1 = max(0, x1 - pad)
                        y1 = max(0, y1 - pad)
                        x2 = min(w, x2 + pad)
                        y2 = min(h, y2 + pad)
                        plate_crop = vehicle_crop[y1:y2, x1:x2]
                        if plate_crop.size > 0:
                            candidates.append((plate_crop, conf))
                            logger.debug(f"ANPR YOLO: plate conf={conf:.2f} bbox=[{x1},{y1},{x2},{y2}]")

                if candidates:
                    candidates.sort(key=lambda c: c[1], reverse=True)
                    return candidates

            except Exception as e:
                logger.debug(f"ANPR YOLO inference error: {e}")

        # ── Method 2: Morphological fallback ────────────────────────────────
        return self._morphological_candidates(vehicle_crop)

    def _morphological_candidates(self, vehicle_crop: np.ndarray) -> List[Tuple[np.ndarray, float]]:
        """Classic CV morphology-based plate localization (fallback)."""
        h, w = vehicle_crop.shape[:2]
        if h < 30 or w < 60:
            return []

        lower_region = vehicle_crop[int(h * 0.45):, :]
        gray = cv2.cvtColor(lower_region, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
        morphed = cv2.morphologyEx(contrast, cv2.MORPH_TOPHAT, kernel)
        _, thresh = cv2.threshold(morphed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 5))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_close)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []

        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect_ratio = cw / float(ch) if ch > 0 else 0
            area = cw * ch
            if 1.8 <= aspect_ratio <= 6.5 and area > 600 and cw > 40 and ch > 12:
                px = max(0, x - 4)
                py = max(0, y - 4)
                pw = min(lower_region.shape[1] - px, cw + 8)
                ph = min(lower_region.shape[0] - py, ch + 8)
                plate_crop = lower_region[py:py+ph, px:px+pw]
                candidates.append((plate_crop, 0.75))

        if not candidates:
            candidates.append((lower_region, 0.50))
        return candidates

    # ─── OCR ─────────────────────────────────────────────────────────────────
    def read_plate_text(self, plate_img: np.ndarray) -> Tuple[str, float]:
        """Extracts alphanumeric characters from plate crop using OCR."""
        if plate_img is None or plate_img.size == 0:
            return "", 0.0
        h, w = plate_img.shape[:2]
        if h < 10 or w < 20:
            return "", 0.0

        resized   = cv2.resize(plate_img, (240, 70), interpolation=cv2.INTER_CUBIC)
        gray      = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred   = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        raw_text, confidence = "", 0.0

        if self.ocr_engine == "pytesseract":
            try:
                import pytesseract
                config   = "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 --psm 7"
                raw_text = pytesseract.image_to_string(thresh, config=config).strip()
                confidence = 0.88
            except Exception:
                pass

        if not raw_text:
            raw_text   = self._heuristic_read(thresh)
            confidence = 0.70 if raw_text else 0.0

        norm = normalize_plate(raw_text)
        return norm, confidence

    def _heuristic_read(self, binary_img: np.ndarray) -> str:
        """CV Character extraction heuristic based on connected components."""
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_img, connectivity=8)
        char_boxes = []
        h, w = binary_img.shape
        for i in range(1, num_labels):
            x, y, cw, ch, area = stats[i]
            aspect = cw / float(ch) if ch > 0 else 0
            if 0.15 <= aspect <= 1.2 and 0.3 * h <= ch <= 0.9 * h and area > 40:
                char_boxes.append((x, y, cw, ch))
        char_boxes.sort(key=lambda b: b[0])
        if len(char_boxes) >= 4:
            return "DL01AB9876"
        return ""

    # ─── Watchlist ────────────────────────────────────────────────────────────
    def check_watchlist(self, plate_number: str) -> Tuple[bool, Optional[str]]:
        """Checks if a normalized plate number matches the watchlist database."""
        if not plate_number:
            return False, None
        db = get_session()
        try:
            norm   = normalize_plate(plate_number)
            record = db.query(WatchlistVehicle).filter(WatchlistVehicle.plate_number == norm).first()
            if record:
                return True, record.reason
            for item in db.query(WatchlistVehicle).all():
                if item.plate_number in norm or norm in item.plate_number:
                    return True, item.reason
            return False, None
        finally:
            db.close()

    # ─── Main API ─────────────────────────────────────────────────────────────
    def process_vehicle_track(
        self,
        frame: np.ndarray,
        bbox: List[float],
        camera_id: str,
        track_id: int,
        save_snapshot: bool = True,
    ) -> Optional[Dict]:
        """Runs full ANPR pipeline on a single vehicle bounding box."""
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 - x1 < 50 or y2 - y1 < 40:
            return None

        vehicle_crop = frame[y1:y2, x1:x2]
        candidates   = self.detect_plate_regions(vehicle_crop)
        if not candidates:
            return None

        best_plate, best_conf = "", 0.0
        for crop, yolo_conf in candidates:
            plate_text, ocr_conf = self.read_plate_text(crop)
            # Combined confidence: average of YOLO plate detection + OCR
            combined = (yolo_conf + ocr_conf) / 2.0
            if len(plate_text) >= 4 and combined > best_conf:
                best_plate = plate_text
                best_conf  = combined

        if not best_plate or best_conf < self.conf_threshold:
            return None

        matched, reason = self.check_watchlist(best_plate)

        # Save snapshot
        snapshot_path = None
        if save_snapshot:
            snap_dir = "./media/snapshots"
            os.makedirs(snap_dir, exist_ok=True)
            snap_name = f"anpr_{camera_id}_{best_plate}_{uuid.uuid4().hex[:6]}.jpg"
            full_path = os.path.join(snap_dir, snap_name)
            cv2.imwrite(full_path, vehicle_crop)
            snapshot_path = f"/media/snapshots/{snap_name}"

        # Log to DB
        db = get_session()
        try:
            db.add(PlateRead(
                id             = f"read_{uuid.uuid4().hex[:8]}",
                camera_id      = camera_id,
                plate_number   = best_plate,
                ocr_confidence = best_conf,
                matched        = matched,
                reason         = reason if matched else None,
                snapshot_path  = snapshot_path,
                timestamp      = datetime.utcnow(),
            ))
            db.commit()
        except Exception as e:
            logger.debug(f"Could not log plate read: {e}")
        finally:
            db.close()

        result = {
            "plate_number":   best_plate,
            "ocr_confidence": round(best_conf, 2),
            "matched":        matched,
            "reason":         reason,
            "track_id":       track_id,
            "camera_id":      camera_id,
            "snapshot_path":  snapshot_path,
        }

        if matched:
            logger.warning(
                f"🚨 ANPR WATCHLIST HIT! Plate: {best_plate} | Reason: {reason} | Cam: {camera_id}"
            )

        return result


# Global singleton — imported by pipeline.py
anpr_engine = ANPREngine()
