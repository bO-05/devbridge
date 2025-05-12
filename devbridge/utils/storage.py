import sqlite3, pathlib, datetime, json

def _conn(db_path): 
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)

def init_db(db_path):
    with _conn(db_path) as c:
        # Drop existing table if we are significantly changing schema (for development)
        # In production, you'd need a migration strategy.
        # c.execute("DROP TABLE IF EXISTS file_index;") # Old table
        # c.execute("DROP TABLE IF EXISTS code_elements;")
        # c.execute("DROP TABLE IF EXISTS indexed_files;")
        # c.execute("DROP TABLE IF EXISTS repositories;")

        c.executescript("""
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, -- User-defined name or directory name
            path TEXT UNIQUE NOT NULL, -- Absolute path to the repo
            primary_language TEXT,
            last_indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            -- Consider adding other fields from Repository model like remote_url
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS indexed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository_id INTEGER NOT NULL,
            relative_path TEXT NOT NULL, -- Path relative to repository root
            language TEXT,
            file_hash TEXT, -- To detect changes for re-indexing
            last_scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE,
            UNIQUE (repository_id, relative_path) -- Ensure a file is indexed only once per repo
        );

        CREATE TABLE IF NOT EXISTS code_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            element_type TEXT NOT NULL, -- e.g., 'function', 'class', 'comment_block', 'todo'
            name TEXT, -- Name of the function/class, if applicable
            snippet TEXT, -- A relevant snippet of the code element
            start_line INTEGER,
            end_line INTEGER,
            -- Consider adding fields like 'dependencies' (e.g. imported modules within this element)
            -- Consider adding 'framework_hint'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES indexed_files (id) ON DELETE CASCADE
        );

        -- Old table for reference, to be removed after migration/verification
        -- CREATE TABLE IF NOT EXISTS file_index(
        --   id INTEGER PRIMARY KEY,
        --   repo TEXT, path TEXT, lang TEXT,
        --   indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """) 

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f) 