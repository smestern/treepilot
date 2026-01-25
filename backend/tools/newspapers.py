"""Chronicling America newspaper search tool for historical records."""

import logging
import httpx
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger("treepilot.tools.newspapers")


class NewspaperParams(BaseModel):
    """Parameters for newspaper search."""
    query: str = Field(description="Search terms - can be a full name, surname only, family name, event, or location. For surname/family searches, just use the surname to find all mentions of anyone with that name.")
    start_year: int | None = Field(default=None, description="Start year for search (1770-1963)")
    end_year: int | None = Field(default=None, description="End year for search (1770-1963)")
    state: str | None = Field(default=None, description="US state to filter by (e.g., 'New York', 'California')")


CHRONICLING_AMERICA_API = "https://chroniclingamerica.loc.gov/search/pages/results/"


@define_tool(description="Search Chronicling America historical newspapers (1770-1963). Supports flexible queries: full names, surnames/family names only, locations, or events. For surname searches, finds all newspaper mentions of anyone with that family name. Great for finding obituaries, birth announcements, marriage notices, and historical context.")
async def search_newspapers(params: NewspaperParams) -> str:
    """Search historical newspapers via Chronicling America API."""
    
    logger.info(f"Searching newspapers for: '{params.query}' (years: {params.start_year}-{params.end_year}, state: {params.state})")
    
    # Build query parameters
    query_params = {
        "andtext": params.query,
        "format": "json",
        "page": 1,
        "rows": 10,
    }
    
    # Add date range if specified
    if params.start_year:
        query_params["dateFilterType"] = "yearRange"
        query_params["date1"] = str(max(1770, params.start_year))
        logger.debug(f"Date filter start: {query_params['date1']}")
    if params.end_year:
        query_params["date2"] = str(min(1963, params.end_year))
        logger.debug(f"Date filter end: {query_params['date2']}")
    
    # Add state filter if specified
    if params.state:
        query_params["state"] = params.state
    
    headers = {
        "User-Agent": "TreePilot/1.0 (Genealogy Research Agent)"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.debug(f"Querying Chronicling America API: {CHRONICLING_AMERICA_API}")
        response = await client.get(
            CHRONICLING_AMERICA_API,
            params=query_params,
            headers=headers,
        )
        
        logger.debug(f"Chronicling America response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"Chronicling America search failed with status {response.status_code}")
            return f"Chronicling America search failed with status {response.status_code}"
        
        data = response.json()
        total_items = data.get("totalItems", 0)
        items = data.get("items", [])
        logger.info(f"Chronicling America returned {total_items} total results, {len(items)} items in response")
        
        if not items:
            logger.info(f"No newspaper articles found for '{params.query}'")
            return f"No newspaper articles found for '{params.query}'"
        
        # Format results
        output = f"## Historical Newspaper Results\n"
        output += f"*Found {total_items} total results for '{params.query}'*\n\n"
        
        for item in items[:10]:
            title = item.get("title", "Unknown Newspaper")
            date = item.get("date", "Unknown date")
            # Format date from YYYYMMDD to readable format
            if date and len(date) == 8:
                date = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"
            
            city = item.get("city", [])
            state = item.get("state", [])
            location = ", ".join(city + state) if city or state else "Unknown location"
            
            # Get OCR text snippet
            ocr_text = item.get("ocr_eng", "")
            if ocr_text:
                # Find the query terms and extract context
                snippet = ocr_text[:500] + "..." if len(ocr_text) > 500 else ocr_text
            else:
                snippet = "No text preview available"
            
            url = item.get("url", "")
            page_url = url.replace(".json", "") if url else ""
            
            output += f"### {title}\n"
            output += f"**Date:** {date} | **Location:** {location}\n\n"
            output += f"> {snippet}\n\n"
            if page_url:
                output += f"[View original page]({page_url})\n\n"
            output += "---\n\n"
        
        return output
