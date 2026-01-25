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
