"""
Handles the crawling of web pages using aiohttp and BeautifulSoup.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Callable, Dict, List, Optional, Set, Tuple, Awaitable
from urllib.parse import urlparse, urljoin, urlunparse

# Add new imports
from urllib.robotparser import RobotFileParser # Standard library
import time # For retry backoff sleep

# Define a list of non-HTML file extensions to skip
NON_HTML_EXTENSIONS = {
    # Styles & Scripts
    '.css', '.js', '.mjs', '.json', '.ts', '.jsx', '.tsx',
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff',
    # Fonts
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    # Documents & Data
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.xml', '.rss', '.atom', '.csv', '.txt', '.rtf', '.md',
    '.yaml', '.yml', '.ini', '.cfg', '.log',
    # Archives
    '.zip', '.tar', '.gz', '.rar', '.7z',
    # Media
    '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.m4a', '.ogg', '.wav',
    # Executables & System
    '.exe', '.dmg', '.apk', '.bin', '.iso', '.img',
    # Other
    '.map', '.webmanifest', '.appcache', '.webarchive', '.bak',
    '.sql', '.db', '.sqlite',
    # Specific to some web frameworks / patterns
    '.php', '.asp', '.aspx', '.jsp', '.cgi',
}

async def fetch_url_content(
    session: aiohttp.ClientSession, 
    url: str, 
    user_agent: str,
    retry_limit: int = 3, 
    backoff_base_ms: int = 300
) -> Tuple[int, str, Dict[str, str]]:
    """
    Fetches a URL using an aiohttp session with retries and backoff.
    Returns status code, text content, and headers.
    """
    request_headers = {"User-Agent": user_agent, "Accept": "text/html,*/*;q=0.8"}
    last_exception = None
    status_code_for_error = 500 # Default error status
    error_message = "Unknown fetch error" # Default error message
    
    for attempt in range(retry_limit + 1):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), headers=request_headers, allow_redirects=True) as response:
                # It's important to read the content before checking status for some error types
                # that might not raise an exception but return an error status.
                content = await response.text(errors='ignore') 
                # Check if the response status indicates success
                response.raise_for_status() # Will raise an HTTPError if status is 400 or 500
                return response.status, content, dict(response.headers)
        except asyncio.TimeoutError as e:
            last_exception = e
            status_code_for_error = 408 # Request Timeout
            error_message = "Request Timeout"
        except aiohttp.ClientResponseError as e: # Handles HTTP errors like 4xx, 5xx
            last_exception = e
            status_code_for_error = e.status
            error_message = f"HTTP Error: {e.status} {e.message}"
            # For 4xx errors, typically don't retry unless specific (e.g. 429 Too Many Requests)
            # For this generic handler, we will retry on 5xx, but for 4xx we might break earlier.
            if 400 <= e.status < 500 and e.status != 408 and e.status != 429: # Example: don't retry on 404
                # print(f"Client error {e.status} for {url}, not retrying.") # Debug
                break # Break from retry loop for client errors like 404
        except aiohttp.ClientConnectionError as e:
            last_exception = e
            status_code_for_error = 503 # Service Unavailable often for connection errors
            error_message = f"Client Connection Error: {type(e).__name__}"
        except aiohttp.ClientError as e: # Other client errors
            last_exception = e
            status_code_for_error = 503 
            error_message = f"Client Error: {type(e).__name__}"
        except Exception as e: 
            last_exception = e
            status_code_for_error = 500 # Internal Server Error for other exceptions
            error_message = f"Generic Fetch Error: {type(e).__name__}"

        if attempt < retry_limit:
            sleep_duration = (backoff_base_ms / 1000) * (2 ** attempt)
            # print(f"Attempt {attempt + 1} failed for {url}: {error_message}. Retrying in {sleep_duration:.2f}s...") # Debug
            await asyncio.sleep(sleep_duration)
        else:
            # print(f"All {retry_limit + 1} attempts failed for {url}. Last error: {error_message}") # Debug
            # This return is after all retries have been exhausted
            return status_code_for_error, f"{error_message} (after {retry_limit + 1} attempts for {url})", {}
            
    # This part is reached if the loop was broken (e.g., by a non-retryable 4xx error)
    return status_code_for_error, f"{error_message} (for {url})", {}

class CrawlResult:
    def __init__(self):
        self.html_contents: Dict[str, str] = {}  # URL -> HTML string
        self.errors: Dict[str, str] = {}       # URL -> Error message
        self.total_bytes: int = 0
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    @property
    def elapsed_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

async def crawl(
    root_url: str,
    max_depth: int = 1,
    emit_progress: Optional[Callable[[Dict], Awaitable[None]]] = None,
    user_agent: str = "DevBridgeBot/0.1",
    respect_robots_txt: bool = True, 
    max_concurrent_tasks: int = 10, # Increased default to 10
    retry_limit: int = 2, 
    backoff_base_ms: int = 500
) -> CrawlResult:
    """
    Crawls web pages starting from root_url up to max_depth.
    Includes robots.txt handling, file extension skipping, and retries for fetches.
    """
    result = CrawlResult()
    result.start_time = asyncio.get_event_loop().time()

    queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
    crawled_urls: Set[str] = set()
    
    parsed_root_url = urlparse(root_url)
    if not parsed_root_url.scheme or not parsed_root_url.netloc:
        if emit_progress: await emit_progress({"type": "error", "message": f"Invalid root_url: {root_url}. Must be absolute."})
        result.errors[root_url] = "Invalid root_url: Must be absolute."
        result.end_time = asyncio.get_event_loop().time()
        return result
        
    base_netloc = parsed_root_url.netloc
    robots_parser: Optional[RobotFileParser] = None

    if respect_robots_txt:
        robots_url_parts = parsed_root_url._replace(path="/robots.txt", query="", fragment="")
        robots_url = urlunparse(robots_url_parts)
        try:
            async with aiohttp.ClientSession() as robots_session:
                r_status, r_content, _ = await fetch_url_content(robots_session, robots_url, user_agent, retry_limit=0)
            if r_status == 200 and r_content:
                robots_parser = RobotFileParser()
                robots_parser.set_url(robots_url) # Important for context
                robots_parser.parse(r_content.splitlines())
                if emit_progress: await emit_progress({"type": "info", "message": f"Successfully parsed robots.txt from {robots_url}"})
            elif emit_progress:
                await emit_progress({"type": "info", "message": f"Could not fetch robots.txt (status {r_status}) from {robots_url}"})
        except Exception as e:
            if emit_progress: await emit_progress({"type": "info", "message": f"Error fetching/parsing robots.txt from {robots_url}: {str(e)}"})

    await queue.put((root_url, 0))
    # Add to crawled_urls *when adding to queue* to prevent re-queueing the same URL
    # if discovered by multiple pages before it's processed.
    crawled_urls.add(root_url) 

    # Use a semaphore to control concurrency more explicitly
    semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async with aiohttp.ClientSession() as session:
        active_processing_tasks: Set[asyncio.Task] = set()

        while True:
            # Try to fetch from queue if semaphore allows and queue has items
            # This loop ensures we fill up to max_concurrent_tasks
            while not queue.empty() and len(active_processing_tasks) < max_concurrent_tasks :
                try:
                    # Non-blocking get to check if we should break and wait for tasks to complete
                    current_url, current_depth = queue.get_nowait() 
                except asyncio.QueueEmpty:
                    break # Queue is empty, break inner loop and wait for tasks or exit

                # Robots.txt check (should be done before acquiring semaphore for this URL)
                if robots_parser and not robots_parser.can_fetch(user_agent, current_url):
                    if emit_progress: await emit_progress({"type": "info", "url": current_url, "message": "Skipped by robots.txt (at queue processing)"})
                    result.errors[current_url] = "Skipped by robots.txt"
                    queue.task_done() # Important if queue.join() is used elsewhere or for tracking
                    continue

                # File extension check (primary check before starting a task for it)
                current_url_path_lower = urlparse(current_url).path.lower()
                if any(current_url_path_lower.endswith(ext) for ext in NON_HTML_EXTENSIONS):
                    if emit_progress: await emit_progress({"type": "info", "url": current_url, "message": f"Skipped due to file extension (at queue processing): {urlparse(current_url).path}"})
                    result.errors[current_url] = f"Skipped due to file extension: {urlparse(current_url).path}"
                    queue.task_done()
                    continue
                
                # Acquire semaphore before creating task
                await semaphore.acquire()
                task = asyncio.create_task(process_single_url(
                    session, current_url, current_depth, max_depth, base_netloc, 
                    result, queue, crawled_urls, emit_progress, user_agent,
                    robots_parser, # Pass robots_parser
                    retry_limit, backoff_base_ms, # Pass retry params
                    semaphore # Pass semaphore to be released in task
                ))
                active_processing_tasks.add(task)
                # Ensure task removes itself from set upon completion
                task.add_done_callback(active_processing_tasks.discard)
            
            if not active_processing_tasks and queue.empty():
                break # All tasks are done and queue is empty

            if active_processing_tasks: # Only wait if there are tasks
                 # Wait for at least one task to complete
                _, pending = await asyncio.wait(active_processing_tasks, return_when=asyncio.FIRST_COMPLETED)
                # active_processing_tasks is already updated by the callback
            else: # No active tasks but queue might not be empty (e.g. if max_concurrent_tasks was 0 or very small)
                 # Or, if all tasks just finished and queue is now empty, this allows loop to break
                 await asyncio.sleep(0.01) # Small sleep to yield control


    result.end_time = asyncio.get_event_loop().time()
    return result

async def process_single_url(
    session: aiohttp.ClientSession, 
    url_to_process: str, 
    depth_of_url: int, 
    max_depth: int,
    base_netloc: str,
    crawl_result_obj: CrawlResult,
    queue_ref: asyncio.Queue,
    crawled_urls_ref: Set[str],
    emit_progress_ref: Optional[Callable[[Dict], Awaitable[None]]],
    user_agent: str,
    robots_parser_ref: Optional[RobotFileParser],
    fetch_retry_limit: int,
    fetch_backoff_base_ms: int,
    semaphore: asyncio.Semaphore # Added semaphore
):
    """Helper function to process a single URL fetch and its links."""
    try:
        if emit_progress_ref:
            await emit_progress_ref({"type": "info", "url": url_to_process, "message": f"Fetching at depth {depth_of_url}"})
        
        status, html_content, response_headers = await fetch_url_content(
            session, url_to_process, user_agent,
            retry_limit=fetch_retry_limit,
            backoff_base_ms=fetch_backoff_base_ms
        )
        content_type = response_headers.get("Content-Type", "").lower()

        if "text/html" not in content_type:
            if emit_progress_ref: await emit_progress_ref({"type": "info", "url": url_to_process, "message": f"Skipped: Not HTML (Content-Type: {content_type})"})
            crawl_result_obj.errors[url_to_process] = f"Skipped: Not HTML (Content-Type: {content_type})"
            return

        if status == 200:
            crawl_result_obj.html_contents[url_to_process] = html_content
            crawl_result_obj.total_bytes += len(html_content.encode('utf-8')) # Approximate
            if emit_progress_ref:
                await emit_progress_ref({
                    "type": "progress", "url": url_to_process, "bytes": len(html_content.encode('utf-8')),
                    "status": status, "fetched_count": len(crawl_result_obj.html_contents), "queue_size": queue_ref.qsize()
                })

            if depth_of_url < max_depth:
                soup = BeautifulSoup(html_content, 'lxml') 
                for link_tag in soup.find_all('a', href=True):
                    href = link_tag['href']
                    if not href or href.startswith('mailto:') or href.startswith('tel:') or href.startswith('javascript:'):
                        continue
                        
                    absolute_link = urljoin(url_to_process, href)
                    parsed_link = urlparse(absolute_link)
                    
                    link_path_lower = parsed_link.path.lower()
                    if any(link_path_lower.endswith(ext) for ext in NON_HTML_EXTENSIONS):
                        if emit_progress_ref: await emit_progress_ref({"type": "info", "url": absolute_link, "message": f"Skipped due to file extension: {parsed_link.path}"})
                        continue

                    if parsed_link.netloc == base_netloc and parsed_link.scheme in ['http', 'https']:
                        normalized_link = urlunparse(parsed_link._replace(fragment=''))
                        
                        if robots_parser_ref and not robots_parser_ref.can_fetch(user_agent, normalized_link):
                            if emit_progress_ref: await emit_progress_ref({"type": "info", "url": normalized_link, "message": "Skipped by robots.txt (discovered link)"})
                            crawl_result_obj.errors[normalized_link] = "Skipped by robots.txt (discovered link)"
                            continue

                        if normalized_link not in crawled_urls_ref:
                            crawled_urls_ref.add(normalized_link)
                            await queue_ref.put((normalized_link, depth_of_url + 1))
        else:
            crawl_result_obj.errors[url_to_process] = f"HTTP Error: {status} - {html_content if html_content else '(No content returned for error)'}"
            if emit_progress_ref: await emit_progress_ref({"type": "error", "url": url_to_process, "status": status, "message": html_content[:100]}) # Send part of content if error
    except Exception as e:
        crawl_result_obj.errors[url_to_process] = f"Processing Error: {type(e).__name__} - {str(e)}"
        if emit_progress_ref: await emit_progress_ref({"type": "error", "url": url_to_process, "message": f"Processing Error: {type(e).__name__} - {str(e)}"})
    finally:
        semaphore.release() # Release semaphore when task is done
        # queue_ref.task_done() # only if using queue.join()


# Example usage (for testing this module directly)
async def main():
    async def _progress(data: Dict):
        progress_type = data.get("type")
        url = data.get('url', '')
        message = data.get('message', '')
        if progress_type == "progress":
            print(f"PROGRESS: Fetched {url} ({data.get('bytes')}B) - Status {data.get('status')}. Total: {data.get('fetched_count')}. Queue: {data.get('queue_size')}")
        elif progress_type == "error":
            print(f"ERROR: URL {url} - Status {data.get('status', '')} Message: {message}")
        else: # "info"
            print(f"INFO: {message} {url}")

    # target = "http://example.com"
    # target = "https://toscrape.com/"
    target = "https://books.toscrape.com/"
    # target = "https://docs.python.org/3/library/asyncio.html"

    print(f"Starting crawl for {target}")
    results = await crawl(target, max_depth=1, emit_progress=_progress, max_concurrent_tasks=5)
    
    print("\n--- Crawl Finished ---")
    print(f"Elapsed time: {results.elapsed_ms:.2f} ms")
    print(f"Total bytes: {results.total_bytes}")
    print(f"Fetched pages: {len(results.html_contents)}")
    
    # Print summary of fetched pages (first 200 chars of first page)
    if results.html_contents:
        first_url = list(results.html_contents.keys())[0]
        print(f"\nContent for {first_url} (first 200 chars):")
        print(results.html_contents[first_url][:200].replace('\n', ' ') + "...")
    
    if results.errors:
        print("\nErrors Encountered:")
        for url, error in results.errors.items():
            print(f"  - {url}: {error}")
    else:
        print("\nNo errors encountered during crawl.")

if __name__ == "__main__":
    # To run this example:
    # Ensure aiohttp, beautifulsoup4, lxml are installed: 
    # pip install aiohttp beautifulsoup4 lxml
    asyncio.run(main()) 