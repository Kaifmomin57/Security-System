"""
api/routes_cameras.py
──────────────────────
Camera registration + health status endpoints.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from storage.db import Camera, get_db

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraIn(BaseModel):
    id: Optional[str] = None
    name: str
    source_url: str


class CameraResponse(BaseModel):
    id: str
    name: str
    source_url: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[CameraResponse])
def list_cameras(db: Session = Depends(get_db)):
    return db.query(Camera).all()


@router.post("", response_model=CameraResponse, status_code=201)
def create_camera(body: CameraIn, db: Session = Depends(get_db)):
    camera = Camera(name=body.name, source_url=body.source_url)
    if body.id:
        camera.id = body.id
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.patch("/{camera_id}/status")
def update_status(camera_id: str, status: str, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    cam.status = status
    db.commit()
    return {"camera_id": camera_id, "status": status}
