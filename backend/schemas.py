"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PatientBase(BaseModel):
    """Base patient schema."""
    Patient_ID: str
    Hour: Optional[int] = None
    HR: Optional[float] = None
    O2Sat: Optional[float] = None
    Temp: Optional[float] = None
    SBP: Optional[float] = None
    MAP: Optional[float] = None
    DBP: Optional[float] = None
    Resp: Optional[float] = None
    Age: int
    Gender: int
    Name: Optional[str] = None
    Unit1: int
    Unit2: int
    RiskScore: Optional[float] = None


class PatientCreate(BaseModel):
    Patient_ID: str
    Age: int
    Gender: int
    Unit1: int
    Unit2: int
    Name: Optional[str] = None
    
    

class Patient(PatientBase):
    """Patient schema for responses."""
    id: int

    class Config:
        from_attributes = True


class VitalsCreate(BaseModel):
    """Schema for creating vital signs reading."""
    patient_id: str
    heart_rate: float
    oxygen_saturation: float
    sbp: float
    dbp: float
    map: float
    respiratory_rate: float
    temperature: float


class VitalsResponse(BaseModel):
    """Schema for vital signs response."""
    id: int
    patient_id: str
    timestamp: datetime
    heart_rate: float
    oxygen_saturation: float
    sbp: float
    dbp: float
    map: float
    respiratory_rate: float
    temperature: float
    sepsis_risk_score: Optional[float] = None

    class Config:
        from_attributes = True


class VitalsListResponse(BaseModel):
    """Response schema for vitals history."""
    patient_id: str
    total_readings: int
    vitals: list[VitalsResponse]


class LoadDataResponse(BaseModel):
    """Response schema for data loading."""
    message: str
    records_loaded: int
    records_filtered: int


class LSTMPredictionResponse(BaseModel):
    """Response schema for LSTM risk prediction."""
    patient_id: str
    lstm_risk_score: float
    total_readings: int
    message: str

    class Config:
        from_attributes = True


class PatientListResponse(BaseModel):
    """Response schema for patient list."""
    total_records: int
    patients: list[Patient]


class HourlyVitalsResponse(BaseModel):
    """Schema for hourly aggregated vitals."""
    patient_id: str
    hour_timestamp: datetime
    avg_heart_rate: Optional[float] = None
    avg_oxygen_saturation: Optional[float] = None
    avg_sbp: Optional[float] = None
    avg_dbp: Optional[float] = None
    avg_map: Optional[float] = None
    avg_respiratory_rate: Optional[float] = None
    avg_temperature: Optional[float] = None
    status_flag: str  # "normal", "delayed", "missing", "estimated"
    data_reliability_score: Optional[float] = None
    disclaimer: Optional[str] = None
    minute_readings_count: int

    class Config:
        from_attributes = True


class NotificationPayload(BaseModel):
    """Real-time notification payload sent to frontend."""
    timestamp: datetime  # When notification was created
    patient_id: str
    hour_timestamp: datetime  # The hour being reported
    status_flag: str  # "normal", "delayed", "missing", "estimated"
    data_reliability_score: Optional[float] = None
    disclaimer: Optional[str] = None
    message: str  # Human-readable message for dashboard
    vitals: Optional[dict] = None  # Aggregated vitals or None if missing
    minute_readings_count: Optional[int] = None


class HourlyVitalsListResponse(BaseModel):
    """Response schema for hourly vitals history."""
    patient_id: str
    total_hours: int
    hourly_records: list[HourlyVitalsResponse]
