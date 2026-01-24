import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import gspread
import cloudinary
import cloudinary.uploader
import io
import json

def get_now_vn():
    """Lấy thời gian hiện tại theo múi giờ Việt Nam (GMT+7)"""
    return datetime.utcnow() + timedelta(hours=7)

def get_now_vn_str():
    """Lấy chuỗi thời gian hiện tại VN định dạng chuẩn"""
    return get_now_vn().strftime("%Y-%m-%d %H:%M:%S")

@st.cache_resource
def init_gspread():
    """Khởi tạo gspread client từ secrets (Dùng chung toàn hệ thống)"""
    try:
        creds_str = st.secrets["connections"]["gsheets"]["service_account"]
        if isinstance(creds_str, str):
            creds_dict = json.loads(creds_str, strict=False)
        else:
            creds_dict = creds_str
        gc = gspread.service_account_from_dict(creds_dict)
        return gc
    except Exception as e:
        st.error(f"Lỗi khởi tạo gspread: {e}")
        return None

# --- CONFIGURATION ---
LIST_DON_VI_TINH = ["Cái", "Kg", "Mét", "Bịch", "Sợi", "Cuộn", "Bộ"]

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
    'nguon_goc': 'nguon_goc',
    'phan_loai': 'phan_loai',
    'hop_dong': 'hop_dong',
    'ma_vat_tu': 'ma_vat_tu',
    'ten_sp': 'ten_sp',
    'sl_kiem': 'so_luong_kiem',
    'md_loi': 'muc_do',
    'mo_ta_loi': 'mo_ta_loi',
    'sl_lo_hang': 'so_luong_lo_hang',
    'nguoi_lap_phieu': 'nguoi_lap_phieu',
    'noi_gay_loi': 'noi_gay_loi',
    'trang_thai': 'trang_thai',
    'thoi_gian_cap_nhat': 'thoi_gian_cap_nhat',
    'nguoi_duyet_1': 'duyet_truong_ca',
    'nguoi_duyet_2': 'duyet_truong_bp',
    'nguoi_duyet_3': 'duyet_qc_manager',
    'nguoi_duyet_4': 'duyet_giam_doc',
    'nguoi_duyet_5': 'duyet_bgd_tan_phu',
    'bien_phap_truong_bp': 'bien_phap_truong_bp',
    'huong_giai_quyet': 'y_kien_qc',
    'huong_xu_ly_gd': 'huong_xu_ly_giam_doc',
    'ly_do_tu_choi': 'ly_do_tu_choi',
    'hinh_anh': 'hinh_anh',
    'don_vi_tinh': 'don_vi_tinh',
    # Hành động khắc phục (Corrective Action)
    'kp_status': 'kp_status',
    'kp_assigned_by': 'kp_assigned_by',
    'kp_assigned_to': 'kp_assigned_to',
    'kp_message': 'kp_message',
    'kp_deadline': 'kp_deadline',
    'kp_response': 'kp_response',
    'so_lan': 'so_lan'
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
def _get_ncr_data_cached():
    try:
        gc = init_gspread()
        if not gc: return pd.DataFrame()
        
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("NCR_DATA")
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        # st.error(f"❌ Lỗi khi tải dữ liệu: {e}")
        return pd.DataFrame()


# --- DATA LOADING & GROUPING ---
def load_ncr_data_with_grouping(gc=None, filter_status=None, filter_department=None):
    try:
        df_original = _get_ncr_data_cached()
        
        if df_original.empty:
            st.warning("📊 Sheet NCR_DATA trống. Chưa có dữ liệu để hiển thị.")
            return pd.DataFrame(), pd.DataFrame()
        
        # Normalize column names
        df_original.columns = df_original.columns.str.strip()
        
        # Create reverse mapping
        reverse_mapping = {v: k for k, v in COLUMN_MAPPING.items()}
        df_original = df_original.rename(columns=reverse_mapping)
        
        # Apply filters
        df_filtered = df_original.copy()
        
        if filter_status:
            if 'trang_thai' in df_filtered.columns:
                if isinstance(filter_status, list):
                    df_filtered = df_filtered[df_filtered['trang_thai'].astype(str).str.strip().isin(filter_status)]
                else:
                    df_filtered = df_filtered[df_filtered['trang_thai'].astype(str).str.strip() == filter_status]
        
        if filter_department:
            if 'so_phieu' in df_filtered.columns:
                def extract_dept(so_phieu):
                    parts = str(so_phieu).split('-')
                    if len(parts) >= 2:
                        return '-'.join(parts[:2]).lower().replace('-', '_')
                    elif len(parts) == 1:
                        return parts[0].lower()
                    return ''
                
                df_filtered['bo_phan'] = df_filtered['so_phieu'].apply(extract_dept)
                
                # Normalize filter_department for comparison
                filter_dept_norm = str(filter_department).lower().strip()
                
                # Condition 1: Origin Department (Standard)
                condition_origin = df_filtered['bo_phan'] == filter_dept_norm
                
                # Condition 2: Cross-Department Assignment
                # Logic: Status starts with 'khac_phuc_' AND kp_message contains [BP: Department]
                condition_cross = pd.Series([False] * len(df_filtered), index=df_filtered.index)
                
                if 'kp_message' in df_filtered.columns and 'trang_thai' in df_filtered.columns:
                    tag = f"[bp: {filter_dept_norm}]"
                    
                    msgs = df_filtered['kp_message'].fillna('').astype(str).str.lower()
                    statuses = df_filtered['trang_thai'].fillna('').astype(str).str.lower()
                    
                    is_khac_phuc = statuses.str.startswith('khac_phuc_')
                    has_tag = msgs.str.contains(tag, regex=False)
                    
                    condition_cross = is_khac_phuc & has_tag
                
                # Combine Filters
                df_filtered = df_filtered[condition_origin | condition_cross]
        
        if df_filtered.empty:
            return df_original, pd.DataFrame()
        
        # Grouping
        group_cols = {
            'ngay_lap': 'first',
            'nguoi_lap_phieu': 'first',
            'trang_thai': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(sorted(set(x.astype(str))))
        }
        
        # Add optional columns if they exist
        optional_cols = [
            'hop_dong', 'ma_vat_tu', 'ten_sp', 'phan_loai', 'nguon_goc', 
            'sl_kiem', 'mo_ta_loi', 'sl_lo_hang', 'hinh_anh',
            'thoi_gian_cap_nhat', 'nguoi_duyet_1', 'nguoi_duyet_2', 
            'nguoi_duyet_3', 'nguoi_duyet_4', 'nguoi_duyet_5', 
            'bien_phap_truong_bp', 'huong_giai_quyet', 'huong_xu_ly_gd', 'ly_do_tu_choi',
            'kp_status', 'kp_assigned_by', 'kp_assigned_to', 'kp_message', 'kp_deadline', 'kp_response',
            'don_vi_tinh'
        ]
        
        for col in optional_cols:
            if col in df_filtered.columns:
                group_cols[col] = 'first'
        
        # Robust groupby
        if 'so_phieu' in df_filtered.columns:
            grouped = df_filtered.groupby('so_phieu', as_index=False).agg(group_cols)
            return df_original, grouped
        else:
             return df_original, pd.DataFrame()

    except Exception as e:
        st.error(f"Lỗi xử lý dữ liệu: {e}")
        return pd.DataFrame(), pd.DataFrame()


# Prefix Mapping
DEPT_PREFIX_MAP = {
    "FI": ("FI", "FI"),
    "NPLDV": ("ĐV Cuộn", "ĐV Cuộn"),
    "DVNPL": ("ĐV NPL", "ĐV NPL"),
    "X2-TR": ("Tráng Cắt", "Tráng"),
    "X2-CA": ("Tráng Cắt", "Cắt"),
    "I'": ("May", "May I"),
    "XA": ("May", "May P2"),
    "X4": ("May", "May N4"),
    "X3": ("May", "May A2"),
    "DVTP": ("TP Đầu Vào", "TP Đầu Vào"),
    "XG-IN": ("In Xưởng D", "In"),
    "XG-SA": ("In Xưởng D", "Siêu Âm"),
    "CAT-BAN": ("Cắt", "Cắt Bàn"),
    "XT": ("Xeo Tỷ", "Xeo Tỷ"), # Dự trù nếu có
    "CAT_BAN": ("Cắt", "Cắt Bàn"),
}

@st.cache_data(ttl=300)
def load_ncr_dataframe_v2():
    try:
        gc = init_gspread()
        if not gc: return pd.DataFrame()
        
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        
        if df.empty:
            return pd.DataFrame()
        
        df.columns = df.columns.str.strip()
        inv_map = {v: k for k, v in COLUMN_MAPPING.items()}
        df.rename(columns=inv_map, inplace=True)
        
        if 'ngay_lap' in df.columns:
            df['date_obj'] = pd.to_datetime(df['ngay_lap'], dayfirst=True, errors='coerce')
            df['year'] = df['date_obj'].dt.year
            df['month'] = df['date_obj'].dt.month
            df['week'] = df['date_obj'].dt.isocalendar().week
        
        # Ensure hop_dong column exists (it should already be mapped from COLUMN_MAPPING)
        if 'hop_dong' not in df.columns and 'so_hop_dong' in df.columns:
            df['hop_dong'] = df['so_hop_dong']
        
        if 'so_phieu' in df.columns:
            def extract_dept_info(so_phieu):
                s = str(so_phieu).upper().strip()
                sorted_prefixes = sorted(DEPT_PREFIX_MAP.keys(), key=len, reverse=True)
                for prefix in sorted_prefixes:
                    if s.startswith(prefix):
                        bp, khau = DEPT_PREFIX_MAP[prefix]
                        return pd.Series([bp, khau])
                parts = s.split('-')
                val = parts[0]
                return pd.Series([val, val])

            df[['bo_phan', 'bo_phan_full']] = df['so_phieu'].apply(extract_dept_info)

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
    if isinstance(status, list):
        return " / ".join([get_status_display_name(s) for s in status])
    status = str(status).strip()
    names = {
        'draft': 'Nháp (Cần xử lý)',
        'cho_truong_ca': 'Chờ Trưởng ca',
        'cho_truong_bp': 'Chờ Trưởng BP',
        'cho_qc_manager': 'Chờ QC Manager',
        'cho_giam_doc': 'Chờ Giám đốc',
        'cho_bgd_tan_phu': 'Chờ BGĐ Tân Phú',
        'hoan_thanh': 'Hoàn thành'
    }
    # Dynamic handling for corrective action confirm
    if status.startswith("xac_nhan_kp_"):
         role_suffix = status.replace("xac_nhan_kp_", "")
         return f"Xác nhận Khắc phục ({role_suffix.upper()})"
         
    if 'tu_choi' in status:
        return f"Bị từ chối ({status})"
    return names.get(status, status)


def get_status_color(status):
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
    if 'tu_choi' in status:
        return 'red'
    return colors.get(status, 'gray')


def format_contract_code(raw_input):
    if not raw_input:
        return ""
    s = str(raw_input).strip()
    import re
    match = re.search(r'^(\d+)[\W_]+(\d+)\s*([a-zA-Z]*)$', s)
    if match:
        p1, p2, suffix = match.groups()
        suffix_upper = suffix.upper() if suffix else ""
        return f"{p1}/{p2}{suffix_upper}"
    s = re.sub(r'[\s\.\-,]+', '/', s)
    return s.upper()


def render_input_buffer_mobile(buffer_list):
    if not buffer_list:
        return buffer_list

    st.markdown("##### 🛒 Danh sách lỗi đã thêm:")
    indices_to_remove = []
    
    for i, err in enumerate(buffer_list):
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{i+1}. {err['ten_loi']}**")
                muc_do = err.get('muc_do', '')
                dvt = err.get('don_vi_tinh', '')
                st.caption(f"SL: **{err['sl_loi']} {dvt}** | Vị trí: {err.get('vi_tri', '')} | Mức độ: {muc_do}")
            with c2:
                if st.button("🗑️", key=f"del_buf_{err['ten_loi']}_{i}", help="Xóa"):
                    indices_to_remove.append(i)

    if indices_to_remove:
        for index in sorted(indices_to_remove, reverse=True):
            buffer_list.pop(index)
        st.rerun()
    
    return buffer_list


def calculate_stuck_time(last_update_str):
    if not last_update_str:
        return 0
    try:
        last_update = pd.to_datetime(str(last_update_str), dayfirst=True)
        if pd.isna(last_update):
            return 0
        delta = get_now_vn() - last_update
        return delta.total_seconds() / 3600
    except:
        return 0

# --- CLOUDINARY UPLOAD ---
def upload_images_to_cloud(file_list, filename_prefix):
    """
    Upload images to Cloudinary.
    Requires [cloudinary] section in secrets.toml with cloud_name, api_key, api_secret.
    """
    if not file_list:
        return ""
    
    try:
        # Initialize Config
        cld = st.secrets["cloudinary"]
        cloudinary.config(
            cloud_name=cld["cloud_name"],
            api_key=cld["api_key"],
            api_secret=cld["api_secret"],
            secure=True
        )
        
        urls = []
        for idx, uploaded_file in enumerate(file_list):
            try:
                # Cloudinary uploader accepts file-like objects (BytesIO) directly
                # folder='ncr_images' keeps things organized
                # public_id ensure uniqueness
                timestamp = int(get_now_vn().timestamp())
                res = cloudinary.uploader.upload(
                    uploaded_file, 
                    folder="ncr_images",
                    public_id=f"{filename_prefix}_{timestamp}_{idx}",
                    resource_type="image"
                )
                urls.append(res.get("secure_url"))
            except Exception as e:
                st.error(f"Lỗi upload ảnh {uploaded_file.name}: {e}")
                
        return "\n".join(urls)
        
    except Exception as e:
        st.error(f"Lỗi cấu hình Cloudinary: {e}")
        return ""


def smart_append_ncr(ws, data_dict):
    """
    Appends a row to Google Sheets based on headers.
    Matches keys in data_dict with headers in row 1 of ws (case-insensitive).
    """
    try:
        # 1. Lấy headers từ row 1
        headers = ws.row_values(1)
        
        # 2. Chuẩn hóa data_dict (strip và lowercase keys)
        normalized_data = {str(k).strip().lower(): v for k, v in data_dict.items()}
        
        # 3. Xây dựng row list dựa trên header
        # Map dữ liệu theo tên cột (chuẩn hóa header để tìm trong normalized_data)
        row_to_append = []
        for h in headers:
            normalized_h = str(h).strip().lower()
            val = normalized_data.get(normalized_h, "")
            row_to_append.append(val)
        
        # 4. Append vào sheet
        if any(row_to_append): # Chỉ lưu nếu có ít nhất một giá trị (tránh dòng trống)
            ws.append_row(row_to_append)
            return True
        else:
            st.error("⚠️ Dữ liệu không khớp với bất kỳ cột nào trên Sheet. Vui lòng kiểm tra lại Header!")
            return False
            
    except Exception as e:
        st.error(f"Lỗi khi lưu dòng dữ liệu: {e}")
        return False


def update_ncr_status(gc, so_phieu, new_status, approver_name, approver_role, solution=None, reject_reason=None, bp_solution=None, director_solution=None, assignee=None):
    """
    Cập nhật trạng thái và thông tin phê duyệt cho tất cả các dòng của một số phiếu.
    
    Args:
        solution: Hướng giải quyết của QC Manager (y_kien_qc)
        bp_solution: Biện pháp xử lý tức thời của Trưởng BP (bien_phap_truong_bp)
        director_solution: Hướng xử lý của Giám đốc (huong_xu_ly_giam_doc)
        assignee: Tên người được chỉ định (nếu có), dùng cho việc Director cụ thể
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        data = ws.get_all_values()
        headers = [str(h).strip().lower() for h in data[0]]
        
        # Tìm chỉ mục các cột cần thiết (Case-insensitive)
        idx_so_phieu = headers.index("so_phieu_ncr")
        idx_status = headers.index("trang_thai")
        idx_update = headers.index("thoi_gian_cap_nhat")
        
        idx_reject = headers.index("ly_do_tu_choi") if "ly_do_tu_choi" in headers else -1
        idx_qc_solution = headers.index("y_kien_qc") if "y_kien_qc" in headers else -1
        idx_bp_solution = headers.index("bien_phap_truong_bp") if "bien_phap_truong_bp" in headers else -1
        idx_director_solution = headers.index("huong_xu_ly_giam_doc") if "huong_xu_ly_giam_doc" in headers else -1
        
        # Cột người duyệt dựa trên vai trò
        approver_col_name = COLUMN_MAPPING.get(ROLE_TO_APPROVER_COLUMN.get(approver_role), "")
        idx_approver = headers.index(approver_col_name.lower()) if approver_col_name.lower() in headers else -1
        
        now = get_now_vn_str()
        range_updates = []
        
        for i, row in enumerate(data[1:], start=2):
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                # Trạng thái & Thời gian
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_status + 1), 'values': [[new_status]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_update + 1), 'values': [[now]]})
                
                # Tên người duyệt
                if idx_approver != -1:
                    range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_approver + 1), 'values': [[approver_name]]})
                
                # Biện pháp của Trưởng BP
                if bp_solution and idx_bp_solution != -1:
                    range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_bp_solution + 1), 'values': [[bp_solution]]})
                
                # Hướng giải quyết của QC Manager
                if solution and idx_qc_solution != -1:
                    full_solution = solution
                    if assignee:
                        full_solution = f"{full_solution}\n[Chỉ định: {assignee}]"
                    range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_qc_solution + 1), 'values': [[full_solution]]})
                
                # Hướng xử lý của Giám đốc
                if director_solution and idx_director_solution != -1:
                    range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_director_solution + 1), 'values': [[director_solution]]})
                
                # Lý do từ chối (Nếu có)
                if reject_reason and idx_reject != -1:
                    full_reject = f"[{approver_name} ({approver_role.upper()})] {reject_reason}"
                    range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_reject + 1), 'values': [[full_reject]]})
        
        if range_updates:
            ws.batch_update(range_updates)
            return True, "Cập nhật trạng thái thành công"
        return False, "Không tìm thấy số phiếu NCR này"
        
    except Exception as e:
        return False, f"Lỗi hệ thống: {e}"


def restart_ncr(gc, so_phieu, target_status, user_name, note=""):
    """
    Khôi phục/Restart một phiếu NCR về trạng thái chỉ định.
    Dùng trong trang Giám sát.
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        data = ws.get_all_values()
        headers = [str(h).strip().lower() for h in data[0]]
        
        idx_so_phieu = headers.index("so_phieu_ncr")
        idx_status = headers.index("trang_thai")
        idx_update = headers.index("thoi_gian_cap_nhat")
        idx_reject = headers.index("ly_do_tu_choi") if "ly_do_tu_choi" in headers else -1
        
        now = get_now_vn_str()
        range_updates = []
        
        for i, row in enumerate(data[1:], start=2):
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_status + 1), 'values': [[target_status]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_update + 1), 'values': [[now]]})
                
                if idx_reject != -1:
                    msg = f"[RESTART BY {user_name}] {note}"
                    range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_reject + 1), 'values': [[msg]]})
        
        if range_updates:
            ws.batch_update(range_updates)
            return True, f"Đã khôi phục phiếu {so_phieu} về {target_status}"
        return False, "Không tìm thấy phiếu"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"
def assign_corrective_action(gc, so_phieu, assigned_by_role, assign_to_role, message, deadline, target_department=None, target_person=None):
    """
    Giao hành động khắc phục cho cấp dưới.
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        data = ws.get_all_values()
        headers = [str(h).strip().lower() for h in data[0]]
        
        idx_so_phieu = headers.index("so_phieu_ncr")
        idx_status = headers.index("trang_thai")
        idx_update = headers.index("thoi_gian_cap_nhat")
        
        idx_kp_status = headers.index("kp_status")
        idx_kp_by = headers.index("kp_assigned_by")
        idx_kp_to = headers.index("kp_assigned_to")
        idx_kp_msg = headers.index("kp_message")
        idx_kp_dl = headers.index("kp_deadline")
        idx_kp_res = headers.index("kp_response")
        
        # Xác định trạng thái mới
        new_status = f"khac_phuc_{assign_to_role}"
        now = get_now_vn_str()
        range_updates = []
        
        for i, row in enumerate(data[1:], start=2):
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_status + 1), 'values': [[new_status]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_update + 1), 'values': [[now]]})
                
                final_message = message
                prefix_info = []
                if target_department:
                    prefix_info.append(f"BP: {target_department}")
                if target_person:
                     prefix_info.append(f"Chỉ định: {target_person}")
                
                if prefix_info:
                    final_message = f"[{' | '.join(prefix_info)}] {final_message}"

                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_status + 1), 'values': [['active']]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_by + 1), 'values': [[assigned_by_role]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_to + 1), 'values': [[assign_to_role]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_msg + 1), 'values': [[final_message]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_dl + 1), 'values': [[str(deadline)]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_res + 1), 'values': [['']]}) # Reset response
        
        if range_updates:
            ws.batch_update(range_updates)
            return True, f"Đã giao hành động khắc phục cho {assign_to_role.upper()}"
        return False, "Không tìm thấy số phiếu"
    except Exception as e:
        return False, f"Lỗi hệ thống: {e}"

def complete_corrective_action(gc, so_phieu, response):
    """
    Người nhận hoàn thành hành động khắc phục và gửi lại cho người giao.
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        data = ws.get_all_values()
        headers = [str(h).strip().lower() for h in data[0]]
        
        idx_so_phieu = headers.index("so_phieu_ncr")
        idx_status = headers.index("trang_thai")
        idx_update = headers.index("thoi_gian_cap_nhat")
        idx_kp_status = headers.index("kp_status")
        idx_kp_by = headers.index("kp_assigned_by")
        idx_kp_res = headers.index("kp_response")
        
        now = get_now_vn_str()
        range_updates = []
        
        # Lấy thông tin người giao từ dòng đầu tiên tìm thấy
        assigned_by = ""
        for row in data[1:]:
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                assigned_by = str(row[idx_kp_by]).strip()
                break
        
        if not assigned_by:
            return False, "Không xác định được người giao task"
            
        # Trạng thái chờ xác nhận
        new_status = f"xac_nhan_kp_{assigned_by}"
        
        for i, row in enumerate(data[1:], start=2):
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_status + 1), 'values': [[new_status]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_update + 1), 'values': [[now]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_status + 1), 'values': [['completed']]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_res + 1), 'values': [[response]]})
        
        if range_updates:
            ws.batch_update(range_updates)
            return True, f"Đã gửi phản hồi khắc phục cho {assigned_by.upper()}"
        return False, "Không tìm thấy số phiếu"
    except Exception as e:
        return False, f"Lỗi hệ thống: {e}"

def accept_corrective_action(gc, so_phieu, approver_role):
    """
    Người giao chấp nhận hành động khắc phục, phiếu quay lại trạng thái chờ duyệt của họ.
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        data = ws.get_all_values()
        headers = [str(h).strip().lower() for h in data[0]]
        
        idx_so_phieu = headers.index("so_phieu_ncr")
        idx_status = headers.index("trang_thai")
        idx_update = headers.index("thoi_gian_cap_nhat")
        idx_kp_status = headers.index("kp_status")
        
        # Quay lại trạng thái chờ duyệt của chính role đó
        new_status = ROLE_TO_STATUS.get(approver_role)
        now = get_now_vn_str()
        range_updates = []
        
        for i, row in enumerate(data[1:], start=2):
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_status + 1), 'values': [[new_status]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_update + 1), 'values': [[now]]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_kp_status + 1), 'values': [['accepted']]})
        
        if range_updates:
            ws.batch_update(range_updates)
            return True, "Đã chấp nhận hành động khắc phục. Phiếu đã quay lại danh sách chờ duyệt."
        return False, "Không tìm thấy số phiếu"
    except Exception as e:
        return False, f"Lỗi hệ thống: {e}"

def load_pending_corrective_actions(gc, role_name):
    """
    Loads tickets that are in 'khac_phuc_truong_bp' status AND were assigned by the current role.
    """
    try:
        if not gc: return pd.DataFrame()
        
        # Load all data (cached)
        df = load_ncr_dataframe_v2()
        if df.empty: return pd.DataFrame()
        
        # Check if necessary columns exist
        required_cols = ['trang_thai', 'kp_assigned_by', 'so_phieu', 'kp_deadline', 'kp_assigned_to']
        for col in required_cols:
            if col not in df.columns:
                return pd.DataFrame() # Missing columns
        
        # Normalizing
        df['status_norm'] = df['trang_thai'].astype(str).str.strip().str.lower()
        df['by_norm'] = df['kp_assigned_by'].astype(str).str.strip().str.lower()
        
        # Filter Logic
        if role_name == 'all':
            mask_owner = pd.Series([True] * len(df)) # Select All
        else:
            role_norm = role_name.lower()
            mask_owner = df['by_norm'] == role_norm
        
        mask_status = df['status_norm'] == 'khac_phuc_truong_bp'
        
        df_pending = df[mask_status & mask_owner].copy()
        
        if df_pending.empty:
            return pd.DataFrame()
            
        # Group by Ticket
        group_cols = {
            'ngay_lap': 'first',
            'kp_assigned_to': 'first',
            'kp_deadline': 'first',
            'kp_message': 'first',
            'kp_assigned_by': 'first',
            'bo_phan': 'first',
            'sl_loi': 'sum'
        }
        # Add dynamic cols if exist
        for c in ['hop_dong', 'ten_sp']:
            if c in df_pending.columns:
                group_cols[c] = 'first'
                
        df_grouped = df_pending.groupby('so_phieu', as_index=False).agg(group_cols)
        
        return df_grouped
        
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_all_users():
    """Lấy danh sách toàn bộ nhân viên từ sheet USERS"""
    try:
        gc = init_gspread()
        if not gc: return []
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("USERS")
        data = ws.get_all_records()
        return data
    except Exception as e:
        return []

def cancel_ncr(gc, so_phieu, reason):
    """
    Hủy phiếu NCR: Chuyển trạng thái sang 'da_huy'
    """
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        data = ws.get_all_values()
        headers = [str(h).strip().lower() for h in data[0]]
        
        idx_so_phieu = headers.index("so_phieu_ncr")
        idx_status = headers.index("trang_thai")
        idx_update = headers.index("thoi_gian_cap_nhat")
        idx_note = headers.index("ly_do_tu_choi") # Use this col for cancel reason
        
        now = get_now_vn_str()
        range_updates = []
        
        for i, row in enumerate(data[1:], start=2):
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_status + 1), 'values': [['da_huy']]})
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_update + 1), 'values': [[now]]})
                current_note = row[idx_note]
                new_note = f"{current_note} | [Lý do hủy: {reason}]" if current_note else f"[Lý do hủy: {reason}]"
                range_updates.append({'range': gspread.utils.rowcol_to_a1(i, idx_note + 1), 'values': [[new_note]]})
        
        if range_updates:
            ws.batch_update(range_updates)
            return True, f"Đã hủy phiếu {so_phieu}"
        return False, "Không tìm thấy số phiếu"
    except Exception as e:
        return False, f"Lỗi hệ thống: {e}"
