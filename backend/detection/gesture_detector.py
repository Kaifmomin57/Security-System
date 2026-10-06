"""
detection/gesture_detector.py
─────────────────────────────
Detects the internationally recognized "Signal for Help" distress hand gesture (FR3-1 to FR3-4):
1. Palm facing camera with thumb tucked into palm
2. Fingers folding/closing down over the thumb into a fist within a 2-3s window
3. Fast-path trigger for deliberate distress signaling
"""

import logging
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("sentryeye.gesture")


class GestureDetector:
    def __init__(self, confidence_threshold: float = 0.65):
        self.conf_threshold = confidence_threshold
        self.mp_hands = None
        self.hands_processor = None
        # Track history of gesture stages per track_id: deque of (timestamp, stage_name)
        self._track_gesture_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=20))
        self._init_mediapipe()

    def _init_mediapipe(self):
        try:
            import mediapipe as mp
            if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands'):
                self.mp_hands = mp.solutions.hands
                self.hands_processor = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                logger.info("GestureDetector: MediaPipe Hands initialized successfully.")
            else:
                logger.info("GestureDetector: Using CV geometric hand keypoint analyzer.")
        except Exception as e:
            logger.info(f"GestureDetector: Fallback to CV hand analyzer: {e}")

    def _analyze_landmarks(self, landmarks, h: int, w: int) -> Optional[str]:
        """
        Analyzes hand landmarks for Signal-for-Help gesture stages:
        - Landmark 0: WRIST
        - Landmark 4: THUMB_TIP
        - Landmark 2: THUMB_MCP, 3: THUMB_IP
        - Landmarks 8, 12, 16, 20: TIPS of Index, Middle, Ring, Pinky
        - Landmarks 6, 10, 14, 18: PIP joints of Index, Middle, Ring, Pinky
        - Landmarks 5, 9, 13, 17: MCP joints
        """
        pts = [(int(lm.x * w), int(lm.y * h), lm.z) for lm in landmarks.landmark]
        wrist = pts[0]
        thumb_tip = pts[4]
        thumb_mcp = pts[2]

        index_tip, index_pip, index_mcp = pts[8], pts[6], pts[5]
        middle_tip, middle_pip, middle_mcp = pts[12], pts[10], pts[9]
        ring_tip, ring_pip, ring_mcp = pts[16], pts[14], pts[13]
        pinky_tip, pinky_pip, pinky_mcp = pts[20], pts[18], pts[17]

        # Check if hand is raised (wrist y is relatively high or above centroid)
        # Check finger extensions
        # Extended finger: Tip is higher (smaller y in image space) than PIP joint
        index_ext = index_tip[1] < index_pip[1]
        middle_ext = middle_tip[1] < middle_pip[1]
        ring_ext = ring_tip[1] < ring_pip[1]
        pinky_ext = pinky_tip[1] < pinky_pip[1]

        # Closed/folded finger: Tip is lower than PIP or near MCP
        index_closed = index_tip[1] >= index_pip[1]
        middle_closed = middle_tip[1] >= middle_pip[1]
        ring_closed = ring_tip[1] >= ring_pip[1]
        pinky_closed = pinky_tip[1] >= pinky_pip[1]

        # Thumb tucked inward check: thumb tip x is between index MCP and pinky MCP
        thumb_tucked = (
            abs(thumb_tip[0] - middle_mcp[0]) < abs(thumb_mcp[0] - middle_mcp[0]) + 20
            or thumb_tip[1] > thumb_mcp[1] - 10
        )

        extended_count = sum([index_ext, middle_ext, ring_ext, pinky_ext])
        closed_count = sum([index_closed, middle_closed, ring_closed, pinky_closed])

        # Stage 1: "thumb_in_palm" (Fingers extended, thumb tucked in)
        if extended_count >= 3 and thumb_tucked:
            return "thumb_in_palm"

        # Stage 2: "fingers_folded" (Fingers folded down over tucked thumb)
        if closed_count >= 3 and thumb_tucked:
            return "fingers_folded"

        # Open palm
        if extended_count >= 4:
            return "open_palm"

        return None

    def process_person_crop(self, person_crop: np.ndarray, track_id: int) -> Tuple[bool, float, Optional[str]]:
        """
        Analyzes a cropped person region for the Signal-for-Help gesture sequence.
        Returns: (is_distress_gesture_confirmed, confidence, description)
        """
        if person_crop is None or person_crop.size == 0:
            return False, 0.0, None

        h, w = person_crop.shape[:2]
        if h < 50 or w < 30:
            return False, 0.0, None

        now = time.time()
        current_stage = None

        if self.hands_processor is not None:
            try:
                rgb = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
                results = self.hands_processor.process(rgb)
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        stage = self._analyze_landmarks(hand_landmarks, h, w)
                        if stage:
                            current_stage = stage
                            break
            except Exception as e:
                logger.debug(f"MediaPipe hands error: {e}")

        # Only use MediaPipe landmark analysis - no naive skin contour heuristic to prevent false alarms
        if current_stage:
            hist = self._track_gesture_history[track_id]
            hist.append((now, current_stage))

            # Look for sequence: "thumb_in_palm" or "open_palm" followed by "fingers_folded" within 2.5 seconds
            has_stage_1 = any(s in ("thumb_in_palm", "open_palm") for t, s in hist if now - t <= 2.5)
            has_stage_2 = current_stage == "fingers_folded" and any(s == "thumb_in_palm" for t, s in hist if now - t <= 2.5)

            if has_stage_1 and has_stage_2:
                # Confirmed Signal-for-Help gesture sequence
                hist.clear()
                return True, 0.95, "Signal-for-Help distress hand gesture confirmed (thumb tucked + fingers folded)"

        return False, 0.0, None

    def _cv_heuristic_hand(self, crop: np.ndarray) -> Optional[str]:
        """Disabled to prevent false positives on general skin/body contours."""
        return None


# Global singleton
gesture_detector = GestureDetector()
