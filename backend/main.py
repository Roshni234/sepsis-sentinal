
import os
import pandas as pd
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import get_db, Patient, PatientVitals, HourlyVitals, Notification, engine, Base
from lstm_predictor import predict_sepsis_risk, KERAS_AVAILABLE
from schemas import (
    PatientCreate,
    PatientBase,
    Patient as PatientSchema,
    VitalsCreate,
    VitalsResponse,
    VitalsListResponse,
    LoadDataResponse,
    PatientListResponse,
    LSTMPredictionResponse,
    HourlyVitalsResponse,
    HourlyVitalsListResponse,
    NotificationPayload,
)
from scheduler import hourly_aggregation_job, set_notification_callback, notification_reminder_job, resolve_overdue_notifications, manage_vital_update_notifications, reclassify_estimated_hour_with_late_vitals
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Sepsis Sentinel API",
    description="Backend API for Sepsis Sentinel Dashboard",
    version="1.0.0"
)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],

)

# Create tables on startup
Base.metadata.create_all(bind=engine)


# ============================================================================
# APScheduler Setup for Hourly Vitals Aggregation
# ============================================================================

# Store for recent notifications (in-memory, for simplicity)
recent_notifications = []
MAX_STORED_NOTIFICATIONS = 100


def notification_handler(notification: dict):
    """
    Handle notifications from the scheduler.
    In production, this would send to frontend via WebSocket or polling endpoint.
    """
    global recent_notifications
    
    # Add timestamp if not present
    if "timestamp" not in notification:
        notification["timestamp"] = datetime.now().isoformat()
    
    recent_notifications.append(notification)
    
    # Keep only recent notifications (memory limit)
    if len(recent_notifications) > MAX_STORED_NOTIFICATIONS:
        recent_notifications = recent_notifications[-MAX_STORED_NOTIFICATIONS:]
    
    logger.info(f"📢 Notification: {notification.get('message', 'N/A')}")


# Initialize scheduler
scheduler = BackgroundScheduler()
set_notification_callback(notification_handler)


@app.on_event("startup")
def startup_event():
    hourly_aggregation_job()   # immediate run
    notification_reminder_job()  # immediate reminder sync
    scheduler.start()
    """
    Startup event: Initialize and start the APScheduler.
    This runs when the FastAPI app starts.
    """
    try:
        logger.info("=" * 70)
        logger.info("STARTING APScheduler for Hourly Vitals Aggregation")
        logger.info("=" * 70)
        
        # Schedule the hourly job to run every hour
        scheduler.add_job(
            hourly_aggregation_job,
            "interval",
            hours =1,
            id="hourly_vitals_aggregation",
            name="Hourly Vitals Aggregation Job",
            replace_existing=True,
        )

        scheduler.add_job(
            notification_reminder_job,
            "interval",
            minutes=1,
            id="notification_reminder_job",
            name="Notification Reminder Job",
            replace_existing=True,
        )
        
        # Start the scheduler
        if not scheduler.running:
            scheduler.start()
            logger.info("✓ APScheduler started successfully")
            logger.info("✓ Job scheduled: hourly_vitals_aggregation (every 1 hour)")
        else:
            logger.info("✓ APScheduler already running")
        
        logger.info("=" * 70)
    
    except Exception as e:
        logger.error(f"✗ Failed to start APScheduler: {e}", exc_info=True)


@app.on_event("shutdown")
def shutdown_event():
    """
    Shutdown event: Gracefully stop the APScheduler.
    """
    try:
        logger.info("Shutting down APScheduler...")
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logger.info("✓ APScheduler shut down successfully")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"message": "Sepsis Sentinel API is running", "status": "healthy"}


@app.get("/api/scheduler-status")
def get_scheduler_status():
    """Get APScheduler status and next run time."""
    if not scheduler.running:
        return {
            "running": False,
            "message": "Scheduler is not running"
        }
    
    job = scheduler.get_job("hourly_vitals_aggregation")
    if not job:
        return {
            "running": True,
            "jobs": 0,
            "message": "Scheduler running but no hourly job found"
        }
    
    return {
        "running": True,
        "job_id": job.id,
        "job_name": job.name,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        "message": f"Scheduler active. Next aggregation at {job.next_run_time}"
    }


@app.get("/api/notifications")
def get_recent_notifications(limit: int = 50, db: Session = Depends(get_db)):
    """
    Get recent notifications from the scheduler.
    This endpoint is used by the frontend for polling notifications.
    
    Query Parameters:
    - limit: Maximum number of notifications to return (default: 50)
    """
    triggered_notifications = (
        db.query(Notification)
        .filter(Notification.status == "triggered")
        .order_by(Notification.triggered_at.desc(), Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    notifications_payload = [
        {
            "timestamp": (n.triggered_at or n.created_at).isoformat() if (n.triggered_at or n.created_at) else datetime.now().isoformat(),
            "patient_id": n.patient_id,
            "hour_timestamp": n.due_time.isoformat() if n.due_time else datetime.now().isoformat(),
            "status_flag": "missing",
            "data_reliability_score": 0.0,
            "disclaimer": "Vitals update is due now.",
            "message": n.message,
            "vitals": None,
            "minute_readings_count": 0,
        }
        for n in triggered_notifications
    ]

    return {
        "total": len(notifications_payload),
        "notifications": notifications_payload
    }


@app.post("/api/load-data", response_model=LoadDataResponse)
def load_csv_data(db: Session = Depends(get_db)):
    """
    Load CSV data into the database.
    Filters records where Hour = 15 and limits to 100 patients.
    """
    try:
        existing_records = db.query(Patient).count()
        if existing_records > 0:
            return LoadDataResponse(
                message="already loaded",
                records_loaded=0,
                records_filtered=0
            )

        # Find CSV file in the parent directory
        csv_path = os.path.join(os.path.dirname(__file__), "..", "sepsis_updated.csv")
        
        if not os.path.exists(csv_path):
            raise HTTPException(
                status_code=404,
                detail=f"CSV file not found at {csv_path}"
            )
        
        # Read CSV file
        df = pd.read_csv("C:/Users/ROSHNI/sepsis/sepsis-sentinal/sepsis_updated.csv")
        
        # Filter records where Hour = 15
        df_filtered = df[df['Hour'] == 15]
        
        # Get all unique patients (removed 100 limit)
        unique_patients = df_filtered['Patient_ID'].unique()
        df_final = df_filtered[df_filtered['Patient_ID'].isin(unique_patients)]
        
        
        
        # Insert filtered data into database
        records_created = 0
        for _, row in df_final.iterrows():
            patient = Patient(
                Patient_ID=str(row['Patient_ID']),
                Hour=int(row['Hour']),
                HR=float(row['HR']),
                O2Sat=float(row['O2Sat']),
                Temp=float(row['Temp']),
                SBP=float(row['SBP']),
                MAP=float(row['MAP']),
                DBP=float(row['DBP']),
                Resp=float(row['Resp']),
                Age=int(row['Age']),
                Gender=int(row['Gender']),
                Unit1=int(row['Unit1']),
                Unit2=int(row['Unit2']),
                RiskScore=float(row['RiskScore']),
                Name=str(row['Name'])
            )
            db.add(patient)
            records_created += 1
        
        db.commit()
        
        return LoadDataResponse(
            message="Data loaded successfully",
            records_loaded=records_created,
            records_filtered=len(df_filtered)
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error loading data: {str(e)}"
        )


@app.get("/api/patients", response_model=PatientListResponse)
def get_patients(skip: int = 0, limit: int = 10000, db: Session = Depends(get_db)):
    """
    Fetch patient records for dashboard display.
    
    Query Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: 10000)
    """
    try:
        # Query patients from database
        patients = db.query(Patient).offset(skip).limit(limit).all()
        total = db.query(Patient).count()
        
        return PatientListResponse(
            total_records=total,
            patients=patients
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching patients: {str(e)}"
        )


@app.post("/api/patients", response_model=PatientBase)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    """
    Create a new patient record in the database.
    """
    try:
        # Check if patient with same Patient_ID already exists
        existing_patient = db.query(Patient).filter(
            Patient.Patient_ID == patient.Patient_ID
        ).first()
        
        if existing_patient:
            raise HTTPException(
                status_code=400,
                detail=f"Patient with ID {patient.Patient_ID} already exists"
            )
        
        # Create new patient record
        db_patient = Patient(
            Patient_ID=patient.Patient_ID,
            Age=patient.Age,
            Gender=patient.Gender,
            Name=patient.Name,
            Unit1=patient.Unit1,
            Unit2=patient.Unit2
        )
        
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)
        
        return db_patient
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating patient: {str(e)}"
        )


@app.get("/api/patients/{patient_id}")
def get_patient_by_id(patient_id: str, db: Session = Depends(get_db)):
    """Get a specific patient by Patient_ID."""
    patient = db.query(Patient).filter(
        Patient.Patient_ID == patient_id
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=404,
            detail=f"Patient with ID {patient_id} not found"
        )
    
    return patient


from sqlalchemy import func

@app.get("/api/patients-with-vitals")
def get_patients_with_latest_vitals(db: Session = Depends(get_db)):
    """
    Returns patient list with their latest vitals (if exists)
    """

    subquery = (
        db.query(
            PatientVitals.patient_id,
            func.max(PatientVitals.timestamp).label("latest_time")
        )
        .group_by(PatientVitals.patient_id)
        .subquery()
    )

    results = (
        db.query(Patient, PatientVitals)
        .outerjoin(subquery, Patient.Patient_ID == subquery.c.patient_id)
        .outerjoin(
            PatientVitals,
            (PatientVitals.patient_id == subquery.c.patient_id) &
            (PatientVitals.timestamp == subquery.c.latest_time)
        )
        .all()
    )

    output = []

    for patient, vitals in results:
        output.append({
            "Patient_ID": patient.Patient_ID,
            "Name": patient.Name,
            "Age": patient.Age,
            "Gender": patient.Gender,

            # From vitals table (may be null)
            "HR": vitals.heart_rate if vitals else None,
            "O2Sat": vitals.oxygen_saturation if vitals else None,
            "Temp": vitals.temperature if vitals else None,
            "RiskScore": vitals.sepsis_risk_score if vitals else None,
        })

    return {
        "total": len(output),
        "patients": output
    }




@app.get("/api/statistics")
def get_statistics(db: Session = Depends(get_db)):
    """Get basic statistics about the patient data."""
    try:
        total_patients = db.query(Patient).count()
        
        # Get average vitals
        patients = db.query(Patient).all()
        
        if not patients:
            return {
                "total_patients": 0,
                "message": "No patient data available"
            }
        
        avg_hr = sum(p.HR for p in patients) / len(patients)
        avg_temp = sum(p.Temp for p in patients) / len(patients)
        avg_o2sat = sum(p.O2Sat for p in patients) / len(patients)
        avg_risk_score = sum(p.RiskScore for p in patients) / len(patients)
        
        return {
            "total_patients": total_patients,
            "average_heart_rate": round(avg_hr, 2),
            "average_temperature": round(avg_temp, 2),
            "average_oxygen_saturation": round(avg_o2sat, 2),
            "average_risk_score": round(avg_risk_score, 4)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating statistics: {str(e)}"
        )


@app.delete("/api/data")
def clear_data(db: Session = Depends(get_db)):
    """Clear all patient data from the database."""
    try:
        db.query(Patient).delete()
        db.query(PatientVitals).delete()
        db.commit()
        return {"message": "All patient data cleared"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing data: {str(e)}"
        )


@app.post("/api/vitals", response_model=VitalsResponse)
def create_vitals(vitals: VitalsCreate, db: Session = Depends(get_db)):
    """
    Save vital signs reading for a patient and store LSTM sepsis risk score.
    """
    try:
        # 1️⃣ Verify patient exists
        patient = (
            db.query(Patient)
            .filter(Patient.Patient_ID == vitals.patient_id)
            .first()
        )

        if not patient:
            raise HTTPException(
                status_code=404,
                detail=f"Patient with ID {vitals.patient_id} not found"
            )

        # 2️⃣ Create and save vitals record
        db_vitals = PatientVitals(
            patient_id=vitals.patient_id,
            heart_rate=vitals.heart_rate,
            oxygen_saturation=vitals.oxygen_saturation,
            sbp=vitals.sbp,
            dbp=vitals.dbp,
            map=vitals.map,
            respiratory_rate=vitals.respiratory_rate,
            temperature=vitals.temperature,
        )

        db.add(db_vitals)
        db.commit()
        db.refresh(db_vitals)

        # 3️⃣ Fetch ALL vitals history for LSTM (chronological)
        records = (
            db.query(PatientVitals)
            .filter(PatientVitals.patient_id == vitals.patient_id)
            .order_by(PatientVitals.timestamp.asc())
            .all()
        )

        vitals_list = [
            {
                "timestamp": r.timestamp,
                "heart_rate": r.heart_rate,
                "oxygen_saturation": r.oxygen_saturation,
                "temperature": r.temperature,
                "sbp": r.sbp,
                "map": r.map,
                "dbp": r.dbp,
                "respiratory_rate": r.respiratory_rate,
            }
            for r in records
        ]

        # 4️⃣ Predict sepsis risk
        risk_score = predict_sepsis_risk(vitals_list)

        # 5️⃣ Store risk score in SAME vitals row
        db_vitals.sepsis_risk_score = risk_score
        db.commit()
        db.refresh(db_vitals)

        # 6️⃣ Update patients table with latest vitals data
        patient.HR = vitals.heart_rate
        patient.O2Sat = vitals.oxygen_saturation
        patient.Temp = vitals.temperature
        patient.SBP = vitals.sbp
        patient.DBP = vitals.dbp
        patient.MAP = vitals.map
        patient.Resp = vitals.respiratory_rate
        patient.RiskScore = risk_score
        db.commit()

        # 7️⃣ Clear any pending notifications for this patient
        # Mark all pending/triggered notifications as "cleared"
        pending_notifications = (
            db.query(Notification)
            .filter(
                Notification.patient_id == vitals.patient_id,
                Notification.status.in_(["pending", "triggered"])
            )
            .all()
        )
        
        now = datetime.now()
        for notif in pending_notifications:
            notif.status = "cleared"
            notif.resolved_at = now
        
        if pending_notifications:
            db.commit()
            logger.info(f"Cleared {len(pending_notifications)} notifications for patient {vitals.patient_id}")

        # 8️⃣ Remove stale in-memory notifications for this patient
        global recent_notifications
        recent_notifications = [
            n for n in recent_notifications
            if n.get("patient_id") != vitals.patient_id
        ]

        # 9️⃣ Resolve any overdue reminder fallback for this patient
        resolve_overdue_notifications(db, vitals.patient_id)

        # 9.1️⃣ If update is late but within correction window, convert estimated -> delayed
        reclassify_estimated_hour_with_late_vitals(db, vitals.patient_id, db_vitals)

        # 🔟 Create the next reminder immediately for this patient
        # (do not wait for the 1-minute scheduler loop)
        manage_vital_update_notifications(db, vitals.patient_id)

        return db_vitals

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error saving vitals: {str(e)}"
        )

@app.get("/api/vitals/{patient_id}", response_model=VitalsListResponse)
def get_patient_vitals(patient_id: str, db: Session = Depends(get_db)):
    """
    Get all vital signs readings for a specific patient.
    """
    try:
        # Verify patient exists
        patient = db.query(Patient).filter(
            Patient.Patient_ID == patient_id
        ).first()
        
        if not patient:
            raise HTTPException(
                status_code=404,
                detail=f"Patient with ID {patient_id} not found"
            )
        
        # Get vitals for patient
        vitals = db.query(PatientVitals).filter(
            PatientVitals.patient_id == patient_id
        ).order_by(PatientVitals.timestamp.desc()).all()
        
        return VitalsListResponse(
            patient_id=patient_id,
            total_readings=len(vitals),
            vitals=vitals
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching vitals: {str(e)}"
        )


@app.get("/api/lstm-prediction/{patient_id}", response_model=LSTMPredictionResponse)
def get_lstm_prediction(patient_id: str, db: Session = Depends(get_db)):
    """
    Get LSTM-based sepsis risk prediction for a patient.
    Uses the pre-trained LSTM model to predict early sepsis risk (0-1).
    """
    try:
        if not KERAS_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="LSTM model not available. Install TensorFlow with: pip install tensorflow"
            )
        
        # Verify patient exists
        patient = db.query(Patient).filter(
            Patient.Patient_ID == patient_id
        ).first()
        
        if not patient:
            raise HTTPException(
                status_code=404,
                detail=f"Patient with ID {patient_id} not found"
            )
        
        # Get patient vitals
        vitals = db.query(PatientVitals).filter(
            PatientVitals.patient_id == patient_id
        ).order_by(PatientVitals.timestamp.desc()).all()
        
        if not vitals:
            # If no vitals recorded yet, return default prediction based on patient baseline
            vitals_data = [{
                'timestamp': datetime.now(),  # Add timestamp for proper aggregation
                'heart_rate': patient.HR,
                'oxygen_saturation': patient.O2Sat,
                'sbp': patient.SBP,
                'dbp': patient.DBP,
                'map': patient.MAP,
                'respiratory_rate': patient.Resp,
                'temperature': patient.Temp,
            }]
        else:
            # Convert vitals to dict format for LSTM predictor
            vitals_data = []
            for vital in vitals:
                vitals_data.append({
                    'timestamp': vital.timestamp,
                    'heart_rate': vital.heart_rate,
                    'oxygen_saturation': vital.oxygen_saturation,
                    'sbp': vital.sbp,
                    'dbp': vital.dbp,
                    'map': vital.map,
                    'respiratory_rate': vital.respiratory_rate,
                    'temperature': vital.temperature,
                })
        
        # Get LSTM prediction
        lstm_risk_score = predict_sepsis_risk(vitals_data)
        
        return LSTMPredictionResponse(
            patient_id=patient_id,
            lstm_risk_score=round(lstm_risk_score, 4),
            total_readings=len(vitals),
            message="LSTM prediction successful"
        )
    
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"LSTM model error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting LSTM prediction: {str(e)}"
        )
