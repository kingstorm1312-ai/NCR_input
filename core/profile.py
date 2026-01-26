from dataclasses import dataclass, field

@dataclass
class DeptProfile:
    """
    Schema đại diện cho cấu hình của một bộ phận (Department).
    """
    code: str
    name: str
    icon: str
    prefix: str
    config_group: str
    has_measurements: bool
    has_checklist: bool
    skip_bp: bool
    sheet_spreadsheet_id: str
    sheet_worksheet_name: str

    def __post_init__(self):
        """
        Validation cơ bản (Fail-fast).
        """
        if not self.code or not self.code.strip():
            raise ValueError("DeptProfile Error: 'code' không được để trống.")
        
        if not self.sheet_spreadsheet_id or not self.sheet_spreadsheet_id.strip():
            raise ValueError("DeptProfile Error: 'sheet_spreadsheet_id' không được để trống.")
            
        if not self.sheet_worksheet_name or not self.sheet_worksheet_name.strip():
            raise ValueError("DeptProfile Error: 'sheet_worksheet_name' không được để trống.")
