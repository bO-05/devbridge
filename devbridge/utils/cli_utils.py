from devbridge.utils.config import Config
from pathlib import Path
from typing import Optional
import shutil
from rich.prompt import Confirm

def resolve_repo_path(repo_identifier: str, debug: bool = False, config: Config = None) -> Optional[str]:
    """Resolves a repository identifier to an absolute path.

    Args:
        repo_identifier: Name of the repo in the workspace, or a local file path.
        debug: Enable debug printing.
        config: The DevBridge config, needed to check workspace.

    Returns:
        The absolute path to the repo if found, else None.
    """
    if debug:
        console.print(f"[debug] Resolving repo identifier: '{repo_identifier}'")

    path_obj = Path(repo_identifier)

    # 1. Check if it's an absolute path that exists
    if path_obj.is_absolute() and path_obj.exists() and path_obj.is_dir():
        if debug:
            console.print(f"[debug] '{repo_identifier}' is an existing absolute path.")
        return str(path_obj.resolve())

    # 2. Check if it's a name in the DevBridge workspace
    if config:
        workspace_path = Path(config.repo_workspace_dir) / repo_identifier
        if workspace_path.exists() and workspace_path.is_dir():
            if debug:
                console.print(f"[debug] Found '{repo_identifier}' in DevBridge workspace: {workspace_path.resolve()}")
            return str(workspace_path.resolve())
    elif debug:
        console.print(f"[debug] Config not provided, skipping workspace check for '{repo_identifier}'.")

    # 3. Check if it's a relative path from CWD that exists
    # (This is implicitly covered by the absolute path check if path_obj.resolve() is used,
    # but let's be explicit for clarity if it wasn't an absolute path to begin with)
    if not path_obj.is_absolute():
        cwd_relative_path = Path.cwd() / repo_identifier
        if cwd_relative_path.exists() and cwd_relative_path.is_dir():
            if debug:
                console.print(f"[debug] Found '{repo_identifier}' as relative path in CWD: {cwd_relative_path.resolve()}")
            return str(cwd_relative_path.resolve())

    if debug:
        console.print(f"[debug] Failed to resolve '{repo_identifier}' as an absolute path, workspace repo, or CWD relative path.")
    return None

def get_q_executable(console_instance) -> Optional[str]:
    """Finds the Amazon Q CLI executable and returns its path or None."""
    q_executable = shutil.which("q")
    if not q_executable:
        console_instance.print("[red]Error: Amazon Q CLI executable ('q') not found in PATH.[/red]")
        console_instance.print("[yellow]Hint: Please ensure Amazon Q CLI is installed and its location is in your PATH.[/yellow]")
        console_instance.print("[yellow]See installation instructions: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/cli-install.html[/yellow]")
        return None
    return q_executable

def confirm_action(prompt_message: str, default_choice: bool = False) -> bool:
    """Prompts the user for confirmation and returns their choice."""
    return Confirm.ask(prompt_message, default=default_choice)

# Ensure console is defined if not already, or pass it as an argument if preferred for these utils
# For now, assuming console might be available in the calling context or created ad-hoc if needed by a specific util.
# get_q_executable explicitly takes it. 