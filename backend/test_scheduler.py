"""
Test file for hourly vitals aggregation system.
Run this after starting the backend to verify all components are working.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_scheduler_status():
    """Test that scheduler is running."""
    print("\n" + "="*70)
    print("TEST 1: Scheduler Status")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/scheduler-status")
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if response.status_code == 200 and data.get("running"):
            print("✓ PASS: Scheduler is running")
            return True
        else:
            print("✗ FAIL: Scheduler is not running")
            return False
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_notifications():
    """Test that notifications endpoint works."""
    print("\n" + "="*70)
    print("TEST 2: Notifications Endpoint")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/notifications?limit=5")
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Total Notifications: {data.get('total', 0)}")
        
        if data.get("notifications"):
            print(f"Recent Notifications ({len(data['notifications'])} shown):")
            for notif in data['notifications'][:2]:  # Show first 2
                print(f"\n  Patient: {notif.get('patient_id')}")
                print(f"  Message: {notif.get('message')}")
                print(f"  Status: {notif.get('status_flag')}")
                print(f"  Reliability: {notif.get('data_reliability_score')}")
        else:
            print("(No notifications yet - scheduler hasn't run or no patient vitals)")
        
        print("\n✓ PASS: Notifications endpoint working")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_hourly_vitals_endpoint():
    """Test hourly vitals endpoint."""
    print("\n" + "="*70)
    print("TEST 3: Hourly Vitals Endpoints")
    print("="*70)
    
    # First, get list of patients
    try:
        print("\n3a. Getting patient list...")
        patients_response = requests.get(f"{BASE_URL}/api/patients?limit=5")
        
        if patients_response.status_code != 200:
            print("  ✗ Could not fetch patients")
            return False
        
        patients_data = patients_response.json()
        patients = patients_data.get("patients", [])
        
        if not patients:
            print("  (No patients in database yet)")
            return True
        
        patient_id = patients[0]["Patient_ID"]
        print(f"  ✓ Found patient: {patient_id}")
        
        # Test hourly vitals for specific patient
        print(f"\n3b. Getting hourly vitals for {patient_id}...")
        hourly_response = requests.get(
            f"{BASE_URL}/api/hourly-vitals/{patient_id}?limit=10"
        )
        
        if hourly_response.status_code == 200:
            hourly_data = hourly_response.json()
            print(f"  Total Hourly Records: {hourly_data.get('total_hours', 0)}")
            
            if hourly_data.get("hourly_records"):
                record = hourly_data["hourly_records"][0]
                print(f"\n  Latest Hour Record:")
                print(f"    Timestamp: {record.get('hour_timestamp')}")
                print(f"    Status: {record.get('status_flag')}")
                print(f"    Reliability: {record.get('data_reliability_score')}")
                print(f"    Avg HR: {record.get('avg_heart_rate')}")
                print(f"    Readings: {record.get('minute_readings_count')}")
            
            print("\n  ✓ PASS: Hourly vitals endpoint working")
            return True
        else:
            print(f"  ✗ FAIL: Status {hourly_response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_hourly_vitals_all():
    """Test all patients hourly summary endpoint."""
    print("\n" + "="*70)
    print("TEST 4: All Patients Hourly Summary")
    print("="*70)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/hourly-vitals-all?limit_per_patient=1"
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total Patients with Data: {data.get('total_patients', 0)}")
            
            if data.get("summary"):
                print(f"\nShowing up to 3 patients:")
                for patient in data["summary"][:3]:
                    print(f"\n  {patient.get('patient_id')} - {patient.get('patient_name')}")
                    print(f"    Status: {patient.get('status_flag')}")
                    print(f"    Reliability: {patient.get('data_reliability_score')}")
                    print(f"    Avg Temp: {patient.get('avg_temperature')}")
            else:
                print("(No hourly records yet)")
            
            print("\n✓ PASS: All patients endpoint working")
            return True
        else:
            print(f"✗ FAIL: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_health_check():
    """Test API health check."""
    print("\n" + "="*70)
    print("TEST 0: API Health Check")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/")
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Message: {data.get('message')}")
        print(f"Status: {data.get('status')}")
        
        if response.status_code == 200 and data.get("status") == "healthy":
            print("✓ PASS: API is healthy")
            return True
        else:
            print("✗ FAIL: API is not responding correctly")
            return False
    except Exception as e:
        print(f"✗ FAIL: Cannot reach API at {BASE_URL}")
        print(f"  Error: {e}")
        print(f"  Make sure backend is running: uvicorn main:app --reload")
        return False


def run_all_tests():
    """Run all tests and summarize results."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  HOURLY VITALS AGGREGATION SYSTEM - TEST SUITE".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    tests = [
        ("Health Check", test_health_check),
        ("Scheduler Status", test_scheduler_status),
        ("Notifications", test_notifications),
        ("Hourly Vitals", test_hourly_vitals_endpoint),
        ("All Patients Summary", test_hourly_vitals_all),
    ]
    
    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✓ PASS" if passed_flag else "✗ FAIL"
        print(f"{status:7} | {test_name}")
    
    print("-"*70)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check logs above.")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    run_all_tests()
    
    print("\nNEXT STEPS:")
    print("-" * 70)
    print("1. Wait for the scheduler to run (next hour mark)")
    print("2. Check API logs to see job execution")
    print("3. Re-run tests to see notifications and hourly records")
    print("4. Try adding vitals via /api/vitals endpoint")
    print("5. Check /api/scheduler-status to see next run time")
    print("-" * 70)
