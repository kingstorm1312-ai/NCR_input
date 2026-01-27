import os
import json
import glob

def check_references():
    # Load mapping
    with open('rename_map.json', 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    # Get all python files
    files = glob.glob('**/*.py', recursive=True)
    
    print("--- CHECKING REFERENCES ---")
    found_refs = False
    
    for file_path in files:
        if file_path.startswith("tools"): continue
        if file_path.startswith("venv"): continue
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            for old_path, new_path in mapping.items():
                # Extract filename only for looser checks if needed, but usually Streamlit uses full path or relative
                old_filename = os.path.basename(old_path)
                
                # Check for explicit string references
                if old_filename in content:
                    found_refs = True
                    try:
                        print(f"[REF FOUND] In '{file_path}': Found '{old_filename}' -> Should match '{os.path.basename(new_path)}'")
                    except UnicodeEncodeError:
                         print(f"[REF FOUND] In '{file_path}': Found Unicode Filename Ref")
                    
                # Special check for Department Routing Map in Dashboard
                # e.g., "fi": "pages/01_🔍_FI.py"
                if old_path.replace("\\", "/") in content.replace("\\", "/"):
                     found_refs = True
                     try:
                        print(f"[PATH REF FOUND] In '{file_path}': Found full path '{old_path}'")
                     except UnicodeEncodeError:
                        print(f"[PATH REF FOUND] In '{file_path}': Found Unicode Path Ref")
                     
        except Exception as e:
            try:
                print(f"Error reading {file_path}: {e}")
            except:
                pass

    if not found_refs:
        print("No direct string references found (which is good, but double check config logic).")
    else:
        print("\n[ACTION REQUIRED] These references must be updated during rename.")

if __name__ == "__main__":
    # Force UTF-8 for stdout if possible
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    check_references()
