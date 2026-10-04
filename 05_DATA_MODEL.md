# Data Model
## SentryEye — Database Schema (SQLite for demo / PostgreSQL for prod)

---

## Table: `cameras`
| Column | Type | Notes |
|---|---|---|
| id | TEXT (PK) | e.g. "cam_03" |
| name | TEXT | human-readable label |
| source_url | TEXT | RTSP URL or file path |
| status | TEXT | online / offline |
| created_at | TIMESTAMP | |

## Table: `zones`
| Column | Type | Notes |
|---|---|---|
| id | TEXT (PK) | |
| camera_id | TEXT (FK -> cameras.id) | |
| name | TEXT | e.g. "ATM Entrance" |
| polygon | JSON | list of [x,y] points |
| created_at | TIMESTAMP | |

## Table: `zone_rules`
| Column | Type | Notes |
|---|---|---|
| id | TEXT (PK) | |
| zone_id | TEXT (FK -> zones.id) | |
| rule_type | TEXT | loitering / intrusion / trailing / crowd / abandoned_object |
| threshold_seconds | INTEGER | nullable, rule-dependent |
| active_hours | TEXT | nullable, e.g. "22:00-06:00" |
| enabled | BOOLEAN | |

## Table: `tracks`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER (PK) | per-session track id |
| camera_id | TEXT (FK) | |
| class | TEXT | person / bag / etc |
| first_seen | TIMESTAMP | |
| last_seen | TIMESTAMP | |
| trajectory | JSON | list of {t, x, y} points (sampled) |

## Table: `events` (confirmed alerts)
| Column | Type | Notes |
|---|---|---|
| id | TEXT (PK) | e.g. "evt_001" |
| camera_id | TEXT (FK) | |
| zone_id | TEXT (FK, nullable) | |
| rule_type | TEXT | |
| confidence | FLOAT | |
| severity | TEXT | low / medium / high |
| status | TEXT | new / acknowledged / resolved / dismissed |
| track_ids | JSON | list of involved track IDs |
| snapshot_path | TEXT | |
| clip_path | TEXT | |
| clip_hash | TEXT | SHA-256 hash (F16 — evidence integrity) |
| explanation | JSON | polygon/trajectory/rule metadata for Explainability Panel (F20) |
| timestamp | TIMESTAMP | |
| responder | TEXT | nullable |
| resolved_at | TIMESTAMP | nullable |

## Table: `alert_feedback` (supports F18 — self-correcting trust)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER (PK) | |
| event_id | TEXT (FK -> events.id) | |
| camera_id | TEXT | |
| rule_type | TEXT | |
| action | TEXT | dismissed / confirmed |
| timestamp | TIMESTAMP | |

## Table: `camera_baselines` (supports F14 — adaptive baseline)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER (PK) | |
| camera_id | TEXT (FK) | |
| rule_type | TEXT | |
| mean_value | FLOAT | e.g. average dwell time |
| std_dev | FLOAT | |
| sample_count | INTEGER | |
| last_updated | TIMESTAMP | |

---

## Relationships Summary
```
cameras 1───* zones 1───* zone_rules
cameras 1───* tracks
cameras 1───* events ──* (links to tracks via track_ids JSON)
events 1───* alert_feedback
cameras 1───* camera_baselines
```
