# Feature PRD
## New Differentiator Features: Abandoned/Lost Person Detection + Sound-Based Distress Detection
**Parent system:** SentryEye — Smart Suspicious Activity Detection System (PS 16)
**Status:** Proposed addition on top of existing shipped core (detection, tracking, loitering, zone intrusion, trailing, crowd density)

---

## 1. Why These Features

Your existing rule set (loitering, zone intrusion, trailing, crowd density) is solid but matches what most
competing teams will also build. These two features were selected because they are:
- **Low build risk** — reuse your existing tracking/alert infrastructure, no new heavy models required
- **Genuinely under-built** — most surveillance projects don't attempt either
- **Additive, not replacing** — your current demo stays fully functional regardless of these shipping
- **Multi-modal (Feature B)** — makes the system structurally different, not just "one more rule"

---

## FEATURE A: Abandoned / Lost Person Detection

### A.1 Problem Statement
Public-safety incidents involving unaccompanied children, elderly persons, or persons with disabilities
left alone in a public space for an extended period are common and under-addressed by existing
"suspicious activity" systems, which focus on threats *caused by* a person rather than risk *to* a person.
Current abandoned-object detection in the market (and in this project) only considers bags/items — never
people.

### A.2 Goal
Detect when a small-stature individual (heuristic proxy for a child) — or any individual flagged as
vulnerable — remains in a defined area without a consistently associated adult-sized companion track
for longer than a configurable threshold, and raise a distinct alert category for it.

### A.3 User Story
> As a control room operator, I want to be notified when a child or vulnerable person appears to be
> alone in a monitored area for too long, so that personnel can check on them before the situation
> escalates (lost child, medical issue, abduction risk).

### A.4 Functional Requirements

| ID | Requirement |
|---|---|
| FA-1 | System shall classify tracked person instances into a size-based category (e.g., "small-stature" vs "adult-stature") using bounding-box height/aspect-ratio heuristics relative to camera calibration |
| FA-2 | System shall maintain, for each small-stature track, a rolling check of whether any adult-stature track remains within a configurable proximity radius |
| FA-3 | If no qualifying adult track is within proximity for more than `threshold_seconds` (default: 90s, configurable per zone), system shall raise an "Unaccompanied Person" alert |
| FA-4 | Alert shall include last-known-accompanied timestamp (if any adult was ever near this track) to help responders assess how long the person has been alone |
| FA-5 | Feature shall reuse existing temporal smoothing (N-of-M frame confirmation) to avoid false triggers from brief visual occlusion |
| FA-6 | Feature shall be rule-based only — no new ML model required beyond the existing YOLOv8 + tracker pipeline already in production |

### A.5 Non-Functional Requirements
- Must not require any new model weights — implemented entirely as logic on top of existing `track_id`, `bbox`, and trajectory history
- Height/stature classification must be configurable per camera (camera distance/angle changes what "small" means in pixel terms) — store a per-camera calibration value, not a global constant
- Must degrade gracefully: if stature classification is ambiguous (confidence low), do not raise this alert type rather than risk false positives

### A.6 Explicit Limitations (state this honestly in the pitch)
- This is a **heuristic proxy**, not true age detection — a short adult could be misclassified as "small-stature." This is acceptable for a prototype if framed honestly; do not claim it as "child detection."
- Works best in low-to-medium crowd density; in dense crowds, proximity-based "accompaniment" logic becomes noisy — scope the demo to appropriate test footage.

### A.7 Data Model Addition

```
Table: track_classifications
| Column          | Type     | Notes                                   |
|------------------|----------|------------------------------------------|
| track_id         | INTEGER  | FK -> tracks.id                          |
| stature_class    | TEXT     | "small" / "adult" / "ambiguous"          |
| confidence       | FLOAT    |                                           |
| camera_calib_ref | TEXT     | FK -> camera calibration config          |

Table: unaccompanied_events (extends existing `events` table via rule_type = "unaccompanied_person")
| Column                  | Type      | Notes                                      |
|--------------------------|-----------|----------------------------------------------|
| track_id                 | INTEGER   | the unaccompanied (small-stature) track      |
| last_adult_seen_at       | TIMESTAMP | nullable, last time an adult track was near  |
| duration_alone_seconds   | INTEGER   |                                                |
```

### A.8 API Addition
```
GET /alerts?rule_type=unaccompanied_person
```
Returns same alert shape as existing `/alerts`, with `duration_alone_seconds` and `last_adult_seen_at`
included in the payload for the Explainability Panel.

### A.9 Acceptance Criteria
- [ ] A small-stature track with no adult-stature track within radius R for > threshold triggers exactly one alert (not repeated spam, respecting existing cooldown logic)
- [ ] Alert correctly reports how long the person has been without a companion
- [ ] No new model download/training required to demo this feature
- [ ] False trigger rate on test footage with accompanied children is near zero (adult proximity correctly suppresses the alert)

---

## FEATURE B: Sound-Based Distress Detection

### B.1 Problem Statement
All current detection (yours and competing projects) is purely visual. Incidents are frequently missed
due to camera blind spots, occlusion, poor lighting, or the camera simply not being angled toward the
event — but audio (a scream, breaking glass, a gunshot-like sound) often still reaches a nearby
microphone even when the camera can't see the event clearly.

### B.2 Goal
Run a lightweight, pretrained audio event classifier in parallel with the video pipeline to detect
distress-indicative sounds, and fuse this signal with the existing visual rule engine for a combined,
higher-confidence alert — or a standalone lower-confidence alert when vision has no corroborating signal.

### B.3 User Story
> As a control room operator, I want to be alerted to screams or violent sounds even if the camera
> doesn't have a clear view of what caused them, so I don't miss incidents that happen just outside
> frame or in poor lighting.

### B.4 Functional Requirements

| ID | Requirement |
|---|---|
| FB-1 | System shall ingest an audio stream (from camera mic or a separate connected microphone) in parallel with the video stream for each camera that has audio capability |
| FB-2 | System shall run a pretrained audio event classifier (YAMNet, via TensorFlow Hub) on rolling short audio windows (e.g., 1–2 seconds) |
| FB-3 | System shall map YAMNet's output classes to a "distress" category set (e.g., Screaming, Shout, Glass, Gunshot/gunfire) with a configurable confidence threshold |
| FB-4 | If a distress-class sound is detected with confidence above threshold, system shall raise an alert, timestamped and linked to the nearest camera/zone |
| FB-5 | If a visual rule (e.g., fight/violence heuristic, crowd alert) fires within the same time window AND on the same camera, system shall raise the fused alert at a higher severity tier than either signal alone (multi-signal fusion, consistent with existing fusion logic) |
| FB-6 | If no corresponding visual signal exists, system shall still raise a standalone "Audio Distress — Unconfirmed Visually" alert at a lower default severity, flagged for human review |

### B.5 Non-Functional Requirements
- YAMNet is pretrained — no training/fine-tuning required for v1
- Audio processing must run independently of the video detection loop so an audio spike doesn't block/slow frame processing (separate thread/process)
- Must handle cameras without audio capability gracefully (feature simply inactive for that camera, not an error state)

### B.6 Explicit Limitations (state this honestly in the pitch)
- Ambient noise (traffic, construction, crowd cheering) can trigger false positives on sound classifiers — this is a known limitation of all audio event detection, not unique to your implementation. Mitigate with confidence thresholding and the same temporal-smoothing pattern used elsewhere (require 2 of 3 consecutive audio windows to agree).
- Only cameras with an attached/compatible microphone benefit from this — be upfront that this is hardware-dependent and won't apply to every camera in a real deployment.
- This is genuinely useful as a **corroborating signal**, not a sole trigger for high-severity response — frame it that way to judges.

### B.7 Data Model Addition

```
Table: audio_events
| Column          | Type      | Notes                                        |
|------------------|-----------|-------------------------------------------------|
| id               | TEXT (PK) |                                                  |
| camera_id        | TEXT      | FK -> cameras.id                                |
| sound_class      | TEXT      | e.g. "Screaming", "Glass", "Gunshot"            |
| confidence       | FLOAT     |                                                  |
| timestamp        | TIMESTAMP |                                                  |
| fused_event_id   | TEXT      | nullable, FK -> events.id if fused with visual  |
```

### B.8 API Addition
```
GET /audio-events?camera_id=&from_date=&to_date=
```
Returns audio-only detections, independent of or linked to visual `events`.

### B.9 Acceptance Criteria
- [ ] YAMNet runs on a test audio clip containing a scream and correctly flags it above threshold
- [ ] A fused event (simultaneous visual + audio trigger) is logged with higher severity than either alone
- [ ] A standalone audio-only alert is clearly labeled "unconfirmed visually" in the dashboard
- [ ] Feature does not reduce video pipeline FPS by more than ~5% (runs on a separate thread)

---

## 2. Build Sequencing (slot into existing `06_DEVELOPMENT_ROADMAP.md`)

Add as **Phase 5.5 — New Differentiators**, after your existing Phase 5:

- [ ] Implement `track_classifications` stature heuristic + `unaccompanied_events` logic (Feature A) — est. 0.5–1 day, no new model
- [ ] Integrate YAMNet via TensorFlow Hub, build audio ingestion thread (Feature B) — est. 1 day
- [ ] Wire both into existing alert/notification/DB pipeline (reuse `alerts/`, `storage/db.py`) — est. 0.5 day
- [ ] Add both alert types to dashboard + Explainability Panel rendering — est. 0.5 day
- [ ] Prepare and test demo clips: one clearly showing unaccompanied child scenario, one with a scream/distress sound cue — est. 0.5 day

**Total estimated effort: ~3 days**, assuming your core pipeline (already shipped) is stable.

---

## 3. Pitch Framing (use this language with judges)

> "Beyond standard behavior rules, we added two safety-focused features most surveillance systems miss
> entirely: detecting when a vulnerable person appears to be left alone in public, and a sound-based
> distress layer that catches incidents our cameras might miss due to blind spots or poor lighting —
> making our system multi-modal, not purely vision-based."

Follow immediately with the honest limitation line for each (stature heuristic ≠ age detection; audio
is a corroborating signal, not a sole trigger) — stating limitations unprompted builds more credibility
with technical judges than waiting for them to find the gap.
