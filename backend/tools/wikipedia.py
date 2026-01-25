"""Wikipedia search tool for biographical information."""

import logging
import httpx
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger("treepilot.tools.wikipedia")


class WikipediaParams(BaseModel):
    """Parameters for Wikipedia search."""
    query: str = Field(description="Search term - can be a person's full name, surname only, family name, location, or any topic. For surname/family searches, just use the surname to find articles about notable people with that name or family histories.")


@define_tool(description="Search Wikipedia for biographical and historical information. Supports flexible queries: full names, surnames/family names only, locations, or topics. For surname searches, finds articles about notable people with that name or family histories. Returns article summaries and key facts.")
async def search_wikipedia(params: WikipediaParams) -> str:
    """Search Wikipedia for information about a person or topic."""
    
    logger.info(f"Searching Wikipedia for: '{params.query}'")
    
    # First, search for the article
    search_url = "https://en.wikipedia.org/w/api.php"
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": params.query,
        "format": "json",
        "srlimit": 3,
    }
    
    headers = {
        "User-Agent": "TreePilot/1.0 (https://github.com/treepilot; treepilot@example.com) httpx"
    }
    
    async with httpx.AsyncClient() as client:
        # Search for matching articles
        logger.debug(f"Querying Wikipedia API: {search_url}")
        response = await client.get(search_url, params=search_params, headers=headers)
        data = response.json()
        
        if not data.get("query", {}).get("search"):
            logger.info(f"No Wikipedia articles found for '{params.query}'")
            return f"No Wikipedia articles found for '{params.query}'"
        
        # Get the top result
        top_result = data["query"]["search"][0]
        title = top_result["title"]
        logger.info(f"Found Wikipedia article: '{title}'")
        
        # Fetch the summary using the REST API
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
        
        logger.debug(f"Fetching article summary from: {summary_url}")
        summary_response = await client.get(summary_url, headers=headers)
        
        if summary_response.status_code != 200:
            logger.warning(f"Failed to fetch summary for '{title}', status: {summary_response.status_code}")
            return f"Found article '{title}' but could not fetch summary."
        
        logger.debug(f"Successfully retrieved Wikipedia summary for '{title}'")
        
        summary_data = summary_response.json()
        
        # Format the response
        result = f"**{summary_data.get('title', title)}**\n\n"
        result += f"{summary_data.get('extract', 'No summary available.')}\n\n"
        
        if summary_data.get("description"):
            result += f"*Description: {summary_data['description']}*\n\n"
        
        result += f"[Read more on Wikipedia]({summary_data.get('content_urls', {}).get('desktop', {}).get('page', '')})"
        
        return result
