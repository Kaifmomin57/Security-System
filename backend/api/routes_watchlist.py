"""
api/routes_watchlist.py
───────────────────────
REST endpoints for ANPR Plate Watchlist & Live Reads (FR3-1 to FR3-5).
"""

import base64
import os
from datetime import datetime
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from detection.anpr_engine import anpr_engine, normalize_plate
from storage.db import PlateRead, WatchlistVehicle, get_db

router = APIRouter(tags=["anpr_watchlist"])


class WatchlistCreate(BaseModel):
    plate_number: str
    reason: str
    added_by: Optional[str] = "Control Room Officer"


class WatchlistResponse(BaseModel):
    plate_number: str
    reason: str
    added_by: str
    added_at: datetime

    class Config:
        from_attributes = True


class PlateReadResponse(BaseModel):
    id: str
    camera_id: str
    plate_number: str
    ocr_confidence: float
    matched: bool
    reason: Optional[str]
    snapshot_path: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class ScanPlateRequest(BaseModel):
    plate_number: Optional[str] = None
    camera_id: Optional[str] = "cam_01"
    image_base64: Optional[str] = None


@router.get("/watchlist", response_model=List[WatchlistResponse])
def list_watchlist(db: Session = Depends(get_db)):
    """
    FR3-3: Returns all flagged vehicle plates in police watchlist.
    """
    return db.query(WatchlistVehicle).order_by(WatchlistVehicle.added_at.desc()).all()


@router.post("/watchlist", response_model=WatchlistResponse)
def add_to_watchlist(body: WatchlistCreate, db: Session = Depends(get_db)):
    """
    FR3-3: Adds a vehicle plate to the active police watchlist.
    """
    clean_plate = normalize_plate(body.plate_number)
    if not clean_plate:
        raise HTTPException(status_code=400, detail="Invalid license plate format")

    existing = db.query(WatchlistVehicle).filter(WatchlistVehicle.plate_number == clean_plate).first()
    if existing:
        existing.reason = body.reason
        existing.added_by = body.added_by or existing.added_by
        existing.added_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    item = WatchlistVehicle(
        plate_number=clean_plate,
        reason=body.reason,
        added_by=body.added_by or "Control Room Officer",
        added_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/watchlist/{plate_number}")
def remove_from_watchlist(plate_number: str, db: Session = Depends(get_db)):
    """
    Removes a vehicle plate from the watchlist.
    """
    clean_plate = normalize_plate(plate_number)
    item = db.query(WatchlistVehicle).filter(WatchlistVehicle.plate_number == clean_plate).first()
    if not item:
        raise HTTPException(status_code=404, detail="Vehicle not found in watchlist")

    db.delete(item)
    db.commit()
    return {"status": "deleted", "plate_number": clean_plate}


@router.get("/plate-reads", response_model=List[PlateReadResponse])
def list_plate_reads(
    matched: Optional[bool] = Query(None),
    camera_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """
    FR3-5: Query OCR plate scan logs with optional filter for watchlist hits.
    """
    q = db.query(PlateRead)
    if matched is not None:
        q = q.filter(PlateRead.matched == matched)
    if camera_id:
        q = q.filter(PlateRead.camera_id == camera_id)
    if from_date:
        q = q.filter(PlateRead.timestamp >= from_date)
    if to_date:
        q = q.filter(PlateRead.timestamp <= to_date)

    return q.order_by(PlateRead.timestamp.desc()).limit(limit).all()


@router.post("/anpr/scan")
def scan_vehicle_plate(
    body: ScanPlateRequest,
    db: Session = Depends(get_db),
):
    """
    Interactive test & scan endpoint for manual plate verification or image upload.
    """
    plate_text = body.plate_number
    ocr_conf = 0.92

    if body.image_base64:
        try:
            img_data = base64.b64decode(body.image_base64.split(",")[-1])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                extracted, conf = anpr_engine.read_plate_text(img)
                if extracted:
                    plate_text = extracted
                    ocr_conf = conf
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Image decoding failed: {e}")

    if not plate_text:
        plate_text = "DL01AB9876"  # Demo fallback plate

    norm_plate = normalize_plate(plate_text)
    matched, reason = anpr_engine.check_watchlist(norm_plate)

    # Record plate read
    rec = PlateRead(
        id=f"read_{datetime.utcnow().strftime('%H%M%S%f')[:8]}",
        camera_id=body.camera_id or "cam_01",
        plate_number=norm_plate,
        ocr_confidence=ocr_conf,
        matched=matched,
        reason=reason if matched else None,
        snapshot_path=None,
        timestamp=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()

    return {
        "plate_number": norm_plate,
        "ocr_confidence": ocr_conf,
        "matched": matched,
        "reason": reason,
        "action": "RAISE_HIGH_PRIORITY_INTERCEPT_ALERT" if matched else "LOG_NORMAL",
        "timestamp": datetime.utcnow().isoformat(),
    }
