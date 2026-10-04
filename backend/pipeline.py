"""
pipeline.py
────────────
Main orchestrator: wires ingestion → detection → tracking → rules → alerts → storage.
Run this as the background AI engine; the FastAPI server runs separately.

Usage:
    python pipeline.py
"""

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime

import cv2
import yaml
from dotenv import load_dotenv

from ingestion.stream_reader  import StreamReader
from detection.detector       import Detector
from detection.tracker        import Tracker
from rules.loitering_rule     import LoiteringRule
from rules.trailing_rule      import TrailingRule
from rules.zone_intrusion_rule import ZoneIntrusionRule
from rules.unaccompanied_person_rule import UnaccompaniedPersonRule
from rules.traffic_violation_rule import TrafficViolationRule
from rules.hit_and_run_rule   import HitAndRunRule
from detection.anpr_engine    import anpr_engine
from rules.fusion             import FusionEngine
from audio.distress_detector  import AudioDistressDetector
from alerts.severity          import score_severity
from alerts.trust_adjuster    import trust_adjuster
from alerts.notifier_telegram import send_alert
from evidence.hasher          import hash_file
from privacy.face_blur        import FaceBlur
from storage.db               import (
    create_tables, get_session, Event, Camera,
    TrackClassification, UnaccompaniedEvent, AudioEvent,
    TrafficViolation, CollisionEvent, PlateRead
)
from storage.clip_saver       import ClipSaver
from api.main                 import pipeline_status
from api.websocket_manager    import ws_manager

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sentryeye.pipeline")

def get_env(key: str, default, cast=str):
    raw = os.getenv(key, "")
    if raw is None or str(raw).strip() == "":
        return default
    # Strip any inline comments
    clean = str(raw).split("#")[0].strip()
    if not clean:
        return default
    try:
        if cast == bool:
            return clean.lower() in ("true", "1", "yes")
        return cast(clean)
    except Exception:
        return default

# ─── Config ───────────────────────────────────────────────────────────────────
VIDEO_SOURCE   = get_env("VIDEO_SOURCE",   "./media/test_cctv.mp4", str)
CAMERA_ID      = get_env("CAMERA_ID",      "cam_01", str)
CAMERA_NAME    = get_env("CAMERA_NAME",    "Main Entrance", str)
YOLO_MODEL     = get_env("YOLO_MODEL",     "yolov8s.pt", str)
DEVICE         = get_env("DEVICE",         "cuda", str)
FRAME_SKIP     = get_env("FRAME_SKIP",     2, int)
CONF_THRESH    = get_env("DETECTION_CONFIDENCE", 0.45, float)
INPUT_W        = get_env("INPUT_WIDTH",    640, int)
INPUT_H        = get_env("INPUT_HEIGHT",   640, int)
MEDIA_DIR      = get_env("MEDIA_DIR",      "./media", str)
FACE_BLUR_ON   = get_env("FACE_BLUR_ENABLED", True, bool)
N_SMOOTH       = get_env("TEMPORAL_SMOOTHING_N", 5, int)
M_SMOOTH       = get_env("TEMPORAL_SMOOTHING_M", 8, int)
COOLDOWN       = get_env("ALERT_COOLDOWN_SECONDS", 30, int)
ZONES_CFG_PATH = "./config/zones.yaml"


def load_zones_config(camera_id: str) -> dict:
    """Load zone/rule config for a specific camera from zones.yaml."""
    try:
        with open(ZONES_CFG_PATH) as f:
            cfg = yaml.safe_load(f)
        for cam in cfg.get("cameras", []):
            if cam["id"] == camera_id:
                return cam
    except Exception as e:
        logger.warning(f"Could not load zones config: {e}")
    return {}


def draw_overlays(frame, tracks, active_alerts):
    """Draw bounding boxes, track IDs, and alert indicators on the frame."""
    for track in tracks:
        x1, y1, x2, y2 = [int(v) for v in track.bbox]
        color = (0, 255, 0)  # green = normal

        # Red for tracks involved in active alerts
        for alert in active_alerts:
            if track.track_id in alert.get("track_ids", []):
                color = (0, 0, 255)
                break

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{track.track_id} {track.class_name}"
        cv2.putText(frame, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return frame


async def save_and_notify(
    result,
    frame,
    camera_name: str,
    clip_saver: ClipSaver,
    face_blur: FaceBlur | None,
    audio_detector: AudioDistressDetector | None = None,
):
    """Save snapshot/clip, hash it, store DB record, perform audio-visual fusion, send Telegram alert."""
    db = get_session()
    event_id = f"evt_{uuid.uuid4().hex[:8]}"

    try:
        severity = score_severity(result)
        metadata = dict(result.metadata) if result.metadata else {}

        # ── Feature B: Multi-Modal Fusion Check ──────────────────────────────
        # Check if there is a recent distress audio event on this camera
        if audio_detector:
            recent_audio = audio_detector.get_recent_audio_distress(window_seconds=6.0)
            if recent_audio:
                # Upgrade severity & mark as fused multi-modal alert
                severity = "critical" if severity == "high" else "high"
                metadata["multi_modal_fused"] = True
                metadata["fused_audio_id"] = recent_audio["id"]
                metadata["fused_sound_class"] = recent_audio["sound_class"]
                metadata["fused_audio_confidence"] = recent_audio["confidence"]
                metadata["fused_explanation"] = (
                    f"🚨 MULTI-MODAL INCIDENT: Visual {result.rule_type} correlated with "
                    f"Audio Distress ({recent_audio['sound_class']}, {int(recent_audio['confidence']*100)}% conf)."
                )

                # Link audio event in DB
                try:
                    a_rec = db.query(AudioEvent).filter(AudioEvent.id == recent_audio["id"]).first()
                    if a_rec:
                        a_rec.fused_event_id = event_id
                        a_rec.status = "fused"
                        db.commit()
                except Exception:
                    pass

        snapshot_path, _ = clip_saver.trigger(event_id, frame)

        # Apply face blur to snapshot
        if face_blur and snapshot_path:
            face_blur.blur_image_file(snapshot_path)

        # Write DB event first (clip path filled after post-event recording)
        event = Event(
            id            = event_id,
            camera_id     = CAMERA_ID,
            rule_type     = result.rule_type,
            confidence    = result.confidence,
            severity      = severity,
            status        = "new",
            track_ids     = result.track_ids,
            snapshot_path = snapshot_path,
            clip_path     = "",
            clip_hash     = "",
            explanation   = metadata,
            timestamp     = datetime.utcnow(),
        )
        db.add(event)

        # ── Feature A: Unaccompanied Person Record in DB ─────────────────────
        if result.rule_type == "unaccompanied_person":
            for tid in result.track_ids:
                try:
                    db.add(TrackClassification(
                        track_id=tid,
                        stature_class="small",
                        confidence=metadata.get("stature_confidence", 0.8),
                        camera_calib_ref=CAMERA_ID,
                    ))
                    db.add(UnaccompaniedEvent(
                        event_id=event_id,
                        track_id=tid,
                        duration_alone_seconds=metadata.get("duration_alone_seconds", 0),
                    ))
                except Exception as e:
                    logger.debug(f"Could not write unaccompanied details: {e}")

        # ── Feature 5: Traffic Violation Record in DB ─────────────────────────
        if result.rule_type in ("signal_jump", "wrong_side"):
            try:
                db.add(TrafficViolation(
                    id=f"tv_{uuid.uuid4().hex[:8]}",
                    event_id=event_id,
                    junction_id=CAMERA_ID,
                    violation_type=result.rule_type,
                    plate_number=metadata.get("plate_number"),
                    signal_state=metadata.get("signal_state"),
                    lane_id=metadata.get("lane_id"),
                    speed_estimate_kmh=metadata.get("speed_estimate_kmh"),
                    timestamp=datetime.utcnow(),
                ))
            except Exception as e:
                logger.debug(f"Could not write traffic violation: {e}")

        # ── Feature 6: Hit-and-Run Collision Record in DB ────────────────────
        if result.rule_type == "possible_hit_and_run":
            try:
                db.add(CollisionEvent(
                    id=f"col_{uuid.uuid4().hex[:8]}",
                    event_id=event_id,
                    track_id_fleeing=metadata.get("track_id_fleeing", result.track_ids[0] if result.track_ids else 0),
                    track_id_stationary=metadata.get("track_id_stationary", result.track_ids[1] if len(result.track_ids) > 1 else 0),
                    plate_number=metadata.get("plate_number"),
                    collision_speed_drop=metadata.get("collision_speed_drop", 0.65),
                    fleeing_velocity=metadata.get("fleeing_velocity_px", 18.0),
                    timestamp=datetime.utcnow(),
                ))
            except Exception as e:
                logger.debug(f"Could not write collision event: {e}")

        db.commit()

        # Send Telegram notification (non-blocking)
        zone_name  = metadata.get("zone_name")
        dwell_time = metadata.get("dwell_time") or metadata.get("duration_alone_seconds")
        await send_alert(
            event_id    = event_id,
            camera_id   = CAMERA_ID,
            camera_name = camera_name,
            rule_type   = result.rule_type,
            confidence  = result.confidence,
            severity    = severity,
            snapshot_path = snapshot_path,
            zone_name   = zone_name,
            dwell_time  = dwell_time,
        )

        # Push to dashboard via WebSocket
        await ws_manager.broadcast_new_alert({
            "id":          event_id,
            "camera_id":   CAMERA_ID,
            "rule_type":   result.rule_type,
            "confidence":  result.confidence,
            "severity":    severity,
            "status":      "new",
            "track_ids":   result.track_ids,
            "snapshot_url": f"/media/snapshots/{os.path.basename(snapshot_path)}" if snapshot_path else None,
            "timestamp":   datetime.utcnow().isoformat(),
            "explanation": metadata,
        })

        logger.info(f"🚨 Alert saved & sent: {event_id} | {result.rule_type} | {severity}")

    except Exception as e:
        logger.error(f"save_and_notify error: {e}", exc_info=True)
    finally:
        db.close()


async def run_pipeline():
    """Main async pipeline loop."""
    logger.info("=" * 60)
    logger.info(f"  SentryEye Pipeline Starting")
    logger.info(f"  Camera : {CAMERA_ID} ({CAMERA_NAME})")
    logger.info(f"  Source : {VIDEO_SOURCE}")
    logger.info(f"  Model  : {YOLO_MODEL} on {DEVICE}")
    logger.info("=" * 60)

    # ── Init database ─────────────────────────────────────────────────────────
    create_tables()
    db = get_session()
    cam = db.query(Camera).filter(Camera.id == CAMERA_ID).first()
    if not cam:
        db.add(Camera(id=CAMERA_ID, name=CAMERA_NAME, source_url=VIDEO_SOURCE, status="online"))
        db.commit()
    else:
        cam.status = "online"
        db.commit()
    db.close()

    # ── Load config ───────────────────────────────────────────────────────────
    cam_config = load_zones_config(CAMERA_ID)

    # ── Init components ───────────────────────────────────────────────────────
    detector       = Detector(model_name=YOLO_MODEL, device=DEVICE, confidence=CONF_THRESH)
    tracker        = Tracker(camera_id=CAMERA_ID)
    rules          = [
        LoiteringRule(),
        ZoneIntrusionRule(),
        TrailingRule(),
        UnaccompaniedPersonRule(), # Feature A: Abandoned/Lost Person Detection
        TrafficViolationRule(),    # Feature 5: Signal Jump & Wrong-Way
        HitAndRunRule(),           # Feature 6: Hit & Run Collision
    ]
    fusion         = FusionEngine(n_required=N_SMOOTH, m_window=M_SMOOTH, cooldown_secs=COOLDOWN)
    clip_saver     = ClipSaver(output_dir=MEDIA_DIR, camera_id=CAMERA_ID)
    face_blur      = FaceBlur() if FACE_BLUR_ON else None
    
    # Feature B: Audio Distress Detector on background thread
    audio_detector = AudioDistressDetector(camera_id=CAMERA_ID)
    audio_detector.start()

    # ── Update pipeline status registry ───────────────────────────────────────
    pipeline_status[CAMERA_ID] = {
        "status":       "running",
        "fps":          0.0,
        "started_at":   time.time(),
        "last_frame_at": None,
    }

    # ── Stream loop ───────────────────────────────────────────────────────────
    fps_counter, fps_timer = 0, time.time()
    anpr_eval_frame_skip = 10  # Evaluate ANPR every 10 frames

    with StreamReader(VIDEO_SOURCE, frame_skip=FRAME_SKIP,
                      width=INPUT_W, height=INPUT_H, camera_id=CAMERA_ID) as reader:

        for frame_idx, timestamp, frame in reader.stream():

            # ── Detection + Tracking ─────────────────────────────────────────
            detections = detector.detect(frame)
            tracks     = tracker.update(detections, frame, frame_idx, timestamp)

            # ── Feed rolling clip buffer ─────────────────────────────────────
            clip_saver.push_frame(frame)

            # ── Feature 3: ANPR + Watchlist Check on Vehicle Tracks ──────────
            if frame_idx % anpr_eval_frame_skip == 0:
                for trk in tracks:
                    if getattr(trk, "class_name", "") in ("car", "truck", "bus", "motorcycle"):
                        anpr_res = anpr_engine.process_vehicle_track(
                            frame=frame,
                            bbox=trk.bbox,
                            camera_id=CAMERA_ID,
                            track_id=trk.track_id,
                        )
                        if anpr_res and anpr_res.get("matched"):
                            # Trigger immediate high severity watchlist hit alert
                            from rules.base_rule import RuleResult
                            wl_hit = RuleResult(
                                triggered=True,
                                confidence=anpr_res["ocr_confidence"],
                                rule_type="watchlist_vehicle_match",
                                track_ids=[trk.track_id],
                                metadata={
                                    "plate_number": anpr_res["plate_number"],
                                    "reason": anpr_res["reason"],
                                    "snapshot_path": anpr_res["snapshot_path"],
                                    "description": f"Flagged vehicle intercepted: Plate {anpr_res['plate_number']} ({anpr_res['reason']})"
                                }
                            )
                            asyncio.create_task(
                                save_and_notify(wl_hit, frame.copy(), CAMERA_NAME, clip_saver, face_blur, audio_detector)
                            )

            # ── Rule evaluation ───────────────────────────────────────────────
            raw_results = []
            for rule in rules:
                raw_results.extend(rule.evaluate(tracks, cam_config))

            # ── Temporal smoothing + fusion ───────────────────────────────────
            confirmed = fusion.process(raw_results, CAMERA_ID)

            # ── For each confirmed alert ──────────────────────────────────────
            active_alert_data = []
            for result in confirmed:
                # Trust adjuster (F18) — skip if dismiss rate too high
                if trust_adjuster.should_suppress(CAMERA_ID, result.rule_type):
                    continue
                active_alert_data.append({
                    "track_ids": result.track_ids,
                    "rule_type": result.rule_type,
                })
                asyncio.create_task(
                    save_and_notify(result, frame.copy(), CAMERA_NAME, clip_saver, face_blur, audio_detector)
                )

            # ── Draw overlays and display (remove for headless / server mode) ─
            annotated = draw_overlays(frame.copy(), tracks, active_alert_data)
            cv2.imshow(f"SentryEye — {CAMERA_NAME}", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                logger.info("User quit.")
                break

            # ── FPS counter ───────────────────────────────────────────────────
            fps_counter += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 5.0:
                fps = fps_counter / elapsed
                pipeline_status[CAMERA_ID]["fps"] = fps
                pipeline_status[CAMERA_ID]["last_frame_at"] = timestamp
                logger.info(f"[{CAMERA_ID}] FPS: {fps:.1f} | Tracks: {len(tracks)} | Frame: {frame_idx}")
                fps_counter, fps_timer = 0, time.time()

            # Yield to event loop so WebSocket tasks can run
            await asyncio.sleep(0)

    # Stop audio detector
    audio_detector.stop()
    cv2.destroyAllWindows()
    pipeline_status[CAMERA_ID]["status"] = "stopped"
    logger.info("Pipeline stopped.")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
