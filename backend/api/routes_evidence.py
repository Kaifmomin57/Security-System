"""
api/routes_evidence.py
──────────────────────
REST endpoints for court-admissible evidence export and chain-of-custody audit logs (FR4-1 to FR4-4).
"""

import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from evidence.package_exporter import export_court_evidence_package
from storage.db import Event, EvidenceAccessLog, get_db

router = APIRouter(tags=["court_evidence"])


class CustodyLogResponse(BaseModel):
    id: str
    event_id: str
    action: str
    user_id: str
    timestamp: datetime
    details: Optional[str]

    class Config:
        from_attributes = True


class LogAccessRequest(BaseModel):
    action: str = "viewed"  # viewed / exported / verified
    user_id: str = "Officer_101"
    details: Optional[str] = "Operator viewed alert playback in forensic console"


@router.post("/events/{event_id}/export-evidence")
def export_evidence(
    event_id: str,
    user_id: str = Query("Officer_101"),
    db: Session = Depends(get_db),
):
    """
    FR4-1 to FR4-4: Generates signed court-admissible evidence package ZIP with hash verification & audit log.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident Event not found")

    try:
        zip_path, summary = export_court_evidence_package(event_id=event_id, user_id=user_id)
        if not os.path.exists(zip_path):
            raise HTTPException(status_code=500, detail="Generated evidence package not found on disk")

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=summary["filename"],
            headers={
                "X-Integrity-Verified": str(summary["integrity_verified"]),
                "X-Custody-Entries": str(summary["total_custody_actions"]),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evidence export failed: {e}")


@router.get("/events/{event_id}/custody-log", response_model=List[CustodyLogResponse])
def get_chain_of_custody_log(event_id: str, db: Session = Depends(get_db)):
    """
    FR4-2: Returns chronological chain-of-custody audit history for an incident.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident Event not found")

    logs = (
        db.query(EvidenceAccessLog)
        .filter(EvidenceAccessLog.event_id == event_id)
        .order_by(EvidenceAccessLog.timestamp.desc())
        .all()
    )
    return logs


@router.post("/events/{event_id}/log-access", response_model=CustodyLogResponse)
def record_access_log(
    event_id: str,
    body: LogAccessRequest,
    db: Session = Depends(get_db),
):
    """
    Records an access / viewing event into the immutable chain of custody.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident Event not found")

    rec = EvidenceAccessLog(
        id=f"log_{datetime.utcnow().strftime('%H%M%S%f')[:8]}",
        event_id=event_id,
        action=body.action,
        user_id=body.user_id,
        timestamp=datetime.utcnow(),
        details=body.details,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec
