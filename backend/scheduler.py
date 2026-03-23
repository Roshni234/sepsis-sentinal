"""
APScheduler-based hourly aggregation mechanism for patient vitals.

This module:
- Aggregates minute-level vitals into hourly windows
- Applies strict timing rules (55-minute rule for next-hour classification)
- Detects and backfills missing hours
- Assigns status flags (normal, delayed, missing, estimated)
- Sends real-time notifications to the frontend
- Runs independently via BackgroundScheduler
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from database import SessionLocal, PatientVitals, Patient, HourlyVitals, Notification, engine
from datetime_utils import get_ist_now, ensure_ist_aware

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# Tolerance for delayed data (in minutes)
DELAY_TOLERANCE_MINUTES = 20

# Late update correction window (in minutes)
LATE_RECLASSIFICATION_WINDOW_MINUTES = 40

# VITAL READING INTERVAL (in minutes) - how often vitals should be taken
VITAL_READING_INTERVAL_MINUTES = 60

# Notification callbacks (will be set by main.py)
notification_callback = None


def set_notification_callback(callback):
    """
    Set the callback function for sending notifications to frontend.
    callback signature: callback(notification: dict)
    """
    global notification_callback
    notification_callback = callback


def send_notification(notification: Dict[str, Any]):
    """
    Send a notification about hourly vitals update.
    Notification payload structure:
    {
        "timestamp": ISO string,
        "patient_id": str,
        "hour_timestamp": ISO string,
        "status_flag": str,
        "data_reliability_score": float,
        "disclaimer": str or None,
        "message": str,
        "vitals": {
            "avg_heart_rate": float,
            "avg_oxygen_saturation": float,
            ...
        }
    }
    """
    if notification_callback:
        try:
            notification_callback(notification)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    else:
        logger.info(f"Notification (no callback set): {notification}")


def manage_vital_update_notifications(db: Session, patient_id: str):
    """
    Manage notifications for when vital signs need to be updated.
    
    This function:
    1. Gets the most recent vital reading for the patient
    2. Calculates when the next reading is due (current time + 1 hour)
    3. Creates a notification that triggers 1 minute before due time
    4. Clears old pending notifications for this patient
    
    The notification will appear at (next_due_time - 1 minute)
    Example: If last reading at 9:30 AM → next reading due at 10:30 AM → notification at 10:29 AM
    """
    try:
        # Get the most recent vital reading for this patient
        latest_vital = db.query(PatientVitals).filter(
            PatientVitals.patient_id == patient_id
        ).order_by(PatientVitals.timestamp.desc()).first()
        
        if not latest_vital:
            logger.debug(f"No vitals found for patient {patient_id}, skipping notification")
            return
        
        last_reading_time = ensure_ist_aware(latest_vital.timestamp)
        
        # Calculate next reading due time (1 hour after last reading)
        next_due_time = last_reading_time + timedelta(minutes=VITAL_READING_INTERVAL_MINUTES)
        
        # Calculate trigger time (1 minute before due time)
        trigger_time = next_due_time - timedelta(minutes=1)
        
        now = get_ist_now()
        
        # Only create notification if trigger time is in the future
        if trigger_time > now:
            # Check if notification already exists for this patient
            existing_notification = db.query(Notification).filter(
                and_(
                    Notification.patient_id == patient_id,
                    Notification.due_time == next_due_time,
                    Notification.status.in_(["pending", "triggered"])
                )
            ).first()
            
            if not existing_notification:
                # Get patient name for better message
                patient = db.query(Patient).filter(Patient.Patient_ID == patient_id).first()
                patient_name = patient.Name if patient else patient_id
                
                # Format the time for display
                due_time_str = next_due_time.strftime("%I:%M %p")
                
                message = f"You need to update the vitals for {patient_name} by {due_time_str}"
                
                # Create new notification
                notification = Notification(
                    patient_id=patient_id,
                    due_time=next_due_time,
                    trigger_time=trigger_time,
                    message=message,
                    status="pending"
                )
                
                db.add(notification)
                db.commit()
                
                logger.info(f"Created notification for {patient_id}: {message}")
                logger.info(f"  Last reading: {last_reading_time.strftime('%I:%M %p')}")
                logger.info(f"  Next due: {next_due_time.strftime('%I:%M %p')}")
                logger.info(f"  Trigger: {trigger_time.strftime('%I:%M %p')}")
        
        # Trigger pending notifications exactly when trigger time is reached
        due_notifications = db.query(Notification).filter(
            and_(
                Notification.patient_id == patient_id,
                Notification.status == "pending",
                Notification.trigger_time <= now,
                Notification.due_time >= (now - timedelta(minutes=DELAY_TOLERANCE_MINUTES))
            )
        ).all()

        for notif in due_notifications:
            notif.status = "triggered"
            notif.triggered_at = now
            send_notification({
                "timestamp": now.isoformat(),
                "patient_id": patient_id,
                "hour_timestamp": get_hour_start(notif.due_time).isoformat(),
                "status_flag": "missing",
                "data_reliability_score": 0.0,
                "disclaimer": "Vitals update is due now.",
                "message": notif.message,
                "vitals": None,
                "minute_readings_count": 0,
            })

        if due_notifications:
            db.commit()
            logger.info(f"Triggered {len(due_notifications)} pending notifications for {patient_id}")
    
    except Exception as e:
        logger.error(f"Error managing vital update notifications for {patient_id}: {e}", exc_info=True)


def get_hour_start(dt: datetime) -> datetime:
    """Get the start of the hour for a given datetime (in IST)."""
    dt = ensure_ist_aware(dt)
    return dt.replace(minute=0, second=0, microsecond=0)


def get_hour_end(dt: datetime) -> datetime:
    """Get the end of the hour for a given datetime (in IST)."""
    return get_hour_start(dt) + timedelta(hours=1)


def calculate_data_reliability_score(
    minute_count: int,
    status_flag: str,
    delay_minutes: int = 0
) -> float:
    """
    Calculate data reliability score (0.0-1.0).
    
    Rules:
    - Perfect hour (60 readings): 1.0
    - Missing hour: 0.0
    - Estimated: 0.3-0.5
    - Delayed: score decreases with delay
    - Normal: score based on reading count
    """
    if status_flag == "missing":
        return 0.0
    
    if status_flag == "estimated":
        return 0.4
    
    # For normal and delayed: base on completeness
    # Assuming 1 reading per minute = 60 per hour
    completeness = min(minute_count / 60.0, 1.0)
    base_score = completeness
    
    # Penalty for delay
    if status_flag == "delayed":
        delay_penalty = min(delay_minutes / DELAY_TOLERANCE_MINUTES, 0.3)
        base_score = max(base_score - delay_penalty, 0.3)
    
    return round(base_score, 2)


def resolve_overdue_notifications(db: Session, patient_id: Optional[str] = None):
    """
    Resolve overdue notifications that were not updated within the grace window.

    Grace rule:
    - If vitals are not updated within 20 minutes after due_time,
      clear the notification and mark the hour as estimated.
    """
    now = get_ist_now()
    grace_cutoff = now - timedelta(minutes=DELAY_TOLERANCE_MINUTES)

    filters = [
        Notification.status.in_(["pending", "triggered"]),
        Notification.due_time <= grace_cutoff,
    ]
    if patient_id:
        filters.append(Notification.patient_id == patient_id)

    overdue_notifications = db.query(Notification).filter(and_(*filters)).all()
    if not overdue_notifications:
        return 0

    resolved_count = 0
    for notif in overdue_notifications:
        patient_hour_start = get_hour_start(notif.due_time)

        existing_hourly = db.query(HourlyVitals).filter(
            and_(
                HourlyVitals.patient_id == notif.patient_id,
                HourlyVitals.hour_timestamp == patient_hour_start,
            )
        ).first()

        latest_before_due = db.query(PatientVitals).filter(
            and_(
                PatientVitals.patient_id == notif.patient_id,
                PatientVitals.timestamp <= notif.due_time,
            )
        ).order_by(PatientVitals.timestamp.desc()).first()

        if existing_hourly and existing_hourly.status_flag in ["normal", "delayed"]:
            # Actual data already present in this hour, just resolve notification
            pass
        else:
            disclaimer = "No vitals update within 20 minutes after due time. Hour estimated from previous reading."
            if not existing_hourly:
                existing_hourly = HourlyVitals(
                    patient_id=notif.patient_id,
                    hour_timestamp=patient_hour_start,
                    status_flag="estimated",
                    data_reliability_score=0.4,
                    disclaimer=disclaimer,
                    minute_readings_count=0,
                )
                db.add(existing_hourly)
            else:
                existing_hourly.status_flag = "estimated"
                existing_hourly.data_reliability_score = 0.4
                existing_hourly.disclaimer = disclaimer
                existing_hourly.minute_readings_count = 0

            if latest_before_due:
                existing_hourly.avg_heart_rate = latest_before_due.heart_rate
                existing_hourly.avg_oxygen_saturation = latest_before_due.oxygen_saturation
                existing_hourly.avg_sbp = latest_before_due.sbp
                existing_hourly.avg_dbp = latest_before_due.dbp
                existing_hourly.avg_map = latest_before_due.map
                existing_hourly.avg_respiratory_rate = latest_before_due.respiratory_rate
                existing_hourly.avg_temperature = latest_before_due.temperature

        notif.status = "cleared"
        notif.resolved_at = now
        resolved_count += 1

    if resolved_count:
        db.commit()

    return resolved_count


def reclassify_estimated_hour_with_late_vitals(db: Session, patient_id: str, vital_row: PatientVitals) -> bool:
    """
    Reclassify an estimated hour to delayed when late vitals arrive within a correction window.

    Example:
    - Notification due at 10:00
    - Auto-estimated after grace window
    - If actual vitals arrive by 10:40, convert that hour from estimated -> delayed
    """
    vital_time = ensure_ist_aware(vital_row.timestamp)
    correction_floor = vital_time - timedelta(minutes=LATE_RECLASSIFICATION_WINDOW_MINUTES)

    related_notification = db.query(Notification).filter(
        and_(
            Notification.patient_id == patient_id,
            Notification.status == "cleared",
            Notification.due_time <= vital_time,
            Notification.due_time >= correction_floor,
        )
    ).order_by(Notification.due_time.desc()).first()

    if not related_notification:
        return False

    target_hour_start = get_hour_start(related_notification.due_time)
    target_hour = db.query(HourlyVitals).filter(
        and_(
            HourlyVitals.patient_id == patient_id,
            HourlyVitals.hour_timestamp == target_hour_start,
            HourlyVitals.status_flag == "estimated",
        )
    ).first()

    if not target_hour:
        return False

    delay_minutes = int((vital_time - ensure_ist_aware(related_notification.due_time)).total_seconds() / 60)
    if delay_minutes < 0:
        return False

    target_hour.status_flag = "delayed"
    target_hour.disclaimer = f"Late vitals received {delay_minutes} minutes after due time. Reclassified from estimated to delayed."
    target_hour.minute_readings_count = max(target_hour.minute_readings_count or 0, 1)
    target_hour.data_reliability_score = calculate_data_reliability_score(
        target_hour.minute_readings_count,
        "delayed",
        delay_minutes,
    )

    target_hour.avg_heart_rate = vital_row.heart_rate
    target_hour.avg_oxygen_saturation = vital_row.oxygen_saturation
    target_hour.avg_sbp = vital_row.sbp
    target_hour.avg_dbp = vital_row.dbp
    target_hour.avg_map = vital_row.map
    target_hour.avg_respiratory_rate = vital_row.respiratory_rate
    target_hour.avg_temperature = vital_row.temperature

    db.commit()
    logger.info(
        f"Reclassified estimated hour to delayed for {patient_id} at {target_hour_start.isoformat()} with delay {delay_minutes} min"
    )
    return True


def notification_reminder_job():
    """
    Frequent reminder loop (runs every minute):
    - Ensure pending reminder notifications exist for patients
    - Trigger reminders at due_time - 1 minute
    - Resolve overdue reminders after 20-minute grace
    """
    db = SessionLocal()
    try:
        patients_with_vitals = db.query(PatientVitals.patient_id).distinct().all()
        patient_ids = [p[0] for p in patients_with_vitals]

        for patient_id in patient_ids:
            manage_vital_update_notifications(db, patient_id)

        resolved = resolve_overdue_notifications(db)
        if resolved:
            logger.info(f"Resolved {resolved} overdue reminder notifications")
    except Exception as e:
        logger.error(f"Error in notification_reminder_job: {e}", exc_info=True)
    finally:
        db.close()


def aggregate_vitals_for_hour(
    db: Session,
    patient_id: str,
    hour_start: datetime,
    hour_end: datetime
) -> Dict[str, Any]:
    """
    Aggregate all minute-level vitals for a patient in a specific hour window.
    
    Uses strict 55-minute boundary rule:
    - If reading is ≥55 min after hour_start, it belongs to NEXT hour (skip it)
    - Otherwise aggregate readings normally
    
    Returns aggregation result with:
    - vitals: averaged values
    - count: number of readings aggregated
    - status: "normal", "delayed", or "missing"
    - disclaimer: message if delayed or missing
    """
    # Query all vitals for this patient in the hour window
    all_readings = db.query(PatientVitals).filter(
        and_(
            PatientVitals.patient_id == patient_id,
            PatientVitals.timestamp >= hour_start,
            PatientVitals.timestamp < hour_end
        )
    ).all()
    
    if not all_readings:
        return {
            "vitals": None,
            "count": 0,
            "status": "missing",
            "disclaimer": "No vitals data available for this hour.",
            "delay_minutes": 0
        }
    
    # Apply 55-minute rule: filter out readings that belong to NEXT hour
    readings = []
    for reading in all_readings:
        minutes_after_hour_start = (reading.timestamp - hour_start).total_seconds() / 60
        if minutes_after_hour_start < 55:
            readings.append(reading)
    
    if not readings:
        # All readings belong to next hour
        return {
            "vitals": None,
            "count": 0,
            "status": "missing",
            "disclaimer": "All readings belong to next hour (55+ min after boundary).",
            "delay_minutes": 0
        }
    
    # Get the latest reading to check for delay
    latest_reading = max(readings, key=lambda r: r.timestamp)
    delay_from_start = int((latest_reading.timestamp - hour_start).total_seconds() / 60)
    
    # Classify status based on delay from hour start
    if delay_from_start <= 0:
        status = "normal"
        disclaimer = None
        delay_minutes = 0
    elif delay_from_start <= DELAY_TOLERANCE_MINUTES:
        status = "delayed"
        disclaimer = f"Vitals delayed by {delay_from_start} minutes."
        delay_minutes = delay_from_start
    else:
        status = "estimated"
        disclaimer = f"No timely vitals in first 20 minutes. Using latest available reading."
        delay_minutes = delay_from_start
    
    # Aggregate vitals
    avg_vitals = {
        "avg_heart_rate": sum(r.heart_rate for r in readings if r.heart_rate) / len([r for r in readings if r.heart_rate]) if any(r.heart_rate for r in readings) else None,
        "avg_oxygen_saturation": sum(r.oxygen_saturation for r in readings if r.oxygen_saturation) / len([r for r in readings if r.oxygen_saturation]) if any(r.oxygen_saturation for r in readings) else None,
        "avg_sbp": sum(r.sbp for r in readings if r.sbp) / len([r for r in readings if r.sbp]) if any(r.sbp for r in readings) else None,
        "avg_dbp": sum(r.dbp for r in readings if r.dbp) / len([r for r in readings if r.dbp]) if any(r.dbp for r in readings) else None,
        "avg_map": sum(r.map for r in readings if r.map) / len([r for r in readings if r.map]) if any(r.map for r in readings) else None,
        "avg_respiratory_rate": sum(r.respiratory_rate for r in readings if r.respiratory_rate) / len([r for r in readings if r.respiratory_rate]) if any(r.respiratory_rate for r in readings) else None,
        "avg_temperature": sum(r.temperature for r in readings if r.temperature) / len([r for r in readings if r.temperature]) if any(r.temperature for r in readings) else None,
    }
    
    return {
        "vitals": avg_vitals,
        "count": len(readings),
        "status": status,
        "disclaimer": disclaimer,
        "delay_minutes": delay_minutes
    }


def detect_and_backfill_missing_hours(db: Session, patient_id: str) -> List[Dict[str, Any]]:
    """
    Detect missing hourly slots since the last stored hourly record for a patient.
    Backfill with status="missing" or "estimated".
    
    Returns list of backfilled hourly records created.
    """
    backfilled = []
    
    # Get the latest hourly record for this patient
    latest_hourly = db.query(HourlyVitals).filter(
        HourlyVitals.patient_id == patient_id
    ).order_by(HourlyVitals.hour_timestamp.desc()).first()
    
    if not latest_hourly:
        # No hourly record yet - check minute vitals for a starting point
        earliest_vital = db.query(PatientVitals).filter(
            PatientVitals.patient_id == patient_id
        ).order_by(PatientVitals.timestamp.asc()).first()
        
        if not earliest_vital:
            # No vitals at all
            return backfilled
        
        gap_start = get_hour_start(earliest_vital.timestamp)
    else:
        gap_start = latest_hourly.hour_timestamp + timedelta(hours=1)
    
    current_hour = get_hour_start(get_ist_now())

    # Normalize to timezone-aware for safe comparisons
    if gap_start.tzinfo is None:
        gap_start = gap_start.replace(tzinfo=IST)
    
    # Backfill all missing hours between gap_start and current_hour
    gap_hour = gap_start
    while gap_hour < current_hour:
        # Check if hourly record already exists
        existing = db.query(HourlyVitals).filter(
            and_(
                HourlyVitals.patient_id == patient_id,
                HourlyVitals.hour_timestamp == gap_hour
            )
        ).first()
        
        if not existing:
            # Aggregate vitals for this hour to check if data exists
            gap_hour_end = gap_hour + timedelta(hours=1)
            aggregation = aggregate_vitals_for_hour(db, patient_id, gap_hour, gap_hour_end)
            
            # Calculate reliability score based on actual data
            reliability_score = calculate_data_reliability_score(
                aggregation["count"],
                aggregation["status"],
                aggregation["delay_minutes"]
            )
            
            # Create backfilled record with aggregated data (if any)
            hourly_record = HourlyVitals(
                patient_id=patient_id,
                hour_timestamp=gap_hour,
                status_flag=aggregation["status"],
                disclaimer=aggregation["disclaimer"],
                data_reliability_score=reliability_score,
                minute_readings_count=aggregation["count"]
            )
            
            # Set aggregated vitals if data exists
            if aggregation["vitals"]:
                hourly_record.avg_heart_rate = aggregation["vitals"]["avg_heart_rate"]
                hourly_record.avg_oxygen_saturation = aggregation["vitals"]["avg_oxygen_saturation"]
                hourly_record.avg_sbp = aggregation["vitals"]["avg_sbp"]
                hourly_record.avg_dbp = aggregation["vitals"]["avg_dbp"]
                hourly_record.avg_map = aggregation["vitals"]["avg_map"]
                hourly_record.avg_respiratory_rate = aggregation["vitals"]["avg_respiratory_rate"]
                hourly_record.avg_temperature = aggregation["vitals"]["avg_temperature"]
            
            db.add(hourly_record)
            backfilled.append({
                "patient_id": patient_id,
                "hour_timestamp": gap_hour.isoformat(),
                "status_flag": aggregation["status"],
                "disclaimer": aggregation["disclaimer"],
                "data_reliability_score": reliability_score
            })
        
        gap_hour += timedelta(hours=1)
    
    if backfilled:
        db.commit()
        logger.info(f"Backfilled {len(backfilled)} missing hours for patient {patient_id}")
    
    return backfilled


def process_hourly_vitals_for_patient(db: Session, patient_id: str) -> Optional[Dict[str, Any]]:
    """
    Process hourly vitals aggregation for a single patient.
    
    Steps:
    1. Get current hour window
    2. Detect and backfill any missing hours
    3. Aggregate vitals for current hour
    4. Assign status flags
    5. Store in hourly_vitals table (avoid duplicates)
    6. Send notification
    
    Returns the hourly record created/updated, or None if no action taken.
    """
    now = get_ist_now()
    hour_start = get_hour_start(now)
    hour_end = get_hour_end(now)
    
    logger.info(f"Processing hourly vitals for patient {patient_id}")
    
    # Step 1: Backfill missing hours
    backfilled_records = detect_and_backfill_missing_hours(db, patient_id)
    for backfill_record in backfilled_records:
        send_notification({
            "timestamp": now.isoformat(),
            "patient_id": patient_id,
            "hour_timestamp": backfill_record["hour_timestamp"],
            "status_flag": "missing",
            "data_reliability_score": backfill_record["data_reliability_score"],
            "disclaimer": backfill_record["disclaimer"],
            "message": f"Missing vitals for {patient_id} at {backfill_record['hour_timestamp']}",
            "vitals": None
        })
    
    # Step 2: Aggregate vitals for current hour
    aggregation = aggregate_vitals_for_hour(db, patient_id, hour_start, hour_end)
    
    # Step 3: Check if hourly record already exists for this hour
    existing_hourly = db.query(HourlyVitals).filter(
        and_(
            HourlyVitals.patient_id == patient_id,
            HourlyVitals.hour_timestamp == hour_start
        )
    ).first()
    
    # Calculate reliability score
    reliability_score = calculate_data_reliability_score(
        aggregation["count"],
        aggregation["status"],
        aggregation["delay_minutes"]
    )
    
    if existing_hourly:
        # Update existing record
        existing_hourly.status_flag = aggregation["status"]
        existing_hourly.disclaimer = aggregation["disclaimer"]
        existing_hourly.data_reliability_score = reliability_score
        existing_hourly.minute_readings_count = aggregation["count"]
        
        if aggregation["vitals"]:
            existing_hourly.avg_heart_rate = aggregation["vitals"]["avg_heart_rate"]
            existing_hourly.avg_oxygen_saturation = aggregation["vitals"]["avg_oxygen_saturation"]
            existing_hourly.avg_sbp = aggregation["vitals"]["avg_sbp"]
            existing_hourly.avg_dbp = aggregation["vitals"]["avg_dbp"]
            existing_hourly.avg_map = aggregation["vitals"]["avg_map"]
            existing_hourly.avg_respiratory_rate = aggregation["vitals"]["avg_respiratory_rate"]
            existing_hourly.avg_temperature = aggregation["vitals"]["avg_temperature"]
        
        db.commit()
        hourly_record = existing_hourly
    else:
        # Create new hourly record
        hourly_record = HourlyVitals(
            patient_id=patient_id,
            hour_timestamp=hour_start,
            status_flag=aggregation["status"],
            disclaimer=aggregation["disclaimer"],
            data_reliability_score=reliability_score,
            minute_readings_count=aggregation["count"]
        )
        
        if aggregation["vitals"]:
            hourly_record.avg_heart_rate = aggregation["vitals"]["avg_heart_rate"]
            hourly_record.avg_oxygen_saturation = aggregation["vitals"]["avg_oxygen_saturation"]
            hourly_record.avg_sbp = aggregation["vitals"]["avg_sbp"]
            hourly_record.avg_dbp = aggregation["vitals"]["avg_dbp"]
            hourly_record.avg_map = aggregation["vitals"]["avg_map"]
            hourly_record.avg_respiratory_rate = aggregation["vitals"]["avg_respiratory_rate"]
            hourly_record.avg_temperature = aggregation["vitals"]["avg_temperature"]
        
        db.add(hourly_record)
        db.commit()
    
    # Step 4: Send notification
    send_notification({
        "timestamp": now.isoformat(),
        "patient_id": patient_id,
        "hour_timestamp": hour_start.isoformat(),
        "status_flag": aggregation["status"],
        "data_reliability_score": reliability_score,
        "disclaimer": aggregation["disclaimer"],
        "message": f"You need to update the vitals for {patient_id} at {hour_start.strftime('%I:%M %p')}",
        "vitals": aggregation["vitals"],
        "minute_readings_count": aggregation["count"]
    })
    
    return {
        "patient_id": patient_id,
        "hour_timestamp": hour_start.isoformat(),
        "status_flag": aggregation["status"],
        "data_reliability_score": reliability_score,
        "vitals": aggregation["vitals"]
    }


def hourly_aggregation_job():
    """
    Main scheduled job - runs every hour.
    
    This is the entry point called by APScheduler.
    - Processes all active patients
    - Aggregates minute vitals into hourly records
    - Detects and backfills missing hours
    - Sends notifications
    - Manages vital update reminders
    """
    logger.info("=" * 60)
    logger.info("Starting hourly vitals aggregation job")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        # Get all unique patients that have vitals data
        patients_with_vitals = db.query(PatientVitals.patient_id).distinct().all()
        patient_ids = [p[0] for p in patients_with_vitals]
        
        if not patient_ids:
            logger.warning("No patients with vitals found")
            return
        
        logger.info(f"Processing vitals for {len(patient_ids)} patients")
        
        # Process each patient
        processed = 0
        for patient_id in patient_ids:
            try:
                process_hourly_vitals_for_patient(db, patient_id)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing patient {patient_id}: {e}", exc_info=True)
        
        logger.info(f"Successfully processed {processed}/{len(patient_ids)} patients")
        logger.info("=" * 60)
        logger.info("Hourly aggregation job completed")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Critical error in hourly_aggregation_job: {e}", exc_info=True)
    finally:
        db.close()


# === EDGE CASE HANDLING ===

def handle_55_minute_rule(last_reading_time: datetime) -> bool:
    """
    STRICT 55-MINUTE RULE:
    If (current_time - last_recorded_time) >= 55 minutes:
        → treat as NEXT hourly reading (DO NOT aggregate)
    
    This ensures we don't double-count data and properly handle late readings.
    
    Examples:
    - Reading at 11:00 AM followed by 11:59 AM → treat as NEXT hourly reading
    - Reading at 1:00 PM followed by 2:10 PM → treat as NEXT hourly reading with status="delayed"
    """
    time_gap_minutes = (get_ist_now() - last_reading_time).total_seconds() / 60
    return time_gap_minutes >= 55


def handle_delayed_data_disclaimer(delay_minutes: int) -> str:
    """
    Generate disclaimer message for delayed data.
    
    Rules:
    - <= 15 minutes: "normal" status (acceptable)
    - > 15 minutes: "delayed" status with disclaimer
    """
    if delay_minutes <= DELAY_TOLERANCE_MINUTES:
        return None
    
    return f"Vitals for patient are delayed by {delay_minutes} minutes. Data reliability reduced to ~{max(0.3, 1 - (delay_minutes / 60)):.1f}"


def handle_missing_hour_detection(db: Session, patient_id: str, last_hour: datetime) -> bool:
    """
    Detect if a full hour has passed without any vitals data.
    
    Returns True if an hour is missing and should be backfilled.
    """
    current_hour = get_hour_start(get_ist_now())
    expected_next_hour = last_hour + timedelta(hours=1)
    
    return expected_next_hour < current_hour


if __name__ == "__main__":
    # For testing
    hourly_aggregation_job()
