import streamlit as st
import pandas as pd
from core.gsheets import get_client

@st.cache_data(ttl=300)
def load_config_sheet():
    """
    Load Master Data from CONFIG sheet (Cached 5 mins).
    Returns: list_noi_may, list_loi, list_vi_tri, dict_muc_do
    """
    try:
        gc = get_client()
        if not gc: return [], [], [], {}
        
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet("CONFIG")
        
        data = worksheet.get_all_records()
        df_config = pd.DataFrame(data)
        
        # --- NORMALIZE DATA ---
        list_noi_may = df_config['noi_may'].dropna().unique().tolist() if 'noi_may' in df_config.columns else []
        
        # Get all defects (not filtered by dept - filtering happens in UI or profile)
        # Or better: return full DF so pages can filter
        list_loi = sorted(df_config['ten_loi'].dropna().unique().tolist()) if 'ten_loi' in df_config.columns else []

        list_vi_tri = df_config['vi_tri_loi'].dropna().unique().tolist() if 'vi_tri_loi' in df_config.columns else []
        
        dict_muc_do = {}
        if 'ten_loi' in df_config.columns and 'muc_do' in df_config.columns:
            dict_muc_do = df_config.drop_duplicates(subset=['ten_loi']).set_index('ten_loi')['muc_do'].to_dict()
            
        # Return Raw DF as well if needed in future, but keeping signature compatible for now
        # Actually, let's return the DF_CONFIG as 5th element for advanced filtering
        return list_noi_may, list_loi, list_vi_tri, dict_muc_do, df_config
        
    except Exception as e:
        st.error(f"Lỗi đọc Config: {e}")
        return [], [], [], {}, pd.DataFrame()
