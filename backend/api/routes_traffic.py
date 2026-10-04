"""
api/routes_traffic.py
─────────────────────
REST endpoints for traffic junctions, signal control, and violation logs (FR5-1 to FR5-5).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rules.traffic_violation_rule import get_junction_signal, set_junction_signal
from storage.db import Event, TrafficViolation, get_db

router = APIRouter(prefix="/traffic", tags=["traffic_violations"])


class SignalStateRequest(BaseModel):
    state: str   # RED | GREEN | YELLOW


class SignalStateResponse(BaseModel):
    camera_id: str
    state: str
    updated_at: datetime


class TrafficViolationResponse(BaseModel):
    id: str
    event_id: str
    junction_id: str
    violation_type: str
    plate_number: Optional[str]
    signal_state: Optional[str]
    lane_id: Optional[str]
    speed_estimate_kmh: Optional[float]
    timestamp: datetime

    class Config:
        from_attributes = True


@router.get("/signal/{camera_id}", response_model=SignalStateResponse)
def get_signal(camera_id: str):
    """
    FR5-3: Gets current traffic light status for a junction camera.
    """
    state = get_junction_signal(camera_id)
    return SignalStateResponse(
        camera_id=camera_id,
        state=state,
        updated_at=datetime.utcnow(),
    )


@router.post("/signal/{camera_id}", response_model=SignalStateResponse)
def update_signal(camera_id: str, body: SignalStateRequest):
    """
    FR5-3: Toggles / updates the traffic light state (RED / GREEN / YELLOW) for live violation detection.
    """
    new_state = set_junction_signal(camera_id, body.state)
    return SignalStateResponse(
        camera_id=camera_id,
        state=new_state,
        updated_at=datetime.utcnow(),
    )


@router.get("/violations", response_model=List[TrafficViolationResponse])
def list_traffic_violations(
    violation_type: Optional[str] = Query(None),
    junction_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """
    FR5-4, FR5-5: List logged traffic violations (signal jumps & wrong-way incidents).
    """
    q = db.query(TrafficViolation)
    if violation_type:
        q = q.filter(TrafficViolation.violation_type == violation_type)
    if junction_id:
        q = q.filter(TrafficViolation.junction_id == junction_id)

    return q.order_by(TrafficViolation.timestamp.desc()).limit(limit).all()
