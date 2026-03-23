import sys
import os
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import tensorflow as tf

from pathlib import Path
# --------------------------------------------------
# CONFIG
# --------------------------------------------------
SEQUENCE_LENGTH = 15
NUM_FEATURES = 7

# Adjust paths if needed
PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = Path(
    r"C:/Users/ROSHNI/sepsis/sepsis-sentinal/backend/models/sepsis_lstm_model (1).keras"
)

# --------------------------------------------------
# LOAD MODEL
# --------------------------------------------------
if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Keras model not found at: {MODEL_PATH}")

print(f"✅ Loading model from: {MODEL_PATH}")
model = tf.keras.models.load_model(MODEL_PATH)



# --------------------------------------------------
# PROVIDED PATIENT HOURLY VITALS (15 HOURS)
# --------------------------------------------------
rows = [
    (82, 97, 36.9, 118, 92, 78, 16),
    (83, 97, 36.9, 117, 91, 77, 16),
    (84, 96, 37.0, 116, 91, 77, 17),
    (85, 96, 37.1, 115, 90, 76, 17),
    (87, 96, 37.2, 114, 89, 75, 17),
    (88, 95, 37.3, 113, 89, 75, 18),
    (89, 95, 37.4, 112, 88, 74, 18),
    (90, 95, 37.5, 111, 88, 74, 18),
    (92, 94, 37.6, 110, 87, 73, 19),
    (93, 94, 37.7, 109, 86, 72, 19),
    (94, 94, 37.8, 108, 86, 72, 19),
    (95, 93, 37.8, 107, 85, 71, 20),
    (96, 93, 37.9, 106, 85, 71, 20),
    (97, 93, 38.0, 105, 84, 70, 21),
    (98, 92, 38.0, 104, 83, 69, 21)

]

# --------------------------------------------------
# PREPARE INPUT (15,7)
# --------------------------------------------------
features = np.array(rows, dtype=np.float32)



# Reshape to (1, 15, 7)
X = features.reshape(1, SEQUENCE_LENGTH, NUM_FEATURES)

print("🔍 Input shape:", X.shape)

# --------------------------------------------------
# PREDICT
# --------------------------------------------------
prediction = model.predict(X, verbose=0)
risk_score = float(prediction.flatten()[0])
risk_score = max(0.0, min(1.0, risk_score))

print("\n🚨 Predicted Sepsis Risk Score:", risk_score)

# Optional interpretation
if risk_score < 0.3:
    print("Risk Level: LOW")
elif risk_score < 0.6:
    print("Risk Level: MEDIUM")
else:
    print("Risk Level: HIGH")
