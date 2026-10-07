"""
handgun_only_detector.py
────────────────────────
Sirf handgun/gun detect karta hai sab videos mein.
Baaki kuch nahi — no persons, no cars, no loitering.
Output: Annotated videos + JSON report with gun detections only.
"""

import os
import sys
import json
import time
import torch
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ultralytics import YOLO

# ─── Config ────────────────────────────────────────────────────────────
VIDEOS = [
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.32 AM.mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.45 AM (1).mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.45 AM.mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.53 AM.mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.32.05 AM.mp4",
]

OUTPUT_DIR = r"d:\security\sentryeye\backend\media\gun_detection"
os.makedirs(OUTPUT_DIR, exist_ok=True)

WEAPON_MODEL_PATH = r"d:\security\sentryeye\backend\best.pt"
GUN_CONF_THRESHOLD = 0.45   # Raised to reduce false positives

# Max allowed bbox dimensions (pixels) — reject full-frame false positives
MAX_BBOX_WIDTH  = 400   # guns realistically < 400px wide in 1280px frame
MAX_BBOX_HEIGHT = 500   # guns realistically < 500px tall
TARGET_CLASSES = {"gun", "pistol", "handgun", "revolver", "firearm"}  # match any of these

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {DEVICE}")


def load_model():
    print(f"Loading weapon model: {WEAPON_MODEL_PATH}")
    model = YOLO(WEAPON_MODEL_PATH)
    model.to(DEVICE)
    # Warmup
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    model(dummy, verbose=False)
    print(f"Model classes: {model.names}")
    return model


def is_gun_class(class_name: str) -> bool:
    """Returns True if this class is a handgun / firearm."""
    name = class_name.lower().strip()
    # Match exact gun class or any variant
    if name in TARGET_CLASSES:
        return True
    # Also match if model calls it just 'gun'
    if name == "gun":
        return True
    return False


def draw_gun_box(frame, x1, y1, x2, y2, conf, label="GUN"):
    """Draw a vivid red bounding box with alert label for gun detection."""
    # Red filled header bar
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)

    # Label background
    text = f"🔴 {label}  {int(conf * 100)}%"
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.75
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)

    label_y1 = max(0, y1 - th - 12)
    label_y2 = y1
    cv2.rectangle(frame, (x1, label_y1), (x1 + tw + 10, label_y2), (0, 0, 200), -1)
    cv2.putText(frame, text, (x1 + 5, label_y2 - 4), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    # Corner markers (military-style)
    corner_len = 18
    corner_color = (0, 50, 255)
    corner_t = 4
    # TL
    cv2.line(frame, (x1, y1), (x1 + corner_len, y1), corner_color, corner_t)
    cv2.line(frame, (x1, y1), (x1, y1 + corner_len), corner_color, corner_t)
    # TR
    cv2.line(frame, (x2, y1), (x2 - corner_len, y1), corner_color, corner_t)
    cv2.line(frame, (x2, y1), (x2, y1 + corner_len), corner_color, corner_t)
    # BL
    cv2.line(frame, (x1, y2), (x1 + corner_len, y2), corner_color, corner_t)
    cv2.line(frame, (x1, y2), (x1, y2 - corner_len), corner_color, corner_t)
    # BR
    cv2.line(frame, (x2, y2), (x2 - corner_len, y2), corner_color, corner_t)
    cv2.line(frame, (x2, y2), (x2, y2 - corner_len), corner_color, corner_t)

    return frame


def draw_hud(frame, video_name, frame_idx, total_frames, timestamp, gun_count_this_frame, total_guns_found):
    """Draw top HUD bar with info."""
    h, w = frame.shape[:2]
    # Dark semi-transparent HUD bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 42), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

    # Left: system name
    cv2.putText(frame, "SentryEye  |  GUN DETECTION MODE",
                (10, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 210, 255), 1, cv2.LINE_AA)

    # Center: frame / time
    info = f"Frame {frame_idx}/{total_frames}  |  {timestamp:.2f}s"
    cv2.putText(frame, info,
                (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1, cv2.LINE_AA)

    # Right: alert count
    alert_color = (0, 60, 255) if gun_count_this_frame > 0 else (60, 180, 60)
    alert_text = f"GUN DETECTED x{gun_count_this_frame}" if gun_count_this_frame > 0 else "No Gun"
    tw, _ = cv2.getTextSize(alert_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[:2]
    cv2.putText(frame, alert_text,
                (w - tw[0] - 15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, alert_color, 2, cv2.LINE_AA)

    # Bottom total counter
    cv2.putText(frame, f"Total detections this video: {total_guns_found}",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 200, 255), 1, cv2.LINE_AA)
    return frame


def process_video(model, video_path):
    vname = os.path.basename(video_path)
    print(f"\n{'='*60}")
    print(f"VIDEO: {vname}")
    print(f"{'='*60}")

    if not os.path.exists(video_path):
        print(f"  ❌ File not found: {video_path}")
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ❌ Cannot open: {video_path}")
        return None

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  {width}x{height} | {fps:.1f}fps | {total} frames | {total/fps:.1f}s")

    out_name = f"GUN_{os.path.splitext(vname)[0]}.mp4"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    fourcc   = cv2.VideoWriter_fourcc(*"mp4v")
    writer   = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    frame_idx   = 0
    total_guns  = 0
    report_dets = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        timestamp = frame_idx / fps

        # Run weapon model on this frame
        results = model(frame, verbose=False, conf=GUN_CONF_THRESHOLD, device=DEVICE)

        guns_this_frame = 0

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id   = int(box.cls[0].item())
                cls_name = model.names.get(cls_id, str(cls_id))
                conf     = float(box.conf[0].item())

                # ── ONLY process gun class ──────────────────────────
                if not is_gun_class(cls_name):
                    continue

                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

                # ── Bbox size filter — reject unrealistically large boxes ──
                box_w = x2 - x1
                box_h = y2 - y1
                if box_w > MAX_BBOX_WIDTH or box_h > MAX_BBOX_HEIGHT:
                    print(f"  ⚠️  Skipped oversized bbox [{x1},{y1},{x2},{y2}] ({box_w}x{box_h}px) — likely false positive")
                    continue

                guns_this_frame += 1
                total_guns      += 1

                draw_gun_box(frame, x1, y1, x2, y2, conf, label=cls_name.upper())

                report_dets.append({
                    "frame":      frame_idx,
                    "timestamp":  round(timestamp, 3),
                    "class":      cls_name,
                    "confidence": round(conf, 3),
                    "bbox":       [x1, y1, x2, y2],
                })

                print(f"  🔴 [{timestamp:.2f}s] {cls_name.upper()} conf={int(conf*100)}%  bbox=[{x1},{y1},{x2},{y2}]")

        # Draw HUD
        frame = draw_hud(frame, vname, frame_idx, total, timestamp, guns_this_frame, total_guns)
        writer.write(frame)

    cap.release()
    writer.release()

    print(f"\n  ✅ Done — {total_guns} gun detections found")
    print(f"  📁 Saved: {out_path}")

    return {
        "video_name":    vname,
        "video_path":    video_path,
        "resolution":    f"{width}x{height}",
        "fps":           fps,
        "total_frames":  total,
        "duration_secs": round(total / fps, 2),
        "total_gun_detections": total_guns,
        "annotated_output": out_path,
        "detections": report_dets,
    }


def main():
    print("=" * 60)
    print("  SentryEye — Handgun Only Detection Pipeline")
    print(f"  Model : {WEAPON_MODEL_PATH}")
    print(f"  Device: {DEVICE}")
    print(f"  Conf  : {GUN_CONF_THRESHOLD}  |  BBox filter: max {MAX_BBOX_WIDTH}x{MAX_BBOX_HEIGHT}px")
    print("=" * 60)

    model   = load_model()
    results = {}

    for vpath in VIDEOS:
        res = process_video(model, vpath)
        if res:
            results[res["video_name"]] = res

    # Save JSON report
    report_path = os.path.join(OUTPUT_DIR, "gun_detection_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    for vname, data in results.items():
        n = data["total_gun_detections"]
        print(f"  {'🔴' if n > 0 else '✅'} {vname}: {n} gun detections")
    print(f"\n  📊 Report: {report_path}")
    print("  🎉 Done!")


if __name__ == "__main__":
    main()
