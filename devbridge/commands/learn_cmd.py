"""
This module implements the 'learn' command for DevBridge.
It fetches documentation from a specified repository identifier (URL or slug),
converts it to Markdown, and displays it.
"""
import asyncio
import click
from rich.console import Console
from rich.markdown import Markdown
import time # For simple timeout measurement if needed
import requests
from typing import Optional
from pathlib import Path

# Instead of requests, we'll use our new utilities
# import requests # REMOVE
# from requests.exceptions import RequestException # REMOVE

from devbridge.utils.deepwiki_helpers import normalize_repo_identifier, construct_deepwiki_url
from devbridge.utils.http_crawler import crawl as crawl_pages, CrawlResult
from devbridge.utils.html_to_markdown import html_to_markdown

# DEEPWIKI_MCP_URL = "http://localhost:3000/mcp" # REMOVE
# REQUEST_TIMEOUT_SECONDS = 30 # REMOVE - timeout will be handled by crawler if necessary

console = Console()

async def learn_command_async(
    repo_identifier: str, 
    mode: str = "aggregate", 
    max_depth: int = 1, # 0 for root page only, 1 for root + 1 level of links, etc.
    verbose: bool = False,
    output_file: Optional[Path] = None,
    # New parameters matching the crawler's capabilities
    user_agent: str = "DevBridgeBot/0.1", # Default user agent
    respect_robots_txt: bool = True,      # Default to respecting robots.txt
    crawl_retry_limit: int = 2,           # Default retry limit for crawler fetches
    crawl_backoff_base_ms: int = 500    # Default backoff base for crawler fetches
) -> None:
    """
    Asynchronously fetches documentation from a repository identifier, processes it,
    and displays it as Markdown.
    """
    start_time = time.monotonic()

    with console.status(f"[bold green]Processing '{repo_identifier}'...") as status:
        normalized_id = normalize_repo_identifier(repo_identifier)
        if not normalized_id:
            console.print(f"[bold red]Error: Could not normalize repository identifier: '{repo_identifier}'")
            return
        
        status.update(f"Normalized to '{normalized_id}'. Constructing URL...")
        target_url = construct_deepwiki_url(normalized_id) # Assuming default deepwiki.com base

        if not target_url:
            console.print(f"[bold red]Error: Could not construct a valid URL from '{normalized_id}'.")
            return

        if verbose:
            console.print(f"Target URL: {target_url}")
            console.print(f"Crawl mode: {mode}, Max depth: {max_depth}")
            console.print(f"[dim]Max depth: {max_depth}[/dim]")
            console.print(f"[dim]User-Agent: {user_agent}[/dim]")
            console.print(f"[dim]Respect robots.txt: {respect_robots_txt}[/dim]")
            console.print(f"[dim]Crawl Retry Limit: {crawl_retry_limit}[/dim]")
            console.print(f"[dim]Crawl Backoff Base (ms): {crawl_backoff_base_ms}[/dim]")

        status.update(f"Fetching content from {target_url} (depth: {max_depth})...")
        
        console.print(f"Attempting to fetch Deepwiki content for: [cyan]{repo_identifier}[/cyan]")
        console.print(f"Constructed URL: [link={target_url}]{target_url}[/link]")
        console.print(f"Mode: [yellow]{mode}[/yellow]")

        json_payload = {
            "action": "deepwiki_fetch",
            "parameters": {
                "url": target_url,
                "mode": mode
            }
        }

        try:
            # Define a progress callback for the crawler if verbose
            async def _progress_callback(data: dict):
                if verbose:
                    progress_type = data.get("type", "info")
                    if progress_type == "progress":
                        # Shorten URL for status message if too long
                        url_to_show = data.get('url', '')
                        if len(url_to_show) > 50:
                            url_to_show = url_to_show[:25] + "..." + url_to_show[-22:]
                        status_msg = f"Crawling: {url_to_show} ({data.get('bytes',0)}B, {data.get('fetched_count',0)} fetched, {data.get('queue_size',0)} queued)"
                        status.update(status_msg)
                    elif progress_type == "error":
                        console.print(f"[yellow]Crawler error for {data.get('url', '')}: {data.get('message', data.get('status', 'Unknown error'))}")
            
            crawl_result: CrawlResult = await crawl_pages(
                root_url=target_url,
                max_depth=max_depth,
                emit_progress=_progress_callback if verbose else None,
                user_agent=user_agent, 
                respect_robots_txt=respect_robots_txt,
                retry_limit=crawl_retry_limit,
                backoff_base_ms=crawl_backoff_base_ms
            )

            if verbose:
                console.print(f"Crawl finished in {crawl_result.elapsed_ms:.2f} ms. Fetched {len(crawl_result.html_contents)} pages, {crawl_result.total_bytes} bytes.")
                if crawl_result.errors:
                    console.print("[yellow]Crawler encountered errors:")
                    for err_url, err_msg in crawl_result.errors.items():
                        console.print(f"  - {err_url}: {err_msg}")
            
            if not crawl_result.html_contents:
                if not crawl_result.errors: # No content and no specific crawl errors
                    console.print(f"[yellow]No HTML content found for '{target_url}'. The page might be empty or not text/html.")
                else: # Errors were already printed if verbose, or list them now
                    console.print(f"[yellow]No HTML content successfully fetched for '{target_url}'. Check crawler errors above or run with --verbose.")
                    if not verbose and crawl_result.errors:
                         console.print("[yellow]Crawler errors:")
                         for err_url, err_msg in crawl_result.errors.items():
                            console.print(f"  - {err_url}: {err_msg}")
                return

            status.update("Converting HTML to Markdown...")
            
            final_markdown_parts = []
            if mode == "aggregate":
                all_html_for_aggregate = []
                # For aggregate mode, we need a defined order if possible.
                # The deepwiki-mcp crawler might have a specific order based on links.
                # Our current simple crawler stores in a dict (unordered).
                # For now, just join them. A more sophisticated approach might sort by URL path.
                sorted_urls = sorted(crawl_result.html_contents.keys())

                for i, url in enumerate(sorted_urls):
                    html_doc = crawl_result.html_contents[url]
                    if verbose:
                        console.print(f"Converting page: {url} to Markdown for aggregation...")
                    # Add a title/separator for aggregated content
                    # The h1 from the page will be the primary title. This adds context.
                    if len(sorted_urls) > 1:
                         final_markdown_parts.append(f"\n---\n*Source URL: {url}*\n\n")
                    md_content = html_to_markdown(html_doc, mode="aggregate", base_url=url)
                    final_markdown_parts.append(md_content)
                final_markdown = "\n".join(final_markdown_parts)
            else: # mode == "pages" (or any other mode, treated as individual pages for now)
                # Display first page found, or allow selection later?
                # For now, let's display content of the root_url if available, else the first one.
                page_to_display_url = target_url
                if target_url not in crawl_result.html_contents and crawl_result.html_contents:
                    page_to_display_url = list(crawl_result.html_contents.keys())[0]
                
                if page_to_display_url in crawl_result.html_contents:
                    html_doc = crawl_result.html_contents[page_to_display_url]
                    if verbose:
                        console.print(f"Converting page: {page_to_display_url} to Markdown (pages mode display)...")
                    final_markdown = html_to_markdown(html_doc, mode="pages", base_url=page_to_display_url)
                    if len(crawl_result.html_contents) > 1 and verbose:
                        console.print(f"[dim]Note: {len(crawl_result.html_contents)} pages were fetched. Displaying content from {page_to_display_url}. Other pages not shown in this mode.[/dim]")
                else:
                    console.print(f"[yellow]Target page {page_to_display_url} not found in fetched content.")
                    return

            status.update("Displaying content...")
            console.print(Markdown(final_markdown))

        except asyncio.TimeoutError: # Should be handled by crawler if it implements timeout
            console.print(f"[bold red]Error: Timeout while processing '{repo_identifier}'. The operation took too long.")
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred while processing '{repo_identifier}':")
            console.print(f"[red]{type(e).__name__}: {str(e)}")
            if verbose:
                import traceback
                console.print("[dim]--- Traceback ---[/dim]")
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
                console.print("[dim]--- End Traceback ---[/dim]")
        finally:
            end_time = time.monotonic()
            if verbose:
                console.print(f"Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == '__main__':
    # Example of how to call this command programmatically (for testing)
    # Note: Click commands are usually run via the CLI entry point.
    class MockContext:
        def __init__(self, params):
            self.params = params
        def invoke(*args, **kwargs):
            pass # Simplified for this example
    
    # Simulate Click invocation for testing the async function
    # This is not a direct CLI call, but tests the async orchestrator
    async def test_run():
        console.print("[bold yellow]Running test for learn_command_async...[/bold yellow]")
        # Test 1: Aggregate mode (mocked crawler will provide content)
        await learn_command_async("http://example.com/root", mode="aggregate", max_depth=1, verbose=True)
        console.print("\n[bold yellow]Test 2: Pages mode...[/bold yellow]")
        # Test 2: Pages mode (mocked crawler, specific page)
        await learn_command_async("http://example.com/page1", mode="pages", max_depth=0, verbose=True)
        console.print("\n[bold yellow]Test 3: Non-existent...[/bold yellow]")
        # Test 3: Non-existent page (mocked crawler will return error or no content)
        await learn_command_async("http://example.com/nonexistent", mode="aggregate", max_depth=0, verbose=True)

    # asyncio.run(test_run())
    # To run CLI for manual testing: python -m devbridge.commands.learn_cmd someuser/somerepo --verbose
    # (ensure PYTHONPATH is set or devbridge is installed)
    pass # Keep if __name__ == '__main__' for potential direct script testing 