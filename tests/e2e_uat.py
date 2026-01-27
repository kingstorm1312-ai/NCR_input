import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime
import copy

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- MOCK STREAMLIT ---
import streamlit as st
st.secrets = {
    "connections": {
        "gsheets": {
            "spreadsheet": "test_spreadsheet_id",
            "service_account": "{}"
        }
    },
    "cloudinary": {
        "cloud_name": "test",
        "api_key": "test",
        "api_secret": "test"
    }
}
st.cache_data = lambda *args, **kwargs: (lambda f: f)
st.cache_resource = lambda *args, **kwargs: (lambda f: f)
st.error = MagicMock()
st.toast = MagicMock()
st.session_state = {}

# --- IN-MEMORY DATABASE (MOCK) ---
# Headers from real NCR_DATA sheet
NCR_HEADERS = [
    "ngay_lap", "so_phieu_ncr", "so_lan", "hop_dong", "ma_vat_tu", 
    "ten_sp", "phan_loai", "nguon_goc", "ten_loi", "vi_tri_loi", 
    "so_luong_loi", "so_luong_kiem", "muc_do", "mo_ta_loi", 
    "so_luong_lo_hang", "nguoi_lap_phieu", "noi_gay_loi", "trang_thai", 
    "thoi_gian_cap_nhat", "hinh_anh", "don_vi_tinh", "ket_qua_kiem_tra",
    "spec_size", "tol_size", "meas_size", "spec_weight", "tol_weight", "meas_weight",
    "check_barcode", "check_weight_box", "check_print", "check_color", "check_other",
    "so_po", "khach_hang", "don_vi_kiem", "ly_do_tu_choi", "y_kien_qc", "bien_phap_truong_bp", "huong_xu_ly_giam_doc"
]

class MockWorksheet:
    def __init__(self, name, data=None):
        self.name = name
        self.data = data if data is not None else [NCR_HEADERS] # Row 1 is header

    def get_all_values(self):
        return self.data

    def get_all_records(self):
        headers = self.data[0]
        records = []
        for row in self.data[1:]:
            records.append(dict(zip(headers, row)))
        return records

    def row_values(self, row_index):
        if row_index <= len(self.data):
            return self.data[row_index - 1]
        return []

    def col_values(self, col_index):
        return [row[col_index - 1] for row in self.data]

    def append_row(self, values):
        # Pad values to match header length
        full_row = values + [""] * (len(NCR_HEADERS) - len(values))
        self.data.append(full_row)

    def append_rows(self, rows_list, value_input_option=None):
        for row in rows_list:
            self.append_row(row)

    def batch_update(self, updates):
        for upd in updates:
            cell_ref = upd['range']
            val = upd['values'][0][0]
            import re
            match = re.match(r"([A-Z]+)(\d+)", cell_ref)
            if match:
                col_str, row_str = match.groups()
                row_idx = int(row_str) - 1
                col_idx = 0
                for char in col_str:
                    col_idx = col_idx * 26 + (ord(char) - ord('A') + 1)
                col_idx -= 1
                
                while len(self.data) <= row_idx:
                    self.data.append([""] * len(NCR_HEADERS))
                self.data[row_idx][col_idx] = val

    def find(self, query):
        for r, row in enumerate(self.data):
            for c, val in enumerate(row):
                if str(val) == str(query):
                    mock_cell = MagicMock()
                    mock_cell.row = r + 1
                    mock_cell.col = c + 1
                    return mock_cell
        return None

class UATScenarioTest(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockWorksheet("NCR_DATA")
        self.mock_users = MockWorksheet("USERS")
        self.mock_gc = MagicMock()
        self.mock_sh = MagicMock()
        self.mock_gc.open_by_key.return_value = self.mock_sh
        
        def side_effect_ws(name):
            if name == "NCR_DATA": return self.mock_db
            if name == "USERS": return self.mock_users
            return MagicMock()
        self.mock_sh.worksheet.side_effect = side_effect_ws

        patch('utils.ncr_helpers.init_gspread').start().return_value = self.mock_gc
        patch('core.services.approval_service.init_gspread').start().return_value = self.mock_gc
        patch('core.gsheets.get_client').start().return_value = self.mock_gc
        patch('utils.ncr_helpers._get_ncr_data_cached').start().side_effect = lambda: pd.DataFrame(self.mock_db.get_all_records())

    def tearDown(self):
        patch.stopall()

    def test_scenario_01_happy_path_dual_branch(self):
        """Scenario 1: Happy Path - Sequential Approvals with Draft Start & Branching"""
        print("\n--- Scenario 1: Happy Path (Dual Branch) ---")
        try:
            from core.services import approval_service
            from utils.ncr_helpers import smart_append_ncr, get_next_status, update_ncr_status
            
            # --- BRANCH A: FI (Skip BP) ---
            print("Branch A: Skip BP (FI)")
            so_phieu_a = "FI-270127-01"
            smart_append_ncr(self.mock_db, {"so_phieu_ncr": so_phieu_a, "trang_thai": "draft", "bo_phan": "fi"})
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_a), "draft")
            
            # SUBMIT using real logic
            success, _ = update_ncr_status(self.mock_gc, so_phieu_a, "cho_truong_ca", "Creator", "creator")
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_a), "cho_truong_ca")

            # Level 1: Truong Ca -> skip to QC Manager
            next_status = get_next_status('cho_truong_ca', 'fi')
            self.assertEqual(next_status, 'cho_qc_manager')
            success, _ = approval_service.approve_ncr(so_phieu_a, 'truong_ca', 'Boss A1', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_a), "cho_qc_manager")

            # IDEMPOTENCY GUARD (Restored)
            success, msg = approval_service.approve_ncr(so_phieu_a, 'truong_ca', 'Boss A1', next_status)
            self.assertFalse(success, "Idempotency Guard Failed: Should block repeated approval")
            self.assertIn("đã được xử lý", msg) 

            # Level 2: QC Manager -> Director
            next_status = get_next_status('cho_qc_manager', 'fi')
            self.assertEqual(next_status, 'cho_giam_doc') # Correct flow: cho_qc_manager -> cho_giam_doc
            success, _ = approval_service.approve_ncr(so_phieu_a, 'qc_manager', 'QC Boss', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_a), "cho_giam_doc")

            # Level 3: Director -> BGD Tan Phu
            next_status = get_next_status('cho_giam_doc', 'fi')
            self.assertEqual(next_status, 'cho_bgd_tan_phu')
            success, _ = approval_service.approve_ncr(so_phieu_a, 'director', 'CEO', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_a), "cho_bgd_tan_phu")
            
            # Level 4: BGD Tan Phu -> Hoan thanh
            next_status = get_next_status('cho_bgd_tan_phu', 'fi')
            self.assertEqual(next_status, 'hoan_thanh')
            success, _ = approval_service.approve_ncr(so_phieu_a, 'bgd_tan_phu', 'Big Boss', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_a), "hoan_thanh")

            # --- BRANCH B: Standard (No Skip BP) ---
            print("Branch B: Standard (No Skip BP)")
            so_phieu_b = "X2-TR-270127-02"
            smart_append_ncr(self.mock_db, {"so_phieu_ncr": so_phieu_b, "trang_thai": "draft", "bo_phan": "trang_cat"})
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_b), "draft")
            
            # SUBMIT
            success, _ = update_ncr_status(self.mock_gc, so_phieu_b, "cho_truong_ca", "Creator", "creator")
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_b), "cho_truong_ca")

            # 1. Truong Ca -> Truong BP
            next_status = get_next_status('cho_truong_ca', 'trang_cat')
            self.assertEqual(next_status, 'cho_truong_bp')
            success, _ = approval_service.approve_ncr(so_phieu_b, 'truong_ca', 'Boss B1', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_b), "cho_truong_bp")
            
            # 2. Truong BP -> QC Manager
            next_status = get_next_status('cho_truong_bp', 'trang_cat')
            self.assertEqual(next_status, 'cho_qc_manager')
            success, _ = approval_service.approve_ncr(so_phieu_b, 'truong_bp', 'Boss B2', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_b), "cho_qc_manager")
            
            # 3. QC Manager -> Director
            next_status = get_next_status('cho_qc_manager', 'trang_cat')
            self.assertEqual(next_status, 'cho_giam_doc')
            success, _ = approval_service.approve_ncr(so_phieu_b, 'qc_manager', 'QC', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_b), "cho_giam_doc")

            # 4. Director -> BGD
            next_status = get_next_status('cho_giam_doc', 'trang_cat')
            self.assertEqual(next_status, 'cho_bgd_tan_phu')
            success, _ = approval_service.approve_ncr(so_phieu_b, 'director', 'CEO', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_b), "cho_bgd_tan_phu")

            # 5. BGD -> Hoan Thanh
            next_status = get_next_status('cho_bgd_tan_phu', 'trang_cat')
            self.assertEqual(next_status, 'hoan_thanh')
            success, _ = approval_service.approve_ncr(so_phieu_b, 'bgd_tan_phu', 'BGD', next_status)
            self.assertTrue(success)
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu_b), "hoan_thanh")
            
            print("Scenario 1: PASS")
        except AssertionError as e:
            print(f"Scenario 1: FAIL: {str(e)}")
            print("Repro: Follow Scenario 1 steps in walkthrough.md (FI/Standard flow)")
            raise e

    def test_scenario_02_uniqueness(self):
        """Scenario 2: Uniqueness Guard - Deterministic Merge of same ticket number"""
        print("\n--- Scenario 2: Uniqueness / Merge Guard ---")
        try:
            from core.gsheets import smart_append_batch
            from utils.ncr_helpers import load_ncr_data_with_grouping
            
            so_phieu = "UNIQUE-999"
            batch = [
                {"so_phieu_ncr": so_phieu, "so_luong_loi": 10, "trang_thai": "draft", "ngay_lap": "27/01/2026"},
                {"so_phieu_ncr": so_phieu, "so_luong_loi": 5, "trang_thai": "draft", "ngay_lap": "27/01/2026"}
            ]
            smart_append_batch(self.mock_db, batch)
            
            # ASSERT: Raw sheet still has 2 separate rows (header + 2 data rows)
            self.assertEqual(len(self.mock_db.data), 3, "Raw sheet should have header + 2 data rows")
            
            _, df_grouped = load_ncr_data_with_grouping(self.mock_gc)
            
            # Robust Conversion
            df_grouped['sl_loi'] = pd.to_numeric(df_grouped['sl_loi'], errors='coerce')
            
            unique_entry = df_grouped[df_grouped['so_phieu'] == so_phieu]
            self.assertEqual(len(unique_entry), 1, "Invariant Violation: Duplicate ticket markers found")
            self.assertEqual(unique_entry.iloc[0]['sl_loi'], 15, f"Merger Error: Expected 15, got {unique_entry.iloc[0]['sl_loi']}")
            
            # ASSERT: Raw sheet UNCHANGED after merge (merge is read-only DataFrame operation)
            self.assertEqual(len(self.mock_db.data), 3, "Data Integrity Violation: Merge mutated raw sheet data")
            
            print("Scenario 2: PASS")
        except AssertionError as e:
            print(f"Scenario 2: FAIL: {str(e)}")
            print("Repro: Add duplicate ncr rows, verify load_ncr_data_with_grouping merges them")
            raise e

    def test_scenario_03_rejection(self):
        """Scenario 3: Rejection Flow - Always returns to Draft"""
        print("\n--- Scenario 3: Rejection ---")
        try:
            from core.services import approval_service
            from utils.ncr_helpers import smart_append_ncr
            
            so_phieu = "REJ-001"
            smart_append_ncr(self.mock_db, {"so_phieu_ncr": so_phieu, "trang_thai": "cho_qc_manager", "bo_phan": "fi"})
            
            success, msg = approval_service.reject_ncr(so_phieu, 'qc_manager', 'QC Boss', 'cho_qc_manager', "Loi")
            self.assertTrue(success, f"Rejection failed: {msg}")
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu), "draft")
            print("Scenario 3: PASS")
        except AssertionError as e:
            print(f"Scenario 3: FAIL: {str(e)}")
            print("Repro: Reject an NCR, assert status becomes 'draft'")
            raise e

    def test_scenario_04_cancellation(self):
        """Scenario 4: Cancellation - Draft -> da_huy & Block Actions"""
        print("\n--- Scenario 4: Cancellation ---")
        try:
            from core.services import approval_service
            from utils.ncr_helpers import smart_append_ncr, cancel_ncr
            
            so_phieu = "CAN-001"
            smart_append_ncr(self.mock_db, {"so_phieu_ncr": so_phieu, "trang_thai": "draft"})
            
            success, msg = cancel_ncr(self.mock_gc, so_phieu, "Error")
            self.assertTrue(success, f"Cancellation failed: {msg}")
            self.assertEqual(approval_service._get_current_status_from_sheet(so_phieu), "da_huy")
            
            success, _ = approval_service.approve_ncr(so_phieu, 'truong_ca', 'Boss', 'cho_qc_manager')
            self.assertFalse(success, "Security Error: Action allowed on cancelled ticket")
            
            print("Scenario 4: PASS")
        except AssertionError as e:
            print(f"Scenario 4: FAIL: {str(e)}")
            print("Repro: Cancel an NCR, assert status 'da_huy' and subsequent approvals blocked")
            raise e

    def test_scenario_05_reporting_integrity(self):
        """Scenario 5: Reporting Integrity - Exclude da_huy & Grouping Check & Read-only"""
        print("\n--- Scenario 5: Reporting Integrity ---")
        try:
            from core.services import report_service
            from utils.ncr_helpers import smart_append_ncr, load_ncr_data_with_grouping
            from core.gsheets import smart_append_batch
            
            # 1. Exclude da_huy
            smart_append_ncr(self.mock_db, {"so_phieu_ncr": "REPORT-OK", "trang_thai": "hoan_thanh"})
            smart_append_ncr(self.mock_db, {"so_phieu_ncr": "REPORT-FAIL", "trang_thai": "da_huy"})
            
            # 2. Multi-row ticket for grouping check
            so_phieu_multi = "REPORT-MULTI"
            batch = [
                {"so_phieu_ncr": so_phieu_multi, "so_luong_loi": 10, "trang_thai": "hoan_thanh"},
                {"so_phieu_ncr": so_phieu_multi, "so_luong_loi": 20, "trang_thai": "hoan_thanh"}
            ]
            smart_append_batch(self.mock_db, batch)

            # 3. Read-only behavior check
            initial_data_snapshot = copy.deepcopy(self.mock_db.data)
            
            # TEST A: get_report_data() - Raw data with da_huy exclusion
            df_report_raw = report_service.get_report_data()
            
            # Assert Immutability
            self.assertEqual(self.mock_db.data, initial_data_snapshot, "Data Integrity Violation: Report generation mutated raw data")
            
            # Assert da_huy exclusion in raw report
            target_col = 'so_phieu' if 'so_phieu' in df_report_raw.columns else 'so_phieu_ncr'
            self.assertNotIn("REPORT-FAIL", df_report_raw[target_col].values, "Integrity Error: da_huy visible in raw report")
            
            # Raw report should have 2 rows for multi-ticket (ungrouped)
            multi_raw = df_report_raw[df_report_raw[target_col] == so_phieu_multi]
            self.assertEqual(len(multi_raw), 2, f"Raw Report Error: Expected 2 ungrouped rows, got {len(multi_raw)}")
            
            # TEST B: load_ncr_data_with_grouping() - Grouped data (includes all statuses)
            _, df_grouped = load_ncr_data_with_grouping(self.mock_gc)
            
            # Grouped data must return EXACTLY 1 row for multi-error ticket
            multi_grouped = df_grouped[df_grouped['so_phieu'] == so_phieu_multi]
            self.assertEqual(len(multi_grouped), 1, f"Grouping Error: Expected 1 grouped row, got {len(multi_grouped)} rows")
            
            # Verify aggregated sum is correct
            df_grouped['sl_loi'] = pd.to_numeric(df_grouped['sl_loi'], errors='coerce')
            aggregated_value = multi_grouped.iloc[0]['sl_loi']
            self.assertEqual(aggregated_value, 30, f"Aggregation Error: Expected 30 (10+20), got {aggregated_value}")
            
            # Assert Immutability again after grouping
            self.assertEqual(self.mock_db.data, initial_data_snapshot, "Data Integrity Violation: Grouping mutated raw data")
            
            print("Scenario 5: PASS")
        except AssertionError as e:
            print(f"Scenario 5: FAIL: {str(e)}")
            print("Repro: Check report logic for da_huy exclusion and grouping behavior")
            raise e

if __name__ == "__main__":
    unittest.main()
