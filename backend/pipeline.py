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
import shutil
import time
import uuid
from datetime import datetime, timezone

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
from rules.gesture_rule       import DistressGestureRule
from rules.weapon_rule        import WeaponDetectionRule
from rules.abandoned_object_rule import AbandonedObjectRule
from rules.traffic_violation_rule import TrafficViolationRule
from rules.hit_and_run_rule   import HitAndRunRule
from detection.anpr_engine    import anpr_engine
from detection.reid_engine    import reid_engine
from rules.fusion             import FusionEngine
from audio.distress_detector  import AudioDistressDetector
from alerts.severity          import score_severity
from alerts.trust_adjuster    import trust_adjuster
from alerts.notifier_telegram import send_alert
from evidence.hasher          import hash_file
from privacy.face_blur        import FaceBlur
from privacy.private_evidence import private_snapshot_path
from storage.db               import (
    create_tables, get_session, Event, Camera,
    TrackClassification, UnaccompaniedEvent, AudioEvent,
    TrafficViolation, CollisionEvent, PlateRead,
    TrailingEvent, GestureEvent, WeaponEvent, AbandonedObjectEvent,
    ReidGallery, ReidMatch
)
from storage.clip_saver       import ClipSaver
from api.main                 import pipeline_status, frame_registry
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


def draw_overlays(frame, tracks, active_alerts, raw_detections=None):
    """Draw bounding boxes, track IDs, object labels, and alert indicators on the frame."""
    # 1. Draw raw detected objects (weapons, bags, everyday items)
    if raw_detections:
        for det in raw_detections:
            cls_name = getattr(det, "class_name", "object")
            conf = getattr(det, "confidence", 0.0)
            bbox = getattr(det, "bbox", [0, 0, 0, 0])
            x1, y1, x2, y2 = [int(v) for v in bbox]

            if cls_name == "person":
                continue  # Persons rendered with Track IDs below

            # Color coding: Weapons (Red), Bags (Yellow)
            if cls_name in ("knife", "gun", "scissors", "baseball bat"):
                color = (0, 0, 255)  # Red for weapons
                label = f"⚠️ {cls_name.upper()} {int(conf * 100)}%"
            elif cls_name in ("backpack", "handbag", "suitcase"):
                color = (0, 215, 255)  # Gold/Yellow for bags
                label = f"{cls_name} {int(conf * 100)}%"
            else:
                color = (0, 255, 255)
                label = f"{cls_name} {int(conf * 100)}%"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - 18)), (x1 + tw + 6, max(0, y1)), color, -1)
            cv2.putText(frame, label, (x1 + 3, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    # 2. Draw person / vehicle tracks
    from detection.gesture_detector import gesture_detector
    for track in tracks:
        x1, y1, x2, y2 = [int(v) for v in track.bbox]
        color = (0, 255, 0)  # green = normal

        # Draw hand gesture landmarks for person tracks
        if getattr(track, "class_name", "") == "person" and gesture_detector:
            try:
                frame = gesture_detector.draw_landmarks(frame, (x1, y1, x2, y2))
            except Exception:
                pass

        # Red for tracks involved in active alerts
        is_alert = False
        for alert in active_alerts:
            if track.track_id in alert.get("track_ids", []):
                color = (0, 0, 255)
                is_alert = True
                break

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{track.track_id} {track.class_name}" + (" [ALERT]" if is_alert else "")
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, max(0, y1 - 20)), (x1 + tw + 6, max(0, y1)), color, -1)
        cv2.putText(frame, label, (x1 + 3, max(14, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0) if not is_alert else (255, 255, 255), 1, cv2.LINE_AA)
    return frame


async def save_and_notify(
    result,
    frame,
    camera_name: str,
    clip_saver: ClipSaver,
    face_blur: FaceBlur | None,
    audio_detector: AudioDistressDetector | None = None,
    captured_at: float | None = None,
    event_camera_id: str = CAMERA_ID,
):
    """Save snapshot/clip, hash it, store DB record, perform audio-visual fusion, send Telegram alert."""
    db = get_session()
    event_id = f"evt_{uuid.uuid4().hex[:8]}"

    try:
        severity = score_severity(result)
        metadata = dict(result.metadata) if result.metadata else {}
        event_timestamp = (
            datetime.fromtimestamp(captured_at, timezone.utc).replace(tzinfo=None)
            if captured_at is not None
            else datetime.utcnow()
        )

        # Track IDs can change when tracking reacquires subjects; prevent a
        # second unresolved incident for the same rule on this camera.
        duplicate = db.query(Event).filter(
            Event.camera_id == event_camera_id,
            Event.rule_type == result.rule_type,
            Event.status.in_(("new", "acknowledged", "confirmed")),
        ).first()
        if duplicate:
            logger.info(
                "Suppressing duplicate incident for %s on %s: existing event %s",
                result.rule_type,
                event_camera_id,
                duplicate.id,
            )
            return

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
            try:
                original_path = private_snapshot_path(event_id)
                os.makedirs(os.path.dirname(original_path), mode=0o700, exist_ok=True)
                shutil.copy2(snapshot_path, original_path)
            except (OSError, ValueError):
                logger.exception("Could not preserve private original for event %s", event_id)
            face_blur.blur_image_file(snapshot_path)

        # Write DB event first (clip path filled after post-event recording)
        event = Event(
            id            = event_id,
            camera_id     = event_camera_id,
            rule_type     = result.rule_type,
            confidence    = result.confidence,
            severity      = severity,
            status        = "new",
            track_ids     = result.track_ids,
            snapshot_path = snapshot_path,
            clip_path     = "",
            clip_hash     = "",
            explanation   = metadata,
            timestamp     = event_timestamp,
        )
        db.add(event)

        # ── Feature 1: Unaccompanied Person Record in DB ─────────────────────
        if result.rule_type == "unaccompanied_person":
            for tid in result.track_ids:
                try:
                    db.add(TrackClassification(
                        track_id=tid,
                        stature_class="small",
                        confidence=metadata.get("stature_confidence", 0.8),
                        camera_calib_ref=event_camera_id,
                    ))
                    db.add(UnaccompaniedEvent(
                        event_id=event_id,
                        track_id=tid,
                        duration_alone_seconds=metadata.get("duration_alone_seconds", 0),
                    ))
                except Exception as e:
                    logger.debug(f"Could not write unaccompanied details: {e}")

        # ── Feature 2: Trailing Event Record in DB & Active Re-ID Gallery ───
        if result.rule_type == "trailing":
            try:
                follower_id = metadata.get("follower_id", result.track_ids[0] if result.track_ids else 0)
                followed_id = metadata.get("followed_id", result.track_ids[1] if len(result.track_ids) > 1 else 0)
                db.add(TrailingEvent(
                    id=f"trl_{uuid.uuid4().hex[:8]}",
                    event_id=event_id,
                    track_id_follower=follower_id,
                    track_id_followed=followed_id,
                    duration_seconds=metadata.get("duration_seconds", 0.0),
                    avg_distance=metadata.get("avg_distance", 0.0),
                    ambient_count=metadata.get("ambient_count", 1),
                    confidence=result.confidence,
                    timestamp=datetime.now(timezone.utc),
                ))
                # Add follower to active Re-ID gallery for cross-camera correlation
                if frame is not None and frame.size > 0:
                    reid_engine.add_to_active_gallery(follower_id, event_camera_id, frame)
            except Exception as e:
                logger.debug(f"Could not write trailing event: {e}")

        # ── Feature 3: Gesture Event Record in DB ────────────────────────────
        if result.rule_type == "signal_for_help":
            try:
                db.add(GestureEvent(
                    id=f"ges_{uuid.uuid4().hex[:8]}",
                    event_id=event_id,
                    track_id=result.track_ids[0] if result.track_ids else 0,
                    camera_id=event_camera_id,
                    confidence=result.confidence,
                    gesture_type=metadata.get("gesture_type", "signal_for_help"),
                    snapshot_path=snapshot_path,
                    timestamp=datetime.now(timezone.utc),
                ))
            except Exception as e:
                logger.debug(f"Could not write gesture event: {e}")

        # ── Feature 5.1: Weapon Event Record in DB ───────────────────────────
        if result.rule_type == "possible_weapon":
            try:
                db.add(WeaponEvent(
                    id=f"wep_{uuid.uuid4().hex[:8]}",
                    event_id=event_id,
                    track_id=result.track_ids[0] if result.track_ids else None,
                    weapon_class=metadata.get("weapon_class", "weapon"),
                    confidence=result.confidence,
                    camera_id=event_camera_id,
                    is_reviewed=False,
                    timestamp=datetime.now(timezone.utc),
                ))
            except Exception as e:
                logger.debug(f"Could not write weapon event: {e}")

        # ── Feature 5.2: Abandoned Object Event Record in DB ─────────────────
        if result.rule_type == "abandoned_object":
            try:
                db.add(AbandonedObjectEvent(
                    id=f"abn_{uuid.uuid4().hex[:8]}",
                    event_id=event_id,
                    object_track_id=metadata.get("object_track_id", result.track_ids[0] if result.track_ids else 0),
                    object_class=metadata.get("object_class", "backpack"),
                    duration_unattended=metadata.get("duration_unattended_seconds", 0.0),
                    camera_id=event_camera_id,
                    timestamp=datetime.now(timezone.utc),
                ))
            except Exception as e:
                logger.debug(f"Could not write abandoned object event: {e}")

        # ── Feature 5: Traffic Violation Record in DB ─────────────────────────
        if result.rule_type in ("signal_jump", "wrong_side"):
            try:
                db.add(TrafficViolation(
                    id=f"tv_{uuid.uuid4().hex[:8]}",
                    event_id=event_id,
                    junction_id=event_camera_id,
                    violation_type=result.rule_type,
                    plate_number=metadata.get("plate_number"),
                    signal_state=metadata.get("signal_state"),
                    lane_id=metadata.get("lane_id"),
                    speed_estimate_kmh=metadata.get("speed_estimate_kmh"),
                    timestamp=event_timestamp,
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
                    timestamp=event_timestamp,
                ))
            except Exception as e:
                logger.debug(f"Could not write collision event: {e}")

        db.commit()

        # Send Telegram notification (non-blocking)
        zone_name  = metadata.get("zone_name")
        dwell_time = metadata.get("dwell_time") or metadata.get("duration_alone_seconds")
        await send_alert(
            event_id    = event_id,
            camera_id   = event_camera_id,
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
            "camera_id":   event_camera_id,
            "rule_type":   result.rule_type,
            "confidence":  result.confidence,
            "severity":    severity,
            "status":      "new",
            "track_ids":   result.track_ids,
            "snapshot_url": f"/media/snapshots/{os.path.basename(snapshot_path)}" if snapshot_path else None,
            "timestamp":   event_timestamp.replace(tzinfo=timezone.utc).isoformat(),
            "explanation": metadata,
        })

        logger.info(f"🚨 Alert saved & sent: {event_id} | {result.rule_type} | {severity}")

    except Exception as e:
        logger.error(f"save_and_notify error: {e}", exc_info=True)
    finally:
        db.close()


async def run_pipeline(camera_id: str = None, video_source: str = None, camera_name: str = None):
    """Main async pipeline loop. Params override env-var globals for multi-camera use."""
    # Allow per-instance overrides (for multi-camera mode)
    _cam_id     = camera_id    or CAMERA_ID
    _vid_src    = video_source or VIDEO_SOURCE
    _cam_name   = camera_name  or CAMERA_NAME

    logger.info("=" * 60)
    logger.info(f"  SentryEye Pipeline Starting")
    logger.info(f"  Camera : {_cam_id} ({_cam_name})")
    logger.info(f"  Source : {_vid_src}")
    logger.info(f"  Model  : {YOLO_MODEL} on {DEVICE}")
    logger.info("=" * 60)

    # ── Init database ─────────────────────────────────────────────────────────
    create_tables()
    db = get_session()
    cam = db.query(Camera).filter(Camera.id == _cam_id).first()
    if not cam:
        db.add(Camera(id=_cam_id, name=_cam_name, source_url=_vid_src, status="online"))
        db.commit()
    else:
        cam.status = "online"
        db.commit()
    db.close()

    # ── Load config ───────────────────────────────────────────────────────────
    cam_config = load_zones_config(_cam_id)

    # ── Init components ───────────────────────────────────────────────────────
    detector       = Detector(model_name=YOLO_MODEL, device=DEVICE, confidence=CONF_THRESH)
    tracker        = Tracker(camera_id=_cam_id)
    rules          = [
        LoiteringRule(),
        ZoneIntrusionRule(),
        TrailingRule(),             # Feature 2: Trailing / Stalking Pattern Detection (gender-neutral)
        UnaccompaniedPersonRule(),  # Feature 1: Unaccompanied Child / Lost Person Detection
        DistressGestureRule(),      # Feature 3: Signal-for-Help Hand Gesture Detection
        WeaponDetectionRule(),      # Feature 5.1: Weapon & Threatening Object Detection
        AbandonedObjectRule(),      # Feature 5.2: Abandoned & Suspicious Object Detection
        TrafficViolationRule(),     # Traffic Violation Detection
        HitAndRunRule(),            # Hit & Run Collision
    ]
    fusion         = FusionEngine(n_required=N_SMOOTH, m_window=M_SMOOTH, cooldown_secs=COOLDOWN)
    clip_saver     = ClipSaver(output_dir=MEDIA_DIR, camera_id=_cam_id)
    face_blur      = FaceBlur() if FACE_BLUR_ON else None

    audio_detector = AudioDistressDetector(camera_id=_cam_id)
    audio_detector.start()

    # ── Update pipeline status registry ───────────────────────────────────────
    pipeline_status[_cam_id] = {
        "status":       "running",
        "fps":          0.0,
        "started_at":   time.time(),
        "last_frame_at": None,
    }

    # ── Stream loop ───────────────────────────────────────────────────────────
    fps_counter, fps_timer = 0, time.time()
    anpr_eval_frame_skip = 10  # Evaluate ANPR every 10 frames
    with StreamReader(_vid_src, frame_skip=FRAME_SKIP,
                      width=INPUT_W, height=INPUT_H, camera_id=_cam_id) as reader:

        for frame_idx, timestamp, frame in reader.stream():

            # ── Model 1: Main Detector (yolov8s.pt) ──────────────────────────
            # Detects: person, car, motorcycle, bus, truck, backpack, handbag, suitcase
            # Does NOT detect guns/knives (removed from COCO_CLASSES_OF_INTEREST)
            detections = detector.detect(frame)

            # ── Model 2: Weapon Detector (best.pt) ────────────────────────────
            # Detects ONLY: gun, knife — specialized 2-class model
            # Kept separate to avoid duplicate detections with main model
            try:
                from detection.weapon_detector import weapon_detector
                weapon_dets = weapon_detector.detect(frame) if weapon_detector else []
            except Exception:
                weapon_dets = []

            # all_detections used for overlays & rule evaluation (both models combined)
            # tracker.update gets ONLY main detections (persons/vehicles for tracking)
            all_detections = detections + weapon_dets

            tracks = tracker.update(detections, frame, frame_idx, timestamp)

            # ── Feed rolling clip buffer ─────────────────────────────────────
            clip_saver.push_frame(frame)

            # ── Feature 3: ANPR + Watchlist Check on Vehicle Tracks ──────────
            if frame_idx % anpr_eval_frame_skip == 0:
                for trk in tracks:
                    if getattr(trk, "class_name", "") in ("car", "truck", "bus", "motorcycle"):
                        anpr_res = anpr_engine.process_vehicle_track(
                            frame=frame,
                            bbox=trk.bbox,
                            camera_id=_cam_id,
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
                                save_and_notify(
                                    wl_hit, frame.copy(), _cam_name, clip_saver, face_blur,
                                    audio_detector, captured_at=timestamp, event_camera_id=_cam_id,
                                )
                            )

            # ── Rule evaluation ───────────────────────────────────────────────
            eval_config = dict(cam_config)
            eval_config["current_frame"] = frame
            eval_config["raw_detections"] = all_detections
            eval_config["camera_id"] = _cam_id

            raw_results = []
            for rule in rules:
                raw_results.extend(rule.evaluate(tracks, eval_config))

            # ── Temporal smoothing + fusion ───────────────────────────────────
            already_temporal = [
                result for result in raw_results
                if result.rule_type == "possible_hit_and_run"
            ]
            confirmed = fusion.process(
                [result for result in raw_results if result.rule_type != "possible_hit_and_run"],
                _cam_id,
            )
            # Hit-and-run results already require a measured impact and an
            # observed fleeing/stationary phase; don't require repeated frames.
            confirmed.extend(already_temporal)

            # ── For each confirmed alert ──────────────────────────────────────
            active_alert_data = []
            for result in confirmed:
                # Trust adjuster (F18) — skip if dismiss rate too high
                if trust_adjuster.should_suppress(_cam_id, result.rule_type):
                    continue

                active_alert_data.append({
                    "track_ids": result.track_ids,
                    "rule_type": result.rule_type,
                })
                asyncio.create_task(
                    save_and_notify(
                        result, frame.copy(), _cam_name, clip_saver, face_blur,
                        audio_detector, captured_at=timestamp, event_camera_id=_cam_id,
                    )
                )

            # ── Draw overlays, push to stream, display ─────────────────────────
            annotated = draw_overlays(
                frame.copy(), tracks, active_alert_data, raw_detections=all_detections
            )
            # Resize for dashboard streaming to reduce lag
            stream_frame = cv2.resize(annotated, (640, 360))
            _, jpeg = cv2.imencode('.jpg', stream_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            frame_registry[_cam_id] = jpeg.tobytes()

            # Remove cv2.imshow as it blocks the thread and lags the dashboard.
            # You can now view everything smoothly on the dashboard.

            # ── FPS counter ───────────────────────────────────────────────────
            fps_counter += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 5.0:
                fps = fps_counter / elapsed
                pipeline_status[_cam_id]["fps"] = fps
                pipeline_status[_cam_id]["last_frame_at"] = timestamp
                logger.info(f"[{_cam_id}] FPS: {fps:.1f} | Tracks: {len(tracks)} | Frame: {frame_idx}")
                fps_counter, fps_timer = 0, time.time()

            # Yield to event loop so WebSocket and other cameras can run
            await asyncio.sleep(0.01)

    # Stop audio detector
    audio_detector.stop()
    frame_registry.pop(_cam_id, None)
    pipeline_status[_cam_id]["status"] = "stopped"
    logger.info(f"Pipeline stopped for {_cam_id}.")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
