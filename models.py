from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # Nullable so a Google-only account does not need a local password.
    password = Column(String(255), nullable=True)
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    avatar_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    created_meetings = relationship("Meeting", back_populates="creator")
    assigned_tasks = relationship("Task", foreign_keys="Task.assigned_to_id", back_populates="assigned_to")
    given_tasks = relationship("Task", foreign_keys="Task.assigned_by_id", back_populates="assigned_by")


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    code = Column(String(12), unique=True, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="created_meetings")
    participants = relationship("MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="meeting", cascade="all, delete-orphan")


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "user_id", name="uq_meeting_user"),)
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deadline = Column(String(100), nullable=True)
<<<<<<< HEAD
    deadline_at = Column(DateTime, nullable=True, index=True)
    deadline_status = Column(String(50), default="OnTrack", nullable=False)
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
    # Pending -> Submitted -> Completed, or Rejected -> Pending for resubmission.
    status = Column(String(50), default="Pending", nullable=False)
    submission = Column(Text, nullable=True)
    submission_filename = Column(String(255), nullable=True)
    submission_stored_name = Column(String(255), nullable=True)
    submission_content_type = Column(String(255), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    approval_note = Column(Text, nullable=True)
<<<<<<< HEAD
    ai_review_status = Column(String(50), default="NotReviewed", nullable=False)
    ai_review_reason = Column(Text, nullable=True)
    ai_corrected_submission = Column(Text, nullable=True)
    ai_reviewed_at = Column(DateTime, nullable=True)
    ai_confidence = Column(String(20), nullable=True)
    completion_declared_at = Column(DateTime, nullable=True)
    completion_statement = Column(Text, nullable=True)
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
    approved_at = Column(DateTime, nullable=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="tasks")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], back_populates="assigned_tasks")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id], back_populates="given_tasks")
<<<<<<< HEAD


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    speaker_name = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    meeting = relationship("Meeting")
    user = relationship("User")
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
