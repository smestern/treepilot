"""Google Books search tool for genealogy and history books."""

import logging
import os
import httpx
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger("treepilot.tools.books")


class BooksParams(BaseModel):
    """Parameters for Google Books search."""
    query: str = Field(description="Search terms (person name, family name, location, topic)")
    category: str | None = Field(default=None, description="Book category filter (e.g., 'genealogy', 'history', 'biography')")


GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


@define_tool(description="Search Google Books for genealogy guides, local histories, biographies, and family history resources. Useful for finding published works about specific families, regions, or time periods.")
async def search_books(params: BooksParams) -> str:
    """Search Google Books for genealogy-related books."""
    
    logger.info(f"Searching Google Books for: '{params.query}' (category: {params.category})")
    
    # Build search query
    search_query = params.query
    if params.category:
        search_query += f" subject:{params.category}"
    
    # Add genealogy-related terms to improve relevance
    if "genealogy" not in search_query.lower() and "history" not in search_query.lower():
        search_query += " (genealogy OR history OR biography OR ancestry)"
    
    logger.debug(f"Final search query: '{search_query}'")
    
    query_params = {
        "q": search_query,
        "maxResults": 10,
        "printType": "books",
        "langRestrict": "en",
    }
    
    # Add API key if available (works without key but with lower rate limits)
    api_key = os.getenv("GOOGLE_BOOKS_API_KEY")
    if api_key:
        query_params["key"] = api_key
    
    headers = {
        "User-Agent": "TreePilot/1.0 (Genealogy Research Agent)"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.debug(f"Querying Google Books API: {GOOGLE_BOOKS_API}")
        response = await client.get(
            GOOGLE_BOOKS_API,
            params=query_params,
            headers=headers,
        )
        
        logger.debug(f"Google Books response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"Google Books search failed with status {response.status_code}")
            return f"Google Books search failed with status {response.status_code}"
        
        data = response.json()
        total_items = data.get("totalItems", 0)
        items = data.get("items", [])
        logger.info(f"Google Books returned {total_items} total results, {len(items)} items in response")
        
        if not items:
            logger.info(f"No books found for '{params.query}'")
            return f"No books found for '{params.query}'"
        
        # Format results
        output = f"## Book Results\n"
        output += f"*Found {total_items} books related to '{params.query}'*\n\n"
        
        for item in items:
            volume_info = item.get("volumeInfo", {})
            
            title = volume_info.get("title", "Unknown Title")
            subtitle = volume_info.get("subtitle", "")
            authors = volume_info.get("authors", ["Unknown Author"])
            published_date = volume_info.get("publishedDate", "Unknown")
            description = volume_info.get("description", "")
            
            # Truncate description
            if description and len(description) > 300:
                description = description[:300] + "..."
            
            categories = volume_info.get("categories", [])
            preview_link = volume_info.get("previewLink", "")
            info_link = volume_info.get("infoLink", "")
            
            output += f"### {title}\n"
            if subtitle:
                output += f"*{subtitle}*\n\n"
            output += f"**Author(s):** {', '.join(authors)}\n"
            output += f"**Published:** {published_date}\n"
            
            if categories:
                output += f"**Categories:** {', '.join(categories)}\n"
            
            if description:
                output += f"\n{description}\n"
            
            if preview_link:
                output += f"\n[Preview Book]({preview_link})"
            if info_link:
                output += f" | [More Info]({info_link})"
            
            output += "\n\n---\n\n"
        
        return output
