"""
api/routes_reports.py
─────────────────────
REST endpoints for auto-generated police incident reports (FR2-1 to FR2-5).
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from evidence.report_generator import generate_incident_pdf, get_or_create_incident_report
from storage.db import Event, IncidentReport, get_db

router = APIRouter(prefix="/reports", tags=["incident_reports"])


class IncidentReportResponse(BaseModel):
    id: str
    event_id: str
    generated_at: datetime
    report_pdf_url: str
    officer_notes: Optional[str]
    reporter_name: Optional[str]
    rule_type: str
    camera_id: str
    severity: str
    confidence: float

    class Config:
        from_attributes = True


class UpdateReportPatch(BaseModel):
    officer_notes: Optional[str] = None
    reporter_name: Optional[str] = None


def _to_report_response(report: IncidentReport, event: Event) -> IncidentReportResponse:
    return IncidentReportResponse(
        id=report.id,
        event_id=report.event_id,
        generated_at=report.generated_at,
        report_pdf_url=report.report_pdf_path,
        officer_notes=report.officer_notes,
        reporter_name=report.reporter_name,
        rule_type=event.rule_type,
        camera_id=event.camera_id,
        severity=event.severity,
        confidence=event.confidence,
    )


@router.get("/{event_id}", response_model=IncidentReportResponse)
def get_incident_report(
    event_id: str,
    auto_create: bool = Query(True),
    db: Session = Depends(get_db),
):
    """
    FR2-1, FR2-4: Returns report metadata and generated PDF path for an incident.
    Auto-generates report if it does not yet exist.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident Event not found")

    report = db.query(IncidentReport).filter(IncidentReport.event_id == event_id).first()
    if not report and auto_create:
        try:
            report = get_or_create_incident_report(event_id=event_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")

    if not report:
        raise HTTPException(status_code=404, detail="Incident Report not found")

    return _to_report_response(report, event)


@router.post("/generate/{event_id}", response_model=IncidentReportResponse)
def force_generate_report(
    event_id: str,
    db: Session = Depends(get_db),
):
    """
    Explicitly triggers / regenerates the PDF incident dossier.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident Event not found")

    try:
        report = get_or_create_incident_report(event_id=event_id, force_rebuild=True)
        return _to_report_response(report, event)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation error: {e}")


@router.patch("/{event_id}", response_model=IncidentReportResponse)
def update_report_notes(
    event_id: str,
    body: UpdateReportPatch,
    db: Session = Depends(get_db),
):
    """
    FR2-3: Updates officer notes and regenerates PDF without creating new records.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident Event not found")

    try:
        report = get_or_create_incident_report(
            event_id=event_id,
            officer_notes=body.officer_notes,
            reporter_name=body.reporter_name,
            force_rebuild=True,
        )
        return _to_report_response(report, event)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update report: {e}")


@router.get("/{event_id}/download")
def download_report_pdf(event_id: str, db: Session = Depends(get_db)):
    """
    Directly streams the incident report PDF.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Incident Event not found")

    report = get_or_create_incident_report(event_id=event_id)
    pdf_rel_path = report.report_pdf_path.lstrip("/")
    if not os.path.exists(pdf_rel_path):
        # Fallback check relative to cwd
        pdf_rel_path = os.path.join(".", pdf_rel_path)

    if not os.path.exists(pdf_rel_path):
        raise HTTPException(status_code=404, detail="PDF report file missing on disk")

    return FileResponse(
        path=pdf_rel_path,
        media_type="application/pdf",
        filename=f"Incident_Report_{event_id}.pdf",
    )
