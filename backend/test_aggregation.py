from lstm_predictor import aggregate_vitals_to_hourly
from datetime import datetime

# Test without timestamp
vitals = [{'heart_rate': 80, 'oxygen_saturation': 95, 'sbp': 120, 'dbp': 80, 'map': 93, 'respiratory_rate': 18, 'temperature': 37.5}]
result = aggregate_vitals_to_hourly(vitals)
print("Result without timestamp:", result)
print()

# Test with timestamp
vitals_with_ts = [{'timestamp': datetime.now(), 'heart_rate': 80, 'oxygen_saturation': 95, 'sbp': 120, 'dbp': 80, 'map': 93, 'respiratory_rate': 18, 'temperature': 37.5}]
result2 = aggregate_vitals_to_hourly(vitals_with_ts)
print("Result with timestamp:", result2)
