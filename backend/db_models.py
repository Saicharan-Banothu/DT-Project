"""
SentiCall v3 — SQLAlchemy Database Models
Stores ONLY identity, sessions, consent, non-sensitive settings, and content-free security events.
CRITICAL PRIVACY RULE: Audio, transcripts, and call content are NEVER stored in this database.
"""

import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from backend.config import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    google_sub = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    picture_url = Column(String(512), nullable=True)
    role = Column(String(32), default="user", nullable=False) # 'user' or 'admin'
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    consent_version = Column(String(32), default="v3.0", nullable=False)
    consent_timestamp = Column(DateTime, nullable=True)
    
    # Non-sensitive UI preferences stored as JSON string
    preferences_json = Column(Text, default="{}", nullable=False)
    is_suspended = Column(Boolean, default=False, nullable=False)

    sessions = relationship("SessionModel", back_populates="user", cascade="all, delete-orphan")
    security_events = relationship("SecurityLog", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        import json
        prefs = {}
        try:
            prefs = json.loads(self.preferences_json) if self.preferences_json else {}
        except Exception:
            pass
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture_url": self.picture_url,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "consent_version": self.consent_version,
            "consent_timestamp": self.consent_timestamp.isoformat() if self.consent_timestamp else None,
            "preferences": prefs,
            "is_suspended": self.is_suspended
        }

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash = Column(String(64), unique=True, index=True, nullable=False) # SHA-256 of session token
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_active_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    ip_hash = Column(String(64), nullable=True) # Hashed IP
    user_agent = Column(String(255), nullable=True)
    csrf_token = Column(String(64), nullable=False)

    user = relationship("User", back_populates="sessions")

class SecurityLog(Base):
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(String(64), nullable=False) # login, logout, consent_change, settings_update, delete_account, suspend
    ip_hash = Column(String(64), nullable=True)
    details_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="security_events")

# Database Engine & Session Factory
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # Ensure directory exists for sqlite file
    if "///" in DATABASE_URL:
        db_file = DATABASE_URL.split("///")[1]
        os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

# Auto-initialize tables upon module load
try:
    init_db()
except Exception:
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

