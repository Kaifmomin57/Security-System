"""
api/routes_reid.py
──────────────────
REST endpoints for Cross-Camera Re-ID tracking and operator confirmation (FR4-1 to FR4-7).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from storage.db import ReidGallery, ReidMatch, get_db

router = APIRouter(prefix="/reid", tags=["reid"])


class ReidMatchResponse(BaseModel):
    id: str
    original_track_id: int
    matched_track_id: int
    camera_id_matched: str
    similarity_score: float
    confirmed_by_operator: Optional[bool]
    timestamp: datetime

    class Config:
        from_attributes = True


class ConfirmMatchPatch(BaseModel):
    confirmed: bool  # true = confirmed, false = rejected


class GalleryItemResponse(BaseModel):
    id: str
    track_id: int
    camera_id: str
    last_seen_at: datetime
    snapshot_path: Optional[str]

    class Config:
        from_attributes = True


class AddGalleryRequest(BaseModel):
    track_id: int
    camera_id: str


@router.get("/matches", response_model=List[ReidMatchResponse])
def list_reid_matches(
    track_id: Optional[int] = Query(None),
    confirmed_only: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """
    FR4-6: List surfaced cross-camera possible matches with similarity scores.
    """
    q = db.query(ReidMatch)
    if track_id is not None:
        q = q.filter(
            (ReidMatch.original_track_id == track_id) | (ReidMatch.matched_track_id == track_id)
        )
    if confirmed_only is not None:
        q = q.filter(ReidMatch.confirmed_by_operator == confirmed_only)

    return q.order_by(ReidMatch.timestamp.desc()).limit(limit).all()


@router.patch("/matches/{match_id}", response_model=ReidMatchResponse)
def confirm_or_reject_match(
    match_id: str,
    body: ConfirmMatchPatch,
    db: Session = Depends(get_db),
):
    """
    FR4-5: Operator confirmation / rejection of a cross-camera track identity link.
    """
    match = db.query(ReidMatch).filter(ReidMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Re-ID match record not found")

    match.confirmed_by_operator = body.confirmed
    db.commit()
    db.refresh(match)
    return match


@router.get("/gallery", response_model=List[GalleryItemResponse])
def list_active_gallery(db: Session = Depends(get_db)):
    """
    FR4-2: Lists all flagged tracks in the active cross-camera search gallery.
    """
    return db.query(ReidGallery).order_by(ReidGallery.last_seen_at.desc()).limit(50).all()
