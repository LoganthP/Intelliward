from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from .session import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    access_role: Mapped[str] = mapped_column(String(20))  # admin | supervisor | staff
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))  # nurse | doctor | ot_staff | cleaner
    department: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_recorded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    images: Mapped[list["EnrollmentImage"]] = relationship(back_populates="staff", cascade="all, delete-orphan")
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(back_populates="staff", cascade="all, delete-orphan")
    access: Mapped[list["StaffWardAccess"]] = relationship(back_populates="staff", cascade="all, delete-orphan")


class EnrollmentImage(Base):
    __tablename__ = "enrollment_images"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    staff: Mapped[Staff] = relationship(back_populates="images")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"
    __table_args__ = (UniqueConstraint("staff_id", "model_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    model_version: Mapped[str] = mapped_column(String(64))
    encrypted_vector: Mapped[str] = mapped_column(Text)
    num_images: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    staff: Mapped[Staff] = relationship(back_populates="embeddings")


class Ward(Base):
    __tablename__ = "wards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(120), default="")
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    prolonged_stay_minutes: Mapped[int] = mapped_column(Integer, default=60)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    source: Mapped[str] = mapped_column(String(500), default="0")  # webcam index, file path or rtsp url
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # desired running state
    status: Mapped[str] = mapped_column(String(20), default="stopped")  # stopped | starting | online | offline
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    zones: Mapped[list] = mapped_column(JSON, default=list)  # [{name, x1, y1, x2, y2}] normalized
    ward: Mapped[Ward] = relationship()


class StaffWardAccess(Base):
    __tablename__ = "staff_ward_access"
    __table_args__ = (UniqueConstraint("staff_id", "ward_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"))
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id", ondelete="CASCADE"))
    staff: Mapped[Staff] = relationship(back_populates="access")


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (UniqueConstraint("camera_id", "track_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    track_key: Mapped[str] = mapped_column(String(64))
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    identity_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | verified | unknown
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    role_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mismatch_count: Mapped[int] = mapped_column(Integer, default=0)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (Index("ix_visits_entry", "entry_at"), Index("ix_visits_staff_ward", "staff_id", "ward_id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"))
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    entry_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="provisional")  # provisional | active | exited
    fragments: Mapped[int] = mapped_column(Integer, default=1)
    track_keys: Mapped[list] = mapped_column(JSON, default=list)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    staff: Mapped[Staff] = relationship()
    ward: Mapped[Ward] = relationship()


class Task(Base):
    __tablename__ = "task_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    task_type: Mapped[str] = mapped_column(String(32))  # ward_inspection | equipment_check | medication_delivery
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"))
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    required_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    min_duration_sec: Mapped[int] = mapped_column(Integer, default=30)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    accumulated_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    staff: Mapped[Staff] = relationship()
    ward: Mapped[Ward] = relationship()
    evidence: Mapped[list["TaskEvidence"]] = relationship(back_populates="task", cascade="all, delete-orphan",
                                                          order_by="TaskEvidence.id")


class TaskEvidence(Base):
    __tablename__ = "task_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task_assignments.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    verification_state: Mapped[str] = mapped_column(String(24), default="observed")
    task: Mapped[Task] = relationship(back_populates="evidence")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(12))  # low | medium | high | critical
    ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id", ondelete="SET NULL"), nullable=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    track_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | acknowledged | resolved | dismissed
    dedup_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    history: Mapped[list] = mapped_column(JSON, default=list)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    payload: Mapped[str] = mapped_column(Text)  # canonical JSON that is hashed
    prev_hash: Mapped[str] = mapped_column(String(64))
    curr_hash: Mapped[str] = mapped_column(String(64))


class AuditBatch(Base):
    __tablename__ = "audit_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    first_sequence: Mapped[int] = mapped_column(Integer)
    last_sequence: Mapped[int] = mapped_column(Integer)
    merkle_root: Mapped[str] = mapped_column(String(64))
    anchor_hash: Mapped[str] = mapped_column(String(64))
    external_reference: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
