"""TreePilot - Agentic Genealogy Researcher Backend.

FastAPI server with GitHub Copilot SDK integration for genealogy research.
"""

import asyncio
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("treepilot")

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv

from copilot import CopilotClient
from tools import (
    search_wikipedia, search_wikidata, search_newspapers, search_books,
    get_person_metadata, get_person_parents, get_person_children,
    get_person_spouses, get_person_siblings, get_person_grandparents,
    get_person_aunts_uncles, get_person_cousins, update_person_metadata,
    undo_last_change, set_gedcom_accessors,
)
from gedcom_utils import (
    parse_gedcom_content,
    get_all_individuals,
    build_ancestor_tree,
    build_bidirectional_tree,
    find_youngest_generation,
    export_gedcom_content,
)

# Load environment variables
load_dotenv()

# Global state
copilot_client: CopilotClient | None = None
current_gedcom_parser = None
current_session = None
change_history: list[dict] = []  # Track metadata changes for undo


# Initialize GEDCOM tool accessors
def _get_parser():
    return current_gedcom_parser

def _get_change_history():
    return change_history

def _add_change_record(record: dict):
    change_history.append(record)

set_gedcom_accessors(_get_parser, _get_change_history, _add_change_record)


SYSTEM_PROMPT = """You are TreePilot, an expert genealogy research assistant. Your purpose is to help users research their family history and ancestry.

## CRITICAL: ALWAYS USE WEB SEARCH
You MUST use the #web tool for EVERY research query. This is your most powerful tool for genealogy research. Do not skip it. Call #web even if other tools return results - web search often finds additional valuable sources.

## Your Capabilities
You have access to the following research tools:
1. **#web** - YOUR PRIMARY TOOL. Search the web for ANY genealogy query. Use this FIRST and ALWAYS. Finds surname origins, immigration records, family histories, ancestry databases, regional genealogy sites, and much more.
2. **Wikipedia** - For biographical information about notable individuals
3. **Wikidata** - For structured genealogical data (birth/death dates, family relationships)
4. **Historical Newspapers** - Search Chronicling America (1770-1963) for obituaries, birth/marriage announcements, and historical mentions
5. **Google Books** - Find genealogy guides, local histories, and biographical works

## Family Tree Tools (GEDCOM)
You can query and update the user's family tree directly:

### Read Tools (query relationships)
- **get_person_metadata** - Get full details about a person (name, dates, places, occupation, notes)
- **get_person_parents** - Get a person's parents
- **get_person_children** - Get a person's children
- **get_person_spouses** - Get a person's spouse(s)
- **get_person_siblings** - Get a person's siblings
- **get_person_grandparents** - Get a person's grandparents
- **get_person_aunts_uncles** - Get a person's aunts and uncles
- **get_person_cousins** - Get a person's cousins

### Write Tools (update metadata)
- **update_person_metadata** - Add or update notes, occupation, birth/death places, or custom facts on a person's record. Use this to save your research findings!
- **undo_last_change** - Revert the most recent metadata update if needed

When using GEDCOM tools, use the person's ID (e.g., '@I1@') which you can find in the person context or from previous tool calls.

## Tool Usage - MANDATORY
1. **ALWAYS call #web ** - For every research request, you MUST invoke the web search tool. No exceptions.
2. Use other tools (Wikipedia, Wikidata, Newspapers, Books) as supplementary sources
3. When other tools return no results, #web becomes even more critical
4. For surname searches, #web finds genealogy-specific databases that other tools cannot access

## Query Interpretation - CRITICAL
Before searching, carefully analyze what the user is actually asking about:

1. **Surname/Family Queries**: If the user asks about a surname or family name (e.g., "Tell me about Spielhausen", "What about the Smith family?"), search for the SURNAME ONLY, not a specific person. This helps find:
   - All people with that surname
   - Family histories and genealogies
   - Regional origins of the name
   - Historical mentions of anyone with that name

2. **Specific Person Queries**: Only search for a specific full name when the user explicitly mentions both first and last name, or clearly refers to a specific individual.

3. **General Topic Queries**: For questions about places, time periods, or historical events, search broadly.

4. **Use Fuzzy/Broad Searches**: When in doubt, start with broader searches. It's better to find too much and filter than to miss relevant results with an overly specific query.

## Research Methodology
When researching, follow these steps:
1. **FIRST: Call #web ()** - This is mandatory for every query. Search the web immediately.
2. **Interpret the query**: Determine if it's about a surname, specific person, place, or topic
3. **Use supplementary tools**: Call Wikipedia, Wikidata, Newspapers, Books as additional sources
4. **Start broad**: Use general search terms first (surname alone, location, time period)
5. **Narrow if needed**: Only narrow searches if initial results are too broad
6. **Try variations**: Search with name variations, alternate spellings, and related terms
7. **Cross-reference**: Use multiple sources to verify findings

## Response Guidelines
- Always cite your sources with links when available
- Distinguish between verified facts and inferences
- Note when information is uncertain or conflicting
- Suggest additional research avenues when appropriate
- Be honest when you cannot find information

## GEDCOM Context
You may receive context about a selected person from the user's family tree. This is REFERENCE CONTEXT ONLY to help understand the family being researched. It does NOT mean every search should be about that specific person:
- Use it to understand the family, time period, and locations relevant to the research
- When the user asks about a surname that matches this person's name, search for the SURNAME broadly, not just that specific individual
- The context provides helpful dates and places for filtering searches, but the user's query determines what to search for

Remember: Genealogical research requires patience and verification. Help users build accurate family histories."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - start and stop Copilot client."""
    global copilot_client
    
    # Startup - Connect to external Copilot CLI server
    # Start the CLI separately with: copilot --server --port 4321
    logger.info("Initializing Copilot client...")
    copilot_client = CopilotClient({
        "cli_path":"copilot",
        "log_level": "all",
    })
    await copilot_client.start()
    logger.info("✓ Copilot client started and connected to localhost:4321")
    
    yield
    
    # Shutdown
    if copilot_client:
        logger.info("Shutting down Copilot client...")
        await copilot_client.stop()
        logger.info("✓ Copilot client stopped")


# Create FastAPI app
app = FastAPI(
    title="TreePilot",
    description="Agentic Genealogy Researcher powered by GitHub Copilot SDK",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request model."""
    prompt: str
    person_context: dict | None = None  # Optional context about a person from GEDCOM


class ChatResponse(BaseModel):
    """Chat response model."""
    content: str
    sources: list[str] = []


class GedcomUploadResponse(BaseModel):
    """Response after uploading a GEDCOM file."""
    message: str
    individual_count: int
    individuals: list[dict]


class TreeResponse(BaseModel):
    """Response containing a family tree structure."""
    tree: dict | None
    root_person: dict | None


# Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "copilot_connected": copilot_client is not None,
    }


@app.post("/upload-gedcom", response_model=GedcomUploadResponse)
async def upload_gedcom(file: UploadFile = File(...)):
    """Upload and parse a GEDCOM file."""
    global current_gedcom_parser
    
    logger.info(f"Received GEDCOM file upload: {file.filename}")
    
    if not file.filename.endswith(('.ged', '.gedcom')):
        logger.warning(f"Invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="File must be a GEDCOM file (.ged or .gedcom)")
    
    try:
        content = await file.read()
        logger.debug(f"Read {len(content)} bytes from file")
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        logger.info("UTF-8 decode failed, trying latin-1 encoding")
        content_str = content.decode('latin-1')
    
    try:
        logger.info("Parsing GEDCOM content...")
        current_gedcom_parser = parse_gedcom_content(content_str)
        individuals = get_all_individuals(current_gedcom_parser)
        logger.info(f"Successfully parsed GEDCOM file with {len(individuals)} individuals")
        
        return GedcomUploadResponse(
            message=f"Successfully parsed GEDCOM file: {file.filename}",
            individual_count=len(individuals),
            individuals=individuals,
        )
    except Exception as e:
        logger.error(f"Failed to parse GEDCOM file: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to parse GEDCOM file: {str(e)}")


@app.get("/individuals")
async def get_individuals():
    """Get all individuals from the loaded GEDCOM file."""
    global current_gedcom_parser
    
    logger.debug("Fetching individuals list")
    
    if not current_gedcom_parser:
        logger.warning("Attempted to get individuals without GEDCOM loaded")
        raise HTTPException(status_code=400, detail="No GEDCOM file loaded. Upload one first.")
    
    individuals = get_all_individuals(current_gedcom_parser)
    logger.info(f"Returning {len(individuals)} individuals")
    return {"individuals": individuals}


@app.get("/tree/{person_id}")
async def get_ancestor_tree(
    person_id: str, 
    max_depth: int = Query(default=10, le=20),
    ancestor_depth: int = Query(default=5, le=15),
    descendant_depth: int = Query(default=5, le=15),
    bidirectional: bool = Query(default=True)
):
    """Get the family tree for a specific person. Supports bidirectional view (ancestors + descendants)."""
    global current_gedcom_parser
    
    logger.info(f"Building tree for person_id={person_id}, bidirectional={bidirectional}, ancestor_depth={ancestor_depth}, descendant_depth={descendant_depth}")
    
    if not current_gedcom_parser:
        logger.warning("Attempted to get tree without GEDCOM loaded")
        raise HTTPException(status_code=400, detail="No GEDCOM file loaded. Upload one first.")
    
    # person_id comes URL-encoded, need to handle @ symbols
    if not person_id.startswith('@'):
        person_id = f"@{person_id}@"
        logger.debug(f"Normalized person_id to: {person_id}")
    
    if bidirectional:
        tree = build_bidirectional_tree(current_gedcom_parser, person_id, ancestor_depth, descendant_depth)
    else:
        tree = build_ancestor_tree(current_gedcom_parser, person_id, max_depth)
    
    if not tree:
        logger.warning(f"Person {person_id} not found in GEDCOM")
        raise HTTPException(status_code=404, detail=f"Person with ID {person_id} not found")
    
    logger.debug(f"Successfully built tree for {person_id}")
    
    return TreeResponse(tree=tree, root_person=tree)


@app.get("/youngest")
async def get_youngest_generation():
    """Get individuals from the youngest generation (good starting points)."""
    global current_gedcom_parser
    
    logger.debug("Fetching youngest generation")
    
    if not current_gedcom_parser:
        logger.warning("Attempted to get youngest generation without GEDCOM loaded")
        raise HTTPException(status_code=400, detail="No GEDCOM file loaded. Upload one first.")
    
    youngest = find_youngest_generation(current_gedcom_parser)
    logger.info(f"Found {len(youngest)} individuals in youngest generation")
    return {"individuals": youngest}


@app.get("/export-gedcom")
async def export_gedcom():
    """Export the current GEDCOM file with any modifications made."""
    global current_gedcom_parser
    
    logger.info("Exporting GEDCOM file")
    
    if not current_gedcom_parser:
        logger.warning("Attempted to export without GEDCOM loaded")
        raise HTTPException(status_code=400, detail="No GEDCOM file loaded. Upload one first.")
    
    try:
        content = export_gedcom_content(current_gedcom_parser)
        logger.info(f"Exported GEDCOM with {len(content)} characters")
        
        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=family-tree-export.ged"
            }
        )
    except Exception as e:
        logger.error(f"Failed to export GEDCOM: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export GEDCOM: {str(e)}")


@app.get("/person/{person_id}")
async def get_person_details(person_id: str):
    """Get full metadata details for a specific person."""
    global current_gedcom_parser
    
    logger.info(f"Fetching details for person_id={person_id}")
    
    if not current_gedcom_parser:
        logger.warning("Attempted to get person details without GEDCOM loaded")
        raise HTTPException(status_code=400, detail="No GEDCOM file loaded. Upload one first.")
    
    # person_id comes URL-encoded, need to handle @ symbols
    if not person_id.startswith('@'):
        person_id = f"@{person_id}@"
        logger.debug(f"Normalized person_id to: {person_id}")
    
    from gedcom_utils import get_person_full_details
    result = get_person_full_details(current_gedcom_parser, person_id)
    
    if isinstance(result, str):
        # Error message returned
        logger.warning(f"Person {person_id} not found: {result}")
        raise HTTPException(status_code=404, detail=result)
    
    logger.debug(f"Successfully fetched details for {person_id}")
    return result


@app.get("/change-history")
async def get_change_history_endpoint():
    """Get the list of metadata changes that can be undone."""
    global change_history
    
    logger.debug(f"Fetching change history ({len(change_history)} entries)")
    
    return {
        "count": len(change_history),
        "changes": [
            {
                "person_id": c.get("person_id"),
                "timestamp": c.get("timestamp"),
                "fields_changed": [ch.get("field") for ch in c.get("changes", [])]
            }
            for c in change_history
        ]
    }


# Helper functions for chat endpoints
def _get_all_tools():
    """Get the complete list of tools for Copilot sessions."""
    return [
        # External research tools
        search_wikipedia, search_wikidata, search_newspapers, search_books,
        # GEDCOM tree tools
        get_person_metadata, get_person_parents, get_person_children,
        get_person_spouses, get_person_siblings, get_person_grandparents,
        get_person_aunts_uncles, get_person_cousins,
        update_person_metadata, undo_last_change,
    ]

def _get_banned_tools():
    """Get the list of banned tools (none currently)."""
    return [
        "powershell", "write_powershell", "read_powershell", "view", "create", "edit"
    ]


def _build_prompt_with_context(prompt: str, person_context: dict | None) -> str:
    """Build a chat prompt with optional person context."""
    if not person_context:
        return prompt
    
    context = person_context
    logger.info(f"Chat includes person context: {context.get('fullName', 'Unknown')}")
    
    return f"""[Family Tree Reference Context - NOT necessarily the search target]
The user has selected a person from their family tree. Use this as BACKGROUND CONTEXT to understand the family, time period, and region being researched. The user's actual query below determines what to search for.

Selected Person: {context.get('fullName', 'Unknown')}
Birth Year: {context.get('birthYear', 'Unknown')}
Death Year: {context.get('deathYear', 'Unknown')}
Birth Place: {context.get('birthPlace', 'Unknown')}

---
User's Actual Query: {prompt}

IMPORTANT: Analyze the user's query to determine what they're actually asking about. If they ask about a surname, search for the surname broadly. If they ask about a location or topic, search for that. Only search for the specific selected person if the user's query explicitly references them."""


def _get_mcp_servers(streaming: bool = False) -> dict:
    """Get the MCP servers configuration.
    
    Args:
        streaming: If True, includes streaming-specific configuration (X-MCP-Tools header and tools list).
    """
    headers = {"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN', '')}"}
    config = {
        "type": "http",
        "url": "https://api.individual.githubcopilot.com/mcp/readonly",
        "headers": headers,
    }
    
    if streaming:
        headers["X-MCP-Tools"] = "web_search"
        config["tools"] = ["*"]
    
    return {
        "github-mcp-server": config
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint."""
    global copilot_client, current_session
    
    logger.info(f"Chat request received: '{request.prompt[:50]}...'" if len(request.prompt) > 50 else f"Chat request received: '{request.prompt}'")
    
    if not copilot_client:
        logger.error("Copilot client not initialized")
        raise HTTPException(status_code=503, detail="Copilot client not initialized")
    
    # Build prompt with person context if provided
    prompt = _build_prompt_with_context(request.prompt, request.person_context)
   
    # Create session with tools
    logger.info("Creating Copilot session with tools...")
    session = await copilot_client.create_session({
        "model": "claude-sonnet-4.5",
        "tools": _get_all_tools(),
        "mcp_servers": _get_mcp_servers(),
        "excluded_tools": _get_banned_tools(),
        "system_message": {"content": SYSTEM_PROMPT},
    })
    logger.debug("Copilot session created")
    
    done = asyncio.Event()
    response_content = ""
    
    def on_event(event):
        nonlocal response_content
        event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
        logger.debug(f"Session event: {event_type}")
        if event_type == "assistant.message":
            response_content = event.data.content
            logger.debug(f"Received assistant message ({len(response_content)} chars)")
        elif event_type == "session.idle":
            logger.debug("Session idle, completing request")
            done.set()
    
    session.on(on_event)
    logger.info("Sending prompt to Copilot...")
    await session.send({"prompt": prompt})
    await done.wait()
    await session.destroy()
    logger.info(f"Chat response complete ({len(response_content)} chars)")
    
    return ChatResponse(content=response_content)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events."""
    global copilot_client
    
    logger.info(f"Streaming chat request: '{request.prompt[:50]}...'" if len(request.prompt) > 50 else f"Streaming chat request: '{request.prompt}'")
    
    if not copilot_client:
        logger.error("Copilot client not initialized for streaming")
        raise HTTPException(status_code=503, detail="Copilot client not initialized")
    
    # Build prompt with person context if provided
    prompt = _build_prompt_with_context(request.prompt, request.person_context)
    
    async def generate() -> AsyncGenerator[str, None]:
        logger.info("Creating streaming Copilot session...")
        session = await copilot_client.create_session({
            "model": "claude-sonnet-4.5",
            "streaming": True,
            "tools":  _get_all_tools(),
            "mcp_servers": _get_mcp_servers(streaming=True),
            "excluded_tools": _get_banned_tools(),
            "system_message": {"content": SYSTEM_PROMPT},
        })
        logger.debug("Streaming session created")
        
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        done = asyncio.Event()
        chunks_sent = 0
        
        def on_event(event):
            nonlocal chunks_sent
            event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
            
            if event_type == "assistant.message_delta":
                delta = event.data.delta_content or ""
                queue.put_nowait({"type": "content", "data": delta})
                chunks_sent += 1
            elif event_type == "assistant.reasoning_delta":
                # Stream thinking/reasoning content
                delta = event.data.delta_content or ""
                queue.put_nowait({"type": "thinking", "data": delta})
                chunks_sent += 1
            elif event_type == "assistant.reasoning":
                # Final reasoning content (for models that support it)
                content = getattr(event.data, 'content', '')
                logger.info(f"Final reasoning received ({len(content)} chars)")
            elif event_type == "tool.execution_start":
                # Notify about tool usage starting
                tool_name = getattr(event.data, 'tool_name', 'unknown')
                logger.info(f"Tool execution started: {tool_name}")
                queue.put_nowait({"type": "tool_start", "data": tool_name})
            elif event_type == "tool.execution_complete":
                tool_name = getattr(event.data, 'tool_name', 'unknown')
                logger.info(f"Tool execution complete: {tool_name}")
                queue.put_nowait({"type": "tool_end", "data": tool_name})
            elif event_type == "session.idle":
                logger.info(f"Streaming session complete, sent {chunks_sent} chunks")
                done.set()
        
        session.on(on_event)
        logger.info("Sending prompt to streaming session...")
        await session.send({"prompt": prompt})
        
        while not done.is_set() or not queue.empty():
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.1)
                if item:
                    # SSE format with type information
                    yield f"data: {json.dumps(item)}\n\n"
            except asyncio.TimeoutError:
                continue
        
        yield "data: [DONE]\n\n"
        await session.destroy()
        logger.debug("Streaming session destroyed")
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
