"""
Handles HTML to Markdown conversion using BeautifulSoup and Markdownify.
"""
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup, Comment, NavigableString # Added specific imports
from markdownify import MarkdownConverter # Added
from urllib.parse import urljoin, urlparse

class CustomMarkdownConverter(MarkdownConverter):
    """Custom converter to handle specific tags or attributes if needed."""
    def __init__(self, **options):
        super().__init__(**options)
        # Example: Convert <details> and <summary> to a Markdown-friendly format
        # self.convert_details = self.convert_details_tag
        # self.convert_summary = self.convert_summary_tag

    def convert_pre(self, el, text, convert_as_inline):
        """Override to handle <pre> tags, especially for code blocks."""
        if not text.strip():
            return ''
        
        # Check if there's a <code> tag inside <pre>
        code_tag = el.find('code')
        lang = ''
        if code_tag:
            # Try to get language from class (e.g., class="language-python")
            classes = code_tag.get('class', [])
            for cls in classes:
                if cls.startswith('language-'):
                    lang = cls.replace('language-', '', 1)
                    break
                elif cls.startswith('lang-'):
                    lang = cls.replace('lang-', '', 1)
                    break
        else:
            # If no <code>, check <pre> itself for language class
            classes = el.get('class', [])
            for cls in classes:
                if cls.startswith('language-'):
                    lang = cls.replace('language-', '', 1)
                    break
                elif cls.startswith('lang-'):
                    lang = cls.replace('lang-', '', 1)
                    break
        
        # Strip leading/trailing newlines from the code block itself
        # text = text.strip('\n') # markdownify already handles this well generally
        return f"```{lang}\n{text}\n```\n\n"

    # def convert_details_tag(self, el, text, convert_as_inline):
    #     return f"<details>\n<summary>{el.find('summary').get_text(strip=True) if el.find('summary') else 'Details'}</summary>\n\n{text.strip()}\n</details>\n\n"

    # def convert_summary_tag(self, el, text, convert_as_inline):
    #     return "" # Handled by convert_details_tag

    def convert_img(self, el, text, convert_as_inline):
        """Convert <img> tags to Markdown image syntax with absolute URLs if possible."""
        alt = el.get('alt', '')
        src = el.get('src', '')
        title = el.get('title', '')

        if not src: # Should not happen if src is required by your schema
            return ""

        # Try to make src absolute if a base_url was passed in options
        base_url = self.options.get('base_url')
        if base_url:
            src = urljoin(base_url, src)

        title_part = f' "{title}"' if title else ''
        return f'![{alt}]({src}{title_part})'

    def convert_a(self, el, text, parent_tags=None, **kwargs):
        """Override to ensure links are absolute if base_url is available."""
        
        # convert_as_inline is not directly passed by the problematic call path.
        # We need to decide a default or get it from kwargs if markdownify *sometimes* passes it.
        # For now, let's assume False as a default for this path if not in kwargs.
        convert_as_inline = kwargs.get('convert_as_inline', False)

        href = el.get('href')
        if not href:
            return text

        # If it's an anchor link, keep it as is
        if href.startswith('#'):
            # Call super with its expected args (el, text, convert_as_inline)
            return super().convert_a(el, text, convert_as_inline) 

        base_url = self.options.get('base_url')
        if base_url:
            actual_href = urljoin(base_url, href)
            el['href'] = actual_href # Update the element for the super call
        
        # Call super with its expected args (el, text, convert_as_inline)
        return super().convert_a(el, text, convert_as_inline)

def sanitize_html_content(html_content: str, base_url: Optional[str] = None) -> BeautifulSoup:
    """
    Parses HTML and removes unwanted elements like <script>, <style>, comments.
    Also attempts to make image and link URLs absolute if base_url is provided.
    """
    soup = BeautifulSoup(html_content, 'lxml') # Use lxml for performance

    # Elements to remove completely
    for tag_name in ['script', 'style', 'noscript', 'link', 'meta', 'header', 'footer', 'nav']:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Attempt to make key URLs absolute (markdownify might also do this for 'a' and 'img')
    if base_url:
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            if href and not urlparse(href).scheme and not href.startswith('#'):
                tag['href'] = urljoin(base_url, href)
        
        for tag in soup.find_all('img', src=True):
            src = tag['src']
            if src and not urlparse(src).scheme:
                tag['src'] = urljoin(base_url, src)

    # Further fine-grained sanitization (e.g., allowed attributes) can be added here
    # For now, this covers common unwanted elements.
    return soup

def rewrite_internal_links_for_mode(soup: BeautifulSoup, mode: str, current_page_url: str) -> None:
    """
    Rewrites internal (same-domain) links based on the specified mode.
    - "aggregate": Converts links to anchors (#target-path).
    - "pages": Converts links to relative .md files (target-path.md).
    Assumes current_page_url is the URL of the document being processed.
    """
    if not current_page_url:
        return

    parsed_current_url = urlparse(current_page_url)
    current_base_netloc = parsed_current_url.netloc

    for link_tag in soup.find_all('a', href=True):
        original_href = link_tag.get('href')
        if not original_href or original_href.startswith('#'): # Skip empty or existing fragment links
            continue

        absolute_link = urljoin(current_page_url, original_href)
        parsed_absolute_link = urlparse(absolute_link)

        # Only process links on the same domain/subdomain
        if parsed_absolute_link.netloc == current_base_netloc:
            path_part = parsed_absolute_link.path.strip('/')
            query_part = parsed_absolute_link.query

            if mode == "aggregate":
                # Create an anchor from the path. Replace / with - and ensure uniqueness if needed.
                # This is a simple version; deepwiki-mcp might have more robust anchor generation.
                new_href = "#" + path_part.replace('/', '-')
                if query_part: # Append query as part of the anchor, sanitized
                    new_href += "-" + query_part.replace('=', '-').replace('&', '-')
                link_tag['href'] = new_href
            elif mode == "pages":
                # Convert to .md file link, keeping path structure.
                # For ../ type links, urljoin should handle resolution correctly against current_page_url.
                # We need the path relative to the current page's directory if possible, or just the full path.md.
                # For simplicity, let's assume we make flat .md files from paths.
                new_href = path_part + ".md"
                if query_part:
                    new_href += "?" + query_part # Keep query parameters if any
                link_tag['href'] = new_href
            # else: no rewrite for other modes or if it's an external link already absolute

def html_to_markdown(
    html_content: str, 
    mode: str = "aggregate", 
    base_url: Optional[str] = None # URL of the page itself, for resolving its relative links
) -> str:
    """
    Converts HTML content to Markdown using BeautifulSoup for sanitization/preprocessing
    and Markdownify for the main conversion.
    """
    # 1. Parse and sanitize the HTML, make relative links absolute to their page context
    soup = sanitize_html_content(html_content, base_url)

    # 2. Rewrite internal links based on mode (aggregate/pages)
    # This step assumes `base_url` is the URL of the *current page* to correctly resolve its internal links.
    if base_url:
        rewrite_internal_links_for_mode(soup, mode, base_url)
    
    # 3. Convert the processed BeautifulSoup object to Markdown
    converter_options = {
        'strip': ['script', 'style'], 
        'heading_style': 'atx',
        'bullets': '-',
        'code_language_callback': lambda el: el.get('class', [None])[0] if el.get('class') and el.get('class')[0].startswith('language-') else None,
        'base_url': base_url
    }
    # Use stock MarkdownConverter
    # converter = CustomMarkdownConverter(**converter_options)
    converter = MarkdownConverter(**converter_options) # STOCK CONVERTER
    
    markdown_output = converter.convert_soup(soup)
    
    return markdown_output

# Example Usage:
if __name__ == "__main__":
    sample_html_page1 = """
    <html><head><title>Page 1</title></head><body>
        <h1>Page One</h1>
        <nav>Internal nav <a href="/page2.html">Next</a></nav>
        <p>Content of <b>page one</b>.</p>
        <a href="page2.html">Relative Link to Page 2</a>
        <a href="/archive/page3.html">Absolute Path Link to Page 3</a>
        <a href="http://example.com/external">External Link</a>
        <a href="#section1">Anchor Link</a>
        <img src="image1.png" alt="Image 1">
        <img src="/images/image2.png" alt="Image 2">
        <pre><code class="language-python">def hello():\n    print("Hello")</code></pre>
        <pre class="lang-javascript">console.log('hi');</pre>
        <script>console.log("sneaky script")</script>
        <!-- This is a comment -->
    </body></html>
    """

    base_url_page1 = "https://docs.example.com/path/to/page1.html"

    print("--- Testing Aggregate Mode ---")
    md_agg = html_to_markdown(sample_html_page1, mode="aggregate", base_url=base_url_page1)
    print("\nMarkdown (Aggregate):")
    print(md_agg)

    print("\n\n--- Testing Pages Mode ---")
    md_pages = html_to_markdown(sample_html_page1, mode="pages", base_url=base_url_page1)
    print("\nMarkdown (Pages):")
    print(md_pages)

    sample_html_details = """
    <details>
        <summary>Click to expand</summary>
        Some hidden details here.
        <a href="another.html">Link inside</a>
    </details>
    """
    print("\n\n--- Testing Details Tag (default markdownify behavior) ---")
    md_details = html_to_markdown(sample_html_details, mode="aggregate", base_url="https://example.com/page.html")
    print(md_details) 