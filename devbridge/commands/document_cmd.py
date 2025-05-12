from rich.console import Console
import subprocess
from pathlib import Path
import shlex # Added for shell argument quoting
from devbridge.utils.wsl_utils import windows_to_wsl_path
import shutil
from rich.text import Text # Added import

console = Console()

def document_command(ctx, path: str, strategy: str, output_format: str):
    cfg = ctx.obj["config"]
    console.print(f"[cyan]Attempting to document path:[/] {path}")

    # Check if the input path looks like a URL
    if path.startswith("http://") or path.startswith("https://"):
        console.print(f"[red]Error:[/] The path '{path}' looks like a URL.")
        console.print("[red]The 'document' command works on local file paths or directories only.[/]")
        console.print("[yellow]Hint:[/] If you want to document a remote repository, first add it to your workspace using:")
        console.print(f"  [bold cyan]devbridge repo add {path}[/bold cyan]")
        console.print("Then, run the document command on the local name of the repository in your workspace, e.g.:")
        console.print(f"  [bold cyan]devbridge document {Path(path).stem}[/bold cyan]  (replace '{Path(path).stem}' with the actual local name)")
        return False # Indicate failure

    # Determine the actual path to document
    resolved_target_path = None
    path_obj = Path(path)
    workspace_path = Path(cfg.repo_workspace_dir) / path

    if path_obj.is_absolute() and path_obj.exists():
        resolved_target_path = path_obj
        console.print(f"[dim]Interpreting '{path}' as an absolute path.[/dim]")
    elif workspace_path.exists():
        resolved_target_path = workspace_path
        console.print(f"[dim]Found '{path}' in DevBridge workspace: {resolved_target_path}[/dim]")
    elif path_obj.exists(): # Relative path from CWD
        resolved_target_path = path_obj.resolve()
        console.print(f"[dim]Interpreting '{path}' as a relative path from CWD: {resolved_target_path}[/dim]")
    else:
        console.print(f"[red]Error:[/] Cannot find path '{path}'. It's not an absolute path, not in the workspace ('{cfg.repo_workspace_dir}'), and not found relative to the current directory.[/]")
        return False

    # NEW: Check if the resolved path is a file or directory
    if not resolved_target_path.is_file():
        console.print(f"[red]Error:[/] The path '{resolved_target_path}' is a directory.")
        console.print("[red]The 'document' command currently operates on individual files.[/]")
        console.print(f"[yellow]Hint:[/] Please specify a specific file within the '{path}' project to document.")
        console.print(f"  Example: devbridge document {path}/your_file_name.py")
        return False # Indicate failure

    console.print(f"[cyan]Using strategy:[/] {strategy}, [cyan]Output format:[/] {output_format}")
    # console.print("[yellow]Placeholder:[/] Would call Amazon Q to generate documentation for the code at the given path.")
    # Example of a potential Q call (now active)
    try:
        # Resolve the input path to an absolute Windows path first
        abs_windows_path = str(resolved_target_path.resolve()) # Use the determined resolved_target_path
        wsl_target_path = windows_to_wsl_path(abs_windows_path)
        console.print(f"[dim]Windows path resolved to: {abs_windows_path}[/dim]")
        console.print(f"[dim]WSL path for Q: {wsl_target_path}[/dim]")

        # Instruct Q to consider the file content via the path in the prompt.
        q_prompt = f"Please read the file at the WSL path '{wsl_target_path}'. Then, generate comprehensive documentation for its content using a {strategy} approach. Format the documentation as {output_format}."
        console.print(f"[dim]Amazon Q Prompt (raw): {q_prompt}[/dim]")

        # Escape the prompt for safe inclusion in a shell command string
        escaped_q_prompt = shlex.quote(q_prompt)
        
        # Since this script runs inside WSL, directly call q
        q_executable = shutil.which("q")
        if not q_executable:
            console.print("[red]Error:[/] Amazon Q CLI executable ('q') not found in WSL's PATH.[/]")
            console.print("[yellow]Hint:[/] Please ensure Amazon Q CLI is installed and its location is in your PATH inside WSL.")
            return False
        
        direct_q_command = [q_executable, "chat", q_prompt] # Use the original, unescaped q_prompt
        console.print(f"[dim]Direct Q command: {' '.join(direct_q_command)}[/dim]")

        resp = subprocess.check_output(
            direct_q_command,
            text=True, timeout=180 # Further increased timeout for WSL + bash -ic + Q
        )
        console.print("[green]Amazon Q Response (documentation draft):[/]")
        console.print(resp)
    except FileNotFoundError as e_fnf:
        # This could be `wsl` not found, or `q` not found within WSL.
        console.print(Text.from_markup("[red]Amazon Q call failed (FileNotFoundError): [/red]"), Text(str(e_fnf)))
    except subprocess.CalledProcessError as e_proc:
        # This will catch non-zero exit codes from WSL/bash/q itself (e.g., q command not found *inside* bash -ic)
        console.print(Text.from_markup(f"[red]Amazon Q call process error (exit code {e_proc.returncode}):[/red]"))
        if e_proc.stdout:
            console.print(Text.from_markup("[dim]Stdout: [/dim]"), Text(str(e_proc.stdout)))
        if e_proc.stderr:
            console.print(Text.from_markup("[dim]Stderr: [/dim]"), Text(str(e_proc.stderr)))
    except subprocess.TimeoutExpired as e_timeout:
        console.print(Text.from_markup("[red]Amazon Q call timed out: [/red]"), Text(str(e_timeout)))
    except Exception as e:
        console.print(Text.from_markup("[red]General error during Amazon Q call: [/red]"), Text(str(e)))
    console.print("[green]Document command executed.[/]")
    return True 