"""
test_live_hand_gestures.py
───────────────────────────
Real-time Live Webcam Hand Gesture Testing Tool.
Uses your webcam to detect hand signs & SOS distress gestures live!

Usage:
    python test_live_hand_gestures.py
"""

import sys
import os
import time
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detection.gesture_detector import GestureDetector, gesture_detector


def run_live_gesture_test():
    print("=" * 65)
    print("  SentryEye — Live Hand Gesture & SOS Testing Tool")
    print("  MediaPipe 21 Landmarks + Kinivi Protocol Active")
    print("=" * 65)
    print("  HOW TO TEST THE HELP GESTURE (Signal-for-Help):")
    print("  1. Hold open palm to camera with thumb tucked inside palm.")
    print("  2. Fold fingers down over thumb into a fist within 2 seconds.")
    print("  -> Screen will flash RED banner: [SOS DISTRESS GESTURE CONFIRMED!]")
    print("=" * 65)
    print("  Press 'q' in the camera window to exit.\n")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Cannot open webcam (Index 0). Please check your camera connection.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    fps_counter = 0
    start_time = time.time()
    fps = 0.0
    sos_banner_timer = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab webcam frame.")
            break

        # Flip horizontally for natural mirror view
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        # Process gesture & draw MediaPipe hand landmarks
        is_sos, conf, desc = gesture_detector.process_person_crop(frame, track_id=1)
        frame = gesture_detector.draw_landmarks(frame, (0, 0, w, h))

        if is_sos:
            sos_banner_timer = time.time() + 3.0  # Keep banner visible for 3 seconds

        # Top HUD Bar
        cv2.rectangle(frame, (0, 0), (w, 50), (20, 20, 20), -1)
        hud_text = "SentryEye Live Gesture Test | Show Hand to Camera"
        cv2.putText(frame, hud_text, (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)

        # How-to Help Gesture box at bottom left
        cv2.rectangle(frame, (10, h - 90), (450, h - 10), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, h - 90), (450, h - 10), (0, 255, 255), 1)
        cv2.putText(frame, "HELP GESTURE STEPS:", (20, h - 68), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        cv2.putText(frame, "1. Open palm + tuck thumb inside", (20, h - 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(frame, "2. Fold fingers down over thumb (Fist)", (20, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # SOS Banner trigger
        if time.time() < sos_banner_timer:
            cv2.rectangle(frame, (0, h - 60), (w, h), (0, 0, 220), -1)
            cv2.putText(frame, "SOS DISTRESS GESTURE CONFIRMED! (Signal for Help)", (30, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)

        # Calculate FPS
        fps_counter += 1
        if time.time() - start_time >= 1.0:
            fps = fps_counter / (time.time() - start_time)
            fps_counter = 0
            start_time = time.time()

        cv2.putText(frame, f"FPS: {fps:.1f}", (w - 120, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("SentryEye — Live Hand Gesture & Help Signal Test (Q to quit)", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Live hand gesture testing stopped.")


if __name__ == "__main__":
    run_live_gesture_test()
