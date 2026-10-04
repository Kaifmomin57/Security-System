"""
api/routes_zones.py
────────────────────
CRUD endpoints for camera zone configuration.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from storage.db import Zone, ZoneRule, get_db

router = APIRouter(prefix="/zones", tags=["zones"])


class ZoneRuleIn(BaseModel):
    rule_type: str
    threshold_seconds: Optional[int] = None
    active_hours: Optional[str] = None
    enabled: bool = True


class ZoneIn(BaseModel):
    camera_id: str
    name: str
    polygon: List[List[float]]   # [[x,y], ...]
    rules: List[ZoneRuleIn] = []


class ZoneResponse(BaseModel):
    id: str
    camera_id: str
    name: str
    polygon: list
    rules: List[dict] = []

    class Config:
        from_attributes = True


@router.get("", response_model=List[ZoneResponse])
def list_zones(camera_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Zone)
    if camera_id:
        q = q.filter(Zone.camera_id == camera_id)
    zones = q.all()
    return [_zone_resp(z) for z in zones]


@router.post("", response_model=ZoneResponse, status_code=201)
def create_zone(body: ZoneIn, db: Session = Depends(get_db)):
    zone = Zone(camera_id=body.camera_id, name=body.name, polygon=body.polygon)
    db.add(zone)
    db.flush()
    for r in body.rules:
        db.add(ZoneRule(
            zone_id=zone.id,
            rule_type=r.rule_type,
            threshold_seconds=r.threshold_seconds,
            active_hours=r.active_hours,
            enabled=r.enabled,
        ))
    db.commit()
    db.refresh(zone)
    return _zone_resp(zone)


@router.put("/{zone_id}", response_model=ZoneResponse)
def update_zone(zone_id: str, body: ZoneIn, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, "Zone not found")
    zone.name    = body.name
    zone.polygon = body.polygon
    # Replace rules
    for r in zone.rules:
        db.delete(r)
    db.flush()
    for r in body.rules:
        db.add(ZoneRule(zone_id=zone.id, rule_type=r.rule_type,
                        threshold_seconds=r.threshold_seconds,
                        active_hours=r.active_hours, enabled=r.enabled))
    db.commit()
    db.refresh(zone)
    return _zone_resp(zone)


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: str, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, "Zone not found")
    db.delete(zone)
    db.commit()


def _zone_resp(zone: Zone) -> ZoneResponse:
    return ZoneResponse(
        id=zone.id,
        camera_id=zone.camera_id,
        name=zone.name,
        polygon=zone.polygon,
        rules=[
            {"type": r.rule_type, "threshold_seconds": r.threshold_seconds,
             "active_hours": r.active_hours, "enabled": r.enabled}
            for r in zone.rules
        ],
    )
