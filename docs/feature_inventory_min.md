# Feature Inventory - Phase 1 Baseline

## Core Functionality Status

- [x] **Streamlit Run**: App khởi động OK (port 8505 tested)
- [x] **Login Admin**: User `admin` authentication OK
- [x] **FI Page Access**: `pages/01_fi.py` loads OK
- [x] **May I Page Access**: `pages/05_may_i.py` loads OK
- [x] **Add Defect Logic**: Buffer + aggregation logic implemented
- [x] **Save NCR (Batch Append)**: `smart_append_ncr()` writes to `NCR_DATA` sheet
- [x] **Secrets Config**: `.streamlit/secrets.toml` + `.toml.example` ready
- [x] **GSheet Connection**: Verified with test script (17 users loaded)

## May P2 Enhanced Features

- [x] **Measurement Tab**: Spec Size/Weight + Tolerance + Measured values
- [x] **Checklist Tab**: Barcode, Weight Box, Print, Color, Other checks
- [x] **Pass/Fail Evaluation**: AQL logic + `ket_qua_kiem_tra` field saved

## Known Limitations

- Browser UI testing blocked (Playwright environment issue)
- Manual UI testing recommended for full verification
