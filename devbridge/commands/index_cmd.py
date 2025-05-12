from pathlib import Path
import os
import sys
import hashlib # For file hashing
from typing import List, Tuple, Optional # Added Tuple, Optional
import re # For basic name extraction

from rich.console import Console
from devbridge.utils.storage import init_db, _conn
# Assuming your Pydantic models might be used later for structuring data before DB interaction
# from devbridge.models import Repository, IndexedFile, CodeElement # Example model imports
from devbridge.utils.js_parser import extract_js_elements

console = Console()

def guess_lang(path_obj: Path) -> str: # Takes Path object
    ext = path_obj.suffix.lower() # Ensure lowercase for matching
    # Expanded list slightly
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c_header",
        ".hpp": "cpp_header",
        ".cs": "csharp",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".rs": "rust",
        ".kt": "kotlin",
        ".swift": "swift",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".html": "html",
        ".css": "css",
    }.get(ext, "text")

def calculate_file_hash(file_path: Path) -> str:
    """Calculates SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except IOError:
        # console.print(f"[yellow]Warning:[/] Could not read file {file_path} for hashing.")
        return "" # Return empty string on error to allow skipping

def extract_element_name(line: str, keyword: str) -> Optional[str]:
    """Rudimentary extraction of function/class name from a line."""
    # Regex to capture typical function/class names (alphanumeric + underscore, not starting with number)
    match = re.search(rf"{keyword}\s+([a-zA-Z_][a-zA-Z0-9_]*)(\(|:)?", line)
    return match.group(1) if match else None

def index_repository(c, repo_path_str: str, depth: int, exclude: List[str], force: bool):
    """Indexes a single repository."""
    abs_repo_path = Path(repo_path_str).resolve()
    repo_name = abs_repo_path.name

    # 1. Add/Get Repository
    cursor = c.execute("SELECT id FROM repositories WHERE path = ?", (str(abs_repo_path),))
    repo_row = cursor.fetchone()
    repo_id: Optional[int] = None

    if repo_row:
        repo_id = repo_row[0]
        c.execute("UPDATE repositories SET last_indexed_at = CURRENT_TIMESTAMP WHERE id = ?", (repo_id,))
    else:
        cursor = c.execute("INSERT INTO repositories (name, path) VALUES (?, ?)", (repo_name, str(abs_repo_path)))
        repo_id = cursor.lastrowid
    
    if not repo_id:
        console.print(f"[red]Error:[/] Could not get or create repository ID for {abs_repo_path}")
        return 0

    # console.print(f"[cyan]Indexing repository:[/] {repo_name} (ID: {repo_id})")
    
    indexed_file_count = 0
    for root, dirs, files in os.walk(abs_repo_path, topdown=True):
        # Handle depth
        current_depth = len(Path(root).relative_to(abs_repo_path).parts)
        if current_depth >= depth:
            dirs[:] = [] 
            continue

        # Handle excludes for directories
        # If a directory itself is excluded, os.walk will not traverse it further if we modify dirs[:]
        original_dirs_len = len(dirs)
        dirs[:] = [d for d in dirs if not any(ex_pattern in Path(root, d).as_posix() for ex_pattern in exclude) and not d.startswith('.')]
        # if len(dirs) < original_dirs_len:
            # console.print(f"[dim]Pruned excluded or hidden subdirectories in {root}[/dim]")

        if any(ex_pattern in Path(root).as_posix() for ex_pattern in exclude) or Path(root).name.startswith('.'):
            dirs[:] = [] # Don't traverse this excluded or hidden directory further
            # console.print(f"[dim]Skipping excluded or hidden directory: {root}[/dim]")
            continue
            
        for f_name in files:
            if f_name.startswith('.'):
                # console.print(f"[dim]Skipping hidden file: {f_name}[/dim]")
                continue
            if any(ex_pattern in f_name for ex_pattern in exclude):
                # console.print(f"[dim]Skipping excluded file pattern: {f_name}[/dim]")
                continue

            file_path_obj = Path(root) / f_name
            relative_file_path_str = str(file_path_obj.relative_to(abs_repo_path))
            
            lang = guess_lang(file_path_obj)
            file_hash = calculate_file_hash(file_path_obj)

            if not file_hash:
                if ctx.obj.get("verbose", False):
                    console.print(f"[yellow]Skipping file due to hashing error or empty file:[/] {file_path_obj}")
                continue

            cursor = c.execute("SELECT id, file_hash FROM indexed_files WHERE repository_id = ? AND relative_path = ?",
                               (repo_id, relative_file_path_str))
            file_row = cursor.fetchone()
            
            file_id: Optional[int] = None
            process_elements = True 

            if file_row:
                file_id = file_row[0]
                if file_row[1] == file_hash and not force:
                    # console.print(f"[dim]Unchanged file, skipping element processing: {relative_file_path_str}[/dim]")
                    process_elements = False # File exists and hash matches, and not forcing
                else:
                    c.execute("""
                        UPDATE indexed_files 
                        SET language = ?, file_hash = ?, last_scanned_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (lang, file_hash, file_id))
                    c.execute("DELETE FROM code_elements WHERE file_id = ?", (file_id,))
                    # console.print(f"[dim]Updated changed file: {relative_file_path_str}[/dim]")
            else:
                cursor = c.execute("""
                    INSERT INTO indexed_files (repository_id, relative_path, language, file_hash)
                    VALUES (?, ?, ?, ?)
                """, (repo_id, relative_file_path_str, lang, file_hash))
                file_id = cursor.lastrowid
                # console.print(f"[dim]Added new file: {relative_file_path_str}[/dim]")
            
            if not file_id:
                # console.print(f"[red]Error:[/] Could not get or create file ID for {relative_file_path_str}")
                continue

            if process_elements:
                indexed_file_count +=1 # Count files whose elements are processed
                try:
                    with open(file_path_obj, 'r', encoding='utf-8', errors='ignore') as f_content:
                        in_docstring = False
                        docstring_start_line = None
                        docstring_content = []
                        lines = f_content.readlines()
                        if lang in ["javascript", "typescript"]:
                            # Use Node.js-based parser for JS/TS
                            source_code = ''.join(lines)
                            js_elements = extract_js_elements(source_code)
                            if not js_elements:
                                console.print(f"[yellow][DEBUG] No JS/TS elements found in {file_path_obj}[/]")
                            for elem in js_elements:
                                console.print(f"[green][DEBUG] Inserting JS/TS element:[/] {elem}")
                                c.execute("""
                                    INSERT INTO code_elements (file_id, element_type, name, snippet, start_line, end_line)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (file_id, elem['type'], elem['name'], elem['snippet'][:255], elem['start_line'], elem['end_line']))
                        else:
                            for line_num, line_text in enumerate(lines, 1):
                                line_text_stripped = line_text.strip()
                                if not line_text_stripped: # Skip empty lines
                                    continue
                                element_type: Optional[str] = None
                                element_name: Optional[str] = None
                                # --- Python-specific logic ---
                                if lang == "python":
                                    # Docstring detection (triple quotes)
                                    if (line_text_stripped.startswith('"""') or line_text_stripped.startswith("'''") ):
                                        if not in_docstring:
                                            in_docstring = True
                                            docstring_start_line = line_num
                                            docstring_content = [line_text_stripped]
                                            if (line_text_stripped.endswith('"""') and len(line_text_stripped) > 3) or (line_text_stripped.endswith("'''") and len(line_text_stripped) > 3):
                                                # Single-line docstring
                                                c.execute("""
                                                    INSERT INTO code_elements (file_id, element_type, name, snippet, start_line, end_line)
                                                    VALUES (?, ?, ?, ?, ?, ?)
                                                """, (file_id, "docstring", None, line_text_stripped[:255], line_num, line_num))
                                                in_docstring = False
                                                docstring_content = []
                                        else:
                                            # End of multi-line docstring
                                            docstring_content.append(line_text_stripped)
                                            c.execute("""
                                                INSERT INTO code_elements (file_id, element_type, name, snippet, start_line, end_line)
                                                VALUES (?, ?, ?, ?, ?, ?)
                                            """, (file_id, "docstring", None, '\n'.join(docstring_content)[:255], docstring_start_line, line_num))
                                            in_docstring = False
                                            docstring_content = []
                                        continue
                                    elif in_docstring:
                                        docstring_content.append(line_text_stripped)
                                        continue
                                    # Function and class detection
                                    if line_text_stripped.startswith("def "):
                                        element_type = "function_py"
                                        element_name = extract_element_name(line_text_stripped, "def")
                                    elif line_text_stripped.startswith("class "):
                                        element_type = "class_py"
                                        element_name = extract_element_name(line_text_stripped, "class")
                                    # TODO detection
                                    elif line_text_stripped.startswith("# TODO"):
                                        element_type = "todo"
                                        element_name = None
                                    # Comment detection (not TODO)
                                    elif line_text_stripped.startswith("#"):
                                        element_type = "comment"
                                        element_name = None
                                # --- General TODO/comment detection for other languages ---
                                elif line_text_stripped.lower().startswith("todo"):
                                    element_type = "todo"
                                    element_name = None
                                # Insert detected element
                                if element_type:
                                    c.execute("""
                                        INSERT INTO code_elements (file_id, element_type, name, snippet, start_line, end_line)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, (file_id, element_type, element_name, line_text_stripped[:255], line_num, line_num)) # Truncate snippet
                except Exception as e:
                    if ctx.obj.get("verbose", False):
                        console.print(f"[yellow]Warning:[/] Could not process file {file_path_obj} for elements: {e}")
    return indexed_file_count

def index_command(ctx, repos: List[str], depth:int, exclude:List[str], force:bool):
    cfg = ctx.obj["config"]
    print(f"[DEBUG] Using database file: {cfg.storage_path}")
    init_db(cfg.storage_path)
    # Debug: print tables after init_db
    import sqlite3
    con = sqlite3.connect(cfg.storage_path)
    tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"[DEBUG] Tables after init_db: {tables}")
    con.close()
    
    total_indexed_files = 0
    repo_count = 0
    verbose = ctx.obj.get("verbose", False)

    console.print(f"[bold blue]Starting DevBridge Indexing Process...[/]")
    if force:
        console.print("[yellow]Force re-indexing enabled: All elements in changed/new files will be re-processed.[/]")

    with _conn(cfg.storage_path) as c:
        try:
            for repo_path_str in repos:
                abs_repo_path = Path(repo_path_str).resolve()
                if not abs_repo_path.is_dir():
                    console.print(f"[yellow]Warning:[/] Repository path not found or not a directory, skipping: {abs_repo_path}")
                    continue
                
                if verbose:
                    console.print(f"[cyan]Processing repository:[/] {abs_repo_path.name} (Path: {abs_repo_path})")
                
                num_files = index_repository(c, str(abs_repo_path), depth, exclude, force)
                total_indexed_files += num_files
                repo_count +=1
                if verbose:
                    console.print(f"[cyan]Finished processing repository:[/] {abs_repo_path.name}. Indexed/Updated {num_files} files containing elements.")
            c.commit()
        except Exception as e:
            c.rollback()
            console.print(f"[bold red]Critical error during indexing, operation rolled back: {e}[/]")
            import traceback
            if verbose:
                console.print(traceback.format_exc())
            return # Exit cleanly after rollback

    if repo_count > 0:
        console.print(f"[bold green]Successfully indexed/updated {total_indexed_files} files (with new/changed elements) across {repo_count} repo(s).[/]")
    elif not repos:
        console.print("[yellow]No repositories specified for indexing. Use --repo option.[/]")
    else:
        console.print("[yellow]No new or changed files with processable elements found in the specified repositories.[/]") 