"""Wikidata SPARQL search tool for structured genealogical data."""

import logging
import httpx
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger("treepilot.tools.wikidata")


class WikidataParams(BaseModel):
    """Parameters for Wikidata search."""
    person_name: str = Field(description="Full name of the person to search for")
    include_family: bool = Field(default=True, description="Whether to include family relationships (parents, spouse, children)")


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# SPARQL query to find a person and their family relationships
FAMILY_QUERY = """
SELECT ?person ?personLabel ?birthDate ?deathDate ?birthPlaceLabel ?deathPlaceLabel
       ?father ?fatherLabel ?mother ?motherLabel
       ?spouse ?spouseLabel ?child ?childLabel
WHERE {{
  ?person ?label "{name}"@en.
  ?person wdt:P31 wd:Q5.  # Instance of human
  
  OPTIONAL {{ ?person wdt:P569 ?birthDate. }}
  OPTIONAL {{ ?person wdt:P570 ?deathDate. }}
  OPTIONAL {{ ?person wdt:P19 ?birthPlace. }}
  OPTIONAL {{ ?person wdt:P20 ?deathPlace. }}
  OPTIONAL {{ ?person wdt:P22 ?father. }}
  OPTIONAL {{ ?person wdt:P25 ?mother. }}
  OPTIONAL {{ ?person wdt:P26 ?spouse. }}
  OPTIONAL {{ ?person wdt:P40 ?child. }}
  
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 20
"""

# Simpler search query
SEARCH_QUERY = """
SELECT ?person ?personLabel ?personDescription ?birthDate ?deathDate ?birthPlaceLabel
WHERE {{
  SERVICE wikibase:mwapi {{
    bd:serviceParam wikibase:endpoint "www.wikidata.org";
                    wikibase:api "EntitySearch";
                    mwapi:search "{name}";
                    mwapi:language "en".
    ?person wikibase:apiOutputItem mwapi:item.
  }}
  ?person wdt:P31 wd:Q5.  # Instance of human
  
  OPTIONAL {{ ?person wdt:P569 ?birthDate. }}
  OPTIONAL {{ ?person wdt:P570 ?deathDate. }}
  OPTIONAL {{ ?person wdt:P19 ?birthPlace. }}
  
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 10
"""


def format_date(date_str: str | None) -> str:
    """Format a Wikidata date string."""
    if not date_str:
        return "Unknown"
    # Wikidata dates are in ISO format, extract just the year for simplicity
    if "T" in date_str:
        date_str = date_str.split("T")[0]
    return date_str


@define_tool(description="Search Wikidata for structured genealogical data about a person, including birth/death dates, birthplace, and family relationships (parents, spouse, children).")
async def search_wikidata(params: WikidataParams) -> str:
    """Search Wikidata for structured genealogical information."""
    
    logger.info(f"Searching Wikidata for: '{params.person_name}' (include_family={params.include_family})")
    
    headers = {
        "User-Agent": "TreePilot/1.0 (https://github.com/treepilot; treepilot@example.com) httpx",
        "Accept": "application/sparql-results+json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Try the search query first
        query = SEARCH_QUERY.format(name=params.person_name.replace('"', '\\"'))
        logger.debug(f"Executing SPARQL query against {SPARQL_ENDPOINT}")
        
        response = await client.get(
            SPARQL_ENDPOINT,
            params={"query": query},
            headers=headers,
        )
        
        logger.debug(f"Wikidata response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"Wikidata query failed with status {response.status_code}")
            return f"Wikidata query failed with status {response.status_code}"
        
        data = response.json()
        results = data.get("results", {}).get("bindings", [])
        logger.info(f"Wikidata returned {len(results)} results for '{params.person_name}'")
        
        if not results:
            logger.info(f"No Wikidata entries found for '{params.person_name}'")
            return f"No Wikidata entries found for '{params.person_name}'"
        
        # Format results
        output = f"## Wikidata Results for '{params.person_name}'\n\n"
        
        seen_persons = set()
        for result in results:
            person_id = result.get("person", {}).get("value", "")
            if person_id in seen_persons:
                continue
            seen_persons.add(person_id)
            
            name = result.get("personLabel", {}).get("value", "Unknown")
            description = result.get("personDescription", {}).get("value", "")
            birth_date = format_date(result.get("birthDate", {}).get("value"))
            death_date = format_date(result.get("deathDate", {}).get("value"))
            birth_place = result.get("birthPlaceLabel", {}).get("value", "Unknown")
            
            output += f"### {name}\n"
            if description:
                output += f"*{description}*\n\n"
            output += f"- **Born:** {birth_date}"
            if birth_place != "Unknown":
                output += f" in {birth_place}"
            output += "\n"
            if death_date != "Unknown":
                output += f"- **Died:** {death_date}\n"
            output += f"- **Wikidata ID:** {person_id.split('/')[-1]}\n\n"
        
        return output
