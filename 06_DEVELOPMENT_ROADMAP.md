# Development Roadmap
## SentryEye — Phased Build Plan (for use with Antigravity or any agentic coding tool)

Feed each phase to the coding agent as a separate task/prompt, referencing the other docs
(`02_TECHNICAL_ARCHITECTURE.md`, `03_FEATURE_SPEC.md`, `04_API_SPEC.md`, `05_DATA_MODEL.md`)
as context so generated code matches the module structure and schema already defined.

---

## Phase 0 — Project Setup
- [ ] Initialize repo structure matching `02_TECHNICAL_ARCHITECTURE.md` module breakdown
- [ ] Set up Python virtual env, `requirements.txt` (ultralytics, opencv-python, fastapi, uvicorn,
      sqlalchemy, python-telegram-bot, deep-sort-realtime or bytetrack package, mediapipe)
- [ ] Set up React frontend scaffold (Vite + Tailwind)
- [ ] Initialize SQLite DB using schema in `05_DATA_MODEL.md`
- [ ] Get a test video file (sample CCTV-style footage) for local testing — no live camera dependency required yet

## Phase 1 — Detection & Tracking Core (F1)
- [ ] `detection/detector.py`: load YOLOv8n, run inference on a frame, return bboxes/classes/confidences
- [ ] `detection/tracker.py`: wrap ByteTrack/DeepSORT, assign persistent track_id to each detection
- [ ] `ingestion/stream_reader.py`: read from video file/RTSP, yield frames with frame-skip support
- [ ] `pipeline.py`: wire ingestion → detector → tracker, print track_id + bbox per frame as sanity check
- [ ] **Milestone check:** same person keeps the same ID across a test clip

## Phase 2 — Rule Engine (F2, F3, F5, F8)
- [ ] `rules/base_rule.py`: abstract class with `evaluate(track_history, config) -> (bool, confidence)`
- [ ] `rules/loitering_rule.py`: implement dwell-time-in-zone logic
- [ ] `rules/trailing_rule.py`: implement trajectory-following logic (identity-agnostic)
- [ ] `rules/zone_intrusion_rule.py`: implement line/polygon crossing logic
- [ ] `rules/fusion.py`: implement temporal smoothing (N-of-M frame confirmation) + multi-signal combination
- [ ] **Milestone check:** rules fire only on sustained behavior in test clips, not single-frame noise

## Phase 3 — Alerts & Storage (F4, F7, F10, F11, F16)
- [ ] `storage/db.py`: SQLAlchemy models matching `05_DATA_MODEL.md`
- [ ] `storage/clip_saver.py`: rolling buffer (deque), save pre/post-event clip on confirmed alert
- [ ] `evidence/hasher.py`: SHA-256 hash of saved clip, store alongside event record
- [ ] `alerts/severity.py`: map confidence + rule type → severity tier
- [ ] `alerts/notifier_telegram.py`: send alert text + snapshot to a Telegram bot/chat
- [ ] `api/routes_alerts.py`: implement `GET/PATCH /alerts` per `04_API_SPEC.md`
- [ ] **Milestone check:** confirmed rule trigger → DB row created → Telegram message received within 5s

## Phase 4 — Dashboard (F6, F13, F20)
- [ ] React: camera grid view, live feed thumbnails
- [ ] WebSocket client: subscribe to `/ws/alerts`, auto-highlight camera with active alert
- [ ] Incident timeline view: list/filter past events (`GET /events`)
- [ ] Explainability panel: render zone polygon + trajectory overlay on alert detail view
- [ ] Zone editor: canvas to draw polygon on a camera's reference frame, save via `POST /zones`
- [ ] **Milestone check:** full loop demoable — video plays, alert appears live on dashboard with explanation

## Phase 5 — Differentiators (pick 2-3 from F14–F19)
- [ ] F18 Self-correcting trust: `alert_feedback` table + dismiss-rate threshold adjustment logic
- [ ] F19 Privacy-by-design: face detector + blur applied to saved clips by default
- [ ] F16 already done in Phase 3 (evidence hashing)
- [ ] F14 Adaptive baseline (if time allows): compute per-camera mean/std dev of dwell times over
      a sample window, use as dynamic threshold instead of fixed constant
- [ ] **Milestone check:** at least 2 differentiators are visibly demoable, not just described in slides

## Phase 6 — Polish for Demo
- [ ] Prepare 2-3 test video clips that clearly trigger each implemented rule
- [ ] Rehearse live demo flow end-to-end (video → detection → alert → dashboard → explanation)
- [ ] Prepare fallback: screen-recorded demo video in case live run fails on stage
- [ ] Update `01_PRD.md` success metrics section with actual measured numbers from testing
- [ ] Finalize PPT using `03_FEATURE_SPEC.md` and `02_TECHNICAL_ARCHITECTURE.md` content

---

## Suggested Team Split (if multiple people)
| Person | Owns |
|---|---|
| A | Detection + Tracking (Phase 1) + Rule Engine (Phase 2) |
| B | Backend API + DB + Alerts (Phase 3) |
| C | Frontend Dashboard + Zone Editor (Phase 4) |
| D | Differentiator features (Phase 5) + demo prep/PPT (Phase 6) |

## Minimum Viable Demo (if time runs out)
Phases 0–3 alone give you a complete, PS-compliant, demoable system:
detection → rule-based alert → notification → logged event. Phase 4's dashboard can be as simple
as a single live video feed with an alert banner if frontend time is short — function over polish.
