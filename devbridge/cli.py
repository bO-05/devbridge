#!/usr/bin/env python3
"""
DevBridge - AI-Powered Cross-Project Knowledge Bridge for Developers
Main CLI entry point
"""

import os
import sys
import typer
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import click
from pathlib import Path
from rich.prompt import Prompt, Confirm
import shutil
from devbridge.utils.cli_utils import resolve_repo_path
import subprocess
import tempfile
import re
import git
import textwrap
import json
from rich.table import Table

from devbridge import __version__ as APP_VERSION # Import the version from __init__.py
from devbridge.utils.config import load_config, Config
from devbridge.config import save_config, get_default_config_path, APP_NAME, CONFIG_FILE_NAME
from devbridge.commands.index_cmd import index_command
from devbridge.commands.find_cmd import find_command
from devbridge.commands.transfer_cmd import transfer_command
from devbridge.commands.document_cmd import document_command
from devbridge.commands.analyze_cmd import analyze_command
from devbridge.commands.chat_cmd import chat_command
from devbridge.commands.init_cmd import init_command
from devbridge.commands.learn_cmd import learn_command_async
import asyncio

# Initialize Typer app and console
app = typer.Typer(
    help="DevBridge: AI-Powered Cross-Project Knowledge Bridge",
    add_completion=False,
)
console = Console()

# Banner art for DevBridge
BANNER = r"""
    ____             ____       _     __         
   / __ \___  __  __/ __ )_____(_)___/ /___  ____ 
  / / / / _ \/ / / / __  / ___/ / __  / __ `/ _ \
 / /_/ /  __/ /_/ / /_/ / /  / / /_/ / /_/ /  __/
/_____/\___/\____/_____/_/  /_/\__,_/\__, /\___/ 
                                   /_____/       
"""

BANNER_STYLE = "cyan bold"

# Global options via callback
def version_callback(value: bool):
    """Display version information and exit"""
    if value:
        console.print(f"[{BANNER_STYLE}]DevBridge[/] version: [bold]{APP_VERSION}[/]")
        raise typer.Exit()

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output"),
    config: Optional[str] = typer.Option(None, "--config", help="Path to config file"),
    version: bool = typer.Option(False, "--version", callback=version_callback, help="Show version and exit"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output for path resolution and other internals"),
):
    """
    DevBridge: AI-Powered Cross-Project Knowledge Bridge
    
    Transfer knowledge, code patterns, and best practices across different projects.
    """
    loaded_config = load_config(config) if config else load_config()
    ctx.obj = {
        "verbose": verbose,
        "quiet": quiet,
        "config": loaded_config,
        "debug": debug,
        "console": console
    }
    
    if not quiet and sys.stdout.isatty():
        console.print(Text(BANNER, style=BANNER_STYLE))
        console.print(
            f"[bold]DevBridge[/] [dim]v{APP_VERSION}[/] - AI-Powered Cross-Project Knowledge Bridge\n"
        )

# Register commands
@app.command()
def index(
    ctx: typer.Context,
    repos: List[str] = typer.Argument(
        None, help="Repositories to index (name from workspace, local path, e.g., `my_repo /path/to/another_repo`). Add remote URLs with 'devbridge repo add <url>' first."
    ),
    depth: int = typer.Option(3, "--depth", "-d", help="Indexing depth for directory traversal (e.g., 0 for root only, 1 for root + direct subdirectories)."),
    exclude: List[str] = typer.Option(
        [], "--exclude", "-e", help="Exclude paths/files matching pattern (e.g., `*.log`, `node_modules/`). Can be used multiple times."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force re-indexing of all files, even if their content hash hasn't changed."
    ),
    json_out: bool = typer.Option(False, "--json", help="Output results as JSON.")
):
    """
    Index repositories to build the knowledge base.
    """
    # Ensure ctx.obj is set
    if not hasattr(ctx, "obj") or ctx.obj is None:
        from devbridge.utils.config import Config
        ctx.obj = {"config": Config(), "debug": False}
    debug = ctx.obj.get("debug", False)

    if not repos:
        console.print("[yellow]No repositories specified. Please provide repository names (from workspace) or local paths to index.[/]")
        console.print("[dim]Example: devbridge index my_repo_name /path/to/another_repo[/]")
        console.print("[dim]To index a remote repository, first add it using: devbridge repo add <URL>[/dim]")
        raise typer.Exit(code=1)
        
    norm_repos = []
    for r_name_or_path in repos:
        resolved_path = resolve_repo_path(r_name_or_path, debug=debug, config=ctx.obj["config"])
        if resolved_path:
            norm_repos.append(resolved_path)
        else:
            if r_name_or_path.startswith("http://") or r_name_or_path.startswith("https://") or r_name_or_path.startswith("git@"):
                console_instance = ctx.obj.get("console", console)
                console_instance.print(f"[dim]Argument '{r_name_or_path}' looks like a remote URL. Attempting to add it to workspace non-interactively.[/dim]")
                try:
                    added_repo_path_str = add_repo_command_logic(
                        ctx.obj["config"], 
                        r_name_or_path, 
                        console_instance,
                        interactive_overwrite=False
                    )
                    if added_repo_path_str:
                        console_instance.print(f"[green]Implicitly added/verified remote repository '{r_name_or_path}' at '{added_repo_path_str}'[/green]")
                        norm_repos.append(added_repo_path_str)
                    else:
                        console_instance.print(f"[yellow]Could not automatically add/verify remote repository '{r_name_or_path}'. Please add it manually using 'devbridge repo add'. Skipping this entry.[/yellow]")
                except Exception as e_add:
                    escaped_error = Text(str(e_add)).plain
                    console_instance.print(f"[red]Error attempting to automatically add URL '{r_name_or_path}': {escaped_error}. Skipping this entry.[/red]")
            else:
                path_obj = Path(r_name_or_path)
                if path_obj.exists() and path_obj.is_dir():
                    norm_repos.append(str(path_obj.resolve()))
                    console.print(f"[dim]Interpreted '{r_name_or_path}' as a direct local path for indexing.[/dim]")
                else:
                    console.print(f"[red]Error:[/] Repository or path '{r_name_or_path}' not found in workspace, as a valid local directory, or as a recognized URL format. Skipping.[/red]")
    
    if not norm_repos:
        console.print("[red]No valid repositories found to index after checking input.[/]")
        raise typer.Exit(code=1)
        
    result = index_command(ctx, norm_repos, depth, list(exclude), force)
    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        return result

@app.command()
def find(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search query (e.g., \"database connection setup\", \"UserAuthentication class\")."),
    repo: Optional[str] = typer.Option(
        None, "--repo", "-r", help="Limit search to a specific repository name (from workspace) or local path."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "-l", help="Filter by programming language (e.g., `python`, `javascript`)."
    ),
    framework: Optional[str] = typer.Option(
        None, "--framework", "-f", help="Limit search to specific framework (Note: This filter is not actively used in the current search logic)."
    ),
    type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter by code element type (e.g., `function_py`, `class_py`, `docstring`, `comment`, `todo`)."
    ),
    limit: int = typer.Option(5, "--limit", "-n", help="Limit number of results."),
    json_out: bool = typer.Option(False, "--json", help="Output results as JSON.")
):
    """
    Search for code patterns and text across indexed repositories.
    """
    results = find_command(ctx, query, repo, language, framework, type, limit)
    
    if json_out:
        if results is None:
            error_output = {"error": "Error querying the database.", "details": "See server logs or run without --json for more info if debug is enabled."}
            typer.echo(json.dumps(error_output, indent=2))
        else:
            typer.echo(json.dumps(results, indent=2, default=str))
    else:
        if results is None:
            console.print("[red]Error querying the database.[/]")
            console.print("[dim] (Run with --debug for more details if the issue persists)[/]")
            return

        table = Table(title=f"Found {len(results)} results for '{query}'" + (f" (type: {type})" if type else ""))
        table.add_column("Repository", style="blue", no_wrap=False)
        table.add_column("File", style="cyan", no_wrap=False)
        table.add_column("L#", style="magenta", justify="right")
        table.add_column("Type", style="yellow")
        table.add_column("Name", style="green")
        table.add_column("Snippet", max_width=80) # Ensure Rich handles wrapping

        if not results:
            # Use a more specific message if the list is empty vs. an error occurred
            if results == []: # Explicitly check for empty list
                 table.add_row("[dim]No matches found based on your criteria.[/]")
            else: # Should not happen if find_command returns [] on no match, but good for safety
                 table.add_row("[dim]No results or an unexpected issue occurred.[/]")
        else:
            for match in results:
                table.add_row(
                    match.get("repo_name", "N/A"),
                    match.get("file_path", "N/A"),
                    str(match.get("line_num", "N/A")),
                    match.get("element_type", "N/A"),
                    match.get("element_name", "N/A"),
                    match.get("snippet", "N/A")
                )
        console.print(table)
        # No return here, as we've printed the table.
        # Typer would try to print a None return if we did `return None`

@app.command()
def transfer(
    ctx: typer.Context,
    from_repo: str = typer.Option(..., "--from", help="Source repository name (from workspace) or local path."),
    to_repo: str = typer.Option(..., "--to", help="Target repository name (from workspace) or local path. Can be a new directory."),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", "-p", help="Filename or fragment within the source repository to identify the file/pattern to transfer (e.g., `auth_utils.py`)."
    ),
    query: Optional[str] = typer.Option(
        None, "--query", "-q", help="Natural language query to find pattern (Note: This feature is not fully implemented for transfer yet)."
    ),
    adapt_level: int = typer.Option(
        3, "--adapt-level", "-a", 
        help="Level of adaptation (1-5, 1=minimal, 5=maximum)",
        min=1, max=5
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--non-interactive", help="Interactive mode for adaptation decisions"
    ),
):
    """
    Adapt and transfer code patterns or solutions between projects using Amazon Q.
    Requires either a pattern ID (from a previous 'find' operation) or a natural language query.
    """
    if not pattern and not query:
        console.print("[red]Error:[/] You must specify either a pattern ID (using --pattern) or a query (using --query).")
        raise typer.Exit(1)
    
    return transfer_command(ctx, from_repo, to_repo, pattern, query, adapt_level, interactive)

# New document command
@app.command()
def document(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Path to the specific code *file* to document (e.g., `src/api.py`, `my_module/utils.js`)."),
    strategy: str = typer.Option("default", "--strategy", "-s", help="Documentation strategy (e.g., `default`, `concise`, `comprehensive`)."),
    output_format: str = typer.Option("markdown", "--format", "-o", help="Output format (e.g., `markdown`, `plaintext`).")
):
    """
    Generate documentation for a specific code file using Amazon Q.
    """
    return document_command(ctx, path, strategy, output_format)

# New analyze command
@app.command()
def analyze(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Path to the specific code *file* to analyze (e.g., `src/auth.py`, `components/payment.js`)."),
    checks: Optional[List[str]] = typer.Option(None, "--check", "-c", help="Specific checks to perform (e.g., `security`, `performance`, `style`). Can be used multiple times. Defaults to 'default' checks."),
    fix: bool = typer.Option(False, "--fix", help="Attempt to automatically apply fixes for identified issues."),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Automatically approve all suggested fixes (use with caution).")
):
    """
    Analyze a specific code file for best practices and issues using Amazon Q.
    """
    # Ensure checks is a list even if None, for the command logic
    active_checks = checks if checks else ["default"]
    return analyze_command(ctx, path, active_checks, fix, auto_approve)

# New check-q command
@app.command("check-q")
def check_q_command(ctx: typer.Context):
    """
    Verify Amazon Q CLI setup and connectivity.
    """
    console = ctx.obj.get("console", Console()) # Get console from context
    q_path = shutil.which("q")

    if q_path:
        console.print(f"[green]SUCCESS:[/] Amazon Q CLI (`q`) found at: [cyan]{q_path}[/]")
        try:
            # Attempt to get version or a simple status check
            # Using a timeout to prevent hanging if q is unresponsive
            result = subprocess.run(["q", "--version"], capture_output=True, text=True, check=False, timeout=10)
            if result.returncode == 0:
                version_info = result.stdout.strip()
                # Try to extract a version number, be robust if format changes
                version_match = re.search(r"q version (\S+)", version_info)
                if version_match:
                    version_str = version_match.group(1)
                    console.print(f"[green]INFO:[/] Amazon Q CLI Version: [bold cyan]{version_str}[/]")
                else:
                    # if specific version string not found, print what we got
                    console.print(f"[yellow]INFO:[/] Amazon Q CLI responded. Output (first line): {version_info.splitlines()[0] if version_info else 'No output'}")
                console.print("[green]INFO:[/] Amazon Q CLI appears to be operational.")
            else:
                # q command ran but returned an error
                console.print(f"[yellow]WARNING:[/] Amazon Q CLI (`q`) found, but `q --version` failed.")
                console.print(f"[dim]Return code: {result.returncode}[/]")
                if result.stderr:
                    console.print(f"[dim]Error output:\n{textwrap.indent(result.stderr.strip(), '  ')}[/]")
                else:
                    console.print(f"[dim]No error output from q, but it exited with code {result.returncode}. It might not be fully configured.")
                console.print("[yellow]INFO:[/] Please ensure Amazon Q CLI is correctly configured (e.g., logged in).")

        except subprocess.TimeoutExpired:
            console.print(f"[yellow]WARNING:[/] Amazon Q CLI (`q`) found, but `q --version` timed out after 10 seconds.")
            console.print("[yellow]INFO:[/] The Q CLI might be unresponsive or very slow to start.")
        except FileNotFoundError: # Should not happen if shutil.which succeeded, but as a safeguard
            console.print(f"[red]ERROR:[/] Amazon Q CLI (`q`) was initially found but now cannot be executed.")
            console.print("[red]INFO:[/] This might indicate a PATH issue or that `q` was removed after the initial check.")
        except Exception as e:
            console.print(f"[red]ERROR:[/] An unexpected error occurred while checking `q --version`.")
            console.print(f"[dim]Details: {e}[/]")
    else:
        console.print(f"[red]FAILED:[/] Amazon Q CLI (`q`) not found in your system's PATH.")
        console.print("[yellow]INFO:[/] Please install the Amazon Q CLI. You can typically find instructions at:")
        console.print("[cyan underline]https://docs.aws.amazon.com/amazonq/latest/userguide/command-line-interface.html[/]") # Keep URL updated
        console.print("[yellow]INFO:[/] Some DevBridge features (transfer, document, analyze, chat) require it.")

# This is the simplified Typer command for learn
@app.command("learn")
def learn_sync_wrapper(
    ctx: typer.Context,
    repo_identifier: str = typer.Argument(..., help="Repository identifier (e.g., `https://github.com/user/repo`, `user/repo`, or a Deepwiki URL)."),
    mode: str = typer.Option("aggregate", "--mode", help="Output mode: 'aggregate' to combine all content, 'pages' to show primary page.", click_type=click.Choice(['aggregate', 'pages'], case_sensitive=False)),
    max_depth: int = typer.Option(0, "--max-depth", help="Crawl depth. 0 for root page, 1 for root + 1 level of links, etc."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output from the learn command itself.")
):
    """
    (Sync Wrapper) Fetches documentation or information for a given repository identifier.
    This wrapper calls the underlying async learn command using asyncio.run().
    REPO_IDENTIFIER can be a direct Deepwiki URL, a GitHub URL (e.g., https://github.com/user/repo),
    a slug (e.g., user/repo), or a specific topic for a known provider (e.g., an AWS service name).
    """
    app_config: Config = ctx.obj.get("config", Config())
    effective_verbose = ctx.obj.get("verbose", False) or verbose
    repo_identifier_help = "Repository identifier (e.g., `https://github.com/user/repo`, `user/repo`, or a Deepwiki URL)."

    # Directly run the original async command logic using asyncio.run()
    return asyncio.run(learn_command_async(
        repo_identifier=repo_identifier,
        mode=mode,
        max_depth=max_depth,
        verbose=effective_verbose,
        user_agent=app_config.default_user_agent,
        respect_robots_txt=app_config.respect_robots_txt,
        crawl_retry_limit=app_config.crawl_retry_limit,
        crawl_backoff_base_ms=app_config.crawl_backoff_base_ms
    ))

@app.command("demo")
def demo_command(ctx: typer.Context):
    """
    Run a quick demonstration of DevBridge's core features.
    This will temporarily clone a public repository, index it, perform a search,
    and show the learn command.
    """
    console = ctx.obj.get("console", Console())
    config = ctx.obj.get("config", Config()) # Get config from context
    debug = ctx.obj.get("debug", False)

    console.print(Panel("[bold cyan]DevBridge Demo Mode[/]", expand=False, border_style="magenta"))
    console.print("This demo will guide you through a few core features of DevBridge.")
    console.print("It will use a pre-packaged sample project.")

    with tempfile.TemporaryDirectory() as tmpdir:
        sample_git_url = "https://github.com/octocat/Spoon-Knife.git"
        temp_repo_path = Path(tmpdir) / "Spoon-Knife"
        repo_name_for_find = temp_repo_path.name

        console.print(f"\\\\n[bold green]Step 1: Setting up a Temporary Sample Repository[/]")
        console.print(f"For this demo, we'll clone a public repository: '{sample_git_url}'")
        console.print(f"It will be cloned into a temporary directory: '{temp_repo_path}'")

        cloned_successfully = False
        if Confirm.ask("Proceed with cloning the sample repository?", default=True):
            try:
                console.print(f"[dim]Cloning '{sample_git_url}'...[/dim]")
                git.Repo.clone_from(sample_git_url, temp_repo_path)
                console.print(f"[green]Successfully cloned '{sample_git_url}' to '{temp_repo_path}'.[/green]")
                cloned_successfully = True
            except git.exc.GitCommandError as e_git:
                console.print(f"[red]Error cloning sample repository:[/] {e_git.stderr}")
            except Exception as e:
                console.print(f"[red]An unexpected error occurred during cloning:[/] {e}")
        else:
            console.print("[yellow]Demo step (cloning) skipped by user. Subsequent steps may be affected.[/yellow]")

        # --- Indexing Step ---
        console.print(f"\\\\n[bold green]Step 2: Indexing the Sample Repository[/]")
        indexed_successfully = False
        if cloned_successfully:
            console.print(f"We will now index the temporary sample repository: '{repo_name_for_find}' located at '{temp_repo_path}'")
            if Confirm.ask("Proceed with indexing?", default=True):
                try:
                    console.print(f"[dim]Executing: devbridge index \"{str(temp_repo_path)}\" --depth 1 --force[/dim]")
                    index_result = index_command(ctx, [str(temp_repo_path)], depth=1, exclude=[], force=True)
                    if index_result:
                        console.print(f"[green]Successfully indexed '{repo_name_for_find}'.[/green]")
                        indexed_successfully = True
                    else:
                        console.print(f"[yellow]Indexing of '{repo_name_for_find}' completed (check output above for details).[/]")
                except Exception as e:
                    console.print(f"[red]Error during demo indexing step:[/] {e}")
            else:
                console.print("[yellow]Demo step (indexing) skipped by user.[/]")
        else:
            console.print(f"Skipping indexing as the sample repository was not cloned successfully or cloning was skipped.")

        # --- Finding Step ---
        console.print(f"\\\\n[bold green]Step 3: Finding Code Elements[/]")
        if indexed_successfully: # Only proceed if indexing was successful
            demo_query = "README"
            console.print(f"Now, let's find elements matching the query: '{demo_query}' in the temporary '{repo_name_for_find}' repository.")
            if Confirm.ask("Proceed with finding?", default=True):
                try:
                    console.print(f"[dim]Executing: devbridge find \"{demo_query}\" --repo \"{repo_name_for_find}\" --limit 3[/dim]")
                    find_command(ctx,
                                 demo_query,
                                 repo_filter=repo_name_for_find,
                                 limit=3,
                                 language_filter=None,
                                 framework_filter=None,
                                 type_filter=None
                                 )
                except Exception as e:
                    console.print(f"[red]Error during demo find step:[/] {e}")
            else:
                console.print("[yellow]Demo step (finding) skipped by user.[/]")
        elif cloned_successfully: # Cloned but not indexed
             console.print(f"Skipping find as indexing was skipped or not successful.")
        else: # Not cloned
            console.print(f"Skipping find as the sample repository was not cloned.")


        # --- Learning Step ---
        console.print(f"\\\\n[bold green]Step 4: Learning from a Public URL[/]")
        demo_url = "https://github.com/aws/amazon-q-developer-cli/"
        console.print(f"Next, we'll use the 'learn' command to fetch content from a public URL: '{demo_url}'.")
        console.print("[dim]This demonstrates fetching and processing online documentation or articles.[/]")
        if Confirm.ask("Proceed with learning (fetches public URL)?", default=True):
            try:
                console.print(f"[dim]Executing: devbridge learn \"{demo_url}\" --mode aggregate --max-depth 0[/dim]")
                asyncio.run(learn_command_async(
                    repo_identifier=demo_url,
                    mode="aggregate",
                    max_depth=0,
                    verbose=ctx.obj.get("verbose", False),
                    user_agent=config.default_user_agent,
                    respect_robots_txt=config.respect_robots_txt,
                    crawl_retry_limit=config.crawl_retry_limit,
                    crawl_backoff_base_ms=config.crawl_backoff_base_ms
                ))
            except Exception as e:
                console.print(f"[red]Error during demo learn step:[/] {e}")
        else:
            console.print("[yellow]Demo step (learning) skipped by user.[/]")

    console.print(f"\\\\n[bold magenta]Demo Complete![/]")
    console.print("You can explore more commands using 'devbridge --help'.")
    console.print("Key commands to try next:")
    console.print("  - `devbridge repo add <your-project-path-or-url>`")
    console.print("  - `devbridge index --repo <your-project-name>`")
    console.print("  - `devbridge find \"your search query\"`")

    console.print(f"\\\\n[dim]The temporary directory '{tmpdir}' and its contents have been cleaned up.[/dim]")

# Define init command correctly using a wrapper function decorated with @app.command()
@app.command(name="init") # Explicitly name it 'init'
def init_cli_wrapper(ctx: typer.Context):
    """Onboard and configure DevBridge for first use."""
    console = ctx.obj.get("console", Console())
    console.print("[bold cyan]\nWelcome to DevBridge![/]")
    console.print("[green]DevBridge[/] helps you transfer knowledge, code patterns, and best practices across all your projects.")
    console.print("\n[bold]Let's get you set up.[/]")

    # Dependency checks
    missing = []
    if not shutil.which("git"):
        missing.append("git")
    if not shutil.which("q"):
        missing.append("Amazon Q CLI (q)")
    if sys.version_info < (3, 8):
        missing.append("Python 3.8+")
    if missing:
        console.print(f"[red]Missing dependencies:[/] {', '.join(missing)}")
        console.print("Please install the above before using all features of DevBridge.")
    else:
        console.print("[green]All required dependencies found![/]")

    # Prompt for demo or real repo
    if Confirm.ask("Would you like to try a quick demo? (Recommended for first-time users)", default=True):
        ctx.obj["console"] = console # Ensure console is in context for the demo_command
        # Directly call the demo_command if user agrees
        demo_command(ctx) 
        return
    if Confirm.ask("Would you like to index a project now?", default=True):
        repo_path_input = Prompt.ask("Enter the path to your project (or leave blank to skip)", default="")
        if repo_path_input:
            repo_path = resolve_repo_path(repo_path_input, debug=ctx.obj.get("debug", False))
            if not repo_path:
                console.print(f"[red]Could not find a valid directory for:[/] {repo_path_input}")
            else:
                from devbridge.commands.index_cmd import index_command
                index_command(ctx, [repo_path], 10, [], False)
                console.print(f"[green]Indexing complete for:[/] {repo_path}")
                # Prompt to search
                if Confirm.ask("Would you like to search for a pattern now?", default=True):
                    query = Prompt.ask("Enter a search query (e.g. 'auth', 'error handling')", default="auth")
                    from devbridge.commands.find_cmd import find_command
                    results = find_command(ctx, query, None, None, None, None, 5)
                    if not results:
                        console.print("[yellow]No results found.[/]")
                    else:
                        from rich.table import Table
                        table = Table(title="Search Results")
                        table.add_column("File")
                        table.add_column("Element")
                        table.add_column("Snippet")
                        for r in results:
                            table.add_row(r.get("path", "?"), r.get("name", "?"), (r.get("code_snippet", "")[:40] + "...") if r.get("code_snippet") else "")
                        console.print(table)
                # If Q CLI present, prompt for doc/analyze
                if shutil.which("q") and Confirm.ask("Would you like to try Amazon Q-powered documentation or analysis?", default=False):
                    path = Prompt.ask("Enter a file or folder to document/analyze", default=repo_path)
                    from devbridge.commands.document_cmd import document_command
                    from devbridge.commands.analyze_cmd import analyze_command
                    if Confirm.ask("Generate documentation?", default=True):
                        document_command(ctx, path, "comprehensive", "markdown")
                    if Confirm.ask("Analyze code?", default=False):
                        analyze_command(ctx, path, ["security"], False, False)
        else:
            console.print("[yellow]Skipping indexing for now. You can run [bold]devbridge index <repo_name_or_path_or_url>[/] anytime.")
    else:
        console.print("[yellow]Skipping indexing for now. You can run [bold]devbridge index <repo_name_or_path_or_url>[/] anytime.")
    # Save config (if needed)
    from devbridge.utils.config import load_config
    cfg = load_config(None)
    console.print(f"[dim]Config loaded: {cfg}[/]")
    console.print("\n[bold green]You're all set![/]")
    console.print("- Use [bold]devbridge help[/] to see all commands and examples.")
    console.print("- Start searching with [bold]devbridge find 'pattern'[/].")
    console.print("- Transfer code with [bold]devbridge transfer --from ... --to ... --pattern ...[/].")
    console.print("- Generate docs or analyze code with [bold]devbridge document[/] and [bold]devbridge analyze[/].")
    console.print("\n[dim]Happy coding![/]")

# Helper function for repo add logic to be callable from index and repo add CLI command
def add_repo_command_logic(config: Config, path_or_url: str, console_instance: Console, interactive_overwrite: bool = False) -> Optional[str]:
    """Core logic to add a repository. Returns the local path string of the repo if successful."""
    ws_dir = Path(config.repo_workspace_dir)
    ws_dir.mkdir(parents=True, exist_ok=True)
    
    final_repo_path_str = None
    is_url = path_or_url.startswith("http") or path_or_url.startswith("https") or path_or_url.startswith("git@")
    
    repo_name_candidate = Path(path_or_url).stem if is_url else Path(path_or_url).name
    target_workspace_path = ws_dir / repo_name_candidate

    try:
        if is_url:
            if target_workspace_path.exists():
                if interactive_overwrite:
                    console_instance.print(f"[yellow]Warning:[/] Target directory '{target_workspace_path}' for URL '{path_or_url}' already exists.[/]")
                    if Confirm.ask(f"Do you want to remove the existing directory and re-clone '{path_or_url}'?", default=False):
                        try:
                            shutil.rmtree(target_workspace_path)
                            console_instance.print(f"[dim]Removed existing directory: {target_workspace_path}[/dim]")
                        except Exception as e_rm:
                            console_instance.print(f"[red]Error removing existing directory '{target_workspace_path}': {e_rm}[/]")
                            return None # Fail removal
                    else:
                        console_instance.print(f"[yellow]Aborted cloning. Repository '{repo_name_candidate}' not changed in workspace.[/]")
                        return str(target_workspace_path.resolve()) # Return existing path as per user decision
                else: # Non-interactive, use existing
                    console_instance.print(f"[dim]Workspace directory '{target_workspace_path}' for URL '{path_or_url}' already exists. Using existing for non-interactive call.[/dim]")
                    final_repo_path_str = str(target_workspace_path.resolve())
                    return final_repo_path_str
            
            # Proceed with cloning if path doesn't exist or was removed
            if not target_workspace_path.exists(): # Re-check after potential removal
                console_instance.print(f"[dim]Cloning '{path_or_url}' into '{target_workspace_path}'...[/dim]")
                cloned_repo = git.Repo.clone_from(path_or_url, target_workspace_path)
                final_repo_path_str = str(Path(cloned_repo.working_tree_dir).resolve())
                console_instance.print(f"Cloned '{repo_name_candidate}' into workspace at '{final_repo_path_str}'.")
            else: # Existed and user chose not to remove (interactive) or it was a non-interactive call that found it
                 final_repo_path_str = str(target_workspace_path.resolve())

        else: # Local path
            src = Path(path_or_url).resolve()
            if not src.exists() or not src.is_dir():
                console_instance.print(f"[red]Local path does not exist or is not a directory: {src}[/]")
                return None
            
            # target_workspace_path already defined based on src.name
            if target_workspace_path.exists():
                if interactive_overwrite:
                    console_instance.print(f"[yellow]Warning:[/] Target directory '{target_workspace_path}' for local copy '{src}' already exists.[/]")
                    if Confirm.ask(f"Do you want to remove the existing directory and re-copy from '{src}'?", default=False):
                        try:
                            shutil.rmtree(target_workspace_path)
                            console_instance.print(f"[dim]Removed existing directory: {target_workspace_path}[/dim]")
                        except Exception as e_rm_local:
                            console_instance.print(f"[red]Error removing existing directory '{target_workspace_path}': {e_rm_local}[/]")
                            return None # Fail removal
                    else:
                        console_instance.print(f"[yellow]Aborted copy. Repository '{src.name}' not changed in workspace.[/]")
                        return str(target_workspace_path.resolve()) # Return existing path
                else: # Non-interactive, use existing
                    console_instance.print(f"[dim]Workspace directory '{target_workspace_path}' for local path '{src}' already exists. Using existing for non-interactive call.[/dim]")
                    final_repo_path_str = str(target_workspace_path.resolve())
                    return final_repo_path_str

            if not target_workspace_path.exists(): # Re-check after potential removal
                shutil.copytree(src, target_workspace_path)
                final_repo_path_str = str(target_workspace_path.resolve())
                console_instance.print(f"Copied local repository '{src.name}' into workspace at '{final_repo_path_str}'.")
            else:
                final_repo_path_str = str(target_workspace_path.resolve())

        return final_repo_path_str

    except git.exc.GitCommandError as e_git:
        escaped_stderr = Text(str(e_git.stderr).strip()).plain
        if target_workspace_path.exists() and "already exists and is not an empty directory" in str(e_git.stderr).lower():
            # Use Text concatenation for safety
            message_prefix = Text.from_markup(f"[yellow]Git clone failed for '{path_or_url}' as directory '{target_workspace_path}' already exists and is not empty. Using existing: ")
            console_instance.print(message_prefix + Text(escaped_stderr + "[/yellow]"))
            return str(target_workspace_path.resolve())
        else:
            # Use Text concatenation for safety
            message_prefix = Text.from_markup(f"[red]Git error while processing '{path_or_url}': ")
            console_instance.print(message_prefix + Text(escaped_stderr + "[/]"))
    except PermissionError as e_perm:
        escaped_error = Text(str(e_perm)).plain
        console_instance.print(Text.from_markup(f"[red]Permission error during operation on '{path_or_url}':[/red] ") + Text(escaped_error))
    except Exception as e:
        # If e is a MarkupError, str(e) is the problematic string.
        # We want to print it as plain text after a styled prefix.
        # Print prefix and error message as separate arguments to console.print()
        prefix_text = Text.from_markup(f"[red]Error processing repository '{path_or_url}':[/red] ")
        # Create a Text object from the error string. Rich should handle this safely.
        # Text(str(e).plain) was used before, let's try Text(str(e)) directly.
        error_message_text = Text(str(e))
        console_instance.print(prefix_text, error_message_text)
    return None

# Chat command is already structured correctly by defining a wrapper
# and calling the imported chat_command, so no change needed there.
@app.command("chat")
def chat_cli_wrapper(ctx: typer.Context, 
                     repo_identifier: Optional[str] = typer.Option(None, "--repo", "-r", help="Optional repository context (name from workspace or local path)."),
                     message: Optional[str] = typer.Option(None, "--message", "-m", help="An initial message to send to the chat.")):
    """Start an interactive chat session with DevBridge AI (Amazon Q)."""
    if not hasattr(ctx, "obj") or ctx.obj is None:
        ctx.obj = {"config": Config(), "debug": False, "console": console}
    else:
        ctx.obj["console"] = console # Ensure console is in context
    # display_banner(ctx.obj["config"].app_name, ctx.obj["config"].app_version) # Banner is shown by main callback
    chat_command(ctx, repo_identifier=repo_identifier, initial_message=message)

# Create a subcommand group for repository management
repo_app = typer.Typer(name="repo", help="Manage local repositories in DevBridge workspace")
app.add_typer(repo_app)

@repo_app.command("add")
def add_repo_cli_wrapper(
    ctx: typer.Context,
    path_or_url: str = typer.Argument(..., help="Local directory path (e.g., `/path/to/my-project`) or a Git URL (e.g., `https://github.com/owner/repo.git`) to add/clone into the DevBridge workspace.")
):
    """Add a repository to the workspace by local path or Git URL.
    
    Handles interactive prompts if the target directory in the workspace already exists.
    Remote repositories are cloned into the workspace. Local paths are copied.
    """
    cfg = ctx.obj["config"]
    console_instance = ctx.obj.get("console", console)
    
    added_path = add_repo_command_logic(cfg, path_or_url, console_instance, interactive_overwrite=True)
    
    if not added_path:
        # Error messages are handled by add_repo_command_logic, 
        # but we still need to exit if it failed.
        raise typer.Exit(1)
    # If added_path is True/str, success messages are also handled by add_repo_command_logic

@repo_app.command("list")
def list_repos(ctx: typer.Context):
    """List all repositories currently managed in the DevBridge workspace."""
    cfg = ctx.obj["config"]
    ws_dir = Path(cfg.repo_workspace_dir)
    if not ws_dir.exists():
        typer.echo("[yellow]No workspace directory found.")
        return
    for d in ws_dir.iterdir():
        if d.is_dir():
            typer.echo(f"- {d.name}")

@repo_app.command("remove")
def remove_repo(ctx: typer.Context, name: str = typer.Argument(..., help="Name of the repository (as listed by `devbridge repo list`) to remove from the workspace.")):
    """Remove a repository and its files from the DevBridge workspace."""
    cfg = ctx.obj["config"]
    ws_dir = Path(cfg.repo_workspace_dir)
    target = ws_dir / name
    if not target.exists():
        typer.echo(f"[red]Repo not found: {target}")
        raise typer.Exit(1)
    import shutil
    shutil.rmtree(target)
    typer.echo(f"Removed repo '{name}' from workspace.")

if __name__ == "__main__":
    app()