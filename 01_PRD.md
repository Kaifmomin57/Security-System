# Product Requirements Document (PRD)
## SentryEye — Smart Suspicious Activity Detection System
**Problem Statement:** PS 16 | **Domain:** AI/ML, Computer Vision, Public Safety

---

## 1. Overview

SentryEye is a camera-based system that detects predefined suspicious or unusual activities in
police-monitored public areas and alerts authorized personnel in real time. The system prioritizes
low false-alarm rates, explainable alerts, and deployment realism (bad connectivity, operator trust,
evidentiary integrity) over raw detection accuracy alone.

### 1.1 Problem Statement (as given)
Develop a camera- and sensor-based system that detects unusual or predefined suspicious activities
in police-monitored areas and provides real-time alerts to authorized personnel.

### 1.2 Goals
- Detect a defined set of suspicious behaviors from live or recorded video feeds
- Notify personnel within seconds of a confirmed detection
- Keep false-positive rate low enough that operators do not develop alert fatigue
- Run continuously on long video streams without degradation
- Log every incident with enough metadata to review and act on later

### 1.3 Non-Goals (explicitly out of scope for v1)
- Fully autonomous facial identification / person-of-interest matching against a criminal database
- Guaranteed weapon detection accuracy suitable for unsupervised auto-response
- Full multi-camera re-identification without human confirmation
- Mobile app for citizens (this is an internal personnel-facing tool only)

---

## 2. Target Users

| User | Need |
|---|---|
| Control room operator | Monitor multiple feeds, triage alerts, dismiss/confirm/escalate |
| Field personnel (constable/guard) | Receive real-time alert with location + context, respond |
| System admin | Configure zones, rules, thresholds per camera |
| Investigating officer (later) | Review logged incidents, export evidence |

---

## 3. Core Requirements (map directly to PS quality expectations)

| ID | Requirement | PS Expectation |
|---|---|---|
| FR-1 | System shall detect persons and objects in each camera frame and track them with a persistent ID while in view | Activity Detection |
| FR-2 | System shall evaluate tracked entities against configurable behavior rules (loitering, zone intrusion, trailing pattern) | Activity Detection |
| FR-3 | System shall push an alert (dashboard + external channel) within ≤5 seconds of a rule being satisfied | Real-Time Alerts |
| FR-4 | System shall require multi-signal confirmation and temporal persistence before raising an alert | Low False Alarms |
| FR-5 | System shall run on a continuous video stream for ≥8 hours without restart or memory growth beyond defined bounds | Continuous Monitoring |
| FR-6 | System shall log every raised incident with timestamp, camera/location ID, rule triggered, confidence score, and a saved snapshot/clip | Event Recording |

---

## 4. Feature Set

### 4.1 Core (v1 — must ship)
1. Person/object detection + multi-object tracking
2. Loitering detection (zone + dwell time)
3. Trailing/stalking pattern detection (trajectory-based, non-demographic)
4. Real-time alert pipeline (dashboard + Telegram/SMS)
5. Multi-signal fusion + temporal smoothing (false-alarm reduction)
6. Continuous monitoring dashboard
7. Event logging database + incident timeline

### 4.2 Secondary (v1.1 — build if time allows)
8. Restricted zone / tripwire intrusion
9. Abandoned object detection
10. Severity tiering (Low/Med/High)
11. Alert lifecycle tracking (New → Acknowledged → Resolved)
12. Rolling context buffer (pre/post-event clip)
13. Zone-configurable rule editor (no-code)

### 4.3 Differentiators (pitch-critical — pick 2-3 to actually build)
14. Per-camera adaptive baseline (learns normal behavior instead of fixed thresholds)
15. Local-language voice/push alerts to field personnel
16. Tamper-proof evidence hashing (SHA-256 on saved clips)
17. Offline-first / edge fallback queuing
18. Self-correcting alert trust (auto-suppress alert types with high dismiss-rate)
19. Privacy-by-design (face blur by default)
20. Explainability panel (shows why an alert fired)

### 4.4 Stretch / Roadmap (mention, don't over-promise in demo)
21. Fighting/violence detection (pose-based)
22. Weapon/malicious object detection
23. Cross-camera re-identification (confidence-based, human-confirmed)
24. Generalized anomaly detection (autoencoder-based)

Full feature-to-model mapping is in `03_FEATURE_SPEC.md`.

---

## 5. Success Metrics

| Metric | Target (hackathon demo) |
|---|---|
| Detection latency (frame → alert) | < 5 seconds |
| False-positive rate on test clips | < 15% after temporal smoothing |
| System uptime on continuous test feed | ≥ 8 hrs without crash |
| Alert delivery success | 100% on available channels |
| Operator time-to-acknowledge (simulated) | < 30 seconds |

---

## 6. Constraints & Assumptions

- Demo will primarily run on pre-recorded CCTV-style clips, not guaranteed live camera feed
- No GPU guarantee — design must degrade gracefully on CPU (lower resolution/frame-skip)
- No access to a labeled "suspicious activity" dataset — rules will be heuristic/trajectory-based for v1, not trained classifiers, except where a public dataset exists (RWF-2000 for violence, if attempted)
- Gender/demographic-based profiling is explicitly disallowed — all behavior rules must be
  identity-agnostic (trajectory, timing, zone-based only)

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Weapon/violence detection false positives | Treat as "flag for human review," never auto-escalate |
| Re-ID misidentifying people | Always show confidence %, require human confirmation |
| Low FPS on CPU-only hardware | Frame skipping, reduced input resolution, lightweight tracker |
| Judges question privacy/legality | Lead with privacy-by-design features in the pitch |
| Demo camera fails live | Fall back to pre-recorded test clips, rehearsed |

---

## 8. Document Index

- `02_TECHNICAL_ARCHITECTURE.md` — system architecture, data flow, tech stack
- `03_FEATURE_SPEC.md` — detailed feature specs, model vs rule-logic breakdown
- `04_API_SPEC.md` — backend API contract
- `05_DATA_MODEL.md` — database schema
- `06_DEVELOPMENT_ROADMAP.md` — phased build plan with task breakdown for agentic coding tools
