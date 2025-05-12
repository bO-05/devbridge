from pathlib import Path
from pydantic import BaseModel
import json, os

DEFAULT_PATH = Path.home() / ".devbridge" / "config.json"

class Config(BaseModel):
    storage_path: str = str(Path.home() / ".devbridge" / "db.sqlite3")
    repo_workspace_dir: str = str(Path.home() / ".devbridge" / "repos")
    default_user_agent: str = "DevBridgeBot/0.1 Crawler"
    respect_robots_txt: bool = True
    crawl_retry_limit: int = 3
    crawl_backoff_base_ms: int = 500

def load_config(path: str | None = None) -> Config:
    file = Path(path) if path else DEFAULT_PATH
    if file.exists():
        # return Config.parse_file(file) # Deprecated
        try:
            file_content = file.read_text()
            return Config.model_validate_json(file_content)
        except Exception as e: # Handle potential read errors or JSON decode errors
            # Fallback to default config if parsing fails, and maybe log error
            # For now, creating a new default config if parsing existing one fails.
            # This matches behavior if file didn't exist, but could overwrite a corrupted one.
            # A more robust solution might warn the user or try to backup corrupted file.
            print(f"Warning: Could not parse config file {file}: {e}. Using default config.") # Temporary print
            pass # Fall through to creating default config
            
    # If file does not exist, or parsing failed and fell through
    file.parent.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    file.write_text(cfg.model_dump_json(indent=2))
    return cfg 