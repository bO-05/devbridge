import subprocess
import json
from pathlib import Path

def extract_js_elements(source_code: str, file_path: str = None):
    """
    Extract all function and class definitions from JS/TS source code using the Node.js js_parser.js script.
    If file_path is provided, it will be used; otherwise, a temp file will be created.
    Returns a list of dicts: {type, name, start_line, end_line, snippet}
    """
    import tempfile
    import os
    if file_path is None:
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tmp:
            tmp.write(source_code)
            tmp_path = tmp.name
    else:
        tmp_path = file_path
    try:
        script_path = str(Path(__file__).parent / 'js_parser.js')
        result = subprocess.run(['node', script_path, tmp_path], capture_output=True, text=True, check=True)
        elements = json.loads(result.stdout)
        return elements
    except Exception as e:
        print(f"[extract_js_elements] Error: {e}")
        return []
    finally:
        if file_path is None and os.path.exists(tmp_path):
            os.remove(tmp_path)

# Example usage:
# with open('somefile.js', 'r') as f:
#     code = f.read()
#     print(extract_js_elements(code)) 