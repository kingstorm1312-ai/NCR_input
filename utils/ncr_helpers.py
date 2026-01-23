import pandas as pd
from datetime import datetime
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
import io
import tempfile
import os

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




# Prefix Mapping for Reporting
DEPT_PREFIX_MAP = {
    # Prefix: (Bộ phận, Khâu)
    "FI": ("FI", "FI"),
    "NPLDV": ("ĐV Cuộn", "ĐV Cuộn"),
    "DVNPL": ("ĐV NPL", "ĐV NPL"),
    "X2-TR": ("Tráng Cắt", "Tráng"),
    "X2-CA": ("Tráng Cắt", "Cắt"),
    "MAY-I": ("May", "May I"),
    "MAY-P2": ("May", "May P2"),
    "MAY-N4": ("May", "May N4"),
    "MAY-A2": ("May", "May A2"),
    "TP-DAU-VAO": ("TP Đầu Vào", "TP Đầu Vào"),
    "TP_DAU_VAO": ("TP Đầu Vào", "TP Đầu Vào"), # Handle potential underscores
    "IN-D": ("In", "Xưởng D"),
    "IN_D": ("In", "Xưởng D"),
    "CAT-BAN": ("Cắt", "Cắt Bàn"),
    "CAT_BAN": ("Cắt", "Cắt Bàn"),
}

@st.cache_data(ttl=300)
def load_ncr_dataframe_v2(_gc):
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
        
        # 2. Extract Department & Section (Khâu) using Map
        if 'so_phieu' in df.columns:
            def extract_dept_info(so_phieu):
                # Standard ID: PREFIX-Month-Suffix (e.g., MAY-I-01-001 or X2-TR-01-001)
                # We need to find the longest matching prefix
                s = str(so_phieu).upper().strip()
                
                # Sort prefixes by length desc to match "MAY-I" before "MAY" if conflict
                sorted_prefixes = sorted(DEPT_PREFIX_MAP.keys(), key=len, reverse=True)
                
                for prefix in sorted_prefixes:
                    if s.startswith(prefix):
                        bp, khau = DEPT_PREFIX_MAP[prefix]
                        return pd.Series([bp, khau])
                
                # Fallback if no map match: Use first part as Dept and Suffix as Khau
                parts = s.split('-')
                val = parts[0]
                return pd.Series([val, val])

            df[['bo_phan', 'bo_phan_full']] = df['so_phieu'].apply(extract_dept_info)

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


# --- IMAGE UPLOAD TO GOOGLE DRIVE ---
def upload_images_to_drive(file_list, filename_prefix):
    """
    Upload multiple images to Google Drive and return direct links separated by newlines.
    
    Args:
        file_list: List of uploaded files from st.file_uploader
        filename_prefix: Prefix for filename (e.g., NCR ticket number)
    
    Returns:
        str: Newline-separated direct links to uploaded images
    """
    if not file_list:
        return ""
    
    try:
        # Get credentials from secrets
        # Get credentials from secrets and handle potential JSON string format
        creds_entry = st.secrets["connections"]["gsheets"]["service_account"]
        if isinstance(creds_entry, str):
            import json
            creds_dict = json.loads(creds_entry, strict=False)
        else:
            creds_dict = creds_entry
            
        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        
        # Build Drive service
        service = build('drive', 'v3', credentials=credentials)
        
        # Get target folder ID
        folder_id = st.secrets["drive"]["folder_id"]
        
        uploaded_links = []
        
        for idx, uploaded_file in enumerate(file_list):
            # Create unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = uploaded_file.name.split('.')[-1]
            unique_filename = f"{filename_prefix}_{timestamp}_{idx+1}.{file_extension}"
            
            # Prepare file metadata
            file_metadata = {
                'name': unique_filename,
                'parents': [folder_id]
            }
            
            # Write to temp file first to avoid BytesIO issues
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                # Upload file
                # resumable=False for small files (images) to avoid complex session checks
                media = MediaFileUpload(tmp_path, mimetype=uploaded_file.type, resumable=False)
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink',
                    supportsAllDrives=True  # Support Shared Drives (Team Drives)
                ).execute()
            finally:
                # Cleanup temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            # Make file publicly accessible
            service.permissions().create(
                fileId=file['id'],
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            
            # Get direct link (convert webViewLink to direct download link)
            file_id = file['id']
            direct_link = f"https://drive.google.com/uc?export=view&id={file_id}"
            uploaded_links.append(direct_link)
        
        # Return links separated by newlines
        return '\n'.join(uploaded_links)
        
    except Exception as e:
        st.error(f"Lỗi upload ảnh: {e}")
        import traceback
        st.code(traceback.format_exc())
        return ""
