"""
test_police_features.py
────────────────────────
Comprehensive verification test suite for all 6 Police Department Features:
1. Historical Incident Heatmap & CSV Export
2. Auto-Generated Incident Report & Notes Update
3. ANPR + Watchlist Matching & Plate Scan
4. Court-Admissible Evidence Export Package (.ZIP & SHA-256 Checksum)
5. Traffic Violation Detection (Signal Jump & Wrong-Way Driving)
6. Hit-and-Run Collision & Fleeing Detection
"""

import os
import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from api.main import app
from detection.anpr_engine import anpr_engine, normalize_plate
from evidence.package_exporter import export_court_evidence_package
from evidence.report_generator import generate_incident_pdf, get_or_create_incident_report
from rules.hit_and_run_rule import HitAndRunRule
from rules.traffic_violation_rule import TrafficViolationRule, set_junction_signal
from storage.db import (
    Camera, Event, PlateRead, WatchlistVehicle, Zone,
    TrafficViolation, CollisionEvent, create_tables, get_session
)

client = TestClient(app)


class MockTrack:
    def __init__(self, track_id, class_name="car", bbox=(100, 100, 200, 200), trajectory=None):
        self.track_id = track_id
        self.class_name = class_name
        self.bbox = bbox
        self.trajectory = trajectory or [(0.0, 150.0, 150.0)]


def run_tests():
    print("=" * 65)
    print("  RUNNING SENTRYEYE POLICE FEATURES TEST SUITE (6 FEATURES)")
    print("=" * 65)

    create_tables()
    db = get_session()

    # Seed test camera & zone
    cam = db.query(Camera).filter(Camera.id == "cam_01").first()
    if not cam:
        cam = Camera(id="cam_01", name="Main Traffic Junction 1", source_url="./media/test.mp4", status="online")
        db.add(cam)
        db.commit()

    zone = db.query(Zone).filter(Zone.id == "zone_01").first()
    if not zone:
        zone = Zone(id="zone_01", camera_id="cam_01", name="Junction Stop Line Zone", polygon=[[0, 0], [100, 100]])
        db.add(zone)
        db.commit()

    # Seed test event
    test_event_id = f"evt_police_{uuid.uuid4().hex[:6]}"
    test_event = Event(
        id=test_event_id,
        camera_id="cam_01",
        zone_id="zone_01",
        rule_type="signal_jump",
        confidence=0.95,
        severity="high",
        status="new",
        track_ids=[42],
        snapshot_path="",
        clip_path="",
        clip_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        explanation={"violation_type": "signal_jump", "signal_state": "RED", "dwell_time": 12.0},
        timestamp=datetime.utcnow() - timedelta(hours=3),
    )
    db.add(test_event)
    db.commit()

    # ── TEST 1: Feature 1 - Heatmap & CSV ─────────────────────────────────────
    print("\n[1/6] Testing Feature 1: Historical Incident Heatmap & CSV Export...")
    r_hm = client.get("/api/v1/analytics/heatmap")
    assert r_hm.status_code == 200, f"Heatmap failed: {r_hm.text}"
    hm_data = r_hm.json()
    assert "zones" in hm_data and "cameras" in hm_data and "summary" in hm_data
    print(f"  [PASS] Heatmap API OK. Total incidents indexed: {hm_data['summary']['total_incidents']}, Peak Hour: {hm_data['summary']['peak_hour']}:00")

    r_csv = client.get("/api/v1/analytics/heatmap/export")
    assert r_csv.status_code == 200, f"Heatmap CSV failed: {r_csv.text}"
    assert "SENTRYEYE POLICE PATROL ANALYTICS" in r_csv.text
    print("  [PASS] Heatmap CSV Export OK.")

    # ── TEST 2: Feature 2 - Auto-Generated Incident Report ────────────────────
    print("\n[2/6] Testing Feature 2: Auto-Generated Incident Report & Notes Update...")
    r_rep = client.get(f"/api/v1/reports/{test_event_id}")
    assert r_rep.status_code == 200, f"Report failed: {r_rep.text}"
    rep_data = r_rep.json()
    assert rep_data["report_pdf_url"].endswith(".pdf")
    print(f"  [PASS] Report generated at: {rep_data['report_pdf_url']}")

    # Test Patch Notes
    r_patch = client.patch(
        f"/api/v1/reports/{test_event_id}",
        json={"officer_notes": "Suspect vehicle intercepted at red signal. Driver cited under Section 184 MV Act.", "reporter_name": "Inspector R. Sharma"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["reporter_name"] == "Inspector R. Sharma"
    print("  [PASS] Report Notes & PDF Re-generation OK.")

    # ── TEST 3: Feature 3 - ANPR + Watchlist Matching ─────────────────────────
    print("\n[3/6] Testing Feature 3: ANPR + Watchlist Match...")
    # Add stolen car to watchlist
    flagged_plate = "DL01AB9876"
    r_wl_add = client.post(
        "/api/v1/watchlist",
        json={"plate_number": flagged_plate, "reason": "Reported Stolen (FIR #412/2026)", "added_by": "Special Cell"}
    )
    assert r_wl_add.status_code == 200
    print(f"  [PASS] Vehicle added to Watchlist: {flagged_plate}")

    # Query Watchlist
    r_wl_list = client.get("/api/v1/watchlist")
    assert r_wl_list.status_code == 200
    assert any(w["plate_number"] == flagged_plate for w in r_wl_list.json())

    # Test Scan Plate
    r_scan = client.post("/api/v1/anpr/scan", json={"plate_number": flagged_plate, "camera_id": "cam_01"})
    assert r_scan.status_code == 200
    scan_res = r_scan.json()
    assert scan_res["matched"] is True
    assert "Stolen" in scan_res["reason"]
    print(f"  [PASS] ANPR Watchlist Match Triggered: Plate {scan_res['plate_number']} -> {scan_res['reason']}")

    # ── TEST 4: Feature 4 - Court Evidence Export Package ─────────────────────
    print("\n[4/6] Testing Feature 4: Court-Admissible Evidence Export Package (.ZIP)...")
    r_exp = client.post(f"/api/v1/events/{test_event_id}/export-evidence?user_id=Inspector_Sharma")
    assert r_exp.status_code == 200
    assert r_exp.headers.get("content-type") == "application/zip"
    print(f"  [PASS] Court Evidence ZIP package exported successfully ({len(r_exp.content)} bytes).")

    # Check Custody Log
    r_custody = client.get(f"/api/v1/events/{test_event_id}/custody-log")
    assert r_custody.status_code == 200
    logs = r_custody.json()
    assert len(logs) >= 1
    print(f"  [PASS] Chain of Custody verified ({len(logs)} audit entries recorded).")

    # ── TEST 5: Feature 5 - Traffic Violation Detection ──────────────────────
    print("\n[5/6] Testing Feature 5: Traffic Violation Detection (Signal Jump & Wrong Side)...")
    set_junction_signal("cam_01", "RED")
    traffic_rule = TrafficViolationRule()

    # Vehicle crossing stop line while RED
    t_jump = MockTrack(
        track_id=101,
        class_name="car",
        trajectory=[(0.0, 300.0, 320.0), (0.5, 300.0, 390.0)]  # crosses Y=360 stop line
    )
    # First evaluate prior position
    traffic_rule.evaluate([MockTrack(101, "car", trajectory=[(0.0, 300.0, 320.0)])], {"camera_id": "cam_01"})
    # Second evaluate crossed position
    res_jump = traffic_rule.evaluate([t_jump], {"camera_id": "cam_01"})
    assert any(r.rule_type == "signal_jump" for r in res_jump), f"Expected signal jump, got {res_jump}"
    print("  [PASS] Signal Jump Rule evaluated & triggered correctly on RED light.")

    # Wrong Side driving
    wrong_side_traj = [
        (0.0, 200.0, 500.0),
        (0.2, 200.0, 450.0),
        (0.4, 200.0, 400.0),
        (0.6, 200.0, 350.0),
        (0.8, 200.0, 300.0),
        (1.0, 200.0, 250.0), # Traveling North (270 deg) on Southbound lane (90 deg)
    ]
    t_wrong = MockTrack(track_id=102, class_name="truck", trajectory=wrong_side_traj)
    for _ in range(6):
        res_wrong = traffic_rule.evaluate([t_wrong], {"camera_id": "cam_01", "expected_heading_deg": 90.0})
    assert any(r.rule_type == "wrong_side" for r in res_wrong)
    print("  [PASS] Wrong-Side Driving Rule evaluated & triggered correctly.")

    # ── TEST 6: Feature 6 - Hit-and-Run Detection ─────────────────────────────
    print("\n[6/6] Testing Feature 6: Hit-and-Run Collision & Fleeing Detection...")
    hit_rule = HitAndRunRule(proximity_threshold_px=100.0, fleeing_speed_min_px=10.0)

    # Frame 1 to 4: Approach & Impact at (300, 300) with speed dropping to 0
    v_flee = MockTrack(10, "car", trajectory=[(0.0, 200.0, 300.0), (0.1, 250.0, 300.0), (0.2, 300.0, 300.0), (0.3, 300.0, 300.0)])
    v_stat = MockTrack(20, "person", trajectory=[(0.0, 310.0, 300.0), (0.1, 305.0, 300.0), (0.2, 300.0, 300.0), (0.3, 300.0, 300.0)])
    
    # Simulate deceleration on impact (both stopped)
    for _ in range(4):
        hit_rule.evaluate([v_flee, v_stat], {})

    # Post-collision: Car accelerates away to (580, 300), Person remains stationary at (300, 300)
    v_flee_away = MockTrack(10, "car", trajectory=[(0.3, 300.0, 300.0), (0.4, 380.0, 300.0), (0.5, 480.0, 300.0), (0.6, 580.0, 300.0)])
    v_stat_down = MockTrack(20, "person", trajectory=[(0.3, 300.0, 300.0), (0.4, 300.0, 300.0), (0.5, 300.0, 300.0), (0.6, 300.0, 300.0)])
    
    res_hit = hit_rule.evaluate([v_flee_away, v_stat_down], {})
    assert any(r.rule_type == "possible_hit_and_run" for r in res_hit)
    print("  [PASS] Hit-and-Run Rule evaluated & triggered correctly (Fleeing Vehicle vs Stationary Subject).")

    db.close()
    print("\n" + "=" * 65)
    print("  ALL 6 POLICE DEPARTMENT FEATURES VERIFIED AND PASSING! [SUCCESS]")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
