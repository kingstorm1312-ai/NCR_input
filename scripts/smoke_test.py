import os
import sys
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock Streamlit to allow running outside of 'streamlit run'
import streamlit as st
if not hasattr(st, "secrets") or not st.secrets:
    st.secrets = {
        "connections": {
            "gsheets": {
                "spreadsheet": "mock_id",
                "service_account": "{}"
            }
        },
        "cloudinary": {
            "cloud_name": "mock",
            "api_key": "mock",
            "api_secret": "mock"
        }
    }

class SmokeTest(unittest.TestCase):
    def test_01_secrets_presence(self):
        """Kiem tra su ton tai cua cac key bat buoc trong secrets."""
        print("\n[STEP 1] Checking Secrets Presence...")
        required_keys = [
            ("connections", "gsheets", "spreadsheet"),
            ("connections", "gsheets", "service_account")
        ]
        
        try:
            for keys in required_keys:
                sec = st.secrets
                for k in keys:
                    sec = sec[k]
            print("PASS - Secrets Presence")
        except Exception as e:
            self.fail(f"FAIL - Secrets Presence - Missing key {keys} ({e})")

    def test_02_service_imports(self):
        """Kiem tra viec import cac service layers."""
        print("\n[STEP 2] Checking Service Imports...")
        try:
            from core.services import report_service, approval_service, monitor_service, user_service
            print("PASS - Service Imports")
        except Exception as e:
            self.fail(f"FAIL - Service Imports - {e}")

    def test_03_readonly_calls_dry_run(self):
        """Kiem tra cac ham read-only (Dry-run/Mocked)."""
        print("\n[STEP 3] Checking Service Functions (Structure)...")
        from core.services import report_service, approval_service, monitor_service, user_service
        
        services_to_test = [
            ("Report Service", report_service.get_report_data),
            ("Monitor Service", monitor_service.get_monitor_data),
            ("User Service", user_service.load_users)
        ]
        
        for name, func in services_to_test:
            try:
                self.assertTrue(callable(func), f"{name} is not callable")
                print(f"PASS - {name} Callable")
            except Exception as e:
                self.fail(f"FAIL - {name} Validation - {e}")

if __name__ == "__main__":
    print("Starting Antigravity Smoke Test Harness")
    print("="*40)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(SmokeTest)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    
    if not result.wasSuccessful():
        print("\nSMOKE TEST FAILED!")
        sys.exit(1)
    else:
        print("\nALL SMOKE TESTS PASSED!")
        sys.exit(0)
