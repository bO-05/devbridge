import json
from pathlib import Path
from typing import Any, Dict

from devbridge.utils.config import Config, DEFAULT_PATH as DEFAULT_CONFIG_MODEL_PATH # Renaming to avoid confusion

APP_NAME = "devbridge"
CONFIG_FILE_NAME = "config.json" # This was in cli.py before, makes sense here

def get_default_config_path() -> Path:
    """Returns the default path for the main configuration file (not the model path)."""
    return Path.home() / f".{APP_NAME}" / CONFIG_FILE_NAME

def save_config(config_data: Dict[str, Any], path: Path | None = None):
    """Saves the provided configuration dictionary to a JSON file."""
    # Note: This saves a raw dictionary. 
    # The existing load_config in utils.config.py loads a Pydantic model.
    # This is a slight mismatch from the earlier structure but more direct for saving.
    # If we want to save the Pydantic model `Config`, that function needs to be smarter.
    # For now, assuming cli.py might want to save specific key-value pairs it constructs.
    
    config_file_path = path if path else get_default_config_path()
    config_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file_path, 'w') as f:
        json.dump(config_data, f, indent=2)
    # To save the Pydantic model as it is currently loaded by utils.config.load_config:
    # if isinstance(config_data, Config):
    #     config_file_path.write_text(config_data.json(indent=2))
    # else:
    #     # Handle dict saving as above or raise error
    #     with open(config_file_path, 'w') as f:
    #         json.dump(config_data, f, indent=2)

# For consistency, we might want utils.config.Config to be defined here,
# or this save_config to specifically take a Config object.
# The original devbridge-dev-llms-txt.txt had Config in utils and save_config here.
# Keeping that separation for now. 