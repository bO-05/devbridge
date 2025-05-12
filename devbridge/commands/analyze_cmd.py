from rich.console import Console
from typing import List
import subprocess
from pathlib import Path
import shlex
from devbridge.utils.wsl_utils import windows_to_wsl_path
import shutil
from rich.text import Text

console = Console()

def analyze_command(ctx, path: str, checks: List[str], fix: bool, auto_approve: bool):
    cfg = ctx.obj["config"]
    console.print(f"[cyan]Attempting to analyze path:[/] {path}")

    # Check if the input path looks like a URL
    if path.startswith("http://") or path.startswith("https://"):
        console.print(f"[red]Error:[/] The path '{path}' looks like a URL.")
        console.print("[red]The 'analyze' command works on local file paths or directories only.[/]")
        console.print("[yellow]Hint:[/] If you want to analyze a remote repository, first add it to your workspace using:")
        console.print(f"  [bold cyan]devbridge repo add {path}[/bold cyan]")
        console.print("Then, run the analyze command on the local name of the repository in your workspace, e.g.:")
        console.print(f"  [bold cyan]devbridge analyze {Path(path).stem}[/bold cyan]  (replace '{Path(path).stem}' with the actual local name)")
        return False # Indicate failure

    # Determine the actual path to analyze
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
        console.print("[red]The 'analyze' command currently operates on individual files.[/]")
        console.print(f"[yellow]Hint:[/] Please specify a specific file within the '{path}' project to analyze.")
        console.print(f"  Example: devbridge analyze {path}/your_file_name.py")
        return False # Indicate failure

    console.print(f"[cyan]With checks:[/] {', '.join(checks)}")
    console.print(f"[cyan]Fix issues:[/] {fix}, [cyan]Auto-approve:[/] {auto_approve}")
    # console.print("[yellow]Placeholder:[/] Would call Amazon Q to analyze the code against best practices or specific checks.")
    # Example of a potential Q call (now active)
    try:
        abs_windows_path = str(resolved_target_path.resolve())
        wsl_target_path = windows_to_wsl_path(abs_windows_path)
        console.print(f"[dim]Windows path resolved to: {abs_windows_path}[/dim]")
        console.print(f"[dim]WSL path for Q: {wsl_target_path}[/dim]")

        checks_str = ", ".join(checks)
        q_prompt = f"Please read the file at the WSL path '{wsl_target_path}'. Then, analyze its content for the following checks: {checks_str}. If --fix is {fix}, also suggest fixes."
        console.print(f"[dim]Amazon Q Prompt (raw): {q_prompt}[/dim]")
        
        escaped_q_prompt = shlex.quote(q_prompt)
        # q_chat_command_in_wsl = f"q chat {escaped_q_prompt}" # Old way
        # console.print(f"[dim]WSL Bash command: bash -ic {shlex.quote(q_chat_command_in_wsl)}[/dim]")
        
        # Since this script runs inside WSL, directly call q (assuming q is in PATH within WSL)
        q_executable = shutil.which("q")
        if not q_executable:
            console.print("[red]Error:[/] Amazon Q CLI executable ('q') not found in WSL's PATH.[/]")
            console.print("[yellow]Hint:[/] Please ensure Amazon Q CLI is installed and its location is in your PATH inside WSL.")
            return False

        # The prompt itself might contain spaces or special characters, but q chat expects a single string argument for the prompt.
        # However, the prompt has already been `shlex.quote`d for the previous bash -ic method.
        # For direct execution, we need to be careful. `q chat` expects the prompt as one argument.
        # If `escaped_q_prompt` is already quoted for a shell, it might be too much for direct exec.
        # Let's use the unescaped prompt for direct `q chat` and let `subprocess` handle argument separation if needed, though `q chat` typically takes the whole prompt as one string.
        # If `q_prompt` contains characters that `q chat` itself interprets, that's a different problem.
        # For now, assume `q chat` handles the prompt string as is.
        direct_q_command = [q_executable, "chat", q_prompt]
        console.print(f"[dim]Direct Q command: {' '.join(direct_q_command)}[/dim]")

        resp = subprocess.check_output(
            direct_q_command,
            text=True, timeout=180
        )
        console.print("[green]Amazon Q Response (analysis):[/]")
        console.print(resp)
    except FileNotFoundError as e_fnf:
        console.print(Text.from_markup("[red]Amazon Q call failed (FileNotFoundError): [/red]"), Text(str(e_fnf)))
    except subprocess.CalledProcessError as e_proc:
        console.print(Text.from_markup(f"[red]Amazon Q call process error (exit code {e_proc.returncode}):[/red]"))
        if e_proc.stdout:
            console.print(Text.from_markup("[dim]Stdout: [/dim]"), Text(str(e_proc.stdout)))
        if e_proc.stderr:
            console.print(Text.from_markup("[dim]Stderr: [/dim]"), Text(str(e_proc.stderr)))
    except subprocess.TimeoutExpired as e_timeout:
        console.print(Text.from_markup("[red]Amazon Q call timed out: [/red]"), Text(str(e_timeout)))
    except Exception as e:
        console.print(Text.from_markup("[red]General error during Amazon Q call: [/red]"), Text(str(e)))
    console.print("[green]Analyze command executed.[/]")
    return True 