"""
api/routes_analytics.py
───────────────────────
Historical incident heatmap and analytics endpoints for police operations planning.
Aggregates events by zone/camera and hour-of-day over configurable date ranges.
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from storage.db import Camera, Event, Zone, get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


class ZoneHeatmapItem(BaseModel):
    zone_id: str
    zone_name: str
    camera_id: str
    camera_name: str
    hourly_counts: List[int]   # 24 elements (0..23)
    total_incidents: int
    peak_hour: int
    peak_count: int


class CameraHeatmapItem(BaseModel):
    camera_id: str
    camera_name: str
    hourly_counts: List[int]   # 24 elements (0..23)
    total_incidents: int
    peak_hour: int
    peak_count: int


class HeatmapSummary(BaseModel):
    total_incidents: int
    peak_hour: int
    peak_hour_count: int
    peak_zone: str
    peak_rule: str
    rule_breakdown: Dict[str, int]
    severity_breakdown: Dict[str, int]


class HeatmapResponse(BaseModel):
    from_date: Optional[str]
    to_date: Optional[str]
    filter_rule: Optional[str]
    filter_camera: Optional[str]
    zones: List[ZoneHeatmapItem]
    cameras: List[CameraHeatmapItem]
    summary: HeatmapSummary


def _build_heatmap_data(
    db: Session,
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    rule_type: Optional[str],
    camera_id: Optional[str],
    zone_id: Optional[str],
):
    """Core aggregation query for heatmap."""
    query = db.query(Event)

    if from_date:
        query = query.filter(Event.timestamp >= from_date)
    if to_date:
        query = query.filter(Event.timestamp <= to_date)
    if rule_type and rule_type != "all":
        query = query.filter(Event.rule_type == rule_type)
    if camera_id and camera_id != "all":
        query = query.filter(Event.camera_id == camera_id)
    if zone_id and zone_id != "all":
        query = query.filter(Event.zone_id == zone_id)

    events = query.all()

    # Preload cameras and zones
    cameras_map = {c.id: c.name for c in db.query(Camera).all()}
    zones_map = {z.id: (z.name, z.camera_id) for z in db.query(Zone).all()}

    # Data structures for 24-hour aggregation
    zone_counts: Dict[str, List[int]] = {}
    camera_counts: Dict[str, List[int]] = {}
    rule_breakdown: Dict[str, int] = {}
    severity_breakdown: Dict[str, int] = {}
    overall_hourly = [0] * 24

    for ev in events:
        hour = ev.timestamp.hour if ev.timestamp else 0
        overall_hourly[hour] += 1

        # Camera aggregation
        cam_id = ev.camera_id or "unknown_cam"
        if cam_id not in camera_counts:
            camera_counts[cam_id] = [0] * 24
        camera_counts[cam_id][hour] += 1

        # Zone aggregation
        z_id = ev.zone_id or "unassigned_zone"
        if z_id not in zone_counts:
            zone_counts[z_id] = [0] * 24
        zone_counts[z_id][hour] += 1

        # Rule & Severity breakdown
        r_type = ev.rule_type or "unknown"
        rule_breakdown[r_type] = rule_breakdown.get(r_type, 0) + 1

        sev = ev.severity or "low"
        severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1

    # Format Zone Items
    zone_items: List[ZoneHeatmapItem] = []
    for z_id, counts in zone_counts.items():
        if z_id in zones_map:
            z_name, c_id = zones_map[z_id]
            c_name = cameras_map.get(c_id, c_id)
        else:
            z_name = "General Surveillance Area" if z_id == "unassigned_zone" else z_id
            c_id = camera_id or "cam_01"
            c_name = cameras_map.get(c_id, c_id)

        tot = sum(counts)
        p_hour = int(max(range(24), key=lambda h: counts[h])) if tot > 0 else 0
        zone_items.append(ZoneHeatmapItem(
            zone_id=z_id,
            zone_name=z_name,
            camera_id=c_id,
            camera_name=c_name,
            hourly_counts=counts,
            total_incidents=tot,
            peak_hour=p_hour,
            peak_count=counts[p_hour],
        ))

    # Format Camera Items
    camera_items: List[CameraHeatmapItem] = []
    for c_id, counts in camera_counts.items():
        c_name = cameras_map.get(c_id, c_id)
        tot = sum(counts)
        p_hour = int(max(range(24), key=lambda h: counts[h])) if tot > 0 else 0
        camera_items.append(CameraHeatmapItem(
            camera_id=c_id,
            camera_name=c_name,
            hourly_counts=counts,
            total_incidents=tot,
            peak_hour=p_hour,
            peak_count=counts[p_hour],
        ))

    # Summary
    total_incidents = len(events)
    peak_hour = int(max(range(24), key=lambda h: overall_hourly[h])) if total_incidents > 0 else 0
    peak_hour_count = overall_hourly[peak_hour]
    peak_zone = max(zone_items, key=lambda z: z.total_incidents).zone_name if zone_items else "None"
    peak_rule = max(rule_breakdown.items(), key=lambda r: r[1])[0] if rule_breakdown else "None"

    summary = HeatmapSummary(
        total_incidents=total_incidents,
        peak_hour=peak_hour,
        peak_hour_count=peak_hour_count,
        peak_zone=peak_zone,
        peak_rule=peak_rule,
        rule_breakdown=rule_breakdown,
        severity_breakdown=severity_breakdown,
    )

    return zone_items, camera_items, summary


@router.get("/heatmap", response_model=HeatmapResponse)
def get_incident_heatmap(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    rule_type: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    FR1-1 to FR1-4: Returns hourly incident density aggregated by Zone and Camera.
    """
    if not from_date and not to_date:
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=30)

    zones, cameras, summary = _build_heatmap_data(
        db=db,
        from_date=from_date,
        to_date=to_date,
        rule_type=rule_type,
        camera_id=camera_id,
        zone_id=zone_id,
    )

    return HeatmapResponse(
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        filter_rule=rule_type,
        filter_camera=camera_id,
        zones=zones,
        cameras=cameras,
        summary=summary,
    )


@router.get("/heatmap/export")
def export_heatmap_csv(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    rule_type: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    FR1-5: Export historical heatmap aggregated incident data as CSV for police patrol reporting.
    """
    if not from_date and not to_date:
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=30)

    zones, cameras, summary = _build_heatmap_data(
        db=db,
        from_date=from_date,
        to_date=to_date,
        rule_type=rule_type,
        camera_id=camera_id,
        zone_id=zone_id,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header section
    writer.writerow(["SENTRYEYE POLICE PATROL ANALYTICS - INCIDENT HEATMAP REPORT"])
    writer.writerow(["Generated At", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow(["Date Range", f"{from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"])
    writer.writerow(["Filter Rule", rule_type or "ALL"])
    writer.writerow(["Filter Camera", camera_id or "ALL"])
    writer.writerow([])

    # Summary Row
    writer.writerow(["SUMMARY STATISTICS"])
    writer.writerow(["Total Incidents", summary.total_incidents])
    writer.writerow(["Peak Incident Hour", f"{summary.peak_hour:02d}:00 - {summary.peak_hour+1:02d}:00 ({summary.peak_hour_count} alerts)"])
    writer.writerow(["Highest Risk Zone", summary.peak_zone])
    writer.writerow(["Most Frequent Violation", summary.peak_rule])
    writer.writerow([])

    # Zone Hourly Table
    hours_header = [f"{h:02d}:00" for h in range(24)]
    writer.writerow(["Zone ID", "Zone Name", "Camera ID", "Camera Name", *hours_header, "Total", "Peak Hour"])

    for z in zones:
        writer.writerow([
            z.zone_id,
            z.zone_name,
            z.camera_id,
            z.camera_name,
            *z.hourly_counts,
            z.total_incidents,
            f"{z.peak_hour:02d}:00",
        ])

    writer.writerow([])
    writer.writerow(["CAMERA-LEVEL HOURLY AGGREGATION"])
    writer.writerow(["Camera ID", "Camera Name", *hours_header, "Total", "Peak Hour"])
    for c in cameras:
        writer.writerow([
            c.camera_id,
            c.camera_name,
            *c.hourly_counts,
            c.total_incidents,
            f"{c.peak_hour:02d}:00",
        ])

    csv_content = output.getvalue()
    filename = f"patrol_heatmap_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
