import pandas as pd
from datetime import datetime
import streamlit as st

# --- STATUS FLOW CONFIGURATION ---
STATUS_FLOW = {
    'draft': 'cho_truong_ca',
    'cho_truong_ca': 'cho_truong_bp',
    'cho_truong_bp': 'cho_qc_manager',
    'cho_qc_manager': 'cho_giam_doc',
    'cho_giam_doc': 'hoan_thanh',
    'hoan_thanh': 'hoan_thanh'  # Completed state
}

ROLE_TO_APPROVER_COLUMN = {
    'truong_ca': 'nguoi_duyet_1',
    'truong_bp': 'nguoi_duyet_2',
    'qc_manager': 'nguoi_duyet_3',
    'director': 'nguoi_duyet_4'
}

ROLE_TO_STATUS = {
    'truong_ca': 'cho_truong_ca',
    'truong_bp': 'cho_truong_bp',
    'qc_manager': 'cho_qc_manager',
    'director': 'cho_giam_doc'
}

# --- DATA LOADING & GROUPING ---
def load_ncr_data_with_grouping(gc, filter_status=None, filter_department=None):
    """
    Load NCR_DATA từ Google Sheets và group theo ticket.
    
    Args:
        gc: Google Sheets client
        filter_status: Filter theo trạng thái (optional)
        filter_department: Filter theo bộ phận (optional)
    
    Returns:
        df_original: DataFrame gốc (dùng để update)
        df_grouped: DataFrame đã group theo so_phieu (dùng để hiển thị UI)
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("NCR_DATA")
        
        # Load all records
        records = ws.get_all_records()
        df_original = pd.DataFrame(records)
        
        if df_original.empty:
            return pd.DataFrame(), pd.DataFrame()
        
        # Normalize column names (strip spaces)
        df_original.columns = df_original.columns.str.strip()
        
        # Apply filters
        df_filtered = df_original.copy()
        
        if filter_status:
            df_filtered = df_filtered[df_filtered['trang_thai'].astype(str).str.strip() == filter_status]
        
        if filter_department:
            # Assuming 'bo_phan' column exists or can be derived from 'so_phieu'
            # Extract department from so_phieu (e.g., 'FI-01-001' -> 'fi')
            df_filtered['bo_phan'] = df_filtered['so_phieu'].astype(str).str.split('-').str[0].str.lower()
            df_filtered = df_filtered[df_filtered['bo_phan'] == filter_department]
        
        if df_filtered.empty:
            return df_original, pd.DataFrame()
        
        # Group by so_phieu
        grouped = df_filtered.groupby('so_phieu', as_index=False).agg({
            'ngay_lap': 'first',
            'nguoi_lap_phieu': 'first',
            'trang_thai': 'first',
            'thoi_gian_cap_nhat': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(sorted(set(x.astype(str)))),
            'nguoi_duyet_1': 'first',
            'nguoi_duyet_2': 'first',
            'nguoi_duyet_3': 'first',
            'nguoi_duyet_4': 'first',
            'huong_giai_quyet': 'first',
            'ly_do_tu_choi': 'first'
        })
        
        # Add bo_phan to grouped
        if 'bo_phan' in df_filtered.columns:
            grouped['bo_phan'] = df_filtered.groupby('so_phieu')['bo_phan'].first().values
        
        return df_original, grouped
        
    except Exception as e:
        st.error(f"Lỗi load NCR data: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame(), pd.DataFrame()


def update_ncr_status(gc, so_phieu, action, user_name, user_role, solution=None, reject_reason=None):
    """
    Cập nhật trạng thái NCR cho TẤT CẢ các rows có cùng so_phieu.
    
    Args:
        gc: Google Sheets client
        so_phieu: Mã phiếu NCR
        action: 'approve' hoặc 'reject'
        user_name: Tên người phê duyệt/từ chối
        user_role: Role của người dùng (để xác định cột nguoi_duyet_X)
        solution: Hướng giải quyết (chỉ cho QC Manager)
        reject_reason: Lý do từ chối (chỉ khi reject)
    
    Returns:
        success: Boolean
        message: Thông báo
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("NCR_DATA")
        
        # Get all data
        all_data = ws.get_all_values()
        headers = all_data[0]
        
        # Find column indices
        col_so_phieu = headers.index('so_phieu')
        col_trang_thai = headers.index('trang_thai')
        col_thoi_gian = headers.index('thoi_gian_cap_nhat')
        
        # Optional columns
        col_huong_giai_quyet = headers.index('huong_giai_quyet') if 'huong_giai_quyet' in headers else None
        col_ly_do_tu_choi = headers.index('ly_do_tu_choi') if 'ly_do_tu_choi' in headers else None
        
        # Get approver column index
        approver_col_name = ROLE_TO_APPROVER_COLUMN.get(user_role)
        col_approver = headers.index(approver_col_name) if approver_col_name in headers else None
        
        # Find all rows matching so_phieu
        rows_to_update = []
        for idx, row in enumerate(all_data[1:], start=2):  # Start from row 2 (skip header)
            if row[col_so_phieu] == so_phieu:
                rows_to_update.append(idx)
        
        if not rows_to_update:
            return False, f"Không tìm thấy phiếu {so_phieu}"
        
        # Determine new status
        current_status = all_data[rows_to_update[0] - 1][col_trang_thai]
        
        if action == 'approve':
            new_status = STATUS_FLOW.get(current_status.strip(), current_status)
        else:  # reject
            new_status = 'draft'
        
        # Update timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare batch update
        updates = []
        
        for row_idx in rows_to_update:
            # Update trang_thai
            updates.append({
                'range': f'{chr(65 + col_trang_thai)}{row_idx}',
                'values': [[new_status]]
            })
            
            # Update thoi_gian_cap_nhat
            updates.append({
                'range': f'{chr(65 + col_thoi_gian)}{row_idx}',
                'values': [[current_time]]
            })
            
            # Update approver name (if approve)
            if action == 'approve' and col_approver is not None:
                updates.append({
                    'range': f'{chr(65 + col_approver)}{row_idx}',
                    'values': [[user_name]]
                })
            
            # Update solution (QC Manager only)
            if solution and col_huong_giai_quyet is not None:
                updates.append({
                    'range': f'{chr(65 + col_huong_giai_quyet)}{row_idx}',
                    'values': [[solution]]
                })
            
            # Update reject reason
            if reject_reason and col_ly_do_tu_choi is not None:
                updates.append({
                    'range': f'{chr(65 + col_ly_do_tu_choi)}{row_idx}',
                    'values': [[reject_reason]]
                })
        
        # Execute batch update
        ws.batch_update(updates)
        
        action_text = "phê duyệt" if action == 'approve' else "từ chối"
        return True, f"Đã {action_text} phiếu {so_phieu} ({len(rows_to_update)} dòng)"
        
    except Exception as e:
        return False, f"Lỗi cập nhật: {str(e)}"


def calculate_stuck_time(timestamp_str):
    """
    Tính số giờ kể từ timestamp.
    
    Args:
        timestamp_str: String timestamp theo format "%Y-%m-%d %H:%M:%S"
    
    Returns:
        hours: Số giờ (float)
    """
    try:
        if not timestamp_str or timestamp_str.strip() == '':
            return 0
        
        timestamp = datetime.strptime(timestamp_str.strip(), "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        delta = now - timestamp
        hours = delta.total_seconds() / 3600
        return round(hours, 1)
    except:
        return 0


def get_status_display_name(status):
    """Chuyển status code thành tên hiển thị"""
    display_names = {
        'draft': 'Nháp',
        'cho_truong_ca': 'Chờ Trưởng ca',
        'cho_truong_bp': 'Chờ Trưởng BP',
        'cho_qc_manager': 'Chờ QC Manager',
        'cho_giam_doc': 'Chờ Giám đốc',
        'hoan_thanh': 'Hoàn thành'
    }
    return display_names.get(status, status)


def get_status_color(status):
    """Trả về màu cho status badge"""
    colors = {
        'draft': 'gray',
        'cho_truong_ca': 'blue',
        'cho_truong_bp': 'violet',
        'cho_qc_manager': 'orange',
        'cho_giam_doc': 'red',
        'hoan_thanh': 'green'
    }
    return colors.get(status, 'gray')
