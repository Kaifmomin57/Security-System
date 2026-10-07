import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone
import cv2
import numpy as np
import torch

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detection.detector import Detector
from detection.tracker import Tracker
from rules.loitering_rule import LoiteringRule
from rules.trailing_rule import TrailingRule
from rules.zone_intrusion_rule import ZoneIntrusionRule
from rules.unaccompanied_person_rule import UnaccompaniedPersonRule
from rules.gesture_rule import DistressGestureRule
from rules.weapon_rule import WeaponDetectionRule
from rules.abandoned_object_rule import AbandonedObjectRule
from rules.traffic_violation_rule import TrafficViolationRule
from rules.hit_and_run_rule import HitAndRunRule
from detection.anpr_engine import anpr_engine
from detection.reid_engine import reid_engine
from rules.fusion import FusionEngine
from privacy.face_blur import FaceBlur
from storage.db import create_tables, get_session, Event, Camera
from detection.weapon_detector import weapon_detector
from detection.gesture_detector import gesture_detector

VIDEOS = [
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.32 AM.mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.45 AM (1).mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.45 AM.mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.23.53 AM.mp4",
    r"d:\security\WhatsApp Video 2026-10-07 at 9.32.05 AM.mp4",
]

OUTPUT_DIR = r"d:\security\sentryeye\backend\media\full_pipeline_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def process_single_video(video_path):
    video_name = os.path.basename(video_path)
    print(f"\n==================================================")
    print(f"🎬 Processing: {video_name}")
    print(f"==================================================")
    
    if not os.path.exists(video_path):
        print(f"❌ File not found: {video_path}")
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Cannot open video: {video_path}")
        return None

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_secs = total_frames / fps if fps > 0 else 0

    print(f"Resolution: {width}x{height} | FPS: {fps:.2f} | Total Frames: {total_frames} | Duration: {duration_secs:.2f}s")

    # Output video writer
    out_filename = f"annotated_{os.path.splitext(video_name)[0]}.mp4"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    # Initialize AI Components
    device = "cuda" if torch.cuda.is_available() else "cpu"
    detector = Detector(model_name="yolov8s.pt", device=device, confidence=0.35)
    camera_id = f"cam_{abs(hash(video_name)) % 10000:04d}"
    tracker = Tracker(camera_id=camera_id)
    
    rules = [
        LoiteringRule(),
        ZoneIntrusionRule(),
        TrailingRule(),
        UnaccompaniedPersonRule(),
        DistressGestureRule(),
        WeaponDetectionRule(),
        AbandonedObjectRule(),
        TrafficViolationRule(),
        HitAndRunRule(),
    ]
    fusion = FusionEngine(n_required=3, m_window=6, cooldown_secs=5)
    
    config = {
        "camera_id": camera_id,
        "trailing": {
            "duration_threshold": 1.5,
            "max_ambient_persons": 10,
            "min_follow_distance": 15,
            "max_follow_distance": 450,
        },
        "unaccompanied": {
            "enabled": True,
            "threshold_seconds": 3,
            "proximity_radius_px": 180,
            "adult_height_px": height * 0.35,
            "small_stature_ratio": 0.65,
        },
        "zones": [
            {
                "id": "zone_general",
                "name": "General Monitored Zone",
                "polygon": [[0, 0], [width, 0], [width, height], [0, height]],
                "rules": [{"type": "loitering", "threshold_seconds": 6, "enabled": True}]
            }
        ]
    }

    frame_idx = 0
    all_detections_summary = {
        "video_name": video_name,
        "video_path": video_path,
        "resolution": f"{width}x{height}",
        "fps": fps,
        "total_frames": total_frames,
        "duration_seconds": round(duration_secs, 2),
        "annotated_video_path": out_path,
        "detected_classes_counts": {},
        "unique_tracks": {},
        "anpr_plates": [],
        "distress_gestures": [],
        "weapons_detected": [],
        "security_incidents": [],
        "timeline_events": [],
    }

    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps
        frame_idx += 1

        # 1. Detect objects
        raw_dets = detector.detect(frame)
        
        # 2. Weapon Detector check
        try:
            extra_wep = weapon_detector.detect(frame) if weapon_detector else []
        except Exception:
            extra_wep = []
        all_dets = raw_dets + extra_wep

        # Tally detected classes
        for d in all_dets:
            cname = getattr(d, 'class_name', 'unknown')
            all_detections_summary["detected_classes_counts"][cname] = all_detections_summary["detected_classes_counts"].get(cname, 0) + 1
            if cname in ("knife", "gun", "scissors", "baseball bat", "weapon"):
                wep_info = {
                    "frame": frame_idx,
                    "timestamp": round(timestamp, 2),
                    "class": cname,
                    "confidence": round(float(getattr(d, 'confidence', 0.0)), 3),
                    "bbox": [int(v) for v in getattr(d, 'bbox', [])]
                }
                all_detections_summary["weapons_detected"].append(wep_info)

        # 3. Tracking
        tracks = tracker.update(raw_dets, frame, frame_idx, timestamp)
        for trk in tracks:
            tid = trk.track_id
            if tid not in all_detections_summary["unique_tracks"]:
                all_detections_summary["unique_tracks"][tid] = {
                    "track_id": tid,
                    "class_name": trk.class_name,
                    "first_seen": round(timestamp, 2),
                    "last_seen": round(timestamp, 2),
                    "frames_active": 1,
                }
            else:
                all_detections_summary["unique_tracks"][tid]["last_seen"] = round(timestamp, 2)
                all_detections_summary["unique_tracks"][tid]["frames_active"] += 1

        # 4. Gesture Detection
        try:
            if gesture_detector and any(t.class_name == "person" for t in tracks):
                for trk in tracks:
                    if trk.class_name == "person":
                        x1, y1, x2, y2 = [int(max(0, v)) for v in trk.bbox]
                        p_crop = frame[y1:y2, x1:x2]
                        if p_crop.size > 0:
                            g_res = gesture_detector.detect_distress_gesture(p_crop)
                            if g_res and g_res.get("detected"):
                                all_detections_summary["distress_gestures"].append({
                                    "frame": frame_idx,
                                    "timestamp": round(timestamp, 2),
                                    "track_id": trk.track_id,
                                    "gesture": g_res.get("gesture_type", "signal_for_help"),
                                    "confidence": round(float(g_res.get("confidence", 0.0)), 3)
                                })
        except Exception as e:
            pass

        # 5. ANPR Check on vehicles
        if frame_idx % 5 == 0:
            for trk in tracks:
                if trk.class_name in ("car", "truck", "bus", "motorcycle"):
                    try:
                        anpr_res = anpr_engine.process_vehicle_track(
                            frame=frame,
                            bbox=trk.bbox,
                            camera_id=camera_id,
                            track_id=trk.track_id
                        )
                        if anpr_res and anpr_res.get("plate_number"):
                            plate_num = anpr_res["plate_number"]
                            if not any(p["plate"] == plate_num for p in all_detections_summary["anpr_plates"]):
                                all_detections_summary["anpr_plates"].append({
                                    "plate": plate_num,
                                    "confidence": round(float(anpr_res.get("ocr_confidence", 0.0)), 3),
                                    "track_id": trk.track_id,
                                    "matched_watchlist": anpr_res.get("matched", False),
                                    "reason": anpr_res.get("reason", "None"),
                                    "timestamp": round(timestamp, 2)
                                })
                    except Exception:
                        pass

        # 6. Evaluate Security Rules
        eval_cfg = dict(config)
        eval_cfg["current_frame"] = frame
        eval_cfg["raw_detections"] = all_dets
        raw_rule_results = []
        for r in rules:
            try:
                res = r.evaluate(tracks, eval_cfg)
                if res:
                    raw_rule_results.extend(res)
            except Exception:
                pass

        confirmed_alerts = fusion.process(raw_rule_results, camera_id)
        for alert in confirmed_alerts:
            inc = {
                "frame": frame_idx,
                "timestamp": round(timestamp, 2),
                "rule_type": alert.rule_type,
                "confidence": round(float(alert.confidence), 3),
                "track_ids": alert.track_ids,
                "metadata": alert.metadata
            }
            all_detections_summary["security_incidents"].append(inc)
            all_detections_summary["timeline_events"].append(
                f"[{round(timestamp, 1)}s] Alert: {alert.rule_type} (Conf: {int(alert.confidence*100)}%) Tracks: {alert.track_ids}"
            )

        # 7. Draw annotations on frame
        annotated_frame = frame.copy()
        
        # Raw detections
        for det in all_dets:
            cname = getattr(det, "class_name", "obj")
            conf = getattr(det, "confidence", 0.0)
            x1, y1, x2, y2 = [int(v) for v in getattr(det, "bbox", [0,0,0,0])]
            if cname == "person":
                continue
            color = (0, 0, 255) if cname in ("knife", "gun", "scissors", "baseball bat", "weapon") else (0, 215, 255)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated_frame, f"{cname} {int(conf*100)}%", (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Tracks
        for trk in tracks:
            x1, y1, x2, y2 = [int(v) for v in trk.bbox]
            color = (0, 255, 0)
            # Red if involved in alert
            if any(trk.track_id in al.track_ids for al in confirmed_alerts):
                color = (0, 0, 255)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated_frame, f"ID:{trk.track_id} {trk.class_name}", (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
            cv2.putText(annotated_frame, f"ID:{trk.track_id} {trk.class_name}", (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # Header HUD
        hud_text = f"SentryEye AI | Frame: {frame_idx}/{total_frames} | Time: {timestamp:.1f}s | Tracks: {len(tracks)}"
        cv2.rectangle(annotated_frame, (0, 0), (width, 35), (20, 20, 20), -1)
        cv2.putText(annotated_frame, hud_text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)

        if confirmed_alerts:
            alert_str = f"ALERT: {confirmed_alerts[0].rule_type.upper()}"
            cv2.putText(annotated_frame, alert_str, (width - 320, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

        out_writer.write(annotated_frame)

        if frame_idx % 50 == 0:
            print(f"  -> Processed {frame_idx}/{total_frames} frames ({frame_idx/total_frames*100:.1f}%)")

    cap.release()
    out_writer.release()
    
    elapsed = time.time() - start_time
    proc_fps = total_frames / elapsed if elapsed > 0 else 0
    print(f"✅ Finished {video_name} in {elapsed:.2f}s ({proc_fps:.1f} FPS). Output saved: {out_path}")
    
    return all_detections_summary

def main():
    results = {}
    for v_path in VIDEOS:
        if os.path.exists(v_path):
            res = process_single_video(v_path)
            if res:
                results[res["video_name"]] = res
        else:
            print(f"Skipping missing: {v_path}")

    # Save complete JSON report
    report_json = os.path.join(OUTPUT_DIR, "detection_report.json")
    # Convert set/non-serializable types if any
    with open(report_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n🎉 All videos processed! Complete report saved to: {report_json}")

if __name__ == "__main__":
    main()
