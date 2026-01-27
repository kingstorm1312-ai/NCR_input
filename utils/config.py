# utils/config.py - Central Configuration for NCR Project

# --- NCR DEPARTMENT PREFIXES ---
# Định nghĩa mã số phiếu cho từng bộ phận
NCR_DEPARTMENT_PREFIXES = {
    # Finished Goods
    "FI": "FI",
    
    # Sewing Departments (Updated to match Approval Logic)
    "MAY_I": "I'",
    "MAY_P2": "XA",   # Was P2 -> Updated to XA
    "MAY_N4": "X4",   # Was N4 -> Updated to X4
    "MAY_A2": "X3",   # Was A2 -> Updated to X3
    
    # Input / Warehouse
    "TP_DAU_VAO": "DVTP", # Was TP-DAU-VAO -> Updated to DVTP
    "DV_NPL": "DVNPL",
    "DV_CUON": "NPLDV",
    
    # Processing
    "CAT_BAN": "CXA", # Was CAT-BAN -> Updated to CXA
    
    # Logic-based Prefixes (Prefixes used in conditional logic)
    "TRANG": "X2-TR", 
    "CAT": "X2-CA",
    
    "IN": "XG-IN",
    "SIEU_AM": "XG-SA"
}
