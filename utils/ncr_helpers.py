import pandas as pd
from datetime import datetime
import streamlit as st

# --- STATUS FLOW CONFIGURATION ---
STATUS_FLOW = {
    'draft': 'cho_truong_ca',
    'cho_truong_ca': 'cho_truong_bp',
    'cho_truong_bp': 'cho_qc_manager',
    'cho_qc_manager': 'cho_giam_doc',
    'cho_giam_doc': 'cho_bgd_tan_phu',      # Director -> BGD Tan Phu
    'cho_bgd_tan_phu': 'hoan_thanh',        # Root -> Finish
    'hoan_thanh': 'hoan_thanh'
}

# Rejection escalation mapping
# When reject, escalate to who?
# When reject, escalate to who?
# ALL REJECTIONS now revert to 'draft' so user can see and fix in "NCR Của Tôi"
REJECT_ESCALATION = {
    'cho_truong_ca': 'draft',
    'cho_truong_bp': 'draft',
    'cho_qc_manager': 'draft',
    'cho_giam_doc': 'draft',
    'cho_bgd_tan_phu': 'draft'
}


# --- COLUMN MAPPING (Code → Sheet) ---
# Map tên cột chuẩn trong code sang tên cột thực tế trong Google Sheet
COLUMN_MAPPING = {
    'so_phieu': 'so_phieu_ncr',
    'sl_loi': 'so_luong_loi',
    'nguon_goc': 'nguon_goc',  # Replaces 'noi_may'
    'phan_loai': 'phan_loai',  # New column
    'nguoi_duyet_1': 'duyet_truong_ca',
    'nguoi_duyet_2': 'duyet_truong_bp',
    'nguoi_duyet_3': 'duyet_qc_manager',
    'nguoi_duyet_4': 'duyet_giam_doc',
    'nguoi_duyet_5': 'duyet_bgd_tan_phu',  # Level 5
    'huong_giai_quyet': 'y_kien_qc'
}

ROLE_TO_APPROVER_COLUMN = {
    'truong_ca': 'nguoi_duyet_1',
    'truong_bp': 'nguoi_duyet_2',
    'qc_manager': 'nguoi_duyet_3',
    'director': 'nguoi_duyet_4',
    'bgd_tan_phu': 'nguoi_duyet_5'
}

ROLE_TO_STATUS = {
    'truong_ca': 'cho_truong_ca',
    'truong_bp': 'cho_truong_bp',
    'qc_manager': 'cho_qc_manager',
    'director': 'cho_giam_doc',
    'bgd_tan_phu': 'cho_bgd_tan_phu'
}

# --- CACHED DATA FETCH ---
@st.cache_data(ttl=30, show_spinner=False)
def _get_ncr_data_cached(_gc):
    """
    Cached function to fetch NCR data from Google Sheets.
    Cache for 30 seconds to avoid rate limit (60 requests/minute).
    
    Args:
        _gc: gspread client (with _ prefix to prevent hashing)
    
    Returns:
        DataFrame with raw NCR data
    """
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = _gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("NCR_DATA")
        
        # Load all records
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        
        return df
    except Exception as e:
        st.error(f"❌ Lỗi khi tải dữ liệu: {e}")
        return pd.DataFrame()


# --- DATA LOADING & GROUPING ---
def load_ncr_data_with_grouping(gc, filter_status=None, filter_department=None):
    """
    Load NCR_DATA từ Google Sheets và group theo ticket.
    
    Args:
        gc: gspread Client
        filter_status: str (optional) - Lọc theo trạng thái
        filter_department: str (optional) - Lọc theo bộ phận
    
    Returns:
        df_original: DataFrame gốc (dùng để update)
        df_grouped: DataFrame đã group theo so_phieu (dùng để hiển thị UI)
    """
    try:
        # Use cached data fetch
        df_original = _get_ncr_data_cached(gc)
        
        if df_original.empty:
            st.warning("📊 Sheet NCR_DATA trống. Chưa có dữ liệu để hiển thị.")
            return pd.DataFrame(), pd.DataFrame()
        
        # Normalize column names (strip spaces)
        df_original.columns = df_original.columns.str.strip()
        
        # Create reverse mapping (Sheet → Code) for renaming
        reverse_mapping = {v: k for k, v in COLUMN_MAPPING.items()}
        
        # Apply column mapping (rename columns từ sheet sang tên chuẩn code)
        df_original = df_original.rename(columns=reverse_mapping)
        
        # Debug: Show available columns if key column missing
        required_cols = ['so_phieu', 'trang_thai', 'ngay_lap', 'nguoi_lap_phieu', 'sl_loi', 'ten_loi']
        missing_cols = [col for col in required_cols if col not in df_original.columns]
        
        if missing_cols:
            st.error(f"❌ Thiếu các cột bắt buộc trong NCR_DATA: {', '.join(missing_cols)}")
            st.info(f"📋 Các cột hiện có: {', '.join(df_original.columns.tolist())}")
            return pd.DataFrame(), pd.DataFrame()
        
        # Apply filters
        df_filtered = df_original.copy()
        
        if filter_status:
            if 'trang_thai' in df_filtered.columns:
                df_filtered = df_filtered[df_filtered['trang_thai'].astype(str).str.strip() == filter_status]
            else:
                st.warning("⚠️ Không tìm thấy cột 'trang_thai' để filter")
        
        if filter_department:
            # Extract department from so_phieu (e.g., 'MAY-I-01-001' -> 'may_i')
            if 'so_phieu' in df_filtered.columns:
                # Split by '-', take first 2 parts (MAY-I), join with '-', then replace '-' with '_'
                # Example: "MAY-I-01-01" → ["MAY", "I", "01", "01"] → "MAY-I" → "may-i" → "may_i"
                def extract_dept(so_phieu):
                    parts = str(so_phieu).split('-')
                    if len(parts) >= 2:
                        # Take first 2 parts for department (e.g., MAY-I)
                        dept = '-'.join(parts[:2]).lower().replace('-', '_')
                        return dept
                    elif len(parts) == 1:
                        # Single part department (e.g., FI)
                        return parts[0].lower()
                    return ''
                
                df_filtered['bo_phan'] = df_filtered['so_phieu'].apply(extract_dept)
                df_filtered = df_filtered[df_filtered['bo_phan'] == filter_department]
        
        if df_filtered.empty:
            return df_original, pd.DataFrame()
        
        # Check if we have necessary columns for grouping
        group_cols = {
            'ngay_lap': 'first',
            'nguoi_lap_phieu': 'first',
            'trang_thai': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(sorted(set(x.astype(str))))
        }
        
        # Add optional columns if they exist
        optional_cols = ['thoi_gian_cap_nhat', 'nguoi_duyet_1', 'nguoi_duyet_2', 
                        'nguoi_duyet_3', 'nguoi_duyet_4', 'nguoi_duyet_5', 'huong_giai_quyet', 'ly_do_tu_choi']
        
        for col in optional_cols:
            if col in df_filtered.columns:
                group_cols[col] = 'first'
        
        # Group by so_phieu
        grouped = df_filtered.groupby('so_phieu', as_index=False).agg(group_cols)
        
        return df_original, grouped

    except Exception as e:
        st.error(f"Lỗi xử lý dữ liệu: {e}")
        return pd.DataFrame(), pd.DataFrame()



@st.cache_data(ttl=300)
def load_ncr_dataframe(_gc):
    """
    Load raw NCR dataframe with preprocessing for Reporting/Dashboard.
    Includes: Column renaming, Date parsing, Department extraction, Stuck time.
    """
    try:
        sh = _gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        
        if df.empty:
            return pd.DataFrame()
        
        # Normalize column names
        df.columns = df.columns.str.strip()
        
        # Map to Code Names
        inv_map = {v: k for k, v in COLUMN_MAPPING.items()}
        df.rename(columns=inv_map, inplace=True)
        
        # 1. Parse Date (Robust)
        if 'ngay_lap' in df.columns:
            df['date_obj'] = pd.to_datetime(df['ngay_lap'], dayfirst=True, errors='coerce')
            df['year'] = df['date_obj'].dt.year
            df['month'] = df['date_obj'].dt.month
            df['week'] = df['date_obj'].dt.isocalendar().week
        
        # 2. Extract Department
        if 'so_phieu' in df.columns:
            # e.g. MAY-I-..., FI-..., DV_CUON-...
            # Split by '-' or '_' and take first part? 
            # Logic: "MAY-I" -> "may_i", "FI" -> "fi"
            def extract_dept(x):
                s = str(x).upper()
                parts = s.split('-')
                if len(parts) >= 2:
                    return f"{parts[0]}_{parts[1]}".lower() # may_i
                return parts[0].lower() # fi
            
            # Simple extraction for now: Just Group Prefix?
            # User wants "Khâu" -> "May I", "May P2".
            # Prefix is usually Dept Code.
            df['bo_phan'] = df['so_phieu'].astype(str).str.split('-').str[0].str.lower()
            
            # More granular extraction if needed (e.g., MAY-I vs MAY-P2)
            # Let's create a full_dept column
            def extract_full_dept(x):
                parts = str(x).split('-')
                if len(parts) >= 2:
                    val = f"{parts[0]}_{parts[1]}".lower()
                    # Check if it matches known patterns or just return
                    return val
                return parts[0].lower()
            
            df['bo_phan_full'] = df['so_phieu'].apply(extract_full_dept)

        # 3. Calculate Stuck Time
        if 'thoi_gian_cap_nhat' in df.columns:
            df['hours_stuck'] = df['thoi_gian_cap_nhat'].apply(calculate_stuck_time)
        else:
            df['hours_stuck'] = 0
            
        return df
        
    except Exception as e:
        st.error(f"Lỗi load data chung: {e}")
        return pd.DataFrame()


# --- HELPER FUNCTIONS ---
def get_status_display_name(status):
    """Trả về tên hiển thị tiếng Việt của trạng thái"""
    status = str(status).strip()
    names = {
        'draft': 'Nháp (Cần xử lý)',
        'cho_truong_ca': 'Chờ Trưởng ca',
        'cho_truong_bp': 'Chờ Trưởng BP',
        'cho_qc_manager': 'Chờ QC Manager',
        'cho_giam_doc': 'Chờ Giám đốc',
        'cho_bgd_tan_phu': 'Chờ BGĐ Tân Phú',
        'hoan_thanh': 'Hoàn thành',
        # Các trạng thái từ chối cũ (để tương thích ngược nếu còn data cũ)
        'bi_tu_choi_truong_ca': 'Bị Trưởng ca từ chối',
        'bi_tu_choi_truong_bp': 'Bị Trưởng BP từ chối',
        'bi_tu_choi_qc_manager': 'Bị QC Manager từ chối',
        'bi_tu_choi_giam_doc': 'Bị Giám đốc từ chối',
        'bi_tu_choi_bgd_tan_phu': 'Bị BGĐ Tân Phú từ chối'
    }
    return names.get(status, status)


def get_status_color(status):
    """
    Trả về màu sắc hiển thị cho status (dùng cho Streamlit :color[text])
    Colors: blue, green, orange, red, violet, gray/grey, rainbow.
    """
    status = str(status).strip()
    colors = {
        'draft': 'gray',
        'cho_truong_ca': 'blue',
        'cho_truong_bp': 'orange',
        'cho_qc_manager': 'violet',
        'cho_giam_doc': 'red',
        'cho_bgd_tan_phu': 'red',
        'hoan_thanh': 'green'
    }
    # Mặc định red cho các trạng thái có chữ 'tu_choi'
    if 'tu_choi' in status:
        return 'red'
    return colors.get(status, 'gray')


def format_contract_code(raw_input):
    """
    Format mã hợp đồng thông minh:
    1. Tự động thay thế các ký tự lạ (khoảng trắng, chấm, phẩy...) thành '/' giữa các số.
    2. Tự động viết hoa các ký tự chữ cái ở cuối.
    VD: '23.25adi' -> '23/25ADI', '23 25 adi' -> '23/25ADI'
    """
    if not raw_input:
        return ""
    
    s = str(raw_input).strip()
    
    # Pattern: Digits + Separator + Digits + Suffix
    import re
    # Match: (Digits) (Separators) (Digits) (Optional spaces) (Suffix Letters)
    match = re.search(r'^(\d+)[\W_]+(\d+)\s*([a-zA-Z]*)$', s)
    
    if match:
        p1, p2, suffix = match.groups()
        suffix_upper = suffix.upper() if suffix else ""
        return f"{p1}/{p2}{suffix_upper}"
    
    # Fallback: Just uppercase everything if it doesn't match the strict pattern
    # But try to replace generic separators first
    s = re.sub(r'[\s\.\-,]+', '/', s)
    return s.upper()


def render_input_buffer_mobile(buffer_list):
    """
    Hiển thị danh sách lỗi trong buffer với giao diện mobile-friendly.
    Cho phép xóa từng lỗi.
    Trả về list mới sau khi xóa (hoặc None nếu không có thay đổi).
    """
    if not buffer_list:
        return buffer_list

    st.markdown("##### 🛒 Danh sách lỗi đã thêm:")
    
    indices_to_remove = []
    
    for i, err in enumerate(buffer_list):
        # Use a container for card-like look
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{i+1}. {err['ten_loi']}**")
                # Show muc_do
                muc_do = err.get('muc_do', '')
                st.caption(f"SL: **{err['sl_loi']}** | Vị trí: {err.get('vi_tri', '')} | Mức độ: {muc_do}")
            with c2:
                # Big delete button for touch target
                if st.button("🗑️", key=f"del_buf_{i}", help="Xóa dòng này"):
                    indices_to_remove.append(i)

    if indices_to_remove:
        # Remove in reverse order to avoid index shifting issues
        for index in sorted(indices_to_remove, reverse=True):
            buffer_list.pop(index)
        st.rerun()
    
    return buffer_list


def update_ncr_status(gc, so_phieu, new_status, approver_name, approver_role, solution=None, reject_reason=None):
    """
    Cập nhật status của NCR trong Google Sheet.
    - Nếu là Rejection -> new_status luôn là 'draft' (theo logic mới ở REJECT_ESCALATION)
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        
        all_data = ws.get_all_values()
        headers = all_data[0]
        
        # Map column names
        col_so_phieu = headers.index(COLUMN_MAPPING.get('so_phieu', 'so_phieu_ncr'))
        col_trang_thai = headers.index(COLUMN_MAPPING.get('trang_thai', 'trang_thai'))
        col_thoi_gian = headers.index(COLUMN_MAPPING.get('thoi_gian_cap_nhat', 'thoi_gian_cap_nhat'))
        
        # Determine approver column for Normal Approval
        # Khi từ chối, ta vẫn có thể ghi tên vào cột người duyệt (như là người đã reject)
        # hoặc bỏ qua. Ở đây ta vẫn ghi để lưu vết.
        approver_col_key = ROLE_TO_APPROVER_COLUMN.get(approver_role)
        target_col_idx = None
        
        if approver_col_key:
            sheet_col_name = COLUMN_MAPPING.get(approver_col_key)
            if sheet_col_name in headers:
                target_col_idx = headers.index(sheet_col_name)
        
        col_solution = None
        if solution is not None:
             sol_col_name = COLUMN_MAPPING.get('huong_giai_quyet', 'y_kien_qc')
             if sol_col_name in headers:
                 col_solution = headers.index(sol_col_name)
                 
        col_reject_reason = None
        if reject_reason:
            if 'ly_do_tu_choi' in headers:
                col_reject_reason = headers.index('ly_do_tu_choi')
        
        # Find rows to update
        rows_to_update = []
        for idx, row in enumerate(all_data[1:], start=2):
            if row[col_so_phieu] == so_phieu:
                rows_to_update.append(idx)
        
        if not rows_to_update:
            return False, f"Không tìm thấy phiếu {so_phieu}"
        
        # Prepare batch update
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updates = []
        
        for row_idx in rows_to_update:
            # 1. Update Status
            updates.append({
                'range': f'{chr(65 + col_trang_thai)}{row_idx}',
                'values': [[new_status]]
            })
            
            # 2. Update Timestamp
            updates.append({
                'range': f'{chr(65 + col_thoi_gian)}{row_idx}',
                'values': [[current_time]]
            })
            
            # 3. Update Approver Name
            if target_col_idx is not None:
                updates.append({
                    'range': f'{chr(65 + target_col_idx)}{row_idx}',
                    'values': [[approver_name]]
                })
            
            # 4. Update Solution
            if col_solution is not None and solution is not None:
                updates.append({
                    'range': f'{chr(65 + col_solution)}{row_idx}',
                    'values': [[solution]]
                })
                
            # 5. Update Reject Reason (Improved Format)
            if col_reject_reason is not None and reject_reason:
                # Format: [Tên người duyệt (Role)] Lý do
                # E.g.: [Nguyen Van A (QC Manager)] Sai quy cách
                formatted_reason = f"[{approver_name} ({approver_role.upper()})] {reject_reason}"
                updates.append({
                    'range': f'{chr(65 + col_reject_reason)}{row_idx}',
                    'values': [[formatted_reason]]
                })

        ws.batch_update(updates)
        return True, "Cập nhật thành công!"
        
    except Exception as e:
        return False, f"Lỗi cập nhật: {str(e)}"

def calculate_stuck_time(last_update_str):
    """Tính toán thời gian bị kẹt (giờ)"""
    if not last_update_str:
        return 0
    try:
        # Use pandas for robust parsing (handles ISO and dd/mm/yyyy)
        # dayfirst=True ensures 01/02/2026 is parsed as Feb 1st (VN style)
        last_update = pd.to_datetime(str(last_update_str), dayfirst=True)
        if pd.isna(last_update):
            return 0
            
        delta = datetime.now() - last_update
        return delta.total_seconds() / 3600
    except:
        return 0

def restart_ncr(gc, so_phieu, target_status, restart_by, restart_note=''):
    """
    QC Manager/Director/Root restart rejected NCR back to a specific level
    
    Args:
        gc: gspread client
        so_phieu: NCR ticket ID
        target_status: Target status to restart to (e.g., 'cho_truong_bp')
        restart_by: Name of person restarting
        restart_note: Optional note explaining restart
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        
        all_data = ws.get_all_values()
        headers = all_data[0]
        
        # Map column names
        col_so_phieu = headers.index(COLUMN_MAPPING.get('so_phieu', 'so_phieu_ncr'))
        col_trang_thai = headers.index(COLUMN_MAPPING.get('trang_thai', 'trang_thai'))
        col_thoi_gian = headers.index(COLUMN_MAPPING.get('thoi_gian_cap_nhat', 'thoi_gian_cap_nhat'))
        col_ly_do = headers.index('ly_do_tu_choi')  # For restart note
        
        # Find rows
        rows_to_update = []
        for idx, row in enumerate(all_data[1:], start=2):
            if row[col_so_phieu] == so_phieu:
                rows_to_update.append(idx)
        
        if not rows_to_update:
            return False, f"Không tìm thấy phiếu {so_phieu}"
        
        # Update
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updates = []
        
        for row_idx in rows_to_update:
            # Update status
            updates.append({
                'range': f'{chr(65 + col_trang_thai)}{row_idx}',
                'values': [[target_status]]
            })
            # Update timestamp
            updates.append({
                'range': f'{chr(65 + col_thoi_gian)}{row_idx}',
                'values': [[current_time]]
            })
            # Update ly_do_tu_choi with restart note
            if restart_note:
                note_text = f"[{restart_by}] {restart_note}"
                updates.append({
                    'range': f'{chr(65 + col_ly_do)}{row_idx}',
                    'values': [[note_text]]
                })
        
        ws.batch_update(updates)
        return True, f"Đã restart phiếu {so_phieu} về {target_status}"
        
    except Exception as e:
        return False, f"Lỗi: {str(e)}"
