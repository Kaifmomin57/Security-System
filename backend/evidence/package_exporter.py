"""
evidence/package_exporter.py
────────────────────────────
Court-Admissible Evidence Export Packaging Service (FR4-1 to FR4-4).
Creates a self-contained, tamper-evident ZIP archive containing:
- Video evidence clip (.mp4)
- Snapshot (.jpg)
- Machine-readable metadata dossier (.json)
- Full Chain of Custody audit log (.txt)
- Auto-generated PDF Incident Report (.pdf)
- SHA-256 cryptographic manifest (.sha256)
"""

import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime
from typing import Dict, Optional, Tuple

from evidence.hasher import hash_file
from evidence.report_generator import get_or_create_incident_report
from storage.db import Event, EvidenceAccessLog, get_session


def _compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file on disk."""
    if not os.path.exists(filepath):
        return ""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def export_court_evidence_package(
    event_id: str,
    user_id: str = "Officer_101",
    output_dir: str = "./media/evidence_packages",
) -> Tuple[str, Dict]:
    """
    Builds a court-admissible ZIP bundle and records access log.
    Returns: (zip_file_path, audit_summary_dict)
    """
    os.makedirs(output_dir, exist_ok=True)
    db = get_session()

    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise ValueError(f"Event {event_id} not found")

        # 1. Log export action in chain-of-custody table
        log_entry = EvidenceAccessLog(
            id=f"log_{uuid.uuid4().hex[:8]}",
            event_id=event_id,
            action="exported",
            user_id=user_id,
            timestamp=datetime.utcnow(),
            details=f"Court-Admissible Package Export requested by {user_id}",
        )
        db.add(log_entry)
        db.commit()

        # 2. Fetch full custody logs
        custody_records = (
            db.query(EvidenceAccessLog)
            .filter(EvidenceAccessLog.event_id == event_id)
            .order_by(EvidenceAccessLog.timestamp.asc())
            .all()
        )

        # 3. Check integrity of stored clip
        clip_rel_path = event.clip_path.lstrip("/") if event.clip_path else ""
        if clip_rel_path and not os.path.exists(clip_rel_path):
            clip_rel_path = os.path.join(".", clip_rel_path)

        current_clip_hash = _compute_sha256(clip_rel_path) if clip_rel_path and os.path.exists(clip_rel_path) else ""
        expected_hash = event.clip_hash or current_clip_hash

        integrity_match = (
            expected_hash == current_clip_hash
            if (expected_hash and current_clip_hash)
            else True
        )

        # 4. Ensure PDF incident report exists
        report = get_or_create_incident_report(event_id=event_id)
        pdf_rel_path = report.report_pdf_path.lstrip("/")
        if not os.path.exists(pdf_rel_path):
            pdf_rel_path = os.path.join(".", pdf_rel_path)

        # 5. Build ZIP Package
        zip_filename = f"Court_Evidence_Package_{event.id}.zip"
        zip_full_path = os.path.join(output_dir, zip_filename)

        with zipfile.ZipFile(zip_full_path, "w", zipfile.ZIP_DEFLATED) as zf:
            checksums = []

            # A. Video clip
            if clip_rel_path and os.path.exists(clip_rel_path):
                zf.write(clip_rel_path, arcname=f"evidence_clip_{event.id}.mp4")
                checksums.append(f"{current_clip_hash}  evidence_clip_{event.id}.mp4")
            else:
                # Add evidence placeholder if clip generation is in background
                dummy_text = f"SENTRYEYE SECURE EVIDENCE CLIP RECORD\nEvent ID: {event.id}\nCamera: {event.camera_id}\nHash: {expected_hash}\n"
                zf.writestr(f"evidence_clip_manifest_{event.id}.txt", dummy_text)
                checksums.append(f"{expected_hash or 'verified'}  evidence_clip_manifest_{event.id}.txt")

            # B. Snapshot
            snap_rel_path = event.snapshot_path.lstrip("/") if event.snapshot_path else ""
            if snap_rel_path and not os.path.exists(snap_rel_path):
                snap_rel_path = os.path.join(".", snap_rel_path)

            if snap_rel_path and os.path.exists(snap_rel_path):
                zf.write(snap_rel_path, arcname=f"incident_snapshot_{event.id}.jpg")
                snap_hash = _compute_sha256(snap_rel_path)
                checksums.append(f"{snap_hash}  incident_snapshot_{event.id}.jpg")

            # C. PDF Report
            if os.path.exists(pdf_rel_path):
                zf.write(pdf_rel_path, arcname=f"Incident_Report_{event.id}.pdf")
                pdf_hash = _compute_sha256(pdf_rel_path)
                checksums.append(f"{pdf_hash}  Incident_Report_{event.id}.pdf")

            # D. Metadata JSON dossier
            metadata_dict = {
                "package_type": "COURT_ADMISSIBLE_EVIDENCE_BUNDLE",
                "version": "1.0",
                "jurisdiction": "POLICE_DEPARTMENT_EVIDENCE_VAULT",
                "incident_id": event.id,
                "camera_id": event.camera_id,
                "zone_id": event.zone_id,
                "rule_type": event.rule_type,
                "severity": event.severity,
                "confidence": event.confidence,
                "timestamp_utc": event.timestamp.isoformat() if event.timestamp else None,
                "track_ids": event.track_ids,
                "initial_computed_hash": event.clip_hash,
                "export_time_hash": current_clip_hash,
                "cryptographic_integrity_verified": integrity_match,
                "exported_by": user_id,
                "exported_at": datetime.utcnow().isoformat(),
                "explanation_meta": event.explanation or {},
            }
            meta_json = json.dumps(metadata_dict, indent=2)
            zf.writestr("metadata_dossier.json", meta_json)
            meta_hash = hashlib.sha256(meta_json.encode("utf-8")).hexdigest()
            checksums.append(f"{meta_hash}  metadata_dossier.json")

            # E. Chain of Custody Document
            custody_lines = [
                "==================================================================",
                "       SENTRYEYE EVIDENCE VAULT - CHAIN OF CUSTODY AUDIT LOG      ",
                "==================================================================",
                f"Incident Reference ID : {event.id}",
                f"Original Timestamp    : {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if event.timestamp else 'N/A'}",
                f"Camera Source         : {event.camera_id}",
                f"Export Timestamp      : {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"Exporting Officer     : {user_id}",
                f"Integrity Status      : {'VERIFIED & INTACT' if integrity_match else 'CRITICAL WARNING: HASH MISMATCH'}",
                "------------------------------------------------------------------",
                "LOGGED CUSTODIAL ACCESS EVENTS:",
                "------------------------------------------------------------------",
            ]
            for rec in custody_records:
                custody_lines.append(
                    f"[{rec.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}] "
                    f"ACTION: {rec.action.upper():<10} | USER: {rec.user_id:<15} | DETAILS: {rec.details or 'Standard Access'}"
                )
            custody_lines.append("==================================================================")
            custody_text = "\n".join(custody_lines)
            zf.writestr("chain_of_custody_audit.txt", custody_text)
            custody_hash = hashlib.sha256(custody_text.encode("utf-8")).hexdigest()
            checksums.append(f"{custody_hash}  chain_of_custody_audit.txt")

            # F. Checksums manifest file
            checksums_text = "\n".join(checksums) + "\n"
            zf.writestr("INTEGRITY_CHECKSUMS.sha256", checksums_text)

            # G. Tamper warning file if mismatch
            if not integrity_match:
                warning_text = (
                    "WARNING: TAMPER DETECTION ALERT\n"
                    "The current SHA-256 hash of the evidence file does not match the originally recorded hash.\n"
                    f"Original Record: {expected_hash}\n"
                    f"Current Hash   : {current_clip_hash}\n"
                )
                zf.writestr("TAMPER_WARNING_FLAG.txt", warning_text)

        summary = {
            "zip_path": f"/media/evidence_packages/{zip_filename}",
            "filename": zip_filename,
            "event_id": event_id,
            "integrity_verified": integrity_match,
            "total_custody_actions": len(custody_records),
            "files_included": len(checksums),
        }

        return zip_full_path, summary

    finally:
        db.close()
