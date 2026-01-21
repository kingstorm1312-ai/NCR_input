"""
QC Data Entry App - Mobile-First Design with Smart Severity
============================================================
App này cho phép QC nhập liệu từ điện thoại, với:
- Buffer Logic: Lưu tạm vào session_state trước khi save
- Aggregation Logic: Cộng dồn số lượng nếu trùng (Error_Name + Location)
- Flexible Input: Cho phép nhập lỗi mới không có trong Master Data
- Smart Severity: Tự động lookup mức độ nghiêm trọng từ Master Data
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import json

# ============================================================================
# MOCK MASTER DATA (sẽ thay bằng Google Sheets sau)
# ============================================================================
MOCK_MASTER_DATA = {
    'factories': ['Nhà máy A', 'Nhà máy B', 'Nhà máy C', 'Xưởng Nội Bộ'],
    'locations': [
        'Cổ',
        'Vai',
        'Tay Áo',
        'Thân Trước',
        'Thân Sau',
        'Viền',
        'Gấu'
    ],
    'products': {
        'SP001': 'Áo Polo Nam',
        'SP002': 'Áo Thun Nữ',
        'SP003': 'Quần Jean Nam',
        'SP004': 'Váy Công Sở',
        'SP005': 'Áo Khoác Ngoài'
    },
    # NEW: Error Names with corresponding Severity
    'errors': {
        'Nút Vỡ/Gãy': 'Critical',
        'Chỉ Thừa': 'Minor',
        'Bong Tróc Sơn': 'Major',
        'Vết Dơ': 'Minor',
        'Kích Thước Sai': 'Critical',
        'Màu Sắc Lệch': 'Major',
        'Đường May Lệch': 'Major',
        'Lỗ Kim': 'Minor'
    },
    'severity_levels': ['Critical', 'Major', 'Minor']
}

# Severity Icons/Colors
SEVERITY_CONFIG = {
    'Critical': {'icon': '🔴', 'color': '#FF4B4B'},
    'Major': {'icon': '🟠', 'color': '#FFA500'},
    'Minor': {'icon': '🟡', 'color': '#FFD700'}
}

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
def init_session_state():
    """Khởi tạo session state để lưu trữ dữ liệu tạm"""
    if 'error_buffer' not in st.session_state:
        st.session_state.error_buffer = []
    
    if 'header_locked' not in st.session_state:
        st.session_state.header_locked = False
    
    # Header data
    if 'ncr_id' not in st.session_state:
        st.session_state.ncr_id = ''
    if 'contract_id' not in st.session_state:
        st.session_state.contract_id = ''
    if 'product_code' not in st.session_state:
        st.session_state.product_code = None
    if 'factory' not in st.session_state:
        st.session_state.factory = None
    if 'checked_qty' not in st.session_state:
        st.session_state.checked_qty = 0
    if 'batch_qty' not in st.session_state:
        st.session_state.batch_qty = 0
    if 'user_name' not in st.session_state:
        st.session_state.user_name = 'QC User'

# ============================================================================
# SMART SEVERITY LOOKUP
# ============================================================================
def get_severity_for_error(error_name):
    """
    Tự động lookup Severity từ Master Data dựa trên Error Name
    Trả về severity hoặc None nếu không tìm thấy
    """
    return MOCK_MASTER_DATA['errors'].get(error_name, None)

def format_severity_badge(severity):
    """
    Format severity thành badge với icon và màu
    """
    if not severity or severity not in SEVERITY_CONFIG:
        return ""
    
    config = SEVERITY_CONFIG[severity]
    return f"{config['icon']} **{severity}**"

# ============================================================================
# AGGREGATION LOGIC - CRITICAL
# ============================================================================
def add_error_to_buffer(error_name, location, severity, qty):
    """
    Thêm lỗi vào buffer với logic aggregation:
    - Nếu (Error_Name + Location) đã tồn tại → Cộng dồn số lượng
    - Nếu chưa tồn tại → Thêm dòng mới
    
    Note: Severity KHÔNG phải là key để check duplicate
    Chỉ dựa vào Error_Name + Location
    """
    # Tìm xem đã có lỗi trùng trong buffer chưa
    found_index = None
    for i, error in enumerate(st.session_state.error_buffer):
        if error['error_name'] == error_name and error['error_location'] == location:
            found_index = i
            break
    
    if found_index is not None:
        # ĐÃ TỒN TẠI → Cộng dồn số lượng
        old_qty = st.session_state.error_buffer[found_index]['error_qty']
        new_qty = old_qty + qty
        st.session_state.error_buffer[found_index]['error_qty'] = new_qty
        
        # Update severity (lấy severity mới nhất)
        st.session_state.error_buffer[found_index]['error_severity'] = severity
        
        st.toast(f"✅ Đã cộng dồn: {error_name} @ {location} ({old_qty} + {qty} = {new_qty})", icon="➕")
    else:
        # CHƯA TỒN TẠI → Thêm dòng mới
        st.session_state.error_buffer.append({
            'error_name': error_name,
            'error_location': location,
            'error_severity': severity,
            'error_qty': qty
        })
        st.toast(f"✅ Đã thêm: {error_name} @ {location} (SL: {qty})", icon="✨")

# ============================================================================
# SAVE TO GOOGLE SHEETS (Mock - sẽ implement sau)
# ============================================================================
def save_to_google_sheets():
    """
    Lưu toàn bộ buffer vào Google Sheets
    Mỗi dòng trong buffer sẽ thành 1 row với đầy đủ thông tin từ Header
    """
    if not st.session_state.error_buffer:
        st.warning("⚠️ Chưa có lỗi nào trong buffer!")
        return False
    
    # Validate Header data
    if not st.session_state.ncr_id or not st.session_state.product_code:
        st.error("❌ Vui lòng điền đầy đủ Số Phiếu NCR và Mã Sản Phẩm!")
        return False
    
    # Tạo timestamp và các thông tin thời gian
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")
    week_str = f"W{now.isocalendar()[1]}"
    month_str = now.strftime("%Y-%m")
    
    # Chuẩn bị data để save
    rows_to_save = []
    for error in st.session_state.error_buffer:
        row = {
            'timestamp': timestamp,
            'date': date_str,
            'week': week_str,
            'month': month_str,
            'user': st.session_state.user_name,
            'ncr_id': st.session_state.ncr_id,
            'contract_id': st.session_state.contract_id,
            'product_code': st.session_state.product_code,
            'product_name': MOCK_MASTER_DATA['products'].get(st.session_state.product_code, ''),
            'factory': st.session_state.factory,
            'checked_qty': st.session_state.checked_qty,  # SL Kiểm - lặp lại mỗi dòng
            'batch_qty': st.session_state.batch_qty,
            'error_name': error['error_name'],
            'error_location': error['error_location'],
            'error_severity': error['error_severity'],  # NEW: Thêm severity
            'error_qty': error['error_qty']
        }
        rows_to_save.append(row)
    
    # TODO: Khi có Google Sheets connection, sẽ append rows_to_save vào sheet 'NCR_DATA'
    # conn = st.connection("gsheets", type=GSheetsConnection)
    # df_existing = conn.read(worksheet="NCR_DATA")
    # df_new = pd.DataFrame(rows_to_save)
    # df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    # conn.update(worksheet="NCR_DATA", data=df_combined)
    
    # Mock: Hiển thị data sẽ được save
    st.success(f"✅ Đã lưu {len(rows_to_save)} dòng vào Google Sheets!")
    with st.expander("📋 Xem dữ liệu đã lưu (Mock)"):
        st.dataframe(pd.DataFrame(rows_to_save), use_container_width=True)
    
    # Clear buffer sau khi save
    st.session_state.error_buffer = []
    st.session_state.header_locked = False
    
    return True

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_header_section():
    """
    Header Section: Thông tin chung về lô hàng
    Có nút Lock/Unlock để khóa khi đang nhập lỗi
    """
    st.subheader("📋 THÔNG TIN LÔ HÀNG")
    
    # Lock/Unlock Toggle
    col_lock, col_user = st.columns([3, 2])
    with col_lock:
        locked = st.toggle(
            "🔒 Khóa Header (Focus vào nhập lỗi)",
            value=st.session_state.header_locked,
            key='toggle_lock'
        )
        st.session_state.header_locked = locked
    
    with col_user:
        user = st.text_input(
            "👤 Người Kiểm",
            value=st.session_state.user_name,
            disabled=st.session_state.header_locked,
            key='input_user'
        )
        st.session_state.user_name = user
    
    # NCR ID và Contract ID
    col1, col2 = st.columns(2)
    with col1:
        ncr = st.text_input(
            "📄 Số Phiếu NCR *",
            value=st.session_state.ncr_id,
            disabled=st.session_state.header_locked,
            placeholder="VD: NCR-2026-001",
            key='input_ncr'
        )
        st.session_state.ncr_id = ncr
    
    with col2:
        contract = st.text_input(
            "📑 Mã Hợp Đồng",
            value=st.session_state.contract_id,
            disabled=st.session_state.header_locked,
            placeholder="VD: HD-2026-A01",
            key='input_contract'
        )
        st.session_state.contract_id = contract
    
    # Product Code và Factory
    col3, col4 = st.columns(2)
    with col3:
        product_options = list(MOCK_MASTER_DATA['products'].keys())
        
        current_index = 0
        if st.session_state.product_code in product_options:
            current_index = product_options.index(st.session_state.product_code)
        
        product_selected = st.selectbox(
            "🏷️ Mã Sản Phẩm *",
            options=product_options,
            format_func=lambda x: f"{x} - {MOCK_MASTER_DATA['products'][x]}",
            index=current_index,
            disabled=st.session_state.header_locked,
            key='select_product'
        )
        st.session_state.product_code = product_selected
    
    with col4:
        factory_index = 0
        if st.session_state.factory in MOCK_MASTER_DATA['factories']:
            factory_index = MOCK_MASTER_DATA['factories'].index(st.session_state.factory)
        
        factory = st.selectbox(
            "🏭 Nhà Gia Công",
            options=MOCK_MASTER_DATA['factories'],
            index=factory_index,
            disabled=st.session_state.header_locked,
            key='select_factory'
        )
        st.session_state.factory = factory
    
    # Số lượng Kiểm và Số lượng Lô
    col5, col6 = st.columns(2)
    with col5:
        checked = st.number_input(
            "📊 SL Kiểm (cái) *",
            min_value=0,
            value=st.session_state.checked_qty,
            disabled=st.session_state.header_locked,
            step=1,
            key='input_checked'
        )
        st.session_state.checked_qty = checked
    
    with col6:
        batch = st.number_input(
            "📦 SL Lô (cái)",
            min_value=0,
            value=st.session_state.batch_qty,
            disabled=st.session_state.header_locked,
            step=1,
            key='input_batch'
        )
        st.session_state.batch_qty = batch

def render_detail_section():
    """
    Detail Section: Nhập từng lỗi
    - Hỗ trợ "Other/New Error" để nhập lỗi mới
    - SMART SEVERITY: Tự động lookup severity khi chọn error
    """
    st.subheader("🔍 NHẬP CHI TIẾT LỖI")
    
    # Error Name với option "Other"
    error_options = list(MOCK_MASTER_DATA['errors'].keys()) + ['➕ Lỗi Khác/Mới...']
    
    error_selected = st.selectbox(
        "❌ Tên Lỗi",
        options=error_options,
        key='select_error_name'
    )
    
    # SMART SEVERITY LOGIC
    auto_severity = None
    final_error_name = error_selected
    final_severity = None
    
    if error_selected == '➕ Lỗi Khác/Mới...':
        # Custom Error: Cho phép nhập tự do
        col_custom1, col_custom2 = st.columns([3, 2])
        with col_custom1:
            custom_error = st.text_input(
                "✏️ Nhập tên lỗi mới:",
                placeholder="VD: Bung Chỉ Thân",
                key='input_custom_error'
            )
            if custom_error:
                final_error_name = custom_error
            else:
                final_error_name = None  # Chưa nhập
        
        with col_custom2:
            # Manual severity selection for custom errors
            manual_severity = st.selectbox(
                "⚠️ Mức Độ",
                options=MOCK_MASTER_DATA['severity_levels'],
                key='select_manual_severity'
            )
            final_severity = manual_severity
            
            # Display badge
            if manual_severity:
                st.markdown(format_severity_badge(manual_severity))
    else:
        # Standard Error: Auto-lookup severity
        auto_severity = get_severity_for_error(error_selected)
        final_severity = auto_severity
        
        # Display auto-detected severity badge
        if auto_severity:
            st.info(f"**Mức Độ Tự Động:** {format_severity_badge(auto_severity)}")
    
    # Location và Qty
    col1, col2 = st.columns([3, 2])
    with col1:
        location_selected = st.selectbox(
            "📍 Vị Trí",
            options=MOCK_MASTER_DATA['locations'],
            key='select_location'
        )
    
    with col2:
        error_qty = st.number_input(
            "🔢 Số Lượng",
            min_value=1,
            value=1,
            step=1,
            key='input_error_qty'
        )
    
    # Add Error Button
    col_btn1, col_btn2 = st.columns([3, 2])
    with col_btn1:
        add_btn = st.button(
            "➕ THÊM LỖI VÀO BUFFER",
            type="primary",
            use_container_width=True,
            key='btn_add_error'
        )
    
    with col_btn2:
        # Spacer
        pass
    
    # Xử lý khi nhấn nút THÊM LỖI
    if add_btn:
        if not final_error_name:
            st.error("⚠️ Vui lòng chọn hoặc nhập tên lỗi!")
        elif not st.session_state.ncr_id:
            st.error("⚠️ Vui lòng điền Số Phiếu NCR ở phần Header trước!")
        elif not final_severity:
            st.error("⚠️ Không tìm thấy Mức Độ cho lỗi này!")
        else:
            add_error_to_buffer(final_error_name, location_selected, final_severity, error_qty)
            st.rerun()

def render_review_section():
    """
    Review Section: Hiển thị buffer và tính toán error rate
    Bao gồm cột Severity trong buffer table
    """
    st.subheader("📊 REVIEW & SAVE")
    
    if not st.session_state.error_buffer:
        st.info("💡 Chưa có lỗi nào trong buffer. Hãy thêm lỗi ở phần trên.")
        return
    
    # Hiển thị buffer dưới dạng DataFrame với severity
    df_buffer = pd.DataFrame(st.session_state.error_buffer)
    df_buffer.index = df_buffer.index + 1  # Start từ 1
    
    # Format severity column với icons
    df_buffer['severity_display'] = df_buffer['error_severity'].apply(
        lambda x: f"{SEVERITY_CONFIG.get(x, {}).get('icon', '')} {x}" if x in SEVERITY_CONFIG else x
    )
    
    # Reorder columns
    display_df = df_buffer[['error_name', 'error_location', 'severity_display', 'error_qty']].copy()
    
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config={
            "error_name": "Tên Lỗi",
            "error_location": "Vị Trí",
            "severity_display": "Mức Độ",
            "error_qty": st.column_config.NumberColumn(
                "Số Lượng",
                format="%d cái"
            )
        },
        hide_index=False
    )
    
    # Tính Error Rate
    total_errors = df_buffer['error_qty'].sum()
    checked_qty = st.session_state.checked_qty
    
    # Severity Breakdown
    severity_counts = df_buffer.groupby('error_severity')['error_qty'].sum().to_dict()
    
    if checked_qty > 0:
        error_rate = (total_errors / checked_qty) * 100
        
        col_rate1, col_rate2, col_rate3 = st.columns(3)
        with col_rate1:
            st.metric("🔢 Tổng Lỗi", f"{total_errors} cái")
        with col_rate2:
            st.metric("📦 SL Kiểm", f"{checked_qty} cái")
        with col_rate3:
            st.metric("📈 Tỷ Lệ Lỗi", f"{error_rate:.2f}%")
        
        # Severity Breakdown Metrics
        st.caption("**Phân Tích Theo Mức Độ:**")
        col_sev1, col_sev2, col_sev3 = st.columns(3)
        with col_sev1:
            critical_count = severity_counts.get('Critical', 0)
            st.metric("🔴 Critical", f"{critical_count} cái")
        with col_sev2:
            major_count = severity_counts.get('Major', 0)
            st.metric("🟠 Major", f"{major_count} cái")
        with col_sev3:
            minor_count = severity_counts.get('Minor', 0)
            st.metric("🟡 Minor", f"{minor_count} cái")
    else:
        st.warning("⚠️ Chưa nhập Số Lượng Kiểm ở Header, không thể tính Error Rate.")
    
    # Nút Clear và Save
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ XÓA BUFFER", type="secondary", use_container_width=True, key='btn_clear'):
            st.session_state.error_buffer = []
            st.toast("🗑️ Đã xóa buffer!", icon="✅")
            st.rerun()
    
    with col_btn2:
        if st.button("💾 LƯU VÀO GOOGLE SHEETS", type="primary", use_container_width=True, key='btn_save'):
            if save_to_google_sheets():
                st.balloons()
                # Delay để user thấy balloons
                import time
                time.sleep(1)
                st.rerun()

# ============================================================================
# MAIN APP
# ============================================================================
def main():
    st.set_page_config(
        page_title="QC Data Entry",
        page_icon="📋",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS cho Mobile-First
    st.markdown("""
    <style>
    /* Mobile-First Optimization */
    .stButton > button {
        font-size: 16px;
        padding: 0.75rem 1rem;
        font-weight: 600;
    }
    
    .stNumberInput > div > div > input {
        font-size: 16px;
    }
    
    .stSelectbox > div > div > div {
        font-size: 16px;
    }
    
    .stTextInput > div > div > input {
        font-size: 16px;
    }
    
    /* Improve readability on mobile */
    h1 {
        font-size: 1.8rem !important;
    }
    
    h2 {
        font-size: 1.4rem !important;
        margin-top: 1.5rem !important;
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
    
    /* Info box for severity */
    .stAlert p {
        font-size: 16px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize
    init_session_state()
    
    # Header
    st.title("📋 QC Data Entry App")
    st.caption("Mobile-First | Buffer Logic | Smart Severity | Auto Aggregation")
    
    st.divider()
    
    # Render các sections
    render_header_section()
    st.divider()
    
    render_detail_section()
    st.divider()
    
    render_review_section()
    
    # Footer
    st.divider()
    st.caption("💡 **Hướng dẫn**: (1) Điền Header → (2) Lock Header → (3) Thêm lỗi (Severity tự động) → (4) Review → (5) Save")
    st.caption("✨ **Smart Severity**: Mức độ nghiêm trọng tự động dựa trên loại lỗi")

if __name__ == "__main__":
    main()
