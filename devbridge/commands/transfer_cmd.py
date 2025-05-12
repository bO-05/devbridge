import shutil, subprocess, uuid, os
from rich.console import Console
from pathlib import Path
import shlex
from devbridge.utils.wsl_utils import windows_to_wsl_path
from rich.text import Text

console = Console()

def transfer_command(ctx, from_repo_name, to_repo_name, pattern, query, adapt_level, interactive):
    cfg = ctx.obj["config"]

    # Resolve from_repo_name
    resolved_from_repo_path = None
    from_path_obj = Path(from_repo_name)
    from_workspace_path = Path(cfg.repo_workspace_dir) / from_repo_name
    if from_repo_name.startswith("http://") or from_repo_name.startswith("https://"):
        console.print(f"[red]Error:[/] The --from path '{from_repo_name}' looks like a URL.")
        console.print("[red]The 'transfer' command works with local repository paths or names from the DevBridge workspace.[/]")
        console.print("[yellow]Hint:[/] If you want to use a remote repository, first add it to your workspace using:")
        console.print(f"  [bold cyan]devbridge repo add {from_repo_name}[/bold cyan]")
        console.print(f"Then, use its local name in the --from option.")
        return False
    if from_path_obj.is_absolute() and from_path_obj.exists():
        resolved_from_repo_path = from_path_obj
    elif from_workspace_path.exists():
        resolved_from_repo_path = from_workspace_path
    elif from_path_obj.exists():
        resolved_from_repo_path = from_path_obj.resolve()
    else:
        console.print(f"[red]Error:[/] Cannot find source repository path '{from_repo_name}'.[/]")
        return False
    console.print(f"[dim]Using source repository: {resolved_from_repo_path}[/dim]")

    # Resolve to_repo_name
    resolved_to_repo_path = None
    to_path_obj = Path(to_repo_name)
    to_workspace_path = Path(cfg.repo_workspace_dir) / to_repo_name
    if to_repo_name.startswith("http://") or to_repo_name.startswith("https://"):
        console.print(f"[red]Error:[/] The --to path '{to_repo_name}' looks like a URL.")
        console.print("[red]The 'transfer' command works with local repository paths or names from the DevBridge workspace.[/]")
        console.print("[yellow]Hint:[/] If you want to use a remote repository, first add it to your workspace using:")
        console.print(f"  [bold cyan]devbridge repo add {to_repo_name}[/bold cyan]")
        console.print(f"Then, use its local name in the --to option.")
        return False
    if to_path_obj.is_absolute() and to_path_obj.exists():
        resolved_to_repo_path = to_path_obj
    elif to_workspace_path.exists():
        resolved_to_repo_path = to_workspace_path
    elif to_path_obj.exists():
        resolved_to_repo_path = to_path_obj.resolve()
    else:
        # For to_repo, if it doesn't exist, we might want to treat it as a target directory to be created,
        # especially if it's not absolute and not in workspace. So, resolve it relative to CWD.
        # If it's a simple name, it implies CWD/name.
        if not to_path_obj.is_absolute() and not to_workspace_path.parent.exists():
            # If it's a name like 'my_new_project' and workspace dir doesn't exist, assume CWD.
            resolved_to_repo_path = Path.cwd() / to_repo_name
        elif to_path_obj.is_absolute(): # Absolute path, might not exist yet but that's fine for a target
            resolved_to_repo_path = to_path_obj
        else: # Default to resolving from CWD if not in workspace or absolute
            resolved_to_repo_path = Path.cwd() / to_repo_name
        console.print(f"[dim]Target repository path will be: {resolved_to_repo_path}[/dim]")
    console.print(f"[dim]Using target repository: {resolved_to_repo_path}[/dim]")

    target_file_to_copy = None
    if pattern: # Check if pattern is not None before using it
        # Now use resolved_from_repo_path for os.walk
        for root,_,files in os.walk(resolved_from_repo_path):
            for f in files:
                if pattern in f:
                    target_file_to_copy = os.path.join(root,f); break
            if target_file_to_copy:
                break
            
        if not target_file_to_copy: # This check is now part of the 'if pattern:' block
            console.print(f"[red]Pattern '{pattern}' not found in {resolved_from_repo_path}[/]"); return False # return False for consistency
    elif query:
        # TODO: Implement finding file by query for transfer command
        console.print(f"[yellow]Warning: Transferring by --query ('{query}') is not fully implemented yet. Please use --pattern with a filename fragment.[/yellow]")
        return False # Exit gracefully
    else:
        # This case should be caught by Typer if both are missing.
        # If, for some reason, both are None here, it's an issue.
        console.print("[red]Error:[/] Neither pattern nor query was effectively provided for transfer.[/]")
        return False
            
    dest_file_name = os.path.basename(target_file_to_copy)
    # Use resolved_to_repo_path for the destination
    dest_path = resolved_to_repo_path / dest_file_name 
    
    try:
        os.makedirs(resolved_to_repo_path, exist_ok=True)
        shutil.copy(target_file_to_copy, dest_path)
        console.print(f"[green]Copied[/] {target_file_to_copy} → {str(dest_path)}")
    except Exception as e:
        console.print(f"[red]Error copying file {target_file_to_copy} to {str(dest_path)}: {e}[/]")
        return

    # call Amazon Q for adaptation plan
    try:
        # For Q, we want the path to the newly copied file (destination)
        abs_windows_dest_path = str(dest_path.resolve())
        wsl_target_file_path = windows_to_wsl_path(abs_windows_dest_path)
        console.print(f"[dim]Windows path for copied file: {abs_windows_dest_path}[/dim]")
        console.print(f"[dim]WSL path for Q (copied file): {wsl_target_file_path}[/dim]")

        wsl_from_repo = windows_to_wsl_path(str(resolved_from_repo_path.resolve()))
        wsl_to_repo = windows_to_wsl_path(str(resolved_to_repo_path.resolve()))

        q_prompt = f"The file '{dest_file_name}' (WSL path: '{wsl_target_file_path}') was copied from project '{wsl_from_repo}' to project '{wsl_to_repo}'. Please read this file. Then, generate a detailed adaptation plan. Consider imports, configurations, and compatibility with the target project. Adaptation level: {adapt_level} (1-5)."
        console.print(f"[dim]Amazon Q Prompt (raw): {q_prompt}[/dim]")
        
        # Since this script runs inside WSL, directly call q
        q_executable = shutil.which("q")
        if not q_executable:
            console.print("[red]Error:[/] Amazon Q CLI executable ('q') not found in WSL's PATH.[/]")
            console.print("[yellow]Hint:[/] Please ensure Amazon Q CLI is installed and its location is in your PATH inside WSL.")
            return False # Or handle error as appropriate for transfer command

        direct_q_command = [q_executable, "chat", q_prompt]
        console.print(f"[dim]Direct Q command: {' '.join(direct_q_command)}[/dim]")

        resp = subprocess.check_output(
            direct_q_command, 
            text=True, timeout=180
        )
        console.print("[green]Amazon Q Response (adaptation plan):[/]")
        console.print("\n".join(resp.splitlines()[:20]))  # show first 20 lines
    except FileNotFoundError as e_fnf:
        console.print(Text.from_markup("[red]Amazon Q call failed (FileNotFoundError): [/red]"), Text(str(e_fnf)))
    except subprocess.CalledProcessError as e_proc:
        console.print(Text.from_markup("[red]Amazon Q call process error (exit code {e_proc.returncode}):[/red]"))
        if e_proc.stdout:
            console.print(Text.from_markup("[dim]Stdout: [/dim]"), Text(str(e_proc.stdout)))
        if e_proc.stderr:
            console.print(Text.from_markup("[dim]Stderr: [/dim]"), Text(str(e_proc.stderr)))
    except subprocess.TimeoutExpired as e_timeout:
        console.print(Text.from_markup("[red]Amazon Q call timed out: [/red]"), Text(str(e_timeout)))
    except Exception as e:
        console.print(Text.from_markup("[yellow]Amazon Q call failed or had an issue: [/yellow]"), Text(str(e))) 