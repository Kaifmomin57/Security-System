"""
detection/gesture_detector.py
─────────────────────────────
Hand Gesture Recognition Engine based on kinivi/hand-gesture-recognition-mediapipe.

Features:
1. MediaPipe Tasks HandLandmarker / GestureRecognizer integration
2. Kinivi landmark normalization (relative wrist offset + max-value scaling)
3. Multi-gesture classification:
   - "SOS_Distress" (Signal for help: thumb tucked + fingers folding)
   - "Open_Palm" (Stop / Hold)
   - "Fist" (Closed hand)
   - "Pointer" (Index finger pointing)
   - "Peace_Victory" (V sign)
   - "OK_Sign" (Thumb + Index circle)
   - "Thumbs_Up" (Like / Confirm)
   - "Thumbs_Down" (Dislike / Reject)
   - "Rock_On" (Rock / Horns sign)
4. Sequence tracking & alert triggers for safety-critical gestures (SOS / Distress)
"""

import copy
import itertools
import logging
import os
import sys
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("sentryeye.gesture")


class GestureDetector:
    GESTURE_LABELS = [
        "Open_Palm",
        "Fist",
        "Pointer",
        "OK_Sign",
        "Peace_Victory",
        "Thumbs_Up",
        "Thumbs_Down",
        "Rock_On",
        "SOS_Distress",
    ]

    def __init__(self, confidence_threshold: float = 0.65):
        self.conf_threshold = confidence_threshold
        self.landmarker = None
        self._track_gesture_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=20))
        self._init_mediapipe_tasks()

    def _init_mediapipe_tasks(self):
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base_dir, "hand_landmarker.task")
            if not os.path.exists(model_path):
                model_path = os.path.join(base_dir, "backend", "hand_landmarker.task")

            if os.path.exists(model_path):
                base_options = python.BaseOptions(model_asset_path=model_path)
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    num_hands=2,
                    min_hand_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self.landmarker = vision.HandLandmarker.create_from_options(options)
                logger.info("GestureDetector: MediaPipe Tasks HandLandmarker initialized successfully.")
            else:
                logger.warning(f"GestureDetector: Hand landmark task file not found at {model_path}")
        except Exception as e:
            logger.error(f"GestureDetector: MediaPipe Tasks initialization error: {e}")

    @staticmethod
    def calc_landmark_list(image_shape: Tuple[int, int], landmarks) -> List[List[int]]:
        """Converts normalized landmarks to pixel coordinates (kinivi protocol)."""
        h, w = image_shape[:2]
        landmark_point = []
        for landmark in landmarks:
            lx = min(int(landmark.x * w), w - 1)
            ly = min(int(landmark.y * h), h - 1)
            landmark_point.append([lx, ly])
        return landmark_point

    @staticmethod
    def pre_process_landmark(landmark_list: List[List[int]]) -> List[float]:
        """
        Kinivi Landmark Pre-processing:
        1. Shift origin to wrist (landmark 0)
        2. Flatten coordinates [x0, y0, x1, y1, ...]
        3. Scale by maximum absolute value to normalize to [-1.0, 1.0]
        """
        temp_landmark_list = copy.deepcopy(landmark_list)
        base_x, base_y = temp_landmark_list[0][0], temp_landmark_list[0][1]

        # 1. Convert to relative coordinates from wrist
        for index in range(len(temp_landmark_list)):
            temp_landmark_list[index][0] -= base_x
            temp_landmark_list[index][1] -= base_y

        # 2. Flatten array
        flat_list = list(itertools.chain.from_iterable(temp_landmark_list))

        # 3. Max value normalization
        max_value = max(map(abs, flat_list)) if flat_list else 1.0
        if max_value != 0:
            flat_list = [val / max_value for val in flat_list]

        return flat_list

    def classify_gesture(self, landmark_pts: List[List[int]]) -> Tuple[str, float]:
        """
        Classifies hand keypoints into gestures using geometric landmark analysis
        conforming to kinivi dataset feature representation.
        Landmarks:
          0: Wrist
          1-4: Thumb (4: Tip)
          5-8: Index (8: Tip, 6: PIP, 5: MCP)
          9-12: Middle (12: Tip, 10: PIP, 9: MCP)
          13-16: Ring (16: Tip, 14: PIP, 13: MCP)
          17-20: Pinky (20: Tip, 18: PIP, 17: MCP)
        """
        if len(landmark_pts) < 21:
            return "Unknown", 0.0

        pts = np.array(landmark_pts)

        wrist = pts[0]
        thumb_tip, thumb_mcp = pts[4], pts[2]
        index_tip, index_pip, index_mcp = pts[8], pts[6], pts[5]
        middle_tip, middle_pip, middle_mcp = pts[12], pts[10], pts[9]
        ring_tip, ring_pip, ring_mcp = pts[16], pts[14], pts[13]
        pinky_tip, pinky_pip, pinky_mcp = pts[20], pts[18], pts[17]

        # Finger extension check (Tip distance from wrist vs PIP distance from wrist)
        def is_extended(tip, pip, wrist):
            return np.linalg.norm(tip - wrist) > np.linalg.norm(pip - wrist) * 1.05

        index_ext = is_extended(index_tip, index_pip, wrist)
        middle_ext = is_extended(middle_tip, middle_pip, wrist)
        ring_ext = is_extended(ring_tip, ring_pip, wrist)
        pinky_ext = is_extended(pinky_tip, pinky_pip, wrist)
        thumb_ext = is_extended(thumb_tip, thumb_mcp, wrist)

        ext_count = sum([index_ext, middle_ext, ring_ext, pinky_ext])

        # Distance checks
        thumb_index_dist = np.linalg.norm(thumb_tip - index_tip)
        palm_size = np.linalg.norm(index_mcp - wrist)
        if palm_size == 0:
            palm_size = 1.0

        # 1. OK Sign: Thumb tip and Index tip touching, other 3 fingers extended
        if (thumb_index_dist < palm_size * 0.45) and middle_ext and ring_ext and pinky_ext:
            return "OK_Sign", 0.92

        # 2. Pointer: Only index finger extended
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "Pointer", 0.90

        # 3. Peace / Victory: Index and Middle extended, Ring and Pinky closed
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return "Peace_Victory", 0.93

        # 4. Rock On: Index and Pinky extended, Middle and Ring closed
        if index_ext and pinky_ext and not middle_ext and not ring_ext:
            return "Rock_On", 0.91

        # 5. Thumbs Up / Down: Thumb extended out, other 4 fingers closed
        if thumb_ext and ext_count == 0:
            if thumb_tip[1] < wrist[1]:
                return "Thumbs_Up", 0.94
            else:
                return "Thumbs_Down", 0.94

        # 6. Open Palm: All 4 fingers extended
        if ext_count >= 4:
            thumb_tucked = np.linalg.norm(thumb_tip - middle_mcp) < palm_size * 1.1
            if thumb_tucked:
                return "SOS_Stage1_ThumbTucked", 0.88
            return "Open_Palm", 0.95

        # 7. Fist / Closed: All 4 fingers closed
        if ext_count == 0 and not thumb_ext:
            thumb_tucked = np.linalg.norm(thumb_tip - middle_mcp) < palm_size * 1.1
            if thumb_tucked:
                return "SOS_Stage2_FistFolded", 0.89
            return "Fist", 0.90

        return "Unknown", 0.50

    def process_person_crop(self, person_crop: np.ndarray, track_id: int) -> Tuple[bool, float, Optional[str]]:
        """
        Processes person image crop for hand gestures.
        Returns: (is_sos_alert, confidence, gesture_description)
        """
        if person_crop is None or person_crop.size == 0 or self.landmarker is None:
            return False, 0.0, None

        h, w = person_crop.shape[:2]
        if h < 40 or w < 30:
            return False, 0.0, None

        try:
            import mediapipe as mp
            rgb = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = self.landmarker.detect(mp_image)
        except Exception as e:
            logger.debug(f"MediaPipe detection error: {e}")
            return False, 0.0, None

        if not results or not results.hand_landmarks:
            return False, 0.0, None

        now = time.time()
        detected_gestures = []

        for hand_landmarks in results.hand_landmarks:
            landmark_pts = self.calc_landmark_list((h, w), hand_landmarks)
            gesture_name, conf = self.classify_gesture(landmark_pts)

            if gesture_name != "Unknown":
                detected_gestures.append((gesture_name, conf, landmark_pts))

        if not detected_gestures:
            return False, 0.0, None

        top_gesture, top_conf, pts = detected_gestures[0]
        hist = self._track_gesture_history[track_id]
        hist.append((now, top_gesture))

        # Check for kinivi SOS distress signal sequence: Stage 1 (thumb tucked) -> Stage 2 (fist folded) within 2.5s
        has_s1 = any(g in ("SOS_Stage1_ThumbTucked", "Open_Palm") for t, g in hist if now - t <= 2.5)
        has_s2 = top_gesture in ("SOS_Stage2_FistFolded", "Fist") and any(g == "SOS_Stage1_ThumbTucked" for t, g in hist if now - t <= 2.5)

        if has_s1 and has_s2:
            hist.clear()
            return True, 0.96, f"SOS Distress Gesture Confirmed (kinivi protocol) — [{top_gesture}]"

        if top_gesture in ("SOS_Stage1_ThumbTucked", "SOS_Stage2_FistFolded"):
            desc = "Signal-for-Help SOS stage detected"
        else:
            desc = f"Hand Gesture: {top_gesture}"

        return False, top_conf, desc

    def draw_landmarks(self, image: np.ndarray, person_crop_bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """Utility to annotate detected hands and gesture labels on full image."""
        if self.landmarker is None:
            return image

        x1, y1, x2, y2 = person_crop_bbox
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return image

        try:
            import mediapipe as mp
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = self.landmarker.detect(mp_image)

            if results and results.hand_landmarks:
                for hand_landmarks in results.hand_landmarks:
                    pts = self.calc_landmark_list(crop.shape, hand_landmarks)
                    gesture_name, conf = self.classify_gesture(pts)

                    for pt in pts:
                        cv2.circle(image, (x1 + pt[0], y1 + pt[1]), 3, (0, 255, 0), -1)

                    label = f"{gesture_name} ({int(conf*100)}%)"
                    cv2.putText(image, label, (x1 + pts[0][0], y1 + pts[0][1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        except Exception as e:
            logger.debug(f"Landmark draw error: {e}")

        return image


# Global instance
gesture_detector = GestureDetector()
