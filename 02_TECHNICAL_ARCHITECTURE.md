# Technical Architecture
## SentryEye — Smart Suspicious Activity Detection System

---

## 1. High-Level Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              CAMERA LAYER                │
                    │   (IP cameras / recorded video files)    │
                    └───────────────────┬───────────────────────┘
                                        │ RTSP / file stream
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │          INGESTION & PREPROCESSING        │
                    │  - Frame extraction (OpenCV)              │
                    │  - Resize / frame-skip (perf control)     │
                    └───────────────────┬───────────────────────┘
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │           DETECTION & TRACKING            │
                    │  - YOLOv8 (person/object detection)        │
                    │  - DeepSORT / ByteTrack (tracking, IDs)    │
                    │  - MediaPipe Pose (optional: fall/fight)   │
                    └───────────────────┬───────────────────────┘
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │              RULE ENGINE                   │
                    │  - Loitering, zone intrusion, trailing     │
                    │  - Per-camera adaptive baselines           │
                    │  - Temporal smoothing + multi-signal fusion│
                    └───────────────────┬───────────────────────┘
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │           ALERT DECISION LAYER             │
                    │  - Severity scoring                         │
                    │  - Dismiss-rate trust adjustment            │
                    └───────────────────┬───────────────────────┘
                          ┌─────────────┼─────────────┐
                          ▼             ▼             ▼
                  ┌──────────┐  ┌──────────────┐  ┌───────────────┐
                  │ Dashboard │  │ Telegram/SMS  │  │ Event Logger   │
                  │ (React)   │  │ Notification  │  │ (DB + hashing) │
                  └──────────┘  └──────────────┘  └───────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Detection | YOLOv8 (Ultralytics) | Pretrained COCO weights for person/object; optional fine-tune for weapons |
| Tracking | DeepSORT or ByteTrack | ByteTrack preferred for robustness; DeepSORT simpler to integrate fast |
| Pose (optional) | MediaPipe Pose | Fall detection, fight detection heuristics |
| Backend | Python, FastAPI | Async-friendly for real-time pipeline + REST API |
| Realtime transport | WebSocket (FastAPI native) or MQTT (paho-mqtt) | Pushes live alerts to dashboard |
| Database | PostgreSQL (prod) / SQLite (hackathon demo) | Event + config storage |
| Frontend | React + Tailwind | Dashboard, zone editor, incident timeline |
| Notifications | Telegram Bot API (free, fast to set up) / Twilio (SMS, paid) | Telegram recommended for hackathon speed |
| Video handling | OpenCV | Frame I/O, drawing overlays |
| Storage | Local filesystem (demo) / S3-compatible (prod) | Saved clips/snapshots |
| Hashing | Python `hashlib` (SHA-256) | Evidence integrity |

---

## 3. Module Breakdown (for codegen / agentic tool task splitting)

```
sentryeye/
├── ingestion/
│   └── stream_reader.py        # reads camera/video, yields frames, handles frame-skip
├── detection/
│   ├── detector.py             # YOLOv8 wrapper, returns bounding boxes + classes
│   ├── tracker.py              # DeepSORT/ByteTrack wrapper, assigns persistent IDs
│   └── pose_estimator.py       # MediaPipe wrapper (optional module)
├── rules/
│   ├── base_rule.py            # abstract Rule class (evaluate(track_history) -> bool, confidence)
│   ├── loitering_rule.py
│   ├── zone_intrusion_rule.py
│   ├── trailing_rule.py
│   ├── crowd_rule.py
│   ├── fall_rule.py            # optional
│   └── fusion.py               # combines multiple rule outputs + temporal smoothing
├── baseline/
│   └── adaptive_baseline.py    # per-camera normal-behavior learner (differentiator #14)
├── alerts/
│   ├── severity.py             # confidence + rule type -> Low/Med/High
│   ├── trust_adjuster.py       # dismiss-rate based auto-suppression (differentiator #18)
│   ├── notifier_telegram.py
│   ├── notifier_sms.py
│   └── offline_queue.py        # queues alerts when network is down (differentiator #17)
├── privacy/
│   └── face_blur.py            # lightweight face detector + blur (differentiator #19)
├── evidence/
│   └── hasher.py                # SHA-256 hash on saved clips (differentiator #16)
├── storage/
│   ├── db.py                    # SQLAlchemy models + session
│   └── clip_saver.py             # rolling buffer, pre/post event clip saving
├── api/
│   ├── main.py                   # FastAPI app entrypoint
│   ├── routes_alerts.py
│   ├── routes_zones.py
│   ├── routes_events.py
│   └── websocket_manager.py
├── frontend/                     # React dashboard (separate build)
├── config/
│   └── zones.yaml / zones table  # per-camera zone + rule config
└── pipeline.py                   # orchestrates: ingestion -> detection -> rules -> alerts
```

---

## 4. Data Flow (per frame)

1. `stream_reader` yields a frame (with frame-skip applied for perf)
2. `detector` runs YOLOv8 → list of `(bbox, class, confidence)`
3. `tracker` matches detections to existing tracks → list of `(track_id, bbox, class)`
4. For each active rule in `rules/`, evaluate against the track's history (position over time, dwell time, trajectory)
5. `fusion.py` combines rule outputs; requires signal persistence across N frames before confirming
6. If confirmed: `severity.py` scores it, `trust_adjuster.py` checks historical dismiss-rate for this rule+camera, decides whether to suppress or send
7. If sending: `clip_saver` saves rolling buffer clip, `hasher` computes SHA-256, `face_blur` applied to stored clip (unless confirmed high-severity), event written to DB, notification dispatched, dashboard updated via WebSocket

---

## 5. Performance Considerations

- Run detection every Nth frame (e.g., every 3rd frame at 30fps) and interpolate tracking in between to hit near-real-time on CPU
- Use YOLOv8n (nano) model for hackathon demo — trades some accuracy for speed; mention YOLOv8m/l as production upgrade path
- Keep rolling buffer in memory (deque) rather than writing every frame to disk
- Batch DB writes where possible; only write on confirmed events, not every frame

---

## 6. Deployment Notes (for pitch credibility, not necessarily built)

- Edge deployment target: NVIDIA Jetson Nano/Orin for on-site inference without constant cloud dependency
- Offline-first: alerts queue locally (SQLite) and sync when connectivity returns
- Horizontal scaling: one pipeline instance per camera, alerts aggregated centrally via message queue (future: Kafka/RabbitMQ)
