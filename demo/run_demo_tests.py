import os
import sys
import json
import traceback
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models import InvestigationRequest
except ImportError as e:
    print(f"Error importing app dependencies: {e}")
    sys.exit(1)

client = TestClient(app)
FOLDER_PATH = r"D:\loganalyser\demo\generated"

# Obtain a valid token to authorize tests
def get_auth_headers():
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    password = os.getenv("ADMIN_PASSWORD", "admin123").strip()
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    if response.status_code != 200:
        raise RuntimeError("Failed to log in for tests: " + response.text)
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}

try:
    AUTH_HEADERS = get_auth_headers()
except Exception as e:
    print(f"Auth Setup Error: {e}")
    AUTH_HEADERS = {}

def run_test(name, payload, expected_status=200, check_fn=None):
    print(f"Running: {name} ... ", end="")
    try:
        response = client.post("/api/investigations", json=payload, headers=AUTH_HEADERS)
        if response.status_code != expected_status:
            print(f"FAILED (Status: {response.status_code}, Expected: {expected_status})")
            print(f"Response: {response.text}")
            return False
        
        if expected_status == 200:
            data = response.json()
            if check_fn:
                check_fn(data)
        print("PASSED")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False

def run_export_test(name, format_type, payload, check_fn=None):
    print(f"Running: {name} ... ", end="")
    try:
        # First get the investigation result
        inv_response = client.post("/api/investigations", json=payload, headers=AUTH_HEADERS)
        if inv_response.status_code != 200:
            print(f"FAILED (Investigation Status: {inv_response.status_code})")
            return False
        
        result_data = inv_response.json()
        
        # Now call the export endpoint
        export_response = client.post(f"/api/export/{format_type}", json=result_data, headers=AUTH_HEADERS)
        if export_response.status_code != 200:
            print(f"FAILED (Export Status: {export_response.status_code})")
            print(f"Response: {export_response.text}")
            return False
            
        if check_fn:
            check_fn(export_response)
        print("PASSED")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("LOG ANALYSER AUTOMATED VALIDATION SUITE")
    print("=" * 60)
    print(f"Target logs directory: {FOLDER_PATH}\n")
    
    success_count = 0
    total_tests = 0
    
    # ----------------------------------------------------
    # Category 1: Target Timestamps
    # ----------------------------------------------------
    
    # Test 1: Start of logs
    total_tests += 1
    t1_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T01:10:00",
        "window_seconds": 300,
        "file_patterns": ["*.log*", "*.txt"]
    }
    def check_t1(data):
        assert data["summary"]["files_scanned"] == 10, f"Expected 10 scanned logs, got {data['summary']['files_scanned']}"
        assert data["summary"]["matching_events"] > 0, "Should match at least some events at start"
    if run_test("Test 1: Start of logs timestamp (01:10:00)", t1_payload, check_fn=check_t1):
        success_count += 1
        
    # Test 2: Normal phase (INFO/WARN only)
    total_tests += 1
    t2_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T05:00:00",
        "window_seconds": 120,
        "file_patterns": ["*.log*", "*.txt"]
    }
    def check_t2(data):
        assert data["summary"]["errors"] == 0, f"Expected 0 errors in normal phase, got {data['summary']['errors']}"
    if run_test("Test 2: Normal phase timestamp (05:00:00, no errors)", t2_payload, check_fn=check_t2):
        success_count += 1

    # Test 3: Failure peak (Contains errors)
    total_tests += 1
    t3_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 300,
        "file_patterns": ["*.log*", "*.txt"]
    }
    def check_t3(data):
        assert data["summary"]["errors"] > 0, "Expected errors in failure peak"
        # Check if the repeated errors lists EC=112 or similar
        messages = [err["message"] for err in data["repeated_errors"]]
        assert any("EC=112" in msg or "space" in msg.lower() or "failed" in msg.lower() for msg in messages), "Should report backup/write failures in repeated errors"
    if run_test("Test 3: Failure peak timestamp (12:15:00)", t3_payload, check_fn=check_t3):
        success_count += 1

    # Test 4: Slash format timestamp
    total_tests += 1
    t4_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026/07/19 12:15:00",
        "window_seconds": 60,
        "file_patterns": ["*.log*", "*.txt"]
    }
    if run_test("Test 4: Slash format timestamp (2026/07/19 12:15:00)", t4_payload):
        success_count += 1

    # Test 5: Invalid target timestamp
    total_tests += 1
    t5_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "invalid-timestamp",
        "window_seconds": 60
    }
    if run_test("Test 5: Invalid target timestamp validation", t5_payload, expected_status=422):
        success_count += 1

    # ----------------------------------------------------
    # Category 2: Window Seconds Adjustment
    # ----------------------------------------------------
    
    # Test 6: 0 seconds window (exact match on second)
    total_tests += 1
    t6_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T06:00:00",
        "window_seconds": 0
    }
    if run_test("Test 6: Window size = 0 seconds (exact match)", t6_payload):
        success_count += 1

    # Test 7: 5 seconds window
    total_tests += 1
    t7_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T06:00:00",
        "window_seconds": 5
    }
    def check_t7(data_t7):
        # Result of 5s should be >= result of 0s
        t6_res = client.post("/api/investigations", json=t6_payload, headers=AUTH_HEADERS).json()
        assert data_t7["summary"]["matching_events"] >= t6_res["summary"]["matching_events"]
    if run_test("Test 7: Window size = 5 seconds range", t7_payload, check_fn=check_t7):
        success_count += 1

    # Test 8: 60 seconds window
    total_tests += 1
    t8_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T06:00:00",
        "window_seconds": 60
    }
    def check_t8(data_t8):
        t7_res = client.post("/api/investigations", json=t7_payload, headers=AUTH_HEADERS).json()
        assert data_t8["summary"]["matching_events"] >= t7_res["summary"]["matching_events"]
    if run_test("Test 8: Window size = 60 seconds range", t8_payload, check_fn=check_t8):
        success_count += 1

    # Test 9: 1800 seconds window (large range)
    total_tests += 1
    t9_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:00:00",
        "window_seconds": 1800
    }
    def check_t9(data):
        assert data["summary"]["matching_events"] > 100, "Should match a large number of logs in 30 mins window"
    if run_test("Test 9: Window size = 1800 seconds range", t9_payload, check_fn=check_t9):
        success_count += 1

    # ----------------------------------------------------
    # Category 3: File Patterns
    # ----------------------------------------------------
    
    # Test 10: tomcat*.* pattern
    total_tests += 1
    t10_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 1800,
        "file_patterns": ["tomcat*.*"]
    }
    def check_t10(data):
        assert data["summary"]["files_scanned"] == 3, f"Expected 3 scanned tomcat files, got {data['summary']['files_scanned']}"
        for f in data["affected_files"]:
            assert "tomcat" in Path(f).name, f"Expected only tomcat files, got {f}"
    if run_test("Test 10: File pattern 'tomcat*.*'", t10_payload, check_fn=check_t10):
        success_count += 1

    # Test 11: WebService*.* pattern
    total_tests += 1
    t11_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 1800,
        "file_patterns": ["WebService*.*"]
    }
    def check_t11(data):
        assert data["summary"]["files_scanned"] == 3, f"Expected 3 web service files, got {data['summary']['files_scanned']}"
        for f in data["affected_files"]:
            assert "WebService" in Path(f).name, f"Expected only WebService files, got {f}"
    if run_test("Test 11: File pattern 'WebService*.*'", t11_payload, check_fn=check_t11):
        success_count += 1

    # Test 12: Backup-*.log pattern
    total_tests += 1
    t12_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 1800,
        "file_patterns": ["Backup-*.log"]
    }
    def check_t12(data):
        assert data["summary"]["files_scanned"] == 3, f"Expected 3 backup logs, got {data['summary']['files_scanned']}"
        for f in data["affected_files"]:
            assert "Backup-" in Path(f).name, f"Expected only Backup- files, got {f}"
    if run_test("Test 12: File pattern 'Backup-*.log'", t12_payload, check_fn=check_t12):
        success_count += 1

    # Test 13: *.log* pattern
    total_tests += 1
    t13_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 1800,
        "file_patterns": ["*.log*"]
    }
    def check_t13(data):
        assert data["summary"]["files_scanned"] == 8, f"Expected 8 scanned log* files, got {data['summary']['files_scanned']}"
    if run_test("Test 13: File pattern '*.log*'", t13_payload, check_fn=check_t13):
        success_count += 1

    # Test 14: Comma-separated patterns (tomcat*.*, Backup-*.log)
    total_tests += 1
    t14_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 1800,
        "file_patterns": ["tomcat*.*, Backup-*.log"]
    }
    def check_t14(data):
        assert data["summary"]["files_scanned"] == 6, f"Expected 6 scanned files, got {data['summary']['files_scanned']}"
    if run_test("Test 14: Comma-separated patterns 'tomcat*.*, Backup-*.log'", t14_payload, check_fn=check_t14):
        success_count += 1

    # Test 15: Nonexistent pattern (0 files scanned)
    total_tests += 1
    t15_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 1800,
        "file_patterns": ["nonexistent*.*"]
    }
    def check_t15(data):
        assert data["summary"]["files_scanned"] == 0, f"Expected 0 scanned files, got {data['summary']['files_scanned']}"
        assert data["summary"]["matching_events"] == 0, "Should match 0 events"
    if run_test("Test 15: Nonexistent file pattern validation", t15_payload, check_fn=check_t15):
        success_count += 1

    # Test 16: IGNORE_SUFFIXES check (.bak ignore)
    total_tests += 1
    t16_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 1800,
        "file_patterns": ["db_backup.log.bak"]
    }
    def check_t16(data):
        assert data["summary"]["files_scanned"] == 0, f"Expected 0 files scanned because .bak is ignored, got {data['summary']['files_scanned']}"
    if run_test("Test 16: Suffix filter check (ignoring .bak files)", t16_payload, check_fn=check_t16):
        success_count += 1

    # ----------------------------------------------------
    # Category 4: Filtering & Exporting
    # ----------------------------------------------------

    # Test 17: Filter keyword "EC=112"
    total_tests += 1
    t17_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 300,
        "filter_keywords": ["EC=112"]
    }
    def check_t17(data):
        for event in data["timeline"]:
            assert "ec=112" in event["message"].lower(), f"Expected event message to contain EC=112, got: {event['message']}"
    if run_test("Test 17: Filter keyword 'EC=112'", t17_payload, check_fn=check_t17):
        success_count += 1

    # Test 18: Filter keyword "SetEndOfFile"
    total_tests += 1
    t18_payload = {
        "folder_path": FOLDER_PATH,
        "target_timestamp": "2026-07-19T12:15:00",
        "window_seconds": 300,
        "filter_keywords": ["SetEndOfFile"]
    }
    def check_t18(data):
        for event in data["timeline"]:
            assert "setendoffile" in event["message"].lower(), f"Expected event message to contain SetEndOfFile, got: {event['message']}"
    if run_test("Test 18: Filter keyword 'SetEndOfFile'", t18_payload, check_fn=check_t18):
        success_count += 1

    # Test 19: Export format "txt"
    total_tests += 1
    def check_t19(response):
        assert "incident-report.txt" in response.headers["Content-Disposition"]
        assert "Incident Investigation Report" in response.text
    if run_export_test("Test 19: Export format TXT", "txt", t3_payload, check_fn=check_t19):
        success_count += 1

    # Test 20: Export format "html"
    total_tests += 1
    def check_t20(response):
        assert "incident-report.html" in response.headers["Content-Disposition"]
        assert "<html><body><pre>" in response.text
    if run_export_test("Test 20: Export format HTML", "html", t3_payload, check_fn=check_t20):
        success_count += 1

    # Test 21: Export format "md"
    total_tests += 1
    def check_t21(response):
        assert "incident-report.md" in response.headers["Content-Disposition"]
        assert "# Incident Investigation Report" in response.text
    if run_export_test("Test 21: Export format Markdown (md)", "md", t3_payload, check_fn=check_t21):
        success_count += 1

    # Test 22: Export format "extracted-txt"
    total_tests += 1
    def check_t22(response):
        assert "extracted-log-entries.txt" in response.headers["Content-Disposition"]
        assert "Backup-Server.log" in response.text
        assert "==========================================" in response.text
    if run_export_test("Test 22: Export format EXTRACTED-TXT", "extracted-txt", t3_payload, check_fn=check_t22):
        success_count += 1

    # Test 23: Export format "pdf"
    total_tests += 1
    def check_t23(response):
        assert "incident-report.pdf" in response.headers["Content-Disposition"]
        assert response.content.startswith(b"%PDF"), "Expected PDF binary header"
    if run_export_test("Test 23: Export format PDF", "pdf", t3_payload, check_fn=check_t23):
        success_count += 1

    print("\n" + "=" * 60)
    print(f"VALIDATION SUMMARY: {success_count} / {total_tests} Tests Passed")
    print("=" * 60)
    
    if success_count == total_tests:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
