import os
from pathlib import Path
from rich.table import Table
from rich.console import Console
from rich.text import Text
from devbridge.utils.storage import _conn
from typing import Optional

console = Console()

# MAX_SNIPPET_LENGTH = 100 # Max characters for a snippet - snippet is now directly from DB

def find_command(
    ctx,
    query: str,
    repo_filter: Optional[str],
    language_filter: Optional[str],
    framework_filter: Optional[str], # Not yet used in DB query
    type_filter: Optional[str], # New filter for element_type
    limit: int
):
    cfg = ctx.obj["config"]
    found_matches = []
    
    # Build the SQL query dynamically
    sql_select_columns = """
        SELECT 
            r.name as repo_name,
            f.relative_path as file_path,
            f.language as file_lang,
            ce.element_type,
            ce.name as element_name,
            ce.snippet,
            ce.start_line
    """
    sql_from_clause = """
        FROM code_elements ce
        JOIN indexed_files f ON ce.file_id = f.id
        JOIN repositories r ON f.repository_id = r.id
    """
    sql_where_conditions = []
    params = []

    # Query against element name and snippet
    if query:
        sql_where_conditions.append("(ce.name LIKE ? OR ce.snippet LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])

    if repo_filter:
        sql_where_conditions.append("r.name LIKE ?") # Or r.path, depending on desired behavior
        params.append(f"%{repo_filter}%")
    
    if language_filter:
        sql_where_conditions.append("f.language = ?")
        params.append(language_filter.lower())

    if type_filter:
        sql_where_conditions.append("ce.element_type LIKE ?")
        params.append(f"%{type_filter}%")
        
    # framework_filter is not used yet as DB doesn't store it.

    sql_query = sql_select_columns + sql_from_clause
    if sql_where_conditions:
        sql_query += " WHERE " + " AND ".join(sql_where_conditions)
    
    sql_query += " ORDER BY r.name, f.relative_path, ce.start_line" # Meaningful order
    sql_query += " LIMIT ?"
    params.append(limit)

    if ctx.obj.get("debug", False):
        print(f"[DEBUG] Executing SQL query: {sql_query}")
        print(f"[DEBUG] With params: {params}")

    with _conn(cfg.storage_path) as c:
        try:
            cursor = c.execute(sql_query, tuple(params))
            db_rows = cursor.fetchall()
            if ctx.obj.get("debug", False):
                print(f"[DEBUG] Rows fetched: {db_rows}")
        except Exception as e:
            if ctx.obj.get("debug", False):
                console.print(f"[DEBUG] Database query error: {e}")
            return None

    for row in db_rows:
        # Each row is a tuple: (repo_name, file_path, file_lang, element_type, element_name, snippet, start_line)
        found_matches.append({
            "repo_name": row[0],
            "file_path": row[1], # This is already relative to its repo
            "lang": row[2],
            "element_type": row[3],
            "element_name": row[4] if row[4] else "", # Handle None names
            "snippet": row[5][:200] + "..." if row[5] and len(row[5]) > 200 else row[5], # Truncate long snippets from DB
            "line_num": row[6]
        })

    # After fetching results, add explainability
    explained_results = []
    for row in found_matches:
        why = []
        if query.lower() in (row.get("element_name") or "").lower():
            why.append("name matches query")
        if query.lower() in (row.get("snippet") or "").lower():
            why.append("code snippet matches query")
        if not why:
            why.append("fuzzy/other match")
        row["why_matched"] = ", ".join(why)
        explained_results.append(row)

    table = Table(title=f"Found {len(explained_results)} results for '{query}'" + (f" (type: {type_filter})" if type_filter else ""))
    table.add_column("Repository", style="blue", no_wrap=False)
    table.add_column("File", style="cyan", no_wrap=False)
    table.add_column("L#", style="magenta", justify="right")
    table.add_column("Type", style="yellow")
    table.add_column("Name", style="green")
    table.add_column("Snippet", max_width=80) # Ensure Rich handles wrapping

    if not explained_results:
        table.add_row("[dim]No matches found based on your criteria.[/]")
    else:
        for match in explained_results:
            # Construct full display path for clarity if needed, or keep as repo + relative_path
            # For now, repo_name and relative_path are separate columns
            table.add_row(
                match["repo_name"],
                match["file_path"],
                str(match["line_num"]),
                match["element_type"],
                match["element_name"],
                match["snippet"]
            )
    
    # console.print(table) # Table printing moved to cli.py
    return explained_results 