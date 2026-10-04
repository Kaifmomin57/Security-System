# API Specification
## SentryEye Backend (FastAPI)

Base URL: `http://localhost:8000/api/v1`

---

## 1. Auth
For hackathon scope, a simple API key or session-based auth is sufficient.

```
Header: X-API-Key: <key>
```

---

## 2. Alerts

### `GET /alerts`
Query params: `status`, `camera_id`, `rule_type`, `from_date`, `to_date`
Returns list of alerts.

```json
[
  {
    "id": "evt_001",
    "camera_id": "cam_03",
    "rule_type": "loitering",
    "confidence": 0.87,
    "severity": "medium",
    "status": "new",
    "timestamp": "2026-10-03T14:22:10Z",
    "snapshot_url": "/media/evt_001.jpg",
    "clip_url": "/media/evt_001.mp4",
    "clip_hash": "a1b2c3...",
    "track_ids": [47]
  }
]
```

### `GET /alerts/{id}`
Returns full detail including rule explanation metadata (zone polygon, trajectory points) for the Explainability Panel.

### `PATCH /alerts/{id}`
Body: `{ "status": "acknowledged" | "resolved" | "dismissed", "responder": "string" }`
Updates alert lifecycle state; dismissals feed into the trust-adjuster (F18).

---

## 3. Zones & Rules Config

### `GET /zones?camera_id=cam_03`
Returns configured zones for a camera.

### `POST /zones`
```json
{
  "camera_id": "cam_03",
  "name": "ATM Entrance",
  "polygon": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
  "rules": [
    { "type": "loitering", "threshold_seconds": 60 },
    { "type": "intrusion", "active_hours": ["22:00-06:00"] }
  ]
}
```

### `PUT /zones/{id}` / `DELETE /zones/{id}`
Update or remove a zone config.

---

## 4. Cameras

### `GET /cameras`
Returns list of registered camera sources (id, name, stream URL or file path, status: online/offline).

### `POST /cameras`
Register a new camera/stream.

---

## 5. WebSocket — Live Alerts

### `WS /ws/alerts`
Server pushes new alert objects as they're confirmed, same shape as `GET /alerts` item.
Client (dashboard) subscribes on load to update the grid in real time.

```json
{ "event": "new_alert", "data": { ...alert object... } }
{ "event": "alert_updated", "data": { ...alert object... } }
```

---

## 6. Events / Incident Timeline

### `GET /events?camera_id=&date=&type=`
Same as `/alerts` but intended for historical search/filter view (searchable timeline, F13/F20 support).

---

## 7. System Health

### `GET /health`
Returns pipeline status per camera: `{ "camera_id": "cam_03", "status": "running", "fps": 14.2, "uptime_seconds": 31200 }`
Used to demonstrate Continuous Monitoring (FR-5) to judges.
