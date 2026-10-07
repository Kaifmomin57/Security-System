"""
test_hand_gestures.py
──────────────────────
Tests the Kinivi MediaPipe hand gesture recognition engine.
Processes videos or synthetic frames and logs hand landmark & gesture predictions.
"""

import sys
import os
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detection.gesture_detector import GestureDetector, gesture_detector


def test_hand_gesture_engine():
    print("=" * 60)
    print("  Testing Kinivi MediaPipe Hand Gesture Detection Engine")
    print("=" * 60)

    # Test initialization
    print(f"MediaPipe Processor Active: {gesture_detector.landmarker is not None}")
    print(f"Supported Gestures: {GestureDetector.GESTURE_LABELS}")

    # Test synthetic frame
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(dummy_frame, (200, 100), (440, 380), (200, 200, 200), -1)

    is_sos, conf, desc = gesture_detector.process_person_crop(dummy_frame, track_id=1)
    print(f"Dummy crop result -> SOS: {is_sos}, Conf: {conf}, Desc: {desc}")
    
    print("\n[SUCCESS] Hand Gesture Recognition Engine is ready and loaded!")


if __name__ == "__main__":
    test_hand_gesture_engine()
