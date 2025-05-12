import pytest
from devbridge.utils.wsl_utils import resolve_repo_path, windows_to_wsl_path
import os
from pathlib import Path

def test_windows_to_wsl_path_basic():
    assert windows_to_wsl_path(r"C:\Users\Admin\file.txt") == "/mnt/c/Users/Admin/file.txt"
    assert windows_to_wsl_path(r"D:\Projects\My Project\src\main.py") == '"/mnt/d/Projects/My Project/src/main.py"'

def test_windows_to_wsl_path_handles_quotes():
    assert windows_to_wsl_path('"C:\\Users\\Admin\\file.txt"') == "/mnt/c/Users/Admin/file.txt"
    assert windows_to_wsl_path("'D:\\foo bar\\bar.txt'") == '"/mnt/d/foo bar/bar.txt"'

def test_windows_to_wsl_path_non_windows():
    # Should return unchanged for non-Windows paths
    assert windows_to_wsl_path("/home/user/file.txt") == "/home/user/file.txt"
    assert windows_to_wsl_path("") == ""

def test_windows_to_wsl_path_absolute():
    from devbridge.utils.wsl_utils import windows_to_wsl_path
    assert windows_to_wsl_path(r"C:\Users\Test\file.txt") == "/mnt/c/Users/Test/file.txt"
    assert windows_to_wsl_path(r"D:/Projects/My Project/src/main.py") == '"/mnt/d/Projects/My Project/src/main.py"'
    assert windows_to_wsl_path(r"E:\foo bar\baz.py") == '"/mnt/e/foo bar/baz.py"'
    assert windows_to_wsl_path(r"/mnt/c/Users/Test/file.txt") == "/mnt/c/Users/Test/file.txt"
    assert windows_to_wsl_path(r"/home/user/file.txt") == "/home/user/file.txt"

def test_windows_to_wsl_path_quotes_for_spaces():
    from devbridge.utils.wsl_utils import windows_to_wsl_path
    assert windows_to_wsl_path(r"C:\Users\Test\file.txt") == "/mnt/c/Users/Test/file.txt"
    assert windows_to_wsl_path(r"D:\My Project\src\main.py") == '"/mnt/d/My Project/src/main.py"'
    assert windows_to_wsl_path(r"E:\foo bar\baz.py") == '"/mnt/e/foo bar/baz.py"'
    assert windows_to_wsl_path(r"/mnt/c/Users/Test/file.txt") == "/mnt/c/Users/Test/file.txt"

def test_resolve_repo_path_existing(tmp_path):
    # Create a temp directory
    d = tmp_path / "myrepo"
    d.mkdir()
    # Should resolve to absolute path
    resolved = resolve_repo_path(str(d))
    assert resolved is not None
    assert Path(resolved).exists()
    assert Path(resolved).is_dir()

def test_resolve_repo_path_nonexistent():
    assert resolve_repo_path("/this/path/does/not/exist") is None

def test_resolve_repo_path_absolute(tmp_path, monkeypatch):
    from devbridge.utils.wsl_utils import resolve_repo_path
    import os
    # Simulate not running in WSL
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    # Absolute path
    p = tmp_path / "foo"
    p.mkdir()
    assert resolve_repo_path(str(p)) == str(p)
    # Relative path
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        rel = "foo"
        assert resolve_repo_path(rel) == str(p)
    finally:
        os.chdir(cwd)
    # Nonexistent path
    assert resolve_repo_path(str(tmp_path / "doesnotexist")) is None 