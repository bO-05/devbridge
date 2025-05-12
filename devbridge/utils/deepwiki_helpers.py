"""
Helper functions for Deepwiki integration, such as URL normalization,
validation, and potentially keyword extraction.
"""
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse

# Placeholder for NLP libraries if keyword extraction is implemented later
# e.g., from nltk.tokenize import word_tokenize
# from nltk.corpus import stopwords

def normalize_repo_identifier(identifier: str) -> Optional[str]:
    """
    Normalizes various forms of repository identifiers to a standard
    "user/repo" string, a full https Deepwiki URL, or a potential topic path.
    Returns None if the identifier is invalid or cannot be meaningfully normalized.

    Examples:
    - "user/repo" -> "user/repo"
    - "https://deepwiki.com/user/repo" -> "https://deepwiki.com/user/repo"
    - "https://github.com/user/repo.git" -> "user/repo"
    - "GitHub.com/user/repo.git" -> "user/repo"
    - "owner repo" -> "owner/repo"
    - "library_name" -> "library_name" (caller might use this as a topic path)
    - "multi word phrase" -> "multi-word-phrase" (for topic path)
    - " user / repo part " -> "user/repo-part"
    """
    if not identifier or not identifier.strip():
        return None

    identifier = identifier.strip()
    parsed = urlparse(identifier)

    # 1. Handle full URLs (Deepwiki or common Git providers)
    if parsed.scheme in ['http', 'https'] and parsed.netloc:
        if 'deepwiki' in parsed.netloc.lower():
            path_str = parsed.path.strip('/')
            if not path_str: # e.g. https://deepwiki.com/
                return None # Or return a root indicator if desired
            return urlunparse((parsed.scheme, parsed.netloc, path_str, '', '', ''))

        for domain_keyword in ["github.com", "gitlab.com", "bitbucket.org"]:
            if domain_keyword in parsed.netloc.lower():
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 2:
                    user = path_parts[0] # Preserve case
                    repo = path_parts[1].replace('.git', '') # Preserve case
                    remaining_path_parts = [p.strip().replace(' ', '-') for p in path_parts[2:] if p.strip()] # Preserve case
                    
                    slug_parts = [user, repo]
                    if remaining_path_parts:
                        slug_parts.extend(remaining_path_parts) # Use extend for list
                    
                    # Clean parts before joining: strip spaces from each part and ensure no empty parts
                    cleaned_slug_parts = [p.strip().replace(' ', '-') for p in slug_parts if p.strip()]
                    if len(cleaned_slug_parts) >= 2:
                         return "/".join(cleaned_slug_parts)
                return None

    # 2. Handle domain/path format like "github.com/user/repo" (no scheme)
    if not parsed.scheme: # No http(s)
        for domain_base in ["github.com", "gitlab.com", "bitbucket.org"]:
            domain_keyword_with_slash = domain_base + "/"
            if identifier.lower().startswith(domain_keyword_with_slash.lower()): # Case-insensitive start check
                try:
                    path_str = identifier[len(domain_keyword_with_slash):] # Get path part, preserving its case
                    path_parts = path_str.strip('/').split('/')
                    if len(path_parts) >= 2:
                        user = path_parts[0].strip().replace(' ', '-') # Preserve case, clean spaces
                        repo = path_parts[1].replace('.git', '').strip().replace(' ', '-') # Preserve case, clean spaces
                        
                        remaining_path_list = [
                            p.strip().replace(' ', '-') 
                            for p_idx, p in enumerate(path_parts) 
                            if p_idx > 1 and p.strip()
                        ] # Preserve case, clean spaces
                        remaining_path = "/".join(remaining_path_list)
                        
                        final_parts = [user, repo]
                        if remaining_path:
                            final_parts.append(remaining_path)
                        
                        valid_final_parts = [part for part in final_parts if part] # Ensure no empty parts
                        if len(valid_final_parts) >= 2:
                             return "/".join(valid_final_parts)
                    return None # Invalid path structure after domain
                except Exception:
                    continue # Error processing this rule, try next domain or fall through

    # 3. Handle "user/repo", "user / repo-part", "user/repo/sub/path" (slash-separated slugs)
    if '/' in identifier: # Assumed to be a slug if no scheme/netloc by this point
        parts = [p.strip().replace(' ', '-') for p in identifier.split('/')]
        # Filter out any empty parts that might result from multiple slashes or leading/trailing slashes
        # that weren't caught by the initial strip if they were internal to the split parts.
        cleaned_parts = [part for part in parts if part] # Ensure no empty strings
        if len(cleaned_parts) >= 1: # Allow single part for topics like "topic/" -> "topic"
             # If original was "topic/", split results in ['topic', ''], cleaned is ['topic']
            if len(cleaned_parts) == 1 and identifier.endswith('/'): # like "topic/"
                 return cleaned_parts[0].lower()
            if len(cleaned_parts) >= 2 : # like "user/repo" or "user/repo/sub"
                 return "/".join(cleaned_parts)
            # if only one part and no trailing slash, it's a single term handled later.
            # Example: "user" given to "user/repo" part. This will fall to single term.
            # However, if input was "user/", it becomes "user". If "user/repo", it's fine.

    # 4. Handle "owner repo" or "multi word phrase" (space-separated, no slashes)
    if ' ' in identifier: # No slashes by this point means it's not user/repo etc.
        parts = [p.strip() for p in identifier.split(' ') if p.strip()] # Split by space and strip
        if len(parts) == 2: # "owner repo"
            return f"{parts[0].lower().replace(' ', '-')}/{parts[1].lower().replace(' ', '-')}"
        elif len(parts) > 0: # "multi word phrase for topic"
            return "-".join(parts).lower()
        # else: empty string after split and strip, should have been caught by initial check

    # 5. Handle single keywords (hardcoded examples or general single terms)
    # Ensure it's genuinely a single segment by this point (no slashes, no spaces)
    if '/' not in identifier and ' ' not in identifier:
        lower_id = identifier.lower()
        # Hardcoded common patterns
        if lower_id == "requests": return "psf/requests"
        if lower_id == "django": return "django/django"
        if lower_id == "react": return "facebook/react" # Or just "react" if to be used as a topic
        if lower_id == "vue": return "vuejs/vue"
        if lower_id == "angular": return "angular/angular"
        if lower_id == "python": return "python" # Generic topic
        if lower_id == "boto3": return "boto/boto3"
        
        # If not a special keyword, return the single term, lowercased, as a potential topic
        return lower_id

    return None # Default if no pattern matches or invalid structure


def construct_deepwiki_url(repo_identifier: str, base_deepwiki_url: str = "https://deepwiki.com") -> Optional[str]:
    """
    Constructs a full Deepwiki URL from a normalized repo_identifier.
    A repo_identifier can be "user/repo", "user/repo/subpath", a topic,
    or a pre-existing full Deepwiki URL.
    """
    if not repo_identifier:
        return None
    if not base_deepwiki_url: # Added check for None or empty base_deepwiki_url
        return None

    parsed_id = urlparse(repo_identifier)
    if parsed_id.scheme and parsed_id.netloc:
        # It's already a full URL
        if 'deepwiki' in parsed_id.netloc.lower():
            return repo_identifier # Return as is if it's a Deepwiki URL
        else:
            # If it's a full URL but not Deepwiki, it should have been converted
            # by normalize_repo_identifier (e.g., GitHub to user/repo).
            # If it reaches here as a non-Deepwiki full URL, it's likely an issue.
            return None

    # At this point, repo_identifier should be a path-like string (e.g., "user/repo", "topic", "user/repo/sub/page")
    # Ensure no leading/trailing slashes for clean join with the base URL.
    path_part = repo_identifier.strip('/')
    
    # Ensure base_url also has no trailing slash before joining
    return f"{base_deepwiki_url.rstrip('/')}/{path_part}"


def extract_keywords_from_query(query: str) -> Optional[str]:
    """
    Extracts potential library or technology keywords from a natural language query.
    (Placeholder - requires NLP)
    """
    # Example: "how do I use react with typescript?" -> could extract "react", "typescript"
    # This is a very complex task. For a placeholder:
    print(f"Extracting keywords from query (mock): '{query}'")
    if "react" in query.lower():
        return "react"
    if "python" in query.lower():
        return "python"
    # A real implementation would use NLP techniques like PoS tagging, NER, etc.
    return None

# Example Usage
if __name__ == "__main__":
    ids_to_test = [
        "user/repo",
        " https://deepwiki.com/user/repo/page ",
        "https://github.com/psf/requests.git",
        "requests",
        "not_a_url_or_slug/but/has_slashes",
        "singleword",
        "",
        None,
        "http://anotherdomain.com/user/repo"
    ]

    print("--- Testing normalize_repo_identifier ---")
    for an_id in ids_to_test:
        if an_id is None: # Skip None for normalization input directly
            print(f"Input: None -> Normalized: None (by convention)")
            continue
        normalized = normalize_repo_identifier(an_id)
        print(f"Input: '{an_id}' -> Normalized: '{normalized}'")
        if normalized:
            url = construct_deepwiki_url(normalized)
            print(f"  -> Constructed URL: '{url}'")
        else:
            url_direct = construct_deepwiki_url(an_id) # What if not normalized first?
            print(f"  -> (Direct construct attempt on original '{an_id}'): '{url_direct}'")
        print("---")

    print("\n--- Testing construct_deepwiki_url directly ---")
    id_formats_for_url_construct = [
        "user1/projectA",
        "https://deepwiki.com/user2/projectB",
        "https://anotherwiki.com/user3/projectC", # Should ideally be None or handled by normalize
        "topic_only",
        "psf/requests", # after normalization
    ]
    for identifier in id_formats_for_url_construct:
        dw_url = construct_deepwiki_url(identifier)
        print(f"Identifier: '{identifier}' -> Deepwiki URL: '{dw_url}'")

    print("\n--- Testing keyword extraction (mock) ---")
    queries = [
        "how to use python logging",
        "explain react hooks",
        "what is FastAPI?"
    ]
    for q in queries:
        keyword = extract_keywords_from_query(q)
        print(f"Query: '{q}' -> Keyword: '{keyword}'") 