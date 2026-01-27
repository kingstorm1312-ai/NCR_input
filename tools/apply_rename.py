import os
import json
import glob
import shutil

def apply_rename():
    # Load mapping
    with open('rename_map.json', 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    # 1. RENAME FILES
    print("--- 1. RENAMING FILES ---")
    for old_path, new_path in mapping.items():
        if os.path.exists(old_path):
            try:
                # Ensure directory exists (though pages/ should exist)
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                
                # Rename
                # Use shutil.move for safer rename/overwrite behavior
                shutil.move(old_path, new_path)
                print(f"✅ Renamed: {old_path} -> {new_path}")
            except Exception as e:
                print(f"❌ Error renaming {old_path}: {e}")
        else:
            print(f"⚠️ File not found (skipped): {old_path}")

    # 2. UPDATE REFERENCES
    print("\n--- 2. UPDATING REFERENCES ---")
    files = glob.glob('**/*.py', recursive=True)
    
    for file_path in files:
        if file_path.startswith("tools") or file_path.startswith("venv"): continue
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            new_content = content
            modified = False
            
            for old_path, new_path in mapping.items():
                old_filename = os.path.basename(old_path)
                new_filename = os.path.basename(new_path)
                
                # Replace full path references (e.g. in Dashboard.py)
                # Normalize slashes for matching
                old_path_forward = old_path.replace("\\", "/")
                new_path_forward = new_path.replace("\\", "/")
                
                if old_path_forward in new_content:
                    new_content = new_content.replace(old_path_forward, new_path_forward)
                    modified = True
                    print(f"   [FIXED PATH] in {file_path}: {old_path_forward} -> {new_path_forward}")
                
                # Replace filename references (e.g. st.switch_page("01_🔍_FI.py"))
                if old_filename in new_content:
                    new_content = new_content.replace(old_filename, new_filename)
                    modified = True
                    print(f"   [FIXED NAME] in {file_path}: {old_filename} -> {new_filename}")
            
            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"💾 Saved updates to: {file_path}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    apply_rename()
