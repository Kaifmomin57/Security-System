"""
create_test_video.py
───────────────────
Generates a sample CCTV test video with simulated motion and people
to test SentryEye end-to-end without requiring an external camera.
"""

import os
import cv2
import numpy as np

def generate_sample_video(output_path="./media/test_cctv.mp4", duration_secs=15, fps=25):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = duration_secs * fps
    
    for i in range(total_frames):
        # Create CCTV background (dark corridor / courtyard)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (35, 35, 40)
        
        # Grid lines / floor pattern
        for y in range(200, height, 40):
            cv2.line(frame, (0, y), (width, y), (50, 50, 55), 1)
        
        # Zone boundary (Restricted area indicator in yellow/red)
        cv2.rectangle(frame, (100, 100), (350, 400), (0, 140, 200), 2)
        cv2.putText(frame, "ZONE: Main Entrance", (110, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 140, 200), 1)

        # Simulated moving person (head, torso, legs)
        # Person enters from left, walks through zone, and loiters
        progress = i / total_frames
        if progress < 0.6:
            px = int(50 + progress * 350)
            py = int(240)
        else:
            # Loitering around the entrance zone
            px = int(260 + 10 * np.sin(i * 0.1))
            py = int(240 + 5 * np.cos(i * 0.1))

        # Draw a humanoid silhouette
        # Head
        cv2.circle(frame, (px, py - 60), 18, (180, 180, 180), -1)
        # Torso
        cv2.rectangle(frame, (px - 20, py - 42), (px + 20, py + 20), (140, 140, 140), -1)
        # Legs
        leg_offset = int(8 * np.sin(i * 0.4)) if progress < 0.6 else 0
        cv2.line(frame, (px - 10, py + 20), (px - 15 + leg_offset, py + 80), (100, 100, 100), 8)
        cv2.line(frame, (px + 10, py + 20), (px + 15 - leg_offset, py + 80), (100, 100, 100), 8)
        # Arms
        cv2.line(frame, (px - 20, py - 35), (px - 30, py), (120, 120, 120), 6)
        cv2.line(frame, (px + 20, py - 35), (px + 30, py), (120, 120, 120), 6)

        # Timestamp overlay
        ts_text = f"CAM-01 REC [{(i/fps):.2f}s]"
        cv2.putText(frame, ts_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        out.write(frame)

    out.release()
    print(f"Generated sample CCTV test video: {output_path} ({total_frames} frames)")

if __name__ == "__main__":
    generate_sample_video()
