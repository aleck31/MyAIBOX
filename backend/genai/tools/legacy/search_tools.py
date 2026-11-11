import os
import time
import httpx
import wikipedia
from ddgs import DDGS
from cachetools import TTLCache
from .. import logger


# Constants
CACHE_TTL = 86400  # Cache for 1 day
CACHE_MAX_SIZE = 1000  # Maximum number of cached responses
MAX_SEARCH_RESULTS = 10  # Maximum number of search results to return

# Create cache for responses
wiki_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)
google_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)

def _get_wikipedia_page_and_summary(title, sentences=6):
    """Helper function to get Wikipedia page and summary
    
    Args:
        title: The title to search for
        sentences: Number of sentences for summary
        
    Returns:
        tuple: (page, summary) or (None, None) if not found
    """
    try:
        # Clean up the title to avoid common errors
        clean_title = title.strip()

        # Try with auto_suggest first
        try:
            page = wikipedia.page(clean_title, auto_suggest=True)
            summary = wikipedia.summary(clean_title, sentences=sentences, auto_suggest=True)
            return page, summary
        except wikipedia.PageError:
            # If that fails, try a direct search
            search_results = wikipedia.search(clean_title, results=1)
            if search_results:
                page = wikipedia.page(search_results[0], auto_suggest=False)
                summary = wikipedia.summary(search_results[0], sentences=sentences, auto_suggest=False)
                return page, summary
            return None, None
    except (wikipedia.PageError, wikipedia.DisambiguationError):
        return None, None
    except Exception as e:
        logger.error(f"Error getting Wikipedia page: {e}")
        return None, None

def search_wikipedia(query: str, num_results: int = 3, language: str = "en"):
    """Search Wikipedia and return relevant information
    
    Args:
        query: The search query
        num_results: Number of results to return (default: 3)
        language: Wikipedia language edition (default: "en")
        
    Returns:
        dict: Contains search results and article content
    """
    # Check cache first
    cache_key = f"{query}:{language}"
    if cache_key in wiki_cache:
        cached_result = wiki_cache[cache_key]
        cached_result["cached"] = True
        return cached_result
    
    try:
        # Set language
        wikipedia.set_lang(language)

        # Search for articles
        search_results = wikipedia.search(query, results=num_results)
        
        if not search_results:
            return {
                "query": query,
                "results": [],
                "content": f"No Wikipedia articles found for '{query}'."
            }
        
        # Try the first search result
        page, summary = _get_wikipedia_page_and_summary(search_results[0])
        
        # If first result fails, try the original query
        if not page and not summary:
            page, summary = _get_wikipedia_page_and_summary(query)
        
        # If we have a page and summary, return the result
        if page and summary:
            result = {
                "query": query,
                "results": search_results,
                "title": page.title,
                "url": page.url,
                "content": summary,
                "timestamp": time.time()
            }
            wiki_cache[cache_key] = result
            return result
            
        # Handle disambiguation
        try:
            # This will raise DisambiguationError if it's a disambiguation page
            wikipedia.page(search_results[0])
        except wikipedia.DisambiguationError as e:
            if e.options:
                # Try the first disambiguation option
                page, summary = _get_wikipedia_page_and_summary(e.options[0])
                if page and summary:
                    result = {
                        "query": query,
                        "results": e.options[:num_results],
                        "title": page.title,
                        "url": page.url,
                        "content": summary,
                        "disambiguation": True,
                        "timestamp": time.time()
                    }
                    wiki_cache[cache_key] = result
                    return result
                else:
                    return {
                        "query": query,
                        "results": e.options[:num_results],
                        "content": f"Found disambiguation options for '{query}', but couldn't retrieve a specific article.",
                        "disambiguation": True,
                        "timestamp": time.time()
                    }
        
        # If we get here, we found search results but couldn't get a specific article
        return {
            "query": query,
            "results": search_results,
            "content": f"Found search results for '{query}', but couldn't retrieve a specific article.",
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Wikipedia search error: {e}")
        return {
            "query": query,
            "error": f"Failed to search Wikipedia: {str(e)}"
        }

EXA_SEARCH_URL = "https://api.exa.ai/search"


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in text)


def _search_exa(query: str, num_results: int, api_key: str) -> list:
    """Exa web search, with a short highlight per result as the description."""
    resp = httpx.post(EXA_SEARCH_URL, headers={"x-api-key": api_key}, timeout=20,
                      json={"query": query, "numResults": num_results, "contents": {"highlights": {"numSentences": 3}}})
    resp.raise_for_status()
    return [{"title": r.get("title") or "", "url": r.get("url") or "",
             "description": " ".join(r.get("highlights") or [])[:600]} for r in resp.json().get("results", [])]


def _search_ddgs(query: str, num_results: int) -> list:
    """Free fallback. Region "wt-wt" makes ddgs query wt.wikipedia.org, which does not exist (DNS error), so the
    region follows the query's script instead."""
    region = "cn-zh" if _has_cjk(query) else "us-en"
    with DDGS(timeout=15) as ddgs:
        found = list(ddgs.text(query, max_results=num_results, region=region))
    return [{"title": r.get("title", ""), "url": r.get("href", ""), "description": r.get("body", "")} for r in found]


def search_internet(query: str, num_results: int = 6, language: str = "en"):
    """Search the web and return relevant results (title, url, description).

    Uses Exa when EXA_API_KEY is set. The free DuckDuckGo scraper is only a fallback: from this server it finds
    nothing for most queries ("No results found", Chinese queries especially), and the model then kept retrying
    with new wording for minutes.
    """
    cache_key = f"{query}:{language}"
    if cache_key in google_cache:
        cached_result = google_cache[cache_key]
        cached_result["cached"] = True
        return cached_result

    num_results = min(num_results, MAX_SEARCH_RESULTS)
    api_key = os.getenv("EXA_API_KEY", "").strip()
    try:
        results = _search_exa(query, num_results, api_key) if api_key else _search_ddgs(query, num_results)
    except Exception as e:
        logger.error(f"Web search error ({'exa' if api_key else 'ddgs'}): {e}")
        return {"query": query, "error": f"Search failed: {e}"}

    result = {"query": query, "results": results, "timestamp": time.time()}
    if results:
        google_cache[cache_key] = result
    return result

# Tool specification in Bedrock format
list_of_tools_specs = [
    {
        "toolSpec": {
            "name": "search_wikipedia",
            "description": "Search Wikipedia and retrieve information about a topic. Use this when asked to find factual information, explanations, or background on specific topics, people, places, events, or concepts. This tool provides access to Wikipedia's encyclopedia content.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query for Wikipedia"
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of search results to return (default: 3)",
                            "default": 3
                        },
                        "language": {
                            "type": "string",
                            "description": "Wikipedia language edition (default: 'en')",
                            "default": "en"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "search_internet",
            "description": "Search the web and retrieve results (title, URL, short excerpt) for a query. Use this to find current information: products, prices, specifications, news, or topics not covered in Wikipedia. Open a result with get_text_from_url when the excerpt is not enough.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of search results to return (default: 6, max: 10)",
                            "default": 6
                        },
                        "language": {
                            "type": "string",
                            "description": "Search language (default: 'en')",
                            "default": "en"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    }
]
