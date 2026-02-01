"""Tavily web search tool for genealogy research - backup for MCP web_search."""

import logging
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional

import httpx
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger("treepilot.tools.tavily")


class LRUTTLCache:
    """LRU cache with TTL expiration for web search results.
    
    Args:
        max_size: Maximum number of entries (default 1000, generous for local use)
        ttl_seconds: Time-to-live in seconds (default 3600 = 1 hour)
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, tuple[str, datetime]] = OrderedDict()
        self._max_size = max_size
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def _make_key(self, query: str, max_results: int) -> str:
        """Create cache key from query parameters."""
        return f"{query.lower().strip()}:{max_results}"
    
    def get(self, query: str, max_results: int) -> Optional[str]:
        """Get cached result if exists and not expired."""
        key = self._make_key(query, max_results)
        
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        
        # Check TTL expiration
        if datetime.now() - timestamp > self._ttl:
            del self._cache[key]
            logger.debug(f"Cache entry expired for: '{query}'")
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        logger.debug(f"Cache hit for: '{query}'")
        return value
    
    def set(self, query: str, max_results: int, value: str) -> None:
        """Store result in cache with LRU eviction."""
        key = self._make_key(query, max_results)
        
        # If key exists, update and move to end
        if key in self._cache:
            self._cache[key] = (value, datetime.now())
            self._cache.move_to_end(key)
            return
        
        # Evict oldest entries if at capacity
        while len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Cache evicted oldest entry: '{oldest_key}'")
        
        # Add new entry
        self._cache[key] = (value, datetime.now())
        logger.debug(f"Cache stored result for: '{query}'")
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        logger.info("Cache cleared")
    
    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)


# Module-level cache instance (shared across requests for server lifetime)
_search_cache = LRUTTLCache(max_size=1000, ttl_seconds=3600)


class TavilySearchParams(BaseModel):
    """Parameters for Tavily web search."""
    query: str = Field(
        description="Search query for genealogy research. Can include names, dates, locations, or topics."
    )
    max_results: int = Field(
        default=10, 
        ge=1, 
        le=20,
        description="Maximum number of search results to return (1-20)"
    )


TAVILY_API_URL = "https://api.tavily.com/search"


@define_tool(
    description="Backup web search using Tavily API for genealogy research. "
    "Use this tool when #web_search is unavailable or returns errors. "
    "Searches the web for ancestry databases, family histories, immigration records, "
    "historical documents, obituaries, and genealogy resources. "
    "Returns relevant web pages with titles, URLs, and content snippets."
)
async def search_web_tavily(params: TavilySearchParams) -> str:
    """Search the web using Tavily API for genealogy research."""
    
    logger.info(f"Tavily web search for: '{params.query}' (max_results: {params.max_results})")
    
    # Check cache first
    cached_result = _search_cache.get(params.query, params.max_results)
    if cached_result:
        logger.info(f"Returning cached result for: '{params.query}'")
        return cached_result
    
    # Check for API key
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.error("TAVILY_API_KEY not configured")
        return (
            "## ❌ Tavily API Key Not Configured\n\n"
            "The Tavily web search backup is not available because `TAVILY_API_KEY` "
            "environment variable is not set.\n\n"
            "To enable this backup search:\n"
            "1. Sign up at https://tavily.com to get a free API key\n"
            "2. Add `TAVILY_API_KEY=your_key_here` to your `.env` file\n"
            "3. Restart the server"
        )
    
    # Build request payload
    payload = {
        "api_key": api_key,
        "query": params.query,
        "max_results": params.max_results,
        "search_depth": "advanced",  # More thorough search
        "include_answer": True,  # Include AI-generated summary
        "include_raw_content": False,  # Don't include full page content
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "TreePilot/1.0 (Genealogy Research Agent)",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.debug(f"Querying Tavily API: {TAVILY_API_URL}")
            response = await client.post(
                TAVILY_API_URL,
                json=payload,
                headers=headers,
            )
            
            logger.debug(f"Tavily response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"Tavily search failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg += f": {error_data['error']}"
                except Exception:
                    pass
                logger.warning(error_msg)
                return f"## ❌ Web Search Error\n\n{error_msg}"
            
            data = response.json()
            
    except httpx.TimeoutException:
        logger.warning("Tavily search timed out")
        return "## ❌ Web Search Timeout\n\nThe search request timed out. Please try again."
    except httpx.RequestError as e:
        logger.warning(f"Tavily request error: {e}")
        return f"## ❌ Web Search Error\n\nFailed to connect to search service: {e}"
    
    # Extract results
    results = data.get("results", [])
    answer = data.get("answer", "")
    
    if not results:
        no_results_msg = f"No web results found for '{params.query}'"
        logger.info(no_results_msg)
        return f"## Web Search Results\n\n*{no_results_msg}*"
    
    # Format output
    output = f"## Web Search Results\n"
    output += f"*Found {len(results)} results for '{params.query}'*\n\n"
    
    # Include AI-generated answer summary if available
    if answer:
        output += f"### Summary\n{answer}\n\n"
    
    output += "### Sources\n\n"
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        content = result.get("content", "")
        score = result.get("score", 0)
        
        # Truncate content snippet
        if content and len(content) > 300:
            content = content[:300] + "..."
        
        output += f"**{i}. [{title}]({url})**\n"
        if content:
            output += f"{content}\n"
        output += "\n"
    
    # Cache the successful result
    _search_cache.set(params.query, params.max_results, output)
    logger.info(f"Tavily search returned {len(results)} results for: '{params.query}'")
    
    return output
