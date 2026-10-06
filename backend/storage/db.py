"""
storage/db.py
─────────────
SQLAlchemy models for PostgreSQL.
All 7 tables from the data model spec.
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, create_engine, text,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sentryeye_user:yourpassword@localhost:5432/sentryeye")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,           # reconnect on stale connections
    pool_size=5,
    max_overflow=10,
    echo=False,                   # set True to debug SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ─── Models ───────────────────────────────────────────────────────────────────

class Camera(Base):
    __tablename__ = "cameras"

    id          = Column(String, primary_key=True, default=lambda: f"cam_{uuid.uuid4().hex[:6]}")
    name        = Column(String, nullable=False)
    source_url  = Column(String, nullable=False)   # RTSP URL or file path
    status      = Column(String, default="offline") # online / offline
    created_at  = Column(DateTime, default=datetime.utcnow)

    zones       = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    events      = relationship("Event", back_populates="camera")
    tracks      = relationship("TrackRecord", back_populates="camera")
    baselines   = relationship("CameraBaseline", back_populates="camera")


class Zone(Base):
    __tablename__ = "zones"

    id          = Column(String, primary_key=True, default=lambda: f"zone_{uuid.uuid4().hex[:6]}")
    camera_id   = Column(String, ForeignKey("cameras.id"), nullable=False)
    name        = Column(String, nullable=False)
    polygon     = Column(JSONB, nullable=False)     # [[x,y], ...]
    created_at  = Column(DateTime, default=datetime.utcnow)

    camera      = relationship("Camera", back_populates="zones")
    rules       = relationship("ZoneRule", back_populates="zone", cascade="all, delete-orphan")
    events      = relationship("Event", back_populates="zone")


class ZoneRule(Base):
    __tablename__ = "zone_rules"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    zone_id             = Column(String, ForeignKey("zones.id"), nullable=False)
    rule_type           = Column(String, nullable=False)  # loitering / intrusion / trailing / crowd
    threshold_seconds   = Column(Integer, nullable=True)
    active_hours        = Column(String, nullable=True)   # e.g. "22:00-06:00"
    enabled             = Column(Boolean, default=True)

    zone                = relationship("Zone", back_populates="rules")


class TrackRecord(Base):
    __tablename__ = "tracks"

    id          = Column(Integer, primary_key=True)        # track_id from DeepSORT
    camera_id   = Column(String, ForeignKey("cameras.id"))
    class_name  = Column(String)
    first_seen  = Column(DateTime, default=datetime.utcnow)
    last_seen   = Column(DateTime, default=datetime.utcnow)
    trajectory  = Column(JSONB)                             # [{t, x, y}, ...]

    camera      = relationship("Camera", back_populates="tracks")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_zone_time", "zone_id", "timestamp"),
        Index("idx_events_camera_time", "camera_id", "timestamp"),
        Index("idx_events_rule_time", "rule_type", "timestamp"),
    )

    id              = Column(String, primary_key=True, default=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    camera_id       = Column(String, ForeignKey("cameras.id"), nullable=False)
    zone_id         = Column(String, ForeignKey("zones.id"), nullable=True)
    rule_type       = Column(String, nullable=False)
    confidence      = Column(Float, nullable=False)
    severity        = Column(String, default="low")        # low / medium / high
    status          = Column(String, default="new")        # new / acknowledged / resolved / dismissed
    track_ids       = Column(JSONB)                        # [47, 52]
    snapshot_path   = Column(String, nullable=True)
    clip_path       = Column(String, nullable=True)
    clip_hash       = Column(String, nullable=True)        # SHA-256
    explanation     = Column(JSONB, nullable=True)         # polygon/trajectory/rule metadata
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)
    responder       = Column(String, nullable=True)
    resolved_at     = Column(DateTime, nullable=True)

    camera          = relationship("Camera", back_populates="events")
    zone            = relationship("Zone", back_populates="events")
    feedback        = relationship("AlertFeedback", back_populates="event", cascade="all, delete-orphan")
    incident_report = relationship("IncidentReport", back_populates="event", uselist=False, cascade="all, delete-orphan")
    evidence_logs   = relationship("EvidenceAccessLog", back_populates="event", cascade="all, delete-orphan")
    traffic_violation = relationship("TrafficViolation", back_populates="event", uselist=False, cascade="all, delete-orphan")
    collision_event   = relationship("CollisionEvent", back_populates="event", uselist=False, cascade="all, delete-orphan")


class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id              = Column(String, primary_key=True, default=lambda: f"rep_{uuid.uuid4().hex[:8]}")
    event_id        = Column(String, ForeignKey("events.id"), nullable=False, unique=True)
    generated_at    = Column(DateTime, default=datetime.utcnow)
    report_pdf_path = Column(String, nullable=False)
    officer_notes   = Column(Text, nullable=True)
    reporter_name   = Column(String, nullable=True, default="Control Room Officer")

    event           = relationship("Event", back_populates="incident_report")


class WatchlistVehicle(Base):
    __tablename__ = "watchlist_vehicles"

    plate_number    = Column(String, primary_key=True)  # normalized uppercase e.g. "DL01AB1234"
    reason          = Column(String, nullable=False)    # Stolen / Wanted / Suspicious / Banned
    added_by        = Column(String, default="System Admin")
    added_at        = Column(DateTime, default=datetime.utcnow)


class PlateRead(Base):
    __tablename__ = "plate_reads"

    id              = Column(String, primary_key=True, default=lambda: f"read_{uuid.uuid4().hex[:8]}")
    camera_id       = Column(String, ForeignKey("cameras.id"), nullable=False)
    plate_number    = Column(String, nullable=False, index=True)
    ocr_confidence  = Column(Float, nullable=False)
    matched         = Column(Boolean, default=False)
    reason          = Column(String, nullable=True)
    snapshot_path   = Column(String, nullable=True)
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)

    camera          = relationship("Camera")


class EvidenceAccessLog(Base):
    __tablename__ = "evidence_access_log"

    id              = Column(String, primary_key=True, default=lambda: f"log_{uuid.uuid4().hex[:8]}")
    event_id        = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    action          = Column(String, nullable=False)   # viewed / exported / verified
    user_id         = Column(String, nullable=False, default="Officer_101")
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)
    details         = Column(Text, nullable=True)

    event           = relationship("Event", back_populates="evidence_logs")


class TrafficViolation(Base):
    __tablename__ = "traffic_violations"

    id                  = Column(String, primary_key=True, default=lambda: f"tv_{uuid.uuid4().hex[:8]}")
    event_id            = Column(String, ForeignKey("events.id"), nullable=False, unique=True)
    junction_id         = Column(String, nullable=False, index=True)
    violation_type      = Column(String, nullable=False) # signal_jump / wrong_side
    plate_number        = Column(String, nullable=True)
    signal_state        = Column(String, nullable=True)  # RED / GREEN / YELLOW
    lane_id             = Column(String, nullable=True)
    speed_estimate_kmh  = Column(Float, nullable=True)
    timestamp           = Column(DateTime, default=datetime.utcnow, index=True)

    event               = relationship("Event", back_populates="traffic_violation")


class CollisionEvent(Base):
    __tablename__ = "collision_events"

    id                      = Column(String, primary_key=True, default=lambda: f"col_{uuid.uuid4().hex[:8]}")
    event_id                = Column(String, ForeignKey("events.id"), nullable=False, unique=True)
    track_id_fleeing        = Column(Integer, nullable=False)
    track_id_stationary     = Column(Integer, nullable=False)
    plate_number            = Column(String, nullable=True)
    collision_speed_drop    = Column(Float, nullable=True)
    fleeing_velocity        = Column(Float, nullable=True)
    timestamp               = Column(DateTime, default=datetime.utcnow, index=True)

    event                   = relationship("Event", back_populates="collision_event")


class AlertFeedback(Base):
    __tablename__ = "alert_feedback"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(String, ForeignKey("events.id"), nullable=False)
    camera_id   = Column(String, nullable=False)
    rule_type   = Column(String, nullable=False)
    action      = Column(String, nullable=False)          # dismissed / confirmed
    timestamp   = Column(DateTime, default=datetime.utcnow)

    event       = relationship("Event", back_populates="feedback")


class TrackClassification(Base):
    __tablename__ = "track_classifications"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    track_id            = Column(Integer, nullable=False)
    stature_class       = Column(String, nullable=False)   # small / adult / ambiguous
    confidence          = Column(Float, nullable=False)
    camera_calib_ref    = Column(String, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow)


class UnaccompaniedEvent(Base):
    __tablename__ = "unaccompanied_events"

    id                      = Column(String, primary_key=True, default=lambda: f"una_{uuid.uuid4().hex[:8]}")
    event_id                = Column(String, ForeignKey("events.id"), nullable=True)
    track_id                = Column(Integer, nullable=False)
    last_adult_seen_at      = Column(DateTime, nullable=True)
    duration_alone_seconds  = Column(Integer, nullable=False)
    created_at              = Column(DateTime, default=datetime.utcnow)


class TrailingEvent(Base):
    __tablename__ = "trailing_events"

    id                  = Column(String, primary_key=True, default=lambda: f"trl_{uuid.uuid4().hex[:8]}")
    event_id            = Column(String, ForeignKey("events.id"), nullable=True)
    track_id_follower   = Column(Integer, nullable=False)
    track_id_followed   = Column(Integer, nullable=False)
    duration_seconds    = Column(Float, nullable=False)
    avg_distance        = Column(Float, nullable=False)
    ambient_count       = Column(Integer, default=1)
    confidence          = Column(Float, nullable=False)
    timestamp           = Column(DateTime, default=datetime.utcnow, index=True)


class GestureEvent(Base):
    __tablename__ = "gesture_events"

    id              = Column(String, primary_key=True, default=lambda: f"ges_{uuid.uuid4().hex[:8]}")
    event_id        = Column(String, ForeignKey("events.id"), nullable=True)
    track_id        = Column(Integer, nullable=False)
    camera_id       = Column(String, nullable=False)
    gesture_type    = Column(String, default="signal_for_help")
    confidence      = Column(Float, nullable=False)
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)
    snapshot_path   = Column(String, nullable=True)


class ReidGallery(Base):
    __tablename__ = "reid_gallery"

    id                  = Column(String, primary_key=True, default=lambda: f"gal_{uuid.uuid4().hex[:8]}")
    track_id            = Column(Integer, nullable=False, index=True)
    camera_id           = Column(String, nullable=False)
    embedding_vector    = Column(JSONB, nullable=False) # list of floats
    last_seen_at        = Column(DateTime, default=datetime.utcnow, index=True)
    snapshot_path       = Column(String, nullable=True)


class ReidMatch(Base):
    __tablename__ = "reid_matches"

    id                      = Column(String, primary_key=True, default=lambda: f"rem_{uuid.uuid4().hex[:8]}")
    original_track_id       = Column(Integer, nullable=False, index=True)
    matched_track_id        = Column(Integer, nullable=False)
    camera_id_matched       = Column(String, nullable=False)
    similarity_score        = Column(Float, nullable=False)
    confirmed_by_operator   = Column(Boolean, nullable=True, default=None) # None = unconfirmed, True = confirmed, False = rejected
    timestamp               = Column(DateTime, default=datetime.utcnow, index=True)


class WeaponEvent(Base):
    __tablename__ = "weapon_events"

    id              = Column(String, primary_key=True, default=lambda: f"wep_{uuid.uuid4().hex[:8]}")
    event_id        = Column(String, ForeignKey("events.id"), nullable=True)
    track_id        = Column(Integer, nullable=True)
    weapon_class    = Column(String, nullable=False) # pistol / knife / gun
    confidence      = Column(Float, nullable=False)
    camera_id       = Column(String, nullable=False)
    is_reviewed     = Column(Boolean, default=False)
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)


class AbandonedObjectEvent(Base):
    __tablename__ = "abandoned_object_events"

    id                  = Column(String, primary_key=True, default=lambda: f"abn_{uuid.uuid4().hex[:8]}")
    event_id            = Column(String, ForeignKey("events.id"), nullable=True)
    object_track_id     = Column(Integer, nullable=False)
    object_class        = Column(String, nullable=False) # backpack / suitcase / handbag
    duration_unattended = Column(Float, nullable=False)
    camera_id           = Column(String, nullable=False)
    timestamp           = Column(DateTime, default=datetime.utcnow, index=True)


class AudioEvent(Base):
    __tablename__ = "audio_events"

    id                  = Column(String, primary_key=True, default=lambda: f"aev_{uuid.uuid4().hex[:8]}")
    camera_id           = Column(String, ForeignKey("cameras.id"), nullable=False)
    sound_class         = Column(String, nullable=False)   # Screaming / Shout / Glass / Gunshot / Distress
    confidence          = Column(Float, nullable=False)
    timestamp           = Column(DateTime, default=datetime.utcnow, index=True)
    fused_event_id      = Column(String, ForeignKey("events.id"), nullable=True)
    status              = Column(String, default="unconfirmed_visually") # unconfirmed_visually / fused / dismissed

    camera              = relationship("Camera")
    fused_event         = relationship("Event")


class CameraBaseline(Base):
    __tablename__ = "camera_baselines"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    camera_id       = Column(String, ForeignKey("cameras.id"), nullable=False)
    rule_type       = Column(String, nullable=False)
    mean_value      = Column(Float, nullable=False)
    std_dev         = Column(Float, nullable=False)
    sample_count    = Column(Integer, default=0)
    last_updated    = Column(DateTime, default=datetime.utcnow)

    camera          = relationship("Camera", back_populates="baselines")


# ─── Utilities ────────────────────────────────────────────────────────────────

def create_tables():
    """Create all tables (run once at startup)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """Use this outside FastAPI (e.g. in pipeline.py)."""
    return SessionLocal()
