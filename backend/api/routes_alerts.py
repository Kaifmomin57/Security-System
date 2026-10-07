"""
api/routes_alerts.py
─────────────────────
REST endpoints for alerts: list, detail, update lifecycle.
"""

import hmac
import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from storage.db import Event, AlertFeedback, EvidenceAccessLog, get_db
from alerts.trust_adjuster import trust_adjuster
from api.websocket_manager import ws_manager
from privacy.private_evidence import private_snapshot_path

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.delete("")
def delete_all_alerts(db: Session = Depends(get_db)):
    """
    Deletes ALL incident events and related records from the database.
    """
    from sqlalchemy import text
    db.execute(text("DELETE FROM incident_reports"))
    db.execute(text("DELETE FROM alert_feedback"))
    db.execute(text("DELETE FROM evidence_access_log"))
    db.execute(text("DELETE FROM plate_reads"))
    db.execute(text("DELETE FROM audio_events"))
    db.execute(text("DELETE FROM unaccompanied_events"))
    db.execute(text("DELETE FROM track_classifications"))
    db.execute(text("DELETE FROM traffic_violations"))
    db.execute(text("DELETE FROM collision_events"))
    db.execute(text("DELETE FROM tracks"))
    db.execute(text("DELETE FROM events"))
    db.commit()
    return {"status": "deleted_all"}


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: str
    camera_id: str
    zone_id: Optional[str]
    rule_type: str
    confidence: float
    severity: str
    status: str
    track_ids: Optional[list]
    snapshot_url: Optional[str]
    clip_url: Optional[str]
    clip_hash: Optional[str]
    explanation: Optional[dict]
    timestamp: datetime
    responder: Optional[str]
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class AlertPatch(BaseModel):
    status: str   # acknowledged | resolved | dismissed
    responder: Optional[str] = None


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=List[AlertResponse])
def list_alerts(
    status:     Optional[str] = Query(None),
    camera_id:  Optional[str] = Query(None),
    rule_type:  Optional[str] = Query(None),
    from_date:  Optional[datetime] = Query(None),
    to_date:    Optional[datetime] = Query(None),
    limit:      int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Event)
    if status:    q = q.filter(Event.status == status)
    if camera_id: q = q.filter(Event.camera_id == camera_id)
    if rule_type: q = q.filter(Event.rule_type == rule_type)
    if from_date: q = q.filter(Event.timestamp >= from_date)
    if to_date:   q = q.filter(Event.timestamp <= to_date)
    events = q.order_by(Event.timestamp.desc()).limit(limit).all()
    return [_to_response(e) for e in events]


@router.get("/{event_id}", response_model=AlertResponse)
def get_alert(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _to_response(event)


@router.get("/{event_id}/unblurred-snapshot")
def get_unblurred_snapshot(
    event_id: str,
    admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    configured_key = os.getenv("FACE_UNBLUR_ADMIN_KEY", "")
    if not configured_key:
        raise HTTPException(status_code=503, detail="Unblurred evidence access is not configured")
    if not admin_key or not hmac.compare_digest(admin_key, configured_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        original_path = private_snapshot_path(event.id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Private evidence storage is misconfigured") from exc
    if not os.path.isfile(original_path):
        raise HTTPException(status_code=404, detail="Unblurred snapshot is not available for this incident")

    db.add(EvidenceAccessLog(
        event_id=event.id,
        action="viewed",
        user_id="admin-key",
        timestamp=datetime.utcnow(),
        details="Admin accessed unblurred incident snapshot",
    ))
    db.commit()

    return FileResponse(
        original_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.patch("/{event_id}", response_model=AlertResponse)
async def update_alert(
    event_id: str,
    body: AlertPatch,
    db: Session = Depends(get_db),
):
    valid_statuses = {"acknowledged", "resolved", "dismissed", "confirmed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Alert not found")

    event.status = body.status
    if body.responder:
        event.responder = body.responder
    if body.status in ("resolved", "confirmed"):
        event.resolved_at = datetime.utcnow()

    # Record feedback for trust adjuster (F18)
    dismissed = body.status == "dismissed"
    feedback = AlertFeedback(
        event_id=event.id,
        camera_id=event.camera_id,
        rule_type=event.rule_type,
        action=body.status,
    )
    db.add(feedback)
    trust_adjuster.record_outcome(event.camera_id, event.rule_type, dismissed)

    db.commit()
    db.refresh(event)

    # FR2-1: Auto-generate incident report PDF on confirmation/resolution
    if body.status in ("confirmed", "resolved"):
        try:
            from evidence.report_generator import get_or_create_incident_report
            get_or_create_incident_report(event_id=event.id, reporter_name=event.responder)
        except Exception:
            pass

    # Push update to dashboard via WebSocket
    await ws_manager.broadcast_alert_update(_to_response(event).__dict__)

    return _to_response(event)


@router.delete("/{event_id}")
def delete_alert(event_id: str, db: Session = Depends(get_db)):
    """
    Deletes an incident event and its corresponding report from the database.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Delete associated IncidentReport if exists
    from storage.db import IncidentReport
    db.query(IncidentReport).filter(IncidentReport.event_id == event_id).delete()

    db.delete(event)
    db.commit()
    return {"status": "deleted", "id": event_id}


def _to_response(event: Event) -> AlertResponse:
    event_timestamp = event.timestamp
    if event_timestamp.tzinfo is None:
        event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)

    snapshot_name = event.snapshot_path.replace("\\", "/").rsplit("/", 1)[-1] if event.snapshot_path else None
    clip_name = event.clip_path.replace("\\", "/").rsplit("/", 1)[-1] if event.clip_path else None

    return AlertResponse(
        id=event.id,
        camera_id=event.camera_id,
        zone_id=event.zone_id,
        rule_type=event.rule_type,
        confidence=event.confidence,
        severity=event.severity,
        status=event.status,
        track_ids=event.track_ids,
        snapshot_url=f"/media/snapshots/{snapshot_name}" if snapshot_name else None,
        clip_url=f"/media/clips/{clip_name}" if clip_name else None,
        clip_hash=event.clip_hash,
        explanation=event.explanation,
        timestamp=event_timestamp,
        responder=event.responder,
        resolved_at=event.resolved_at,
    )
