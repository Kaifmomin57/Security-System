# Feature Specification
## SentryEye — Smart Suspicious Activity Detection System

Each feature below includes: description, inputs, logic/model used, output, and acceptance criteria —
written so an agentic coding tool (e.g., Antigravity) can generate the corresponding module directly.

---

## CORE FEATURES (v1 — build first)

### F1. Person/Object Detection + Tracking
- **Uses:** YOLOv8 (model) + ByteTrack/DeepSORT (tracking)
- **Input:** video frame (numpy array)
- **Output:** list of `{track_id, class, bbox, confidence}` per frame
- **Acceptance criteria:** same physical person retains the same `track_id` across at least 95% of consecutive frames while continuously in view

### F2. Loitering Detection
- **Uses:** Rule-based logic (no model beyond F1's output)
- **Input:** track history (positions over time) + zone polygon config
- **Logic:** if `track_id` centroid remains inside zone polygon for > `threshold_seconds` (configurable per zone) → candidate alert
- **Output:** `{track_id, zone_id, dwell_time, confidence}`
- **Acceptance criteria:** triggers only after sustained presence, not a single-frame overlap

### F3. Trailing / Stalking Pattern Detection
- **Uses:** Rule-based trajectory logic (no model beyond F1)
- **Input:** trajectories of ≥2 tracked IDs over a rolling time window + ambient person-count in area
- **Logic:** flag if `track_B` maintains a roughly fixed following distance behind `track_A` for > `duration_threshold`, AND total person-count in the zone is below a "low activity" threshold during that window
- **Output:** `{track_A_id, track_B_id, duration, avg_distance, confidence}`
- **Explicit constraint:** logic must NOT use any demographic/gender attribute — trajectory and timing only

### F4. Real-Time Alert Pipeline
- **Uses:** Rule-based + integration code (no model)
- **Input:** confirmed rule output from fusion layer
- **Logic:** push to WebSocket (dashboard) and Telegram Bot API simultaneously
- **Output:** delivered notification with snapshot, timestamp, camera ID, rule type
- **Acceptance criteria:** delivery within 5 seconds of confirmation

### F5. Multi-Signal Fusion + Temporal Smoothing
- **Uses:** Rule-based logic (no model)
- **Input:** raw rule outputs per frame
- **Logic:**
  - Temporal smoothing: require the same rule to fire on ≥ N consecutive evaluations (e.g., 5 of last 8 frames) before confirming
  - Multi-signal fusion: combine ≥2 independent signals (e.g., zone + dwell time + low ambient traffic) before raising severity above "Low"
- **Output:** confirmed/unconfirmed boolean + combined confidence score
- **Acceptance criteria:** single-frame flicker detections must never reach the notification layer

### F6. Continuous Monitoring Dashboard
- **Uses:** Frontend + backend integration (no model)
- **Logic:** grid of camera feeds; feed with active alert auto-highlighted/enlarged, others shown as muted thumbnails
- **Acceptance criteria:** runs for ≥8 hours on test loop without memory growth beyond a fixed bound

### F7. Event Logging Database
- **Uses:** Rule-based / DB logic (no model)
- **Input:** confirmed alert object
- **Output:** DB row with `timestamp, camera_id, rule_type, confidence, snapshot_path, status`
- **Acceptance criteria:** every confirmed alert has exactly one corresponding DB row; queryable by date/camera/type

---

## SECONDARY FEATURES (v1.1)

### F8. Restricted Zone / Tripwire Intrusion
- **Uses:** Rule-based (uses F1 output)
- **Logic:** line-crossing detection — check if centroid trajectory crosses a defined line segment

### F9. Abandoned Object Detection
- **Uses:** YOLOv8 (needs object classes like bag/suitcase) + rule logic
- **Logic:** object detected with no associated "person" track within radius R for > threshold_seconds

### F10. Severity Tiering
- **Uses:** Rule-based (if/else on confidence + rule type, no model)

### F11. Alert Lifecycle Tracking
- **Uses:** Backend state machine (no model) — `New → Acknowledged → Resolved`

### F12. Rolling Context Buffer
- **Uses:** Engineering logic (deque buffer in memory, no model) — saves last 15s before + after trigger

### F13. Zone-Configurable Rule Editor
- **Uses:** Frontend (canvas polygon drawing) + backend config storage (no model)

---

## DIFFERENTIATOR FEATURES (pick 2-3 to actually build)

### F14. Per-Camera Adaptive Baseline
- **Uses:** Lightweight unsupervised model (e.g., simple statistical model or small autoencoder on dwell-time/footfall distributions)
- **Logic:** learn each camera's typical footfall/dwell-time distribution over a configurable window (e.g., first N hours of footage); flag behavior that deviates significantly (e.g., z-score beyond threshold) instead of using one global constant

### F15. Local-Language Voice/Push Alerts
- **Uses:** Rule-based + TTS integration (e.g., gTTS or any local-language TTS library), no detection model
- **Logic:** convert alert text to speech in configured local language, push via mobile notification/app

### F16. Tamper-Proof Evidence Hashing
- **Uses:** Pure backend (`hashlib.sha256`), no model
- **Logic:** hash saved clip/snapshot bytes at save time, store hash alongside DB record

### F17. Offline-First / Edge Fallback
- **Uses:** Engineering/infra logic, no model
- **Logic:** local SQLite queue for alerts when network unreachable; background sync job on reconnect

### F18. Self-Correcting Alert Trust
- **Uses:** Rule-based statistics (no model)
- **Logic:** track dismiss-rate per `(camera_id, rule_type)`; if dismiss-rate > threshold over rolling window, automatically raise that rule's confirmation threshold for that camera

### F19. Privacy-by-Design (Face Blur)
- **Uses:** Lightweight face detector (Haar Cascade or MediaPipe Face Detection) + OpenCV blur, not a "heavy" model
- **Logic:** blur all detected faces in stored clips by default; unblur only on operator-confirmed high-severity incident with logged justification

### F20. Explainability Panel
- **Uses:** Frontend + metadata already generated by rule engine (no model)
- **Logic:** render the triggering zone polygon, trajectory path, and rule name alongside the alert

---

## STRETCH / ROADMAP (mention, don't over-promise)

### F21. Fighting/Violence Detection
- **Uses:** MediaPipe Pose + heuristic (limb velocity between close tracks) OR fine-tuned action-recognition model (I3D/SlowFast on RWF-2000)

### F22. Weapon/Malicious Object Detection
- **Uses:** Fine-tuned YOLOv8 on open weapon-detection dataset — flag for human review only, never auto-escalate

### F23. Cross-Camera Re-Identification
- **Uses:** Appearance embedding model (OSNet/ResNet-based Re-ID)
- **Logic:** cosine similarity match against recent gallery; always shown as "possible match: X% confidence" requiring human confirmation

### F24. Generalized Anomaly Detection
- **Uses:** Autoencoder trained on per-scene "normal" footage; flags high reconstruction error as anomalous

---

## Summary: Model Dependency Matrix

| Needs YOLO | Needs other model | Pure rule/engineering |
|---|---|---|
| F1, F9, F22 | F14 (stats/autoencoder), F19 (face detector), F21 (pose), F23 (Re-ID), F24 (autoencoder) | F2, F3, F4, F5, F6, F7, F8, F10, F11, F12, F13, F15, F16, F17, F18, F20 |
