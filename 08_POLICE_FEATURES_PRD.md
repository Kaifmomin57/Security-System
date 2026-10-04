# Feature PRD
## Police Department Features
**Parent system:** SentryEye — Smart Suspicious Activity Detection System (PS 16)
**Status:** Proposed addition on top of existing shipped core (detection, tracking, loitering, zone intrusion, trailing, crowd density, evidence clip+snapshot, face blur, PostgreSQL backend, dashboard)

This PRD covers 6 features selected for police department use:
1. Historical Incident Heatmap
2. Auto-Generated Incident Report
3. ANPR (Automatic Number Plate Recognition) + Watchlist Match
4. Court-Admissible Evidence Export Package
5. Traffic Violation Detection
6. Hit-and-Run Detection

---

## FEATURE 1: Historical Incident Heatmap

### 1.1 Problem Statement
Police currently decide patrol routes based on experience and manual incident records, not on
aggregated data from automated systems. Your system already logs every confirmed alert with
timestamp, camera/zone, and rule type — this data is never reused after the alert is handled.

### 1.2 Goal
Aggregate historical `events` data to show which zones are riskiest at which times, so patrol
deployment can shift from reactive to data-informed.

### 1.3 User Story
> As a station in-charge, I want to see which areas and times have the most incidents, so I can
> assign patrol staff to high-risk zones at the right hours instead of spreading them evenly.

### 1.4 Functional Requirements

| ID | Requirement |
|---|---|
| FR1-1 | System shall aggregate all records in `events` table grouped by `zone_id`/`camera_id` and hour-of-day over a configurable date range |
| FR1-2 | System shall render a heatmap view: X-axis = hour of day (0–23), Y-axis = zone/camera, color intensity = alert count |
| FR1-3 | System shall support filtering by `rule_type` (e.g., show heatmap for only "loitering" or only "crowd density") |
| FR1-4 | System shall support a map-overlay view if camera GPS coordinates are available, otherwise fall back to a grid/table view by zone name |
| FR1-5 | System shall allow export of the heatmap data as CSV for offline reporting to senior officers |

### 1.5 Non-Functional Requirements
- Must not require any new ML model — pure aggregation query on existing `events` table
- Query must be performant on at least 6 months of event history (add DB index on `timestamp`, `zone_id` if not already present)
- Heatmap should load within 2–3 seconds for a typical date range (1 month)

### 1.6 Data Model
No new tables required. Add indexes to existing `events` table:
```sql
CREATE INDEX idx_events_zone_time ON events (zone_id, timestamp);
CREATE INDEX idx_events_camera_time ON events (camera_id, timestamp);
```

### 1.7 API Addition
```
GET /analytics/heatmap?from_date=&to_date=&rule_type=&camera_id=
```
Response:
```json
{
  "zones": [
    { "zone_id": "zone_12", "zone_name": "ATM Entrance", "hourly_counts": [0,0,1,3,5,2,...] }
  ]
}
```

### 1.8 Acceptance Criteria
- [ ] Heatmap correctly reflects actual counts from `events` table for a known test date range
- [ ] Filtering by rule type changes the displayed data correctly
- [ ] CSV export matches what's shown on screen

---

## FEATURE 2: Auto-Generated Incident Report

### 2.1 Problem Statement
When an officer needs to file a report on an incident (for internal records or as a preliminary
note toward an FIR/daily diary entry), they currently have to manually note down time, location,
and details — time-consuming and error-prone when done from memory after the fact.

### 2.2 Goal
When an alert is marked "Confirmed" by an operator, auto-generate a structured, human-readable
report document pre-filled with all data the system already has.

### 2.3 User Story
> As a control room operator, when I confirm an incident, I want a ready-made report with all the
> facts already filled in, so I only need to add my own notes instead of writing everything from scratch.

### 2.4 Functional Requirements

| ID | Requirement |
|---|---|
| FR2-1 | On `PATCH /alerts/{id}` with `status=confirmed`, system shall auto-generate a report document (PDF) |
| FR2-2 | Report shall include: incident ID, date/time, camera/zone name + location description, rule type triggered, confidence score, snapshot image, link/QR to evidence clip, and the operator's name/ID |
| FR2-3 | Report shall include an empty "Officer Notes" section for the responding officer to fill in manually (printed or digital) |
| FR2-4 | Report shall be stored and retrievable via the dashboard, linked to the original event record |
| FR2-5 | Report format shall be a standard template (not AI-generated prose) to ensure consistency and avoid hallucinated details — this is a templated document fill, not a generative-text feature |

### 2.5 Non-Functional Requirements
- No LLM/generative text required — this is a template-fill operation using data already in the `events` table, which keeps it fast, free, and fully accurate (no hallucination risk)
- PDF generation should complete within 2 seconds of confirmation

### 2.6 Data Model
```
Table: incident_reports
| Column          | Type      | Notes                                  |
|------------------|-----------|-------------------------------------------|
| id               | TEXT (PK) |                                            |
| event_id         | TEXT      | FK -> events.id                           |
| generated_at     | TIMESTAMP |                                            |
| report_pdf_path  | TEXT      |                                            |
| officer_notes    | TEXT      | nullable, filled in later                 |
```

### 2.7 API Addition
```
GET /reports/{event_id}        -> returns report metadata + PDF link
PATCH /reports/{event_id}      -> body: { "officer_notes": "..." }, updates notes
```

### 2.8 Acceptance Criteria
- [ ] Confirming an alert produces a PDF within 2 seconds containing all required fields correctly pulled from the event record
- [ ] Report PDF includes a clickable/scanned reference to the evidence clip (see Feature 4)
- [ ] Officer notes can be added after generation without regenerating the whole report

---

## FEATURE 3: ANPR (Automatic Number Plate Recognition) + Watchlist Match

### 3.1 Problem Statement
Police need to identify stolen or wanted vehicles passing through monitored areas. Manual checking
is impossible at scale; this is a well-established, high-value automation use case.

### 3.2 Goal
Detect and read vehicle number plates from camera feeds and match them against a configurable
watchlist of flagged vehicle numbers.

### 3.3 User Story
> As a traffic/patrol officer, I want to be alerted automatically when a stolen or wanted vehicle's
> number plate is seen on any monitored camera, so I can respond immediately.

### 3.4 Functional Requirements

| ID | Requirement |
|---|---|
| FR3-1 | System shall detect vehicle objects in frame (reuse existing YOLOv8 COCO classes: car, truck, motorcycle, bus) |
| FR3-2 | System shall run a plate-detection + OCR step on detected vehicle regions (pretrained model, e.g., OpenALPR or a YOLO-based plate detector + Tesseract/EasyOCR for character recognition) |
| FR3-3 | System shall normalize and compare the read plate number against a configurable `watchlist` table |
| FR3-4 | On a match, system shall raise a high-severity alert with the vehicle snapshot, read plate number, matched watchlist reason (e.g., "Reported Stolen"), camera, and timestamp |
| FR3-5 | System shall log low-confidence OCR reads separately (not auto-alerted) for optional manual review, to avoid false alerts from misread characters |

### 3.5 Non-Functional Requirements
- Plate detection + OCR accuracy depends heavily on camera resolution/angle — be upfront that this needs a reasonably clear, front/rear-facing camera angle, not an arbitrary CCTV angle
- OCR confidence threshold must be configurable; default conservative to avoid false watchlist matches

### 3.6 Explicit Limitations (state honestly)
- OCR accuracy on low-resolution or angled CCTV footage is a known weak point industry-wide, not unique to this implementation — frame this as "effective at dedicated traffic/entry-point cameras," not every camera in the network
- This is a pretrained-model integration for the prototype, not a custom-trained plate reader — acceptable and expected for a hackathon demo

### 3.7 Data Model
```
Table: watchlist_vehicles
| Column        | Type      | Notes                                |
|----------------|-----------|------------------------------------------|
| plate_number   | TEXT (PK) | normalized format                        |
| reason         | TEXT      | "Stolen" / "Wanted" / "Other"            |
| added_by       | TEXT      |                                            |
| added_at       | TIMESTAMP |                                            |

Table: plate_reads
| Column        | Type      | Notes                                |
|----------------|-----------|------------------------------------------|
| id             | TEXT (PK) |                                            |
| camera_id      | TEXT      | FK -> cameras.id                         |
| plate_number   | TEXT      |                                            |
| ocr_confidence | FLOAT     |                                            |
| matched        | BOOLEAN   |                                            |
| timestamp      | TIMESTAMP |                                            |
```

### 3.8 API Addition
```
POST /watchlist         -> add a plate to watchlist
GET /watchlist          -> list watchlist entries
GET /plate-reads?matched=true&from_date=&to_date=
```

### 3.9 Acceptance Criteria
- [ ] A test vehicle with a known plate in the watchlist triggers a high-severity alert when it appears in test footage
- [ ] Low-confidence reads do not generate alerts, only logged entries
- [ ] False-match rate on a test set of non-watchlisted plates is reasonably low for a clear, front-facing test clip

---

## FEATURE 4: Court-Admissible Evidence Export Package

### 4.1 Problem Statement
CCTV footage used as evidence is frequently challenged in court due to lack of documented integrity
(no proof the footage wasn't altered, no clear chain of custody of who accessed it). Your system
already saves clips and computes a SHA-256 hash — this feature formalizes that into a usable package.

### 4.2 Goal
Provide a one-click export of a signed, self-contained evidence bundle for any confirmed incident,
including integrity proof and access history.

### 4.3 User Story
> As an investigating officer, I want to export a single package for an incident that contains the
> video, snapshot, and proof it hasn't been tampered with, so I can submit it as supporting evidence.

### 4.4 Functional Requirements

| ID | Requirement |
|---|---|
| FR4-1 | System shall allow export of a ZIP package per `event_id` containing: evidence clip (.mp4), snapshot (.jpg), a metadata file (JSON: timestamps, rule triggered, confidence, camera ID, zone), and the SHA-256 hash of the original clip file |
| FR4-2 | System shall log every export action (who exported, when) into a chain-of-custody log tied to the event |
| FR4-3 | System shall include the chain-of-custody log (all views/exports of this evidence) inside the exported package as a text/PDF file |
| FR4-4 | System shall verify the stored clip's current hash matches the originally computed hash at export time, and flag a warning in the package if they don't match (integrity check) |

### 4.5 Non-Functional Requirements
- No new model required — this is backend file-packaging + logging logic on data you already generate (Feature A16 — evidence hashing — from the original roadmap)
- Export operation should not modify the original stored clip/snapshot files

### 4.6 Data Model
```
Table: evidence_access_log
| Column       | Type      | Notes                                   |
|---------------|-----------|---------------------------------------------|
| id            | TEXT (PK) |                                               |
| event_id      | TEXT      | FK -> events.id                             |
| action        | TEXT      | "viewed" / "exported"                       |
| user_id       | TEXT      | who performed the action                    |
| timestamp     | TIMESTAMP |                                               |
```

### 4.7 API Addition
```
POST /events/{id}/export-evidence   -> generates and returns the ZIP package, logs the export
GET /events/{id}/custody-log         -> returns full access history
```

### 4.8 Acceptance Criteria
- [ ] Exported ZIP contains all required files and a correctly matching hash
- [ ] Every export action is recorded in `evidence_access_log`
- [ ] If a clip file is manually altered after the fact (test by modifying the file), the integrity check correctly flags a mismatch on next export

---

## FEATURE 5: Traffic Violation Detection

### 5.1 Problem Statement
Traffic police manually monitor junctions for signal jumping and wrong-side driving, which doesn't
scale across many junctions simultaneously.

### 5.2 Goal
Automatically detect signal-jumping and wrong-side-driving violations at monitored junctions using
existing detection + tracking infrastructure.

### 5.3 User Story
> As a traffic police officer, I want the system to automatically flag vehicles that jump a red
> signal or drive on the wrong side, so violations can be reviewed and challaned without someone
> watching the junction live.

### 5.4 Functional Requirements

| ID | Requirement |
|---|---|
| FR5-1 | System shall detect vehicle objects (reuse existing YOLOv8 COCO classes) at a configured junction camera |
| FR5-2 | System shall support a configurable "stop line" per junction (reuse existing zone/line-crossing logic from Zone Intrusion feature) |
| FR5-3 | System shall accept a signal-state input — either manual toggle (for prototype) or integration with an existing signal controller (future) — to know when the signal is red |
| FR5-4 | If a vehicle track crosses the stop line while the signal is red, system shall raise a "Signal Jump" violation with vehicle snapshot, plate read (if ANPR available), timestamp |
| FR5-5 | System shall detect wrong-side driving by comparing a vehicle track's direction vector against the expected lane direction (configured per lane); sustained movement against expected direction for > N frames raises a "Wrong Side Driving" violation |

### 5.5 Non-Functional Requirements
- Reuses existing line-crossing and trajectory-direction logic already built for Zone Intrusion and Trailing rules — no new model required beyond vehicle detection (already available via COCO classes)
- Signal-state input is the main missing piece for a full production system — for a prototype demo, a manual/simulated signal state toggle is acceptable and should be stated as such

### 5.6 Data Model
```
Table: traffic_violations (extends `events` via rule_type = "signal_jump" / "wrong_side")
| Column        | Type      | Notes                                |
|----------------|-----------|------------------------------------------|
| event_id       | TEXT      | FK -> events.id                          |
| junction_id    | TEXT      | FK -> cameras.id or a dedicated junctions table |
| plate_number   | TEXT      | nullable, if ANPR matched the vehicle    |
| violation_type | TEXT      | "signal_jump" / "wrong_side"             |
```

### 5.7 Acceptance Criteria
- [ ] A test vehicle crossing the stop line during a simulated red signal is correctly flagged
- [ ] A test vehicle moving against configured lane direction for a sustained period is correctly flagged
- [ ] Violations correctly link to a plate read when ANPR (Feature 3) is also active on that camera

---

## FEATURE 6: Hit-and-Run Detection

### 6.1 Problem Statement
Hit-and-run incidents require quick identification of the fleeing vehicle; manual footage review
after the fact is slow, and the vehicle may already be far away before anyone reviews the tape.

### 6.2 Goal
Detect a collision-like event pattern (sudden simultaneous motion disruption between two tracks)
followed by one track fleeing at high speed, and raise an immediate high-severity alert.

### 6.3 User Story
> As a traffic/patrol officer, I want to be alerted in real time when a collision appears to have
> happened and the vehicle is fleeing, so I can respond immediately rather than reviewing footage later.

### 6.4 Functional Requirements

| ID | Requirement |
|---|---|
| FR6-1 | System shall monitor pairs of nearby tracks (vehicle-vehicle or vehicle-person) for a sudden, simultaneous sharp drop in speed and/or abrupt direction change — a collision-pattern signature |
| FR6-2 | Following a detected collision-pattern signature, system shall monitor involved tracks for the next N seconds |
| FR6-3 | If one involved track resumes movement at above-normal speed and leaves the frame without stopping, while the other track remains stationary/down, system shall raise a "Possible Hit-and-Run" alert at high severity |
| FR6-4 | Alert shall include the pre/post-event clip (reuse existing rolling buffer feature), snapshot of both tracks at the moment of the collision-pattern, and plate read of the fleeing vehicle if ANPR (Feature 3) is active on that camera |

### 6.5 Non-Functional Requirements
- Reuses existing tracking, rolling buffer, and (optionally) ANPR infrastructure — no new detection model required, only new trajectory/velocity rule logic
- This is a heuristic pattern-match, not a certified collision-detection system — frame honestly as "flags for human review," not an automatic legal determination

### 6.6 Explicit Limitations (state honestly)
- Camera angle and frame rate significantly affect reliability of velocity-based collision detection — works best on a clear, moderately wide junction/road view, not a narrow or obstructed angle
- False positives can occur from vehicles stopping normally (e.g., for a pedestrian) near another vehicle — multi-signal confirmation (both sudden stop AND one party fleeing fast) is what keeps this usable; either signal alone is not sufficient

### 6.7 Data Model
```
Table: collision_events (extends `events` via rule_type = "possible_hit_and_run")
| Column            | Type      | Notes                                  |
|---------------------|-----------|---------------------------------------------|
| event_id            | TEXT      | FK -> events.id                             |
| track_id_fleeing    | INTEGER   |                                               |
| track_id_stationary | INTEGER   |                                               |
| plate_number        | TEXT      | nullable, if ANPR matched the fleeing vehicle |
```

### 6.8 Acceptance Criteria
- [ ] Test clip showing a staged collision + one vehicle fleeing correctly triggers the alert
- [ ] Test clip showing a normal stop-and-go (no fleeing) does NOT trigger a false alert
- [ ] Alert includes correct pre/post clip and both involved track snapshots

---

## Build Sequencing (slot into `06_DEVELOPMENT_ROADMAP.md`)

Add as **Phase 7 — Police Department Features**, after your existing phases:

| Feature | New Model Needed? | Est. Effort |
|---|---|---|
| 1. Heatmap | No | 0.5 day |
| 2. Auto Report | No | 0.5–1 day |
| 4. Evidence Export Package | No | 0.5–1 day |
| 3. ANPR + Watchlist | Yes (pretrained plate detector + OCR) | 1–1.5 days |
| 5. Traffic Violation | No (reuses existing logic) | 1 day |
| 6. Hit-and-Run | No (reuses existing logic) | 1 day |

**Recommended build order:** 1 → 2 → 4 (no new models, fastest wins) → 5 → 6 (reuse logic) → 3 (ANPR last, since it needs a new pretrained component and the most specific camera-angle conditions to demo well).

**Total estimated effort: ~5–6 days.** If time is short, Features 1, 2, and 4 alone (no new models, ~1.5–2 days total) already give you a strong "we thought about real police workflow" story even without touching the vehicle-related features.

---

## Pitch Framing

> "Beyond detecting suspicious activity, we built features that fit directly into how police actually
> work day to day — a heatmap to plan patrols from real data, auto-generated reports to save officer
> time, evidence packages that hold up to scrutiny, and vehicle-focused detection for traffic violations
> and hit-and-run cases."

State the ANPR and Hit-and-Run limitations (camera angle dependency, heuristic not certified) upfront
in the same breath — this is consistent with how you've framed every other feature in this project,
and it reads as engineering maturity to judges rather than a weakness.
