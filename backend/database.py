import os
from sqlalchemy import create_engine, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, Float, String, ForeignKey
from datetime import datetime
from zoneinfo import ZoneInfo
from datetime import datetime

IST = ZoneInfo("Asia/Kolkata")


# Database URL
DATABASE_URL = "sqlite:///./sepsis.db"

# Create engine and session
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


class Patient(Base):
    """Patient model for database."""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    Patient_ID = Column(String, index=True)
    Hour = Column(Integer, nullable=True)
    HR = Column(Float, nullable=True)
    O2Sat = Column(Float, nullable=True)
    Temp = Column(Float, nullable=True)
    SBP = Column(Float, nullable=True)
    MAP = Column(Float, nullable=True)
    DBP = Column(Float, nullable=True)
    Resp = Column(Float, nullable=True)
    RiskScore = Column(Float, nullable=True)
    Age = Column(Integer)
    Gender = Column(Integer)
    Name = Column(String, nullable=True)
    Unit1 = Column(Integer)
    Unit2 = Column(Integer)
    


class PatientVitals(Base):
    """Vital signs readings for patients over time."""
    __tablename__ = "patient_vitals"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.Patient_ID"), index=True)

    timestamp = Column(DateTime, default=lambda: datetime.now(IST))
    heart_rate = Column(Float)
    oxygen_saturation = Column(Float)
    sbp = Column(Float)
    dbp = Column(Float)
    map = Column(Float)
    respiratory_rate = Column(Float)
    temperature = Column(Float)
    sepsis_risk_score = Column(Float, nullable=True)


class HourlyVitals(Base):
    """Aggregated hourly vital signs for patients."""
    __tablename__ = "hourly_vitals"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.Patient_ID"), index=True)
    hour_timestamp = Column(DateTime, index=True)  # Start of hour in IST
    
    # Aggregated vitals (averages)
    avg_heart_rate = Column(Float, nullable=True)
    avg_oxygen_saturation = Column(Float, nullable=True)
    avg_sbp = Column(Float, nullable=True)
    avg_dbp = Column(Float, nullable=True)
    avg_map = Column(Float, nullable=True)
    avg_respiratory_rate = Column(Float, nullable=True)
    avg_temperature = Column(Float, nullable=True)
    
    # Status and metadata
    status_flag = Column(String)  # "normal", "delayed", "missing", "estimated"
    data_reliability_score = Column(Float, nullable=True)  # 0.0-1.0
    disclaimer = Column(String, nullable=True)  # For delayed/missing data
    minute_readings_count = Column(Integer, default=0)  # How many minute-level readings aggregated
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(IST))
    updated_at = Column(DateTime, default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST))


class Notification(Base):
    """Notification for upcoming vital sign readings."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.Patient_ID"), index=True)
    
    # When the next vitals reading is due
    due_time = Column(DateTime, index=True)
    
    # When the notification should be triggered (1 minute before due_time)
    trigger_time = Column(DateTime, index=True)
    
    # Notification message
    message = Column(String)
    
    # Status: "pending", "triggered", "read", "dismissed", "cleared"
    status = Column(String, default="pending")
    
    # When notification was actually triggered
    triggered_at = Column(DateTime, nullable=True)
    
    # When notification was dismissed/read/cleared
    resolved_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(IST), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST))

# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
