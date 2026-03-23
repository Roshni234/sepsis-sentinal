import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from sqlalchemy import desc

try:
    import tensorflow as tf
    KERAS_AVAILABLE = True
except ImportError:
    KERAS_AVAILABLE = False
    tf = None

# --------------------------------------------------
# CONFIG (MUST MATCH TRAINING / WORKING SCRIPT)
# --------------------------------------------------
SEQUENCE_LENGTH = 15
NUM_FEATURES = 7

# Feature order MUST match your working code:
# (HR, O2Sat, Temp, SBP, MAP, DBP, Resp)
FEATURE_KEYS = [
    "heart_rate",
    "oxygen_saturation",
    "temperature",
    "sbp",
    "map",
    "dbp",
    "respiratory_rate",
]


VARIATION_LIMITS = {
    "heart_rate": 3,              
    "oxygen_saturation": 1,      
    "temperature": 0.2,           
    "sbp": 4,                    
    "map": 3,                     
    "dbp": 3,                    
    "respiratory_rate": 2        
}

def apply_bounded_variation(value, key):
    """Apply small, safe variation to missing values."""
    limit = VARIATION_LIMITS.get(key, 0)
    if limit == 0:
        return value
    return value + np.random.uniform(-limit, limit)

# --------------------------------------------------
# SAFE HOURLY AGGREGATION (NO ZEROS)
# --------------------------------------------------
def aggregate_vitals_to_hourly(vitals_list):
    if not vitals_list:
        return []

    hourly = defaultdict(list)

    for v in vitals_list:
        ts = v.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif not isinstance(ts, datetime):
            continue

        hour = ts.replace(minute=0, second=0, microsecond=0)
        hourly[hour].append(v)

    aggregated = []
    for hour in sorted(hourly.keys()):
        records = hourly[hour]

        hourly_record = {"timestamp": hour}
        for key in FEATURE_KEYS:
            values = [r[key] for r in records if r.get(key) is not None]
            hourly_record[key] = float(np.mean(values)) if values else None

        aggregated.append(hourly_record)

    return aggregated


# --------------------------------------------------
# LSTM PREDICTOR
# --------------------------------------------------
class SepsisLSTMPredictor:

    def __init__(self):
        self.model = self._load_model()

    def _load_model(self):
        if not KERAS_AVAILABLE or tf is None:
            raise RuntimeError("TensorFlow/Keras is not installed. Install with: pip install tensorflow")
        
        model_path = (
            Path(__file__).parent / "models" / "sepsis_lstm_model (1).keras"
        )

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        print(f"✅ Loaded LSTM model from {model_path}")
        return tf.keras.models.load_model(model_path)

    # --------------------------------------------------
    # PREPARE INPUT (MATCHES WORKING SCRIPT)
    # --------------------------------------------------
    def prepare_sequence(self, hourly_vitals):
        # Ensure chronological order (oldest → newest)
        hourly_vitals = sorted(hourly_vitals, key=lambda x: x["timestamp"])

        if not hourly_vitals:
            raise ValueError("No valid hourly vitals")

        # Pad using first valid hour (NOT zeros)
        if len(hourly_vitals) < SEQUENCE_LENGTH:
            first = hourly_vitals[0]
            padding = [first.copy() for _ in range(SEQUENCE_LENGTH - len(hourly_vitals))]
            hourly_vitals = padding + hourly_vitals

        # Use last 15 hours only
        hourly_vitals = hourly_vitals[-SEQUENCE_LENGTH:]

        features = []
        last_valid = None 
        for v in hourly_vitals:
            row = []
            for key in FEATURE_KEYS:
                val = v.get(key)

                if val is None:
                   if last_valid is None:
                       raise ValueError("Cannot forward-fill without an initial valid reading")
                   
            # Apply bounded variation instead of exact copy
                   val = apply_bounded_variation(last_valid[key], key)

                row.append(float(val))
            last_valid = dict(zip(FEATURE_KEYS, row))

    # ✅ append row to features
            features.append(row)


        X = np.array(features, dtype=np.float32)
        X = X.reshape(1, SEQUENCE_LENGTH, NUM_FEATURES)

        # Debug: compare with working script
        print("🔍 Final LSTM input shape:", X.shape)
        print("🔍 Final LSTM input values:\n", X)

        return X

    # --------------------------------------------------
    # PREDICT
    # --------------------------------------------------
    def predict(self, vitals_list):
        hourly = aggregate_vitals_to_hourly(vitals_list)

        if not hourly:
            return 0.0

        X = self.prepare_sequence(hourly)

        prediction = self.model.predict(X, verbose=0)
        score = float(prediction.flatten()[0])

        return max(0.0, min(1.0, score))


# --------------------------------------------------
# SINGLETON
# --------------------------------------------------
_predictor = None


def get_predictor():
    global _predictor
    if _predictor is None:
        _predictor = SepsisLSTMPredictor()
    return _predictor


# --------------------------------------------------
# INFERENCE API (FOR MAIN.PY)
# --------------------------------------------------
def predict_sepsis_risk(vitals_data):
    """
    Predict sepsis risk from vitals data.
    
    Args:
        vitals_data: List of dicts with vital signs data
        
    Returns:
        float: Risk score between 0 and 1
    """
    if not KERAS_AVAILABLE:
        return 0.0
    
    try:
        predictor = get_predictor()
        return predictor.predict(vitals_data)
    except Exception as e:
        print(f"Error in LSTM prediction: {e}")
        return 0.0


# --------------------------------------------------
# DB-BASED INFERENCE (ALTERNATIVE)
# --------------------------------------------------
def predict_sepsis_risk_by_patient(patient_id, db=None):
    from .database import SessionLocal, PatientVitals

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        records = (
            db.query(PatientVitals)
            .filter(PatientVitals.patient_id == patient_id)
            .order_by(desc(PatientVitals.timestamp))
            .limit(SEQUENCE_LENGTH)
            .all()
        )

        if not records:
            raise ValueError(f"No vitals found for patient {patient_id}")

        records = list(reversed(records))  # oldest → newest

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

        predictor = get_predictor()
        return predictor.predict(vitals_list)

    finally:
        if close_db:
            db.close()
