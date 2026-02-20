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
    search_web_tavily,
    get_person_metadata, get_person_parents, get_person_children,
    get_person_spouses, get_person_siblings, get_person_grandparents,
    get_person_aunts_uncles, get_person_cousins, update_person_metadata,
    undo_last_change, set_gedcom_accessors,
    add_person_to_tree, link_parent_child, link_spouses, add_source_to_person,
    begin_person_transaction, commit_person_transaction, undo_transaction,
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
current_streaming_session = None  # Persistent streaming session for conversation history
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
You MUST use the #web_search tool for EVERY research query. This is your most powerful tool for genealogy research. Do not skip it. Call #web_search even if other tools return results - web search often finds additional valuable sources.

**IMPORTANT FALLBACK:** If #web_search fails, returns an error, is unavailable, or times out, immediately use **search_web_tavily** as a backup. Do not give up on web searching - always try the Tavily backup when the primary search fails.

## Your Capabilities
You have access to the following research tools:
1. **#web_search** - YOUR PRIMARY TOOL. Search the web for ANY genealogy query. Use this FIRST and ALWAYS. Finds surname origins, immigration records, family histories, ancestry databases, regional genealogy sites, and much more.
2. **search_web_tavily** - BACKUP web search via Tavily API. Use this automatically when #web_search is unavailable or fails.
3. **Wikipedia** - For biographical information about notable individuals
4. **Wikidata** - For structured genealogical data (birth/death dates, family relationships)
5. **Historical Newspapers** - Search Chronicling America (1770-1963) for obituaries, birth/marriage announcements, and historical mentions
6. **Google Books** - Find genealogy guides, local histories, and biographical works

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

### Write Tools (update and add to tree)
- **update_person_metadata** - Add or update notes, occupation, birth/death places, or custom facts on a person's record
- **undo_last_change** - Revert the most recent metadata update if needed

### NEW: Autonomous Research Tools (add people to tree)
- **add_person_to_tree** - Add a new person to the tree (automatically checks for duplicates)
- **link_parent_child** - Establish parent-child relationship
- **link_spouses** - Link two people as spouses/married
- **add_source_to_person** - Attach source citation to a person's event (birth, death, etc.)
- **begin_person_transaction** - Start grouping operations for atomic undo
- **commit_person_transaction** - Finish transaction group
- **undo_transaction** - Undo an entire group of operations at once

When using GEDCOM tools, use the person's ID (e.g., '@I1@') which you can find in the person context or from previous tool calls.

## Autonomous Research Workflow
When the user asks you to "research [person name] and add them to the tree", follow this workflow:

### Phase 1: Research & Data Collection
1. **Search Multiple Sources** - Use #web_search, Wikidata, Wikipedia, newspapers, books
2. **Deduplicate Sources** - Compare URLs and titles to identify duplicate sources
3. **Extract Structured Data** - Collect:
   - Full name (first name, last name)
   - Birth date and place (be specific: "15 MAR 1850" better than "1850")
   - Death date and place
   - Gender
   - Occupation, notes, relationships
4. **Note Conflicts** - Track when sources disagree on facts

### Phase 2: Duplicate Detection
1. **Check Existing Tree** - Use `add_person_to_tree` with `check_duplicates=True` (default)
2. **Review Matches** - If duplicates found, tool returns ranked list with similarity percentages
3. **Present to User** - Show user the potential matches with:
   - Similarity percentage (e.g., "85% match")
   - Name, birth/death years, locations
   - ID for reference
4. **User Decision**:
   - User selects existing person (use that ID)
   - User confirms adding as new person (call `add_person_to_tree` with `check_duplicates=False`)
   - User asks for more research to distinguish

### Phase 3: Add Person & Sources
1. **Begin Transaction** (optional, recommended for complex additions):
   ```
   begin_person_transaction(description="Added [Name] with sources and relationships")
   ```

2. **Add Person** - Once duplicates resolved:
   ```
   add_person_to_tree(
       first_name="Hans",
       last_name="Mestern",
       gender="M",
       birth_date="1850",
       birth_place="Germany",
       death_date="ABT 1920",
       notes=["Found in Wikidata Q12345", "Mentioned in 1880 census"],
       check_duplicates=False  # Already checked
   )
   ```
   Save the returned ID for next steps.

3. **Add Each Unique Source**:
   ```
   add_source_to_person(
       person_id="@I123@",
       source_title="Wikidata Q12345",
       source_url="https://www.wikidata.org/wiki/Q12345",
       source_author="Wikidata Contributors",
       event_type="BIRT",  # or "DEAT", "NAME", etc.
       quality=2,  # 0=unreliable, 1=questionable, 2=secondary, 3=primary
       citation_text="Born 1850 in Germany"
   )
   ```
   
   **Source Quality Guidelines**:
   - Quality 3 (Primary): Government records, certificates, census
   - Quality 2 (Secondary): Wikidata, newspapers, published genealogies
   - Quality 1 (Questionable): Wikipedia, family trees from other users
   - Quality 0 (Unreliable): Unsourced web content

4. **Link Relationships** (if known):
   ```
   link_parent_child(parent_id="@I100@", child_id="@I123@")
   link_spouses(spouse1_id="@I123@", spouse2_id="@I124@", marriage_date="1875")
   ```

5. **Commit Transaction** (if started):
   ```
   commit_person_transaction()
   ```

### Phase 4: Report Results
Summarize what was done:
- Person added with ID
- Number of sources attached
- Relationships established
- Any warnings or conflicts noted
- Suggest next research steps

## Source Deduplication
When collecting sources from multiple tools:
1. **Compare URLs** - Same URL = same source (keep one, note multiple access dates)
2. **Compare Titles** - Similar titles likely indicate same source
3. **Merge Metadata** - If duplicate found, combine publication info, authors, etc.
4. **Create ONE source record** per unique source

## Handling Errors & Edge Cases

### Circular Ancestry
If `link_parent_child` returns error about circular ancestry:
1. Explain the issue to user (X is a descendant of Y, cannot also be ancestor)
2. Ask user to verify the relationship is correct
3. Suggest alternative relationship (perhaps they are siblings, cousins, etc.)

### Date Validation Errors
If dates fail validation (death before birth, parent too young):
1. Report the issue to user
2. Tool will attempt auto-correction for minor issues (month name format, etc.)
3. For major errors, ask user to verify dates

### Low Confidence Research
When sources are limited or conflicting:
1. Add person with available data
2. Mark notes as "needs verification"
3. Add quality 0-1 sources with disclaimer
4. Suggest specific research avenues to improve confidence

## Tool Usage - MANDATORY
1. **ALWAYS call #web_search first** - For every research request, you MUST invoke the web search tool. No exceptions.
2. Use other tools (Wikipedia, Wikidata, Newspapers, Books) as supplementary sources
3. When other tools return no results, #web_search becomes even more critical
4. For surname searches, #web_search finds genealogy-specific databases that other tools cannot access

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
1. **FIRST: Call #web_search** - This is mandatory for every query. Search the web immediately.
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
- When adding people to tree, show clear progress through the workflow phases

## GEDCOM Context
You may receive context about a selected person from the user's family tree. This is REFERENCE CONTEXT ONLY to help understand the family being researched. It does NOT mean every search should be about that specific person:
- Use it to understand the family, time period, and locations relevant to the research
- When the user asks about a surname that matches this person's name, search for the SURNAME broadly, not just that specific individual
- The context provides helpful dates and places for filtering searches, but the user's query determines what to search for

Remember: Genealogical research requires patience and verification. Help users build accurate family histories with proper source documentation."""


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
    return (
    search_wikipedia, search_wikidata, search_newspapers, search_books,
    search_web_tavily,
    get_person_metadata, get_person_parents, get_person_children,
    get_person_spouses, get_person_siblings, get_person_grandparents,
    get_person_aunts_uncles, get_person_cousins, update_person_metadata,
    undo_last_change, 
    add_person_to_tree, link_parent_child, link_spouses, add_source_to_person,
    begin_person_transaction, commit_person_transaction, undo_transaction,
)

def _get_banned_tools():
    """Get the list of banned tools (none currently)."""
    return [
        "powershell", "write_powershell", "read_powershell", "view", "create", "edit" #Banned any code or file system tools, this is a genealogy researcher only
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
    
    
    headers["X-MCP-Tools"] = "web_search"
    config["tools"] = ["*"]
    
    return {
        "github-mcp-server": config
    }


@app.post("/chat/reset")
async def reset_chat_session():
    """Reset the chat session to start a fresh conversation."""
    global current_session, current_streaming_session
    
    logger.info("Resetting chat sessions...")
    
    if current_session:
        try:
            await current_session.destroy()
        except Exception as e:
            logger.warning(f"Error destroying non-streaming session: {e}")
        current_session = None
        
    if current_streaming_session:
        try:
            await current_streaming_session.destroy()
        except Exception as e:
            logger.warning(f"Error destroying streaming session: {e}")
        current_streaming_session = None
    
    logger.info("Chat sessions reset successfully")
    return {"message": "Chat session reset successfully"}


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
   
    # Reuse existing session or create new one
    if current_session is None:
        logger.info("Creating Copilot session with tools...")
        current_session = await copilot_client.create_session({
            "model": "claude-sonnet-4.5",
            "tools": _get_all_tools(),
            "mcp_servers": _get_mcp_servers(),
            "excluded_tools": _get_banned_tools(),
            "system_message": {"content": SYSTEM_PROMPT},
        })
        logger.debug("Copilot session created")
    else:
        logger.debug("Reusing existing Copilot session")
    
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
    
    current_session.on(on_event)
    logger.info("Sending prompt to Copilot...")
    await current_session.send({"prompt": prompt})
    await done.wait()
    # Don't destroy session - keep it for conversation history
    logger.info(f"Chat response complete ({len(response_content)} chars)")
    
    return ChatResponse(content=response_content)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events."""
    global copilot_client, current_streaming_session
    
    logger.info(f"Streaming chat request: '{request.prompt[:50]}...'" if len(request.prompt) > 50 else f"Streaming chat request: '{request.prompt}'")
    
    if not copilot_client:
        logger.error("Copilot client not initialized for streaming")
        raise HTTPException(status_code=503, detail="Copilot client not initialized")
    
    # Build prompt with person context if provided
    prompt = _build_prompt_with_context(request.prompt, request.person_context)
    
    # Reuse existing streaming session or create new one
    if current_streaming_session is None:
        logger.info("Creating streaming Copilot session...")
        current_streaming_session = await copilot_client.create_session({
            "model": "claude-sonnet-4.5",
            "streaming": True,
            "tools":  _get_all_tools(),
            "mcp_servers": _get_mcp_servers(streaming=True),
            "excluded_tools": _get_banned_tools(),
            "system_message": {"content": SYSTEM_PROMPT},
        })
        logger.debug("Streaming session created")
    else:
        logger.debug("Reusing existing streaming session")
    
    session = current_streaming_session
    
    async def generate() -> AsyncGenerator[str, None]:
        
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
        # Don't destroy session - keep it for conversation history
        logger.debug("Streaming request complete, session preserved")
    
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
