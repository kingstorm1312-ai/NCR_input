

import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import gspread
from core.gsheets import open_worksheet, smart_append_batch

# Tên sheet trong Google Sheets
SHEET_MASTER = "DNXL"
SHEET_DETAIL = "DNXL_DETAILS"

@st.cache_data(ttl=60)
def get_dnxl_by_ncr(ncr_id):
    """
    Lấy danh sách DNXL Master thuộc về một NCR cụ thể.
    (Chưa lấy details để tối ưu hiệu năng hiển thị danh sách)
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, SHEET_MASTER)
        
        if not ws: return pd.DataFrame()

        data = ws.get_all_records()
        if not data: return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        if 'ncr_id' in df.columns:
            ncr_id_str = str(ncr_id).strip()
            df['ncr_id_str'] = df['ncr_id'].astype(str).str.strip()
            return df[df['ncr_id_str'] == ncr_id_str].drop(columns=['ncr_id_str'])
            
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu DNXL: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_dnxl_details(dnxl_id):
    """Lấy chi tiết các lỗi của một phiếu DNXL"""
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, SHEET_DETAIL)
        
        if not ws: return pd.DataFrame()

        data = ws.get_all_records()
        if not data: return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        if 'dnxl_id' in df.columns:
            # Convert both to string to be safe
            dnxl_id_str = str(dnxl_id).strip()
            df['dnxl_id_str'] = df['dnxl_id'].astype(str).str.strip()
            return df[df['dnxl_id_str'] == dnxl_id_str].drop(columns=['dnxl_id_str'])
            
        return pd.DataFrame()
    except Exception as e:
        # st.error(f"Lỗi tải chi tiết: {e}") # Silent error to avoid spam
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_all_dnxl_details_map():
    """
    Lấy toàn bộ details và gom nhóm theo dnxl_id.
    Returns: dict { 'dnxl_id': DataFrame }
    Giúp tối ưu hiển thị danh sách, tránh gọi API N lần.
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, SHEET_DETAIL)
        if not ws: return {}
        
        data = ws.get_all_records()
        if not data: return {}
        
        df = pd.DataFrame(data)
        if df.empty or 'dnxl_id' not in df.columns: return {}
        
        # Group by dnxl_id
        result = {}
        # Ensure dnxl_id is string
        df['dnxl_id'] = df['dnxl_id'].astype(str)
        
        for d_id, group in df.groupby('dnxl_id'):
            result[d_id] = group
            
        return result
    except Exception:
        return {}

def create_dnxl(ncr_data, form_header, details_df, user_name):
    """
    Tạo phiếu DNXL mới (Master) và DNXL Details.
    """
    try:
        # Validate details
        if details_df.empty:
            return False, "Danh sách lỗi chi tiết không được để trống!"

        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws_master = open_worksheet(spreadsheet_id, SHEET_MASTER)
        ws_detail = open_worksheet(spreadsheet_id, SHEET_DETAIL)
        
        if not ws_master or not ws_detail:
            return False, "Không thể kết nối đến Google Sheets"
            
        # 1. Prepare Master Data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dnxl_id = f"DNXL-{uuid.uuid4().hex[:8].upper()}"
        
        # Use Dict instead of List to ensure correct column mapping
        row_master = {
            "dnxl_id": dnxl_id,
            "ncr_id": ncr_data.get('so_phieu', ''),
            "target_scope": form_header['target_scope'],
            "deadline": str(form_header['deadline']),
            "handling_instruction": form_header['handling_instruction'],
            "status": 'moi_tao',
            "created_by": user_name,
            "created_at": timestamp,
            "claimed_by": "",
            "claimed_at": "",
            "worker_response": "",
            "worker_images": "",
            "qc_review_note": "",
            "completed_at": ""
        }
        
        # 2. Prepare Details Data
        rows_detail = []
        for _, r in details_df.iterrows():
            rows_detail.append({
                "dnxl_id": dnxl_id,
                "ncr_id": ncr_data.get('so_phieu', ''),
                "defect_name": r['Tên Lỗi'],
                "qty_assigned": r['SL Cần Xử Lý'],
                "qty_fixed": 0,
                "qty_fail": 0,
                "worker_note": "",
                "created_at": timestamp
            })
            
        # 3. Write to Sheets (Batch)
        smart_append_batch(ws_master, [row_master])
        smart_append_batch(ws_detail, rows_detail)
        
        st.cache_data.clear() # Clear cache to refresh data immediately
        return True, f"Đã tạo phiếu {dnxl_id} thành công!"
        
    except Exception as e:
        return False, str(e)

# --- NEW FUNCTIONS FOR DNXL FULL FLOW ---

def get_pending_dnxl(role, user_name):
    """
    Lấy danh sách DNXL cần xử lý dựa trên role.
    
    Args:
        role: 'to_xu_ly' hoặc 'qc_manager'
        user_name: Tên user hiện tại
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, SHEET_MASTER)
        if not ws: return pd.DataFrame()

        data = ws.get_all_records()
        if not data: return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Ensure required columns exist
        for col in ['status', 'claimed_by', 'created_by']:
            if col not in df.columns:
                df[col] = ''
                
        # Filter Logic
        if role == 'to_xu_ly':
            # 1. Mới tạo (Chưa ai nhận)
            cond_new = (df['status'] == 'moi_tao')
            # 2. Đang xử lý (Chính user này nhận)
            cond_processing = (df['status'] == 'dang_xu_ly') & (df['claimed_by'] == user_name)
            # 3. Trả lại (Chính user này nhận)
            cond_reject = (df['status'] == 'tra_lai') & (df['claimed_by'] == user_name)
            
            return df[cond_new | cond_processing | cond_reject]
            
        elif role == 'qc_manager':
            # QC Manager xem phiếu chờ duyệt kết quả
            return df[df['status'] == 'cho_duyet_ket_qua']
            
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Lỗi tải danh sách DNXL: {e}")
        return pd.DataFrame()

def claim_dnxl(dnxl_id, user_name):
    """
    Tổ xử lý nhận việc (Claim).
    Status: moi_tao -> dang_xu_ly
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, SHEET_MASTER)
        
        # Find row
        cell = ws.find(dnxl_id)
        if not cell:
            return False, "Không tìm thấy phiếu"
            
        row_idx = cell.row
        
        # Get Header mapping
        headers = ws.row_values(1)
        try:
            col_status = headers.index('status') + 1
            col_claimed_by = headers.index('claimed_by') + 1
            col_claimed_at = headers.index('claimed_at') + 1
        except ValueError:
            return False, "Sheet thiếu cột metadata (status/claimed_by)"
            
        # Check current status (Optional safety)
        current_status = ws.cell(row_idx, col_status).value
        if current_status != 'moi_tao':
            return False, f"Phiếu này không còn ở trạng thái Mới (Status: {current_status})"
            
        # Update
        updates = [
            {'range': gspread.utils.rowcol_to_a1(row_idx, col_status), 'values': [['dang_xu_ly']]},
            {'range': gspread.utils.rowcol_to_a1(row_idx, col_claimed_by), 'values': [[user_name]]},
            {'range': gspread.utils.rowcol_to_a1(row_idx, col_claimed_at), 'values': [[datetime.now().strftime("%Y-%m-%d %H:%M:%S")]]}
        ]
        ws.batch_update(updates)
        st.cache_data.clear()
        return True, "Đã nhận việc thành công!"
        
    except Exception as e:
        return False, f"Lỗi system: {e}"

def update_dnxl_progress(dnxl_id, details_list, worker_response, worker_images):
    """
    Cập nhật tiến độ xử lý và gửi duyệt.
    Status: dang_xu_ly/tra_lai -> cho_duyet_ket_qua
    
    Args:
        details_list: List dict updated details (qty_fixed, worker_note...)
        worker_response: Text chung
        worker_images: Url string (newline separated)
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws_master = open_worksheet(spreadsheet_id, SHEET_MASTER)
        ws_detail = open_worksheet(spreadsheet_id, SHEET_DETAIL)
        
        # --- 1. UPDATE MASTER ---
        cell_m = ws_master.find(dnxl_id)
        if not cell_m: return False, "Không tìm thấy Master DNXL"
        
        headers_m = ws_master.row_values(1)
        col_status = headers_m.index('status') + 1
        col_response = headers_m.index('worker_response') + 1
        col_images = headers_m.index('worker_images') + 1
        
        updates_m = [
            {'range': gspread.utils.rowcol_to_a1(cell_m.row, col_status), 'values': [['cho_duyet_ket_qua']]},
            {'range': gspread.utils.rowcol_to_a1(cell_m.row, col_response), 'values': [[worker_response]]},
            {'range': gspread.utils.rowcol_to_a1(cell_m.row, col_images), 'values': [[worker_images]]},
        ]
        ws_master.batch_update(updates_m)
        
        # --- 2. UPDATE DETAILS ---
        # Get all details to find rows
        all_details = ws_detail.get_all_records()
        headers_d = ws_detail.row_values(1)
        
        col_qty_fixed = headers_d.index('qty_fixed') + 1
        col_worker_note = headers_d.index('worker_note') + 1
        # Optional columns check
        col_qty_fail = headers_d.index('qty_fail') + 1 if 'qty_fail' in headers_d else -1
        
        updates_d = []
        new_rows = []
        
        # Map existing rows for fast lookup: detail_id -> row_idx
        detail_map = {}
        for i, d in enumerate(all_details):
             # Row in sheet = i + 2 (Header starts 1, data starts 2)
             if str(d.get('dnxl_id')) == str(dnxl_id):
                 detail_map[str(d.get('detail_id'))] = i + 2
                 
        for item in details_list:
            d_id = str(item.get('detail_id', ''))
            
            # Case A: Existing Detail -> Update
            if d_id in detail_map:
                r_idx = detail_map[d_id]
                updates_d.append({'range': gspread.utils.rowcol_to_a1(r_idx, col_qty_fixed), 'values': [[item.get('qty_fixed', 0)]]})
                updates_d.append({'range': gspread.utils.rowcol_to_a1(r_idx, col_worker_note), 'values': [[item.get('worker_note', '')]]})
                if col_qty_fail != -1:
                    updates_d.append({'range': gspread.utils.rowcol_to_a1(r_idx, col_qty_fail), 'values': [[item.get('qty_fail', 0)]]})
                    
            # Case B: New Detail (Added by worker) -> Insert
            elif item.get('is_new', False):
                new_row = {
                    "detail_id": f"D-{uuid.uuid4().hex[:8]}",
                    "dnxl_id": dnxl_id,
                    "defect_name": item.get('defect_name'),
                    "qty_assigned": 0, # Worker added implies 0 assigned originally? Or should allow input? Let's say 0.
                    "qty_fixed": item.get('qty_fixed', 0),
                    "qty_fail": item.get('qty_fail', 0),
                    "worker_note": item.get('worker_note', ''),
                    "is_added_by_worker": "TRUE"
                }
                new_rows.append(new_row)

        if updates_d:
            ws_detail.batch_update(updates_d)
            
        if new_rows:
            smart_append_batch(ws_detail, new_rows)
            
        st.cache_data.clear()
        return True, "Đã gửi kết quả xử lý thành công"
        
    except Exception as e:
        return False, f"Lỗi update: {e}"

def qc_review_dnxl(dnxl_id, decision, note):
    """
    QC Manager duyệt kết quả.
    Decision: 'approve' -> hoan_thanh
              'reject' -> tra_lai
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, SHEET_MASTER)
        cell = ws.find(dnxl_id)
        if not cell: return False, "Phiếu không tồn tại"
        
        headers = ws.row_values(1)
        col_status = headers.index('status') + 1
        
        updates = []
        
        if decision == 'approve':
            updates.append({'range': gspread.utils.rowcol_to_a1(cell.row, col_status), 'values': [['hoan_thanh']]})
            # Ghi nhận kết quả vào result_summary
            col_res = headers.index('result_summary') + 1 if 'result_summary' in headers else -1
            if col_res != -1:
                 updates.append({'range': gspread.utils.rowcol_to_a1(cell.row, col_res), 'values': [[note]]})
                 
        elif decision == 'reject':
            updates.append({'range': gspread.utils.rowcol_to_a1(cell.row, col_status), 'values': [['tra_lai']]})
            col_note = headers.index('qc_review_note') + 1 if 'qc_review_note' in headers else -1
            if col_note != -1:
                 updates.append({'range': gspread.utils.rowcol_to_a1(cell.row, col_note), 'values': [[note]]})
                 
        ws.batch_update(updates)
        st.cache_data.clear()
        return True, f"Đã {decision} phiếu {dnxl_id}"
        
    except Exception as e:
        return False, f"Lỗi duyệt: {e}"

def force_complete_dnxl(dnxl_id, user_name, note="Hoàn tất thủ công (Offline)"):
    """
    QC Manager chủ động hoàn tất phiếu (bỏ qua quy trình online của Worker).
    Status: * -> hoan_thanh
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, SHEET_MASTER)
        cell = ws.find(dnxl_id)
        if not cell: return False, "Phiếu không tồn tại"
        
        headers = ws.row_values(1)
        col_status = headers.index('status') + 1
        col_res = headers.index('result_summary') + 1 if 'result_summary' in headers else -1
        
        updates = []
        updates.append({'range': gspread.utils.rowcol_to_a1(cell.row, col_status), 'values': [['hoan_thanh']]})
        
        if col_res != -1:
             updates.append({'range': gspread.utils.rowcol_to_a1(cell.row, col_res), 'values': [[note]]})
             
        ws.batch_update(updates)
        st.cache_data.clear()
        return True, f"Đã hoàn tất phiếu {dnxl_id}"
        
    except Exception as e:
        return False, f"Lỗi system: {e}"
