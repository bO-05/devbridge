import os
from pathlib import Path
import re

def windows_to_wsl_path(path: str) -> str:
    """
    Convert a Windows path to a WSL path, handling spaces, quotes, and mixed slashes robustly.
    Always quote the result if it contains spaces.
    """
    path = path.strip().strip('"').strip("'")
    path = path.replace('\\', '/')
    match = re.match(r'([a-zA-Z]):/(.*)', path)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2)
        wsl_path = f"/mnt/{drive}/{rest}"
        if ' ' in wsl_path:
            wsl_path = f'"{wsl_path}"'
        return wsl_path
    return path

# Example usage (for testing this function independently):
# if __name__ == '__main__':
#     test_paths = [
#         "C:\\Users\\Admin\\file.txt",
#         "D:\\Projects\\My Project\\src\\main.py",
#         ".\\relative\\path.md", # This will be resolved to absolute first
#         "d:\\another\\case.txt",
#         str(Path.home() / "test_file.txt")
#     ]
#     for p_str in test_paths:
#         # Simulate how it would be used: resolve first, then convert
#         resolved_p = Path(p_str).resolve()
#         print(f"Windows: {resolved_p} -> WSL: {windows_to_wsl_path(str(resolved_p))}") 

def resolve_repo_path(user_input: str, debug: bool = False) -> str | None:
    """
    Normalize and resolve a user-supplied repo path:
    - Strips quotes and whitespace
    - Expands ~ to home
    - Converts Windows paths to WSL paths if running under WSL
    - Checks if the path exists and is a directory
    Returns the resolved absolute path as a string, or None if not found.
    """
    path_str = user_input.strip().strip('"').strip("'")
    if not path_str:
        return None
    path_str = os.path.expanduser(path_str)
    # Normalize slashes for Windows
    if os.name == 'nt':
        path_str = path_str.replace('\\', '/')
    p = Path(path_str)
    if not p.exists():
        # Only join with CWD if the path is relative
        if not p.is_absolute():
            p = Path.cwd() / path_str
        if not p.exists():
            if debug:
                print(f"[DEBUG] Path does not exist: {p}")
            return None
    abs_path = p.resolve()
    running_in_wsl = 'WSL_DISTRO_NAME' in os.environ
    if running_in_wsl:
        return windows_to_wsl_path(str(abs_path))
    return str(abs_path) 