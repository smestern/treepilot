"""GEDCOM family tree tools for querying and updating family relationships."""

import logging
from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger("treepilot.tools.gedcom_tree")


# ============================================================================
# Parameter Models
# ============================================================================

class PersonIdParams(BaseModel):
    """Parameters for tools that require a person ID."""
    person_id: str = Field(
        description="The person to look up. Can be a GEDCOM ID (e.g., '@I1@' or 'I1') or "
        "the person's name (e.g., 'John Smith'). IDs are preferred when available from "
        "the person context or previous tool calls."
    )


class UpdateMetadataParams(BaseModel):
    """Parameters for updating a person's metadata."""
    person_id: str = Field(
        description="The person to update. Can be a GEDCOM ID (e.g., '@I1@' or 'I1') or "
        "the person's name (e.g., 'John Smith'). IDs are preferred when available."
    )
    notes: str | None = Field(
        default=None,
        description="Research notes or biographical information to add to this person's record."
    )
    occupation: str | None = Field(
        default=None,
        description="The person's occupation or profession."
    )
    birth_place: str | None = Field(
        default=None,
        description="The person's place of birth (city, state, country format preferred)."
    )
    death_place: str | None = Field(
        default=None,
        description="The person's place of death (city, state, country format preferred)."
    )
    custom_facts: dict[str, str] | None = Field(
        default=None,
        description="Additional custom facts as key-value pairs. Keys can be: EDUC (education), "
        "RELI (religion), NATI (nationality), TITL (title), FACT (general fact), EVEN (event)."
    )


# ============================================================================
# Getter/Accessor for parser and change history
# These are set from main.py at runtime
# ============================================================================

_get_parser = None
_get_change_history = None
_add_change_record = None


def set_gedcom_accessors(get_parser_fn, get_change_history_fn, add_change_record_fn):
    """Set the accessor functions for parser and change history from main.py."""
    global _get_parser, _get_change_history, _add_change_record
    _get_parser = get_parser_fn
    _get_change_history = get_change_history_fn
    _add_change_record = add_change_record_fn


def _get_current_parser():
    """Get the current GEDCOM parser, or None if not loaded."""
    if _get_parser is None:
        return None
    return _get_parser()


def _no_gedcom_loaded():
    """Return message when no GEDCOM is loaded."""
    return "No GEDCOM file is currently loaded. Please upload a GEDCOM file first."


# ============================================================================
# READ Tools - Query Family Relationships
# ============================================================================

@define_tool(description="Get detailed metadata about a person in the family tree including name, birth/death dates and places, occupation, notes, and custom facts. Use this to retrieve comprehensive information about a specific individual.")
async def get_person_metadata(params: PersonIdParams) -> str:
    """Get full details about a person from the GEDCOM file."""
    from gedcom_utils import get_person_full_details
    
    logger.info(f"Getting metadata for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_person_full_details(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    # Format as readable markdown
    output = f"## {result['fullName']}\n\n"
    output += f"**ID:** {result['id']}\n"
    output += f"**Gender:** {result['gender'] or 'Unknown'}\n"
    
    if result['birthYear']:
        output += f"**Birth Year:** {result['birthYear']}\n"
    if result['birthPlace']:
        output += f"**Birth Place:** {result['birthPlace']}\n"
    if result['deathYear']:
        output += f"**Death Year:** {result['deathYear']}\n"
    if result['deathPlace']:
        output += f"**Death Place:** {result['deathPlace']}\n"
    if result['occupation']:
        output += f"**Occupation:** {result['occupation']}\n"
    
    if result['notes']:
        output += f"\n### Notes\n"
        for note in result['notes']:
            output += f"- {note}\n"
    
    if result['customFacts']:
        output += f"\n### Additional Facts\n"
        for tag, values in result['customFacts'].items():
            for val in values:
                output += f"- **{tag}:** {val}\n"
    
    return output


@define_tool(description="Get the parents of a person in the family tree. Returns father and mother if known.")
async def get_person_parents(params: PersonIdParams) -> str:
    """Get parents of a person from the GEDCOM file."""
    from gedcom_utils import get_parents
    
    logger.info(f"Getting parents for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_parents(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    if not result:
        return f"No parents found for {params.person_id}"
    
    output = f"## Parents of {params.person_id}\n\n"
    for parent in result:
        years = ""
        if parent['birthYear']:
            years = f" ({parent['birthYear']}"
            if parent['deathYear']:
                years += f"-{parent['deathYear']}"
            years += ")"
        output += f"- **{parent['fullName']}** [{parent['id']}]{years}\n"
    
    return output


@define_tool(description="Get the children of a person in the family tree.")
async def get_person_children(params: PersonIdParams) -> str:
    """Get children of a person from the GEDCOM file."""
    from gedcom_utils import get_children
    
    logger.info(f"Getting children for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_children(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    if not result:
        return f"No children found for {params.person_id}"
    
    output = f"## Children of {params.person_id}\n\n"
    for child in result:
        years = ""
        if child['birthYear']:
            years = f" ({child['birthYear']}"
            if child['deathYear']:
                years += f"-{child['deathYear']}"
            years += ")"
        output += f"- **{child['fullName']}** [{child['id']}]{years}\n"
    
    return output


@define_tool(description="Get the spouse(s) of a person in the family tree.")
async def get_person_spouses(params: PersonIdParams) -> str:
    """Get spouses of a person from the GEDCOM file."""
    from gedcom_utils import get_spouses
    
    logger.info(f"Getting spouses for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_spouses(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    if not result:
        return f"No spouses found for {params.person_id}"
    
    output = f"## Spouse(s) of {params.person_id}\n\n"
    for spouse in result:
        years = ""
        if spouse['birthYear']:
            years = f" ({spouse['birthYear']}"
            if spouse['deathYear']:
                years += f"-{spouse['deathYear']}"
            years += ")"
        output += f"- **{spouse['fullName']}** [{spouse['id']}]{years}\n"
    
    return output


@define_tool(description="Get the siblings of a person in the family tree (people who share at least one parent).")
async def get_person_siblings(params: PersonIdParams) -> str:
    """Get siblings of a person from the GEDCOM file."""
    from gedcom_utils import get_siblings
    
    logger.info(f"Getting siblings for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_siblings(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    if not result:
        return f"No siblings found for {params.person_id}"
    
    output = f"## Siblings of {params.person_id}\n\n"
    for sibling in result:
        years = ""
        if sibling['birthYear']:
            years = f" ({sibling['birthYear']}"
            if sibling['deathYear']:
                years += f"-{sibling['deathYear']}"
            years += ")"
        output += f"- **{sibling['fullName']}** [{sibling['id']}]{years}\n"
    
    return output


@define_tool(description="Get the grandparents of a person in the family tree (parents of their parents).")
async def get_person_grandparents(params: PersonIdParams) -> str:
    """Get grandparents of a person from the GEDCOM file."""
    from gedcom_utils import get_grandparents
    
    logger.info(f"Getting grandparents for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_grandparents(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    if not result:
        return f"No grandparents found for {params.person_id}"
    
    output = f"## Grandparents of {params.person_id}\n\n"
    for gp in result:
        years = ""
        if gp['birthYear']:
            years = f" ({gp['birthYear']}"
            if gp['deathYear']:
                years += f"-{gp['deathYear']}"
            years += ")"
        output += f"- **{gp['fullName']}** [{gp['id']}]{years}\n"
    
    return output


@define_tool(description="Get the aunts and uncles of a person in the family tree (siblings of their parents).")
async def get_person_aunts_uncles(params: PersonIdParams) -> str:
    """Get aunts and uncles of a person from the GEDCOM file."""
    from gedcom_utils import get_aunts_uncles
    
    logger.info(f"Getting aunts/uncles for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_aunts_uncles(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    if not result:
        return f"No aunts or uncles found for {params.person_id}"
    
    output = f"## Aunts & Uncles of {params.person_id}\n\n"
    for au in result:
        years = ""
        if au['birthYear']:
            years = f" ({au['birthYear']}"
            if au['deathYear']:
                years += f"-{au['deathYear']}"
            years += ")"
        output += f"- **{au['fullName']}** [{au['id']}]{years}\n"
    
    return output


@define_tool(description="Get the cousins of a person in the family tree (children of their aunts and uncles).")
async def get_person_cousins(params: PersonIdParams) -> str:
    """Get cousins of a person from the GEDCOM file."""
    from gedcom_utils import get_cousins
    
    logger.info(f"Getting cousins for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = get_cousins(parser, params.person_id)
    if isinstance(result, str):
        return result  # Error message
    
    if not result:
        return f"No cousins found for {params.person_id}"
    
    output = f"## Cousins of {params.person_id}\n\n"
    for cousin in result:
        years = ""
        if cousin['birthYear']:
            years = f" ({cousin['birthYear']}"
            if cousin['deathYear']:
                years += f"-{cousin['deathYear']}"
            years += ")"
        output += f"- **{cousin['fullName']}** [{cousin['id']}]{years}\n"
    
    return output


# ============================================================================
# WRITE Tools - Update Person Metadata
# ============================================================================

@define_tool(description="Update metadata on a person in the family tree. Can add or update notes, occupation, birth place, death place, or custom facts. Changes are tracked and can be undone. Use this to record research findings directly in the family tree.")
async def update_person_metadata(params: UpdateMetadataParams) -> str:
    """Update a person's metadata in the GEDCOM file."""
    from gedcom_utils import update_person_metadata as do_update
    
    logger.info(f"Updating metadata for person: {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = do_update(
        parser,
        params.person_id,
        notes=params.notes,
        occupation=params.occupation,
        birth_place=params.birth_place,
        death_place=params.death_place,
        custom_facts=params.custom_facts,
    )
    
    if isinstance(result, str):
        return result  # Error message
    
    # Store change record for undo
    if _add_change_record and result.get("changes"):
        _add_change_record(result)
    
    # Format success message
    output = f"## Updated {params.person_id}\n\n"
    output += "The following changes were made:\n\n"
    
    for change in result.get("changes", []):
        field = change["field"]
        old_val = change["old_value"] or "(empty)"
        new_val = change["new_value"]
        output += f"- **{field}**: `{old_val}` → `{new_val}`\n"
    
    output += "\n*This change can be undone using the undo_last_change tool.*"
    return output


# ============================================================================
# UNDO Tool
# ============================================================================

class UndoParams(BaseModel):
    """Parameters for undo operation."""
    confirm: bool = Field(
        default=True,
        description="Confirm that you want to undo the last change. Set to true to proceed."
    )


@define_tool(description="Undo the most recent metadata change made to the family tree. Use this if a previous update was made in error or needs to be reverted.")
async def undo_last_change(params: UndoParams) -> str:
    """Undo the last metadata change."""
    from gedcom_utils import apply_undo
    
    if not params.confirm:
        return "Undo cancelled. Set confirm=true to proceed."
    
    logger.info("Undoing last change")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    if not _get_change_history:
        return "Undo system not initialized."
    
    change_history = _get_change_history()
    if not change_history:
        return "No changes to undo. The change history is empty."
    
    # Pop the last change
    last_change = change_history.pop()
    
    result = apply_undo(parser, last_change)
    
    output = f"## Undo Complete\n\n{result}\n\n"
    output += f"Reverted changes from {last_change.get('timestamp', 'unknown time')}:\n"
    for change in last_change.get("changes", []):
        output += f"- **{change['field']}**: restored to `{change['old_value'] or '(empty)'}`\n"
    
    remaining = len(change_history)
    output += f"\n*{remaining} change(s) remaining in history.*"
    
    return output


# ============================================================================
# NEW: Person Management Tools (Write Operations)
# ============================================================================

class AddPersonParams(BaseModel):
    """Parameters for adding a new person to the tree."""
    first_name: str = Field(description="Given name of the person")
    last_name: str = Field(description="Surname/family name of the person")
    gender: str = Field(
        default="U",
        description="Gender: 'M' (male), 'F' (female), or 'U' (unknown). Default is 'U'."
    )
    birth_date: str | None = Field(
        default=None,
        description="Birth date in GEDCOM format (e.g., '15 MAR 1850', 'MAR 1850', '1850', 'ABT 1850')"
    )
    birth_place: str | None = Field(
        default=None,
        description="Birth place (city, state, country format preferred)"
    )
    death_date: str | None = Field(
        default=None,
        description="Death date in GEDCOM format"
    )
    death_place: str | None = Field(
        default=None,
        description="Death place"
    )
    notes: list[str] | None = Field(
        default=None,
        description="List of notes/sources about this person"
    )
    check_duplicates: bool = Field(
        default=True,
        description="Whether to check for potential duplicate persons before adding. Recommended: true"
    )


class LinkParentChildParams(BaseModel):
    """Parameters for linking parent and child."""
    parent_id: str = Field(description="GEDCOM ID of the parent (e.g., '@I1@' or 'I1')")
    child_id: str = Field(description="GEDCOM ID of the child (e.g., '@I2@' or 'I2')")
    check_circular: bool = Field(
        default=True,
        description="Whether to check for circular ancestry. Recommended: true"
    )


class LinkSpousesParams(BaseModel):
    """Parameters for linking spouses."""
    spouse1_id: str = Field(description="GEDCOM ID of first spouse")
    spouse2_id: str = Field(description="GEDCOM ID of second spouse")
    marriage_date: str | None = Field(
        default=None,
        description="Marriage date in GEDCOM format (optional)"
    )
    marriage_place: str | None = Field(
        default=None,
        description="Marriage place (optional)"
    )


class AddSourceParams(BaseModel):
    """Parameters for attaching a source citation to a person."""
    person_id: str = Field(description="GEDCOM ID of the person")
    source_title: str = Field(description="Title of the source (e.g., 'Wikidata Q12345', 'Boston Birth Records')")
    source_author: str | None = Field(default=None, description="Author or originator of the source")
    source_publication: str | None = Field(default=None, description="Publication information")
    source_url: str | None = Field(default=None, description="URL of the source")
    event_type: str = Field(
        default="BIRT",
        description="Event to attach source to: 'BIRT' (birth), 'DEAT' (death), 'NAME' (name), etc."
    )
    page: str | None = Field(default=None, description="Specific page/location in source")
    quality: int = Field(
        default=2,
        description="Quality assessment 0-3: 0=unreliable, 1=questionable, 2=secondary evidence, 3=primary evidence"
    )
    citation_text: str | None = Field(default=None, description="Verbatim text extracted from source")


class TransactionParams(BaseModel):
    """Parameters for transaction operations."""
    description: str = Field(description="Description of the transaction (e.g., 'Added Hans Henrich Mestern with sources')")


class EmptyParams(BaseModel):
    """Empty parameters for tools that don't require input."""
    pass


@define_tool(description="Add a new person to the family tree. Automatically checks for potential duplicates and warns if similar persons already exist. Returns the new person's ID if successful, or duplicate matches for user review.")
async def add_person_to_tree(params: AddPersonParams) -> str:
    """Add a new individual to the GEDCOM file."""
    from gedcom_utils import add_individual, find_potential_duplicates
    
    logger.info(f"Adding person: {params.first_name} {params.last_name}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    # Check for duplicates first
    if params.check_duplicates:
        candidate = {
            "fullName": f"{params.first_name} {params.last_name}",
            "birthYear": None,
            "birthPlace": params.birth_place,
            "gender": params.gender,
            "deathYear": None
        }
        
        # Extract years from dates
        if params.birth_date:
            parts = params.birth_date.split()
            for part in parts:
                if part.isdigit() and len(part) == 4:
                    candidate["birthYear"] = int(part)
                    break
        
        if params.death_date:
            parts = params.death_date.split()
            for part in parts:
                if part.isdigit() and len(part) == 4:
                    candidate["deathYear"] = int(part)
                    break
        
        duplicates = find_potential_duplicates(parser, candidate, threshold=0.60)
        
        if duplicates:
            output = f"## ⚠️ Potential Duplicates Found\n\n"
            output += f"Found {len(duplicates)} existing person(s) that may match **{params.first_name} {params.last_name}**:\n\n"
            
            for i, match in enumerate(duplicates[:5], 1):  # Show top 5
                person = match['person']
                similarity = match['percentage']
                output += f"### {i}. {person['fullName']} ({similarity}% match)\n"
                output += f"- **ID:** {person['id']}\n"
                output += f"- **Birth:** {person.get('birthYear') or '?'}"
                if person.get('birthPlace'):
                    output += f" in {person['birthPlace']}"
                output += "\n"
                output += f"- **Death:** {person.get('deathYear') or '?'}"
                if person.get('deathPlace'):
                    output += f" in {person['deathPlace']}"
                output += "\n"
                output += f"- **Gender:** {person.get('gender', 'U')}\n\n"
            
            output += "\n**Options:**\n"
            output += "1. Use one of the existing persons above (note their ID)\n"
            output += "2. Call `add_person_to_tree` again with `check_duplicates=False` to add as new person\n"
            output += "3. Gather more research to distinguish between candidates\n"
            
            return output
    
    # No duplicates or check disabled - proceed with adding
    result = add_individual(
        parser,
        first_name=params.first_name,
        last_name=params.last_name,
        gender=params.gender,
        birth_date=params.birth_date,
        birth_place=params.birth_place,
        death_date=params.death_date,
        death_place=params.death_place,
        notes=params.notes
    )
    
    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        warnings = result.get("warnings", [])
        output = f"## ❌ Error Adding Person\n\n{error_msg}\n\n"
        if warnings:
            output += "**Warnings:**\n"
            for w in warnings:
                output += f"- {w}\n"
        return output
    
    person_id = result["id"]
    warnings = result.get("warnings", [])
    
    output = f"## ✅ Added {params.first_name} {params.last_name}\n\n"
    output += f"**New Person ID:** {person_id}\n\n"
    
    if warnings:
        output += "**Warnings:**\n"
        for w in warnings:
            output += f"- {w}\n"
        output += "\n"
    
    output += "**Next Steps:**\n"
    output += "1. Add sources with `add_source_to_person`\n"
    output += "2. Link relationships with `link_parent_child` or `link_spouses`\n"
    output += "3. Add metadata with `update_person_metadata`\n"
    
    return output


@define_tool(description="Link a parent-child relationship in the family tree. Creates or updates family records as needed. Automatically checks for circular ancestry to prevent invalid relationships.")
async def link_parent_child(params: LinkParentChildParams) -> str:
    """Link a parent and child in the GEDCOM file."""
    from gedcom_utils import add_family_relationship
    
    logger.info(f"Linking parent {params.parent_id} to child {params.child_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = add_family_relationship(
        parser,
        parent_id=params.parent_id,
        child_id=params.child_id,
        check_circular=params.check_circular
    )
    
    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        warnings = result.get("warnings", [])
        output = f"## ❌ Error Linking Relationship\n\n{error_msg}\n\n"
        if warnings:
            output += "**Warnings:**\n"
            for w in warnings:
                output += f"- {w}\n"
        return output
    
    family_id = result["family_id"]
    warnings = result.get("warnings", [])
    
    output = f"## ✅ Linked Parent-Child Relationship\n\n"
    output += f"**Parent:** {params.parent_id}\n"
    output += f"**Child:** {params.child_id}\n"
    output += f"**Family ID:** {family_id}\n\n"
    
    if warnings:
        output += "**Warnings:**\n"
        for w in warnings:
            output += f"- {w}\n"
    
    return output


@define_tool(description="Link two persons as spouses in the family tree. Creates a marriage/family record linking them together. Optionally includes marriage date and place.")
async def link_spouses(params: LinkSpousesParams) -> str:
    """Link two persons as spouses in the GEDCOM file."""
    from gedcom_utils import add_spouse_relationship
    
    logger.info(f"Linking spouses {params.spouse1_id} and {params.spouse2_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    result = add_spouse_relationship(
        parser,
        spouse1_id=params.spouse1_id,
        spouse2_id=params.spouse2_id,
        marriage_date=params.marriage_date,
        marriage_place=params.marriage_place
    )
    
    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        return f"## ❌ Error Linking Spouses\n\n{error_msg}"
    
    family_id = result["family_id"]
    
    output = f"## ✅ Linked Spouses\n\n"
    output += f"**Spouse 1:** {params.spouse1_id}\n"
    output += f"**Spouse 2:** {params.spouse2_id}\n"
    output += f"**Family ID:** {family_id}\n"
    
    if params.marriage_date or params.marriage_place:
        output += f"\n**Marriage Info:**\n"
        if params.marriage_date:
            output += f"- Date: {params.marriage_date}\n"
        if params.marriage_place:
            output += f"- Place: {params.marriage_place}\n"
    
    return output


@define_tool(description="Attach a source citation to a person's event (birth, death, etc.). Creates GEDCOM 5.5.1 standard source records with quality assessment. Use this to document research findings.")
async def add_source_to_person(params: AddSourceParams) -> str:
    """Create a source record and attach it to a person's event."""
    from gedcom_utils import create_source_record, attach_source_citation
    
    logger.info(f"Adding source to person {params.person_id}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    # Create source record
    source_result = create_source_record(
        parser,
        title=params.source_title,
        author=params.source_author,
        publication=params.source_publication,
        url=params.source_url
    )
    
    if not source_result.get("success"):
        return f"## ❌ Error Creating Source\n\n{source_result.get('error', 'Unknown error')}"
    
    source_id = source_result["id"]
    
    # Attach to person's event
    citation_result = attach_source_citation(
        parser,
        person_id=params.person_id,
        source_id=source_id,
        event_type=params.event_type,
        page=params.page,
        quality=params.quality,
        citation_text=params.citation_text
    )
    
    if not citation_result.get("success"):
        return f"## ❌ Error Attaching Source\n\n{citation_result.get('error', 'Unknown error')}"
    
    quality_labels = {
        0: "Unreliable",
        1: "Questionable",
        2: "Secondary Evidence",
        3: "Primary Evidence"
    }
    quality_label = quality_labels.get(params.quality, "Unknown")
    
    output = f"## ✅ Source Added\n\n"
    output += f"**Source ID:** {source_id}\n"
    output += f"**Title:** {params.source_title}\n"
    output += f"**Attached to:** {params.person_id} ({params.event_type} event)\n"
    output += f"**Quality:** {quality_label} ({params.quality}/3)\n"
    
    if params.source_url:
        output += f"**URL:** {params.source_url}\n"
    
    return output


@define_tool(description="Begin a transaction to group multiple operations (add person, add sources, link relationships) as a single undoable unit. Use this when performing complex multi-step operations.")
async def begin_person_transaction(params: TransactionParams) -> str:
    """Begin a transaction for grouping operations."""
    from gedcom_utils import begin_transaction
    
    logger.info(f"Beginning transaction: {params.description}")
    
    try:
        result = begin_transaction(params.description)
        return f"## 🔄 Transaction Started\n\n**ID:** {result['id']}\n**Description:** {result['description']}\n\nAll subsequent operations will be grouped until you call `commit_person_transaction`."
    except RuntimeError as e:
        return f"## ❌ Error\n\n{str(e)}"


@define_tool(description="Commit the current transaction, saving all grouped operations as a single undoable unit. Call this after completing all related operations.")
async def commit_person_transaction(params: EmptyParams) -> str:
    """Commit the current transaction."""
    from gedcom_utils import commit_transaction
    
    logger.info("Committing transaction")
    
    try:
        result = commit_transaction()
        
        # Store in change history for undo
        if _add_change_record:
            _add_change_record(result)
        
        output = f"## ✅ Transaction Committed\n\n"
        output += f"**Description:** {result['description']}\n"
        output += f"**Operations:** {result['operation_count']}\n"
        output += f"**Started:** {result['started_at']}\n"
        output += f"**Committed:** {result['committed_at']}\n\n"
        output += "*This transaction can be undone as a single unit using `undo_transaction`.*"
        
        return output
    except RuntimeError as e:
        return f"## ❌ Error\n\n{str(e)}"


class UndoTransactionParams(BaseModel):
    """Parameters for undoing a transaction."""
    transaction_index: int = Field(
        default=-1,
        description="Index of transaction to undo. -1 (default) = most recent, -2 = second most recent, etc."
    )
    confirm: bool = Field(
        default=True,
        description="Confirm that you want to undo this transaction. Set to true to proceed."
    )


@define_tool(description="Undo an entire transaction, reversing all operations as a group (e.g., remove added person, sources, and relationships together). Use this to rollback complex multi-step operations.")
async def undo_transaction(params: UndoTransactionParams) -> str:
    """Undo an entire transaction."""
    from gedcom_utils import apply_transaction_undo
    
    if not params.confirm:
        return "Undo cancelled. Set confirm=true to proceed."
    
    logger.info(f"Undoing transaction at index {params.transaction_index}")
    parser = _get_current_parser()
    if not parser:
        return _no_gedcom_loaded()
    
    if not _get_change_history:
        return "Undo system not initialized."
    
    change_history = _get_change_history()
    if not change_history:
        return "No transactions to undo. The change history is empty."
    
    try:
        # Get the transaction record
        transaction_record = change_history[params.transaction_index]
        
        # Check if it's a transaction (has 'operations' field)
        if 'operations' not in transaction_record:
            return "Selected change is not a transaction. Use `undo_last_change` for single-operation undo."
        
        # Remove from history
        change_history.pop(params.transaction_index)
        
        # Apply undo
        result = apply_transaction_undo(parser, transaction_record)
        
        if not result.get("success"):
            errors = result.get("errors", [])
            output = f"## ❌ Undo Failed\n\n"
            output += f"**Operations undone:** {result['operations_undone']}\n\n"
            output += "**Errors:**\n"
            for error in errors:
                output += f"- {error}\n"
            return output
        
        output = f"## ✅ Transaction Undone\n\n"
        output += f"**Description:** {transaction_record['description']}\n"
        output += f"**Operations Reversed:** {result['operations_undone']}\n"
        output += f"**Original Commit Time:** {transaction_record.get('committed_at', 'unknown')}\n\n"
        
        remaining = len(change_history)
        output += f"*{remaining} change(s) remaining in history.*"
        
        return output
        
    except IndexError:
        return f"Invalid transaction index: {params.transaction_index}. History has {len(change_history)} items."

