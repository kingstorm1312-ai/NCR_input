# utils/config.py - Central Configuration for NCR Project

# --- NCR DEPARTMENT PREFIXES ---
# Định nghĩa mã số phiếu cho từng bộ phận
NCR_DEPARTMENT_PREFIXES = {
    # Finished Goods
    "FI": "FI",
    
    # Sewing Departments
    "MAY_I": "I'",
    "MAY_P2": "P2",
    "MAY_N4": "N4",
    "MAY_A2": "A2",
    
    # Input / Warehouse
    "TP_DAU_VAO": "TP-DAU-VAO",
    "DV_NPL": "DVNPL",
    "DV_CUON": "NPLDV",
    
    # Processing
    "CAT_BAN": "CAT-BAN",
    
    # Logic-based Prefixes (Prefixes used in conditional logic)
    "TRANG": "X2-TR", 
    "CAT": "X2-CA",
    
    "IN": "XG-IN",
    "SIEU_AM": "XG-SA"
}
