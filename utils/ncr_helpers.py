import pandas as pd
from datetime import datetime
import streamlit as st
import cloudinary
import cloudinary.uploader
import io

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
    'sl_loi': 'sl_loi',
    'nguon_goc': 'nguon_goc',
    'phan_loai': 'phan_loai',
    'nguoi_duyet_1': 'duyet_truong_ca',
    'nguoi_duyet_2': 'duyet_truong_bp',
    'nguoi_duyet_3': 'duyet_qc_manager',
    'nguoi_duyet_4': 'duyet_giam_doc',
    'nguoi_duyet_5': 'duyet_bgd_tan_phu',
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
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = _gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("NCR_DATA")
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        st.error(f"❌ Lỗi khi tải dữ liệu: {e}")
        return pd.DataFrame()


# --- DATA LOADING & GROUPING ---
def load_ncr_data_with_grouping(gc, filter_status=None, filter_department=None):
    try:
        df_original = _get_ncr_data_cached(gc)
        
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
                df_filtered = df_filtered[df_filtered['bo_phan'] == filter_department]
        
        if df_filtered.empty:
            return df_original, pd.DataFrame()
        
        # Grouping
        group_cols = {
            'ngay_lap': 'first',
            'nguoi_lap_phieu': 'first', # Updated map key check needed if column name changed
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
    "MAY-I": ("May", "May I"),
    "MAY-P2": ("May", "May P2"),
    "MAY-N4": ("May", "May N4"),
    "MAY-A2": ("May", "May A2"),
    "TP-DAU-VAO": ("TP Đầu Vào", "TP Đầu Vào"),
    "TP_DAU_VAO": ("TP Đầu Vào", "TP Đầu Vào"),
    "IN-D": ("In", "Xưởng D"),
    "IN_D": ("In", "Xưởng D"),
    "CAT-BAN": ("Cắt", "Cắt Bàn"),
    "CAT_BAN": ("Cắt", "Cắt Bàn"),
}

@st.cache_data(ttl=300)
def load_ncr_dataframe_v2(_gc):
    try:
        sh = _gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
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
                st.caption(f"SL: **{err['sl_loi']}** | Vị trí: {err.get('vi_tri', '')} | Mức độ: {muc_do}")
            with c2:
                if st.button("🗑️", key=f"del_buf_{int(datetime.now().timestamp())}_{i}", help="Xóa"):
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
        delta = datetime.now() - last_update
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
                timestamp = int(datetime.now().timestamp())
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
    Matches keys in data_dict with headers in row 1 of ws.
    """
    try:
        # 1. Lấy headers từ row 1 (cache hoặc đọc trực tiếp)
        # Để đảm bảo chính xác nhất, ta đọc trực tiếp row 1
        headers = ws.row_values(1)
        
        # 2. Xây dựng row list dựa trên header
        # Map dữ liệu theo tên cột, nếu không có thì để trống
        row_to_append = [data_dict.get(h, "") for h in headers]
        
        # 3. Append vào sheet
        ws.append_row(row_to_append)
        return True
    except Exception as e:
        st.error(f"Lỗi khi lưu dòng dữ liệu: {e}")
        return False
