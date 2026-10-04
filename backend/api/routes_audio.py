"""
api/routes_audio.py
───────────────────
REST endpoints for Sound-Based Distress Detection (Feature B).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from storage.db import AudioEvent, get_db
from api.websocket_manager import ws_manager

router = APIRouter(prefix="/audio-events", tags=["audio-distress"])


class AudioEventResponse(BaseModel):
    id: str
    camera_id: str
    sound_class: str
    confidence: float
    timestamp: datetime
    fused_event_id: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class SimulateAudioRequest(BaseModel):
    sound_class: str = "Screaming"   # Screaming, Glass Breaking, Gunshot, Shout
    confidence: float = 0.88
    camera_id: str = "cam_01"


@router.get("", response_model=List[AudioEventResponse])
def list_audio_events(
    camera_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date:   Optional[datetime] = Query(None),
    limit:     int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """
    Returns audio distress detections (Feature B PRD spec: GET /audio-events).
    """
    q = db.query(AudioEvent)
    if camera_id:
        q = q.filter(AudioEvent.camera_id == camera_id)
    if from_date:
        q = q.filter(AudioEvent.timestamp >= from_date)
    if to_date:
        q = q.filter(AudioEvent.timestamp <= to_date)
    events = q.order_by(AudioEvent.timestamp.desc()).limit(limit).all()
    return events


@router.post("/simulate", response_model=AudioEventResponse)
async def simulate_audio_event(
    req: SimulateAudioRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger a simulated distress sound event (useful for demonstrations & testing).
    """
    import uuid
    from datetime import datetime
    event_id = f"aev_{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow()

    event = AudioEvent(
        id=event_id,
        camera_id=req.camera_id,
        sound_class=req.sound_class,
        confidence=req.confidence,
        timestamp=now,
        status="unconfirmed_visually",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Broadcast via WebSocket
    await ws_manager.broadcast({
        "type": "audio_distress_alert",
        "data": {
            "id": event.id,
            "camera_id": event.camera_id,
            "sound_class": event.sound_class,
            "confidence": event.confidence,
            "timestamp": event.timestamp.isoformat(),
            "status": event.status,
            "explanation": f"Simulated Audio Sensor: Detected {event.sound_class} with {int(event.confidence*100)}% confidence.",
        }
    })

    return event
