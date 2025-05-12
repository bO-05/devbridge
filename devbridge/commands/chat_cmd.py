# devbridge/commands/chat_cmd.py

import typer
from rich.console import Console
from rich.prompt import Prompt
import subprocess
import shlex
import shutil
from pathlib import Path
from typing import Optional

from devbridge.utils.config import Config
from devbridge.utils.cli_utils import resolve_repo_path, get_q_executable, confirm_action # Assuming confirm_action and get_q_executable exist
from devbridge.utils.wsl_utils import windows_to_wsl_path

console = Console()

def chat_command(
    ctx: typer.Context,
    repo_identifier: Optional[str] = typer.Option(None, "--repo", "-r", help="Optional repository context (name from workspace or local path)."),
    initial_message: Optional[str] = typer.Option(None, "--message", "-m", help="An initial message to send to the chat.")
):
    """Starts an interactive chat session with Amazon Q, optionally within a specific repository context."""
    cfg: Config = ctx.obj["config"]
    debug: bool = ctx.obj.get("debug", False)
    q_exec = get_q_executable(console)
    if not q_exec:
        return

    wsl_repo_path_context = None
    repo_context_message = ""

    if repo_identifier:
        resolved_repo_path = resolve_repo_path(repo_identifier, debug=debug, config=cfg)
        if resolved_repo_path:
            if Path(resolved_repo_path).is_dir(): # Ensure it's a directory for context
                wsl_repo_path_context = windows_to_wsl_path(str(Path(resolved_repo_path).resolve()))
                repo_context_message = f"You are now chatting in the context of the repository at WSL path: '{wsl_repo_path_context}'. Ask me anything about it."
                console.print(f"[cyan]Chatting in context of repository:[/] {resolved_repo_path} (WSL: {wsl_repo_path_context})")
            else:
                console.print(f"[yellow]Warning:[/] Specified repository context '{repo_identifier}' resolved to '{resolved_repo_path}', which is not a directory. Proceeding without repository context.")
        else:
            console.print(f"[yellow]Warning:[/] Could not resolve repository context '{repo_identifier}'. Proceeding without repository context.")

    console.print("[bold green]Welcome to DevBridge Chat with Amazon Q![/]")
    if repo_context_message:
        console.print(f"[italic green]{repo_context_message}[/italic green]")
    console.print("Type your questions or '/quit' to exit.")

    session_history = [] # To maintain some context for Q, perhaps

    if initial_message:
        console.print(f"[magenta]You (initial):[/] {initial_message}")
        user_input = initial_message
    else:
        user_input = Prompt.ask("[magenta]You[/]")


    while True:
        if user_input.lower() in ["/quit", "/exit"]:
            console.print("[bold green]Exiting chat. Goodbye![/]")
            break

        if not user_input.strip():
            user_input = Prompt.ask("[magenta]You[/]")
            continue

        # Construct the prompt for Amazon Q
        # For now, a simple prompt. Could be enhanced with history or specific instructions.
        q_prompt_parts = []
        if wsl_repo_path_context:
            q_prompt_parts.append(f"Given the repository context at WSL path '{wsl_repo_path_context}',")
        
        # Simple history (last user message, last Q response) - can be expanded
        # if session_history:
        #     if len(session_history) > 0: # last Q
        #        q_prompt_parts.append(f"Previously, I said: '{session_history[-1]['q']}'")
        #     if len(session_history) > 1: # last User
        #        q_prompt_parts.append(f"To which you asked: '{session_history[-2]['user']}'")

        q_prompt_parts.append(f"Please respond to the following: {user_input}")
        full_q_prompt = " ".join(q_prompt_parts)

        if debug:
            console.print(f"[dim]Amazon Q Prompt (raw): {full_q_prompt}[/dim]")

        try:
            # Direct Q call
            # No shlex.quote needed for list-based Popen/run
            direct_q_command = [q_exec, "chat", full_q_prompt]
            if debug:
                console.print(f"[dim]Direct Q command: {' '.join(direct_q_command)}[/dim]")

            # Using subprocess.Popen for interactive-like chat
            # We want to stream the output as Q generates it.
            # However, 'q chat' itself is interactive. We send one prompt and get one response.
            # For a true streaming experience from Q's side, Q would need to support that.
            # For now, check_output is fine for single turn.
            
            # If 'q chat' enters its own interactive loop, we might need to manage stdin/stdout more carefully
            # For now, assume 'q chat <prompt>' gives a direct answer and exits.
            process = subprocess.Popen(direct_q_command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=300) # Increased timeout

            if process.returncode == 0:
                console.print(f"[blue]Amazon Q:[/]")
                # Filter out Q's interactive cruft if any, or known status lines.
                # This is a heuristic.
                lines = stdout.splitlines()
                # Example filter:
                # filtered_lines = [line for line in lines if not line.startswith(("To learn more about", "Welcome to", "╭──", "│", "╰──", "/help", "━━━━━━━━")) and "ctrl + j new lines" not in line]
                # For now, let's just print it all and refine later if needed.
                console.print(stdout)
                session_history.append({"user": user_input, "q": stdout.strip()})
            else:
                console.print(f"[red]Error from Amazon Q (Code: {process.returncode}):[/]")
                if stdout:
                    console.print(f"[dim]Stdout: {stdout}[/dim]")
                if stderr:
                    console.print(f"[dim]Stderr: {stderr}[/dim]")
                # Don't add to history if error
        
        except subprocess.TimeoutExpired:
            console.print("[red]Amazon Q call timed out.[/]")
        except FileNotFoundError:
            console.print(f"[red]Error:[/] Amazon Q CLI executable ('{q_exec}') not found or other components missing.[/]")
            break # Exit chat if Q is not found
        except Exception as e:
            console.print(f"[red]General error during Amazon Q call: {e}[/]")

        user_input = Prompt.ask("[magenta]You[/]")

    console.print("Chat session ended.") 