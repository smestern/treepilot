"""GEDCOM file parsing and D3.js tree conversion utilities."""

from datetime import datetime
from typing import Any
from difflib import SequenceMatcher
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement
from gedcom.element.family import FamilyElement


# ============================================================================
# Helper: Find individual by ID or Name
# ============================================================================

def find_individual_by_id(parser: Parser, person_id: str) -> IndividualElement | None:
    """Find an individual element by their GEDCOM ID (pointer)."""
    if not person_id.startswith('@'):
        person_id = f"@{person_id}@"
    
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            if element.get_pointer() == person_id:
                return element
    return None


def find_individual_by_name(parser: Parser, name: str) -> IndividualElement | None:
    """Find an individual element by their name (case-insensitive partial match)."""
    name_lower = name.lower().strip()
    
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            first_name, last_name = element.get_name()
            full_name = f"{first_name} {last_name}".strip().lower()
            # Try exact match first
            if full_name == name_lower:
                return element
            # Then try if the search name is contained in the full name
            if name_lower in full_name:
                return element
    return None


def find_individual(parser: Parser, identifier: str) -> IndividualElement | None:
    """
    Find an individual by ID or name.
    First tries to find by ID (e.g., '@I1@' or 'I1'), then falls back to name search.
    """
    # Check if it looks like an ID (starts with @ or is alphanumeric like I1, I23)
    identifier = identifier.strip()
    
    if identifier.startswith('@') or (len(identifier) <= 10 and identifier[0].isalpha() and any(c.isdigit() for c in identifier)):
        # Try as ID first
        result = find_individual_by_id(parser, identifier)
        if result:
            return result
    
    # Fall back to name search
    return find_individual_by_name(parser, identifier)


# ============================================================================
# Extended Individual Data (with more metadata)
# ============================================================================

def get_person_full_details(parser: Parser, person_id: str) -> dict[str, Any] | str:
    """
    Get comprehensive details about a person including all available metadata.
    Returns a dict with full information, or an error message string if not found.
    Accepts either a GEDCOM ID (e.g., '@I1@') or a person's name.
    """
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    first_name, last_name = individual.get_name()
    birth_year = individual.get_birth_year()
    
    # Death data
    death_year = None
    death_place = None
    death_data = individual.get_death_data()
    if death_data:
        if death_data[0]:
            for part in death_data[0].split():
                if part.isdigit() and len(part) == 4:
                    death_year = int(part)
                    break
        if len(death_data) > 1:
            death_place = death_data[1]
    
    # Birth data
    birth_place = None
    birth_data = individual.get_birth_data()
    if birth_data and len(birth_data) > 1:
        birth_place = birth_data[1]
    
    # Occupation
    occupation = None
    for child in individual.get_child_elements():
        if child.get_tag() == "OCCU":
            occupation = child.get_value()
            break
    
    # Notes
    notes = []
    for child in individual.get_child_elements():
        if child.get_tag() == "NOTE":
            note_value = child.get_value()
            if note_value:
                notes.append(note_value)
    
    # Custom facts (other interesting tags)
    custom_facts = {}
    interesting_tags = ["EDUC", "RELI", "NATI", "TITL", "FACT", "EVEN"]
    for child in individual.get_child_elements():
        tag = child.get_tag()
        if tag in interesting_tags:
            value = child.get_value()
            if value:
                if tag in custom_facts:
                    custom_facts[tag].append(value)
                else:
                    custom_facts[tag] = [value]
    
    return {
        "id": individual.get_pointer(),
        "firstName": first_name,
        "lastName": last_name,
        "fullName": f"{first_name} {last_name}".strip(),
        "gender": individual.get_gender(),
        "birthYear": birth_year if birth_year != -1 else None,
        "birthPlace": birth_place,
        "deathYear": death_year,
        "deathPlace": death_place,
        "occupation": occupation,
        "notes": notes,
        "customFacts": custom_facts,
    }


# ============================================================================
# Family Relationship Helpers
# ============================================================================

def get_parents(parser: Parser, person_id: str) -> list[dict[str, Any]] | str:
    """Get parents of a person. Returns list of parent dicts or error message."""
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    parents = parser.get_parents(individual)
    return [get_individual_data(p) for p in parents if isinstance(p, IndividualElement)]


def get_children(parser: Parser, person_id: str) -> list[dict[str, Any]] | str:
    """Get children of a person. Returns list of child dicts or error message."""
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    children = []
    for family in parser.get_families(individual):
        if isinstance(family, FamilyElement):
            for child in parser.get_family_members(family, "CHIL"):
                if isinstance(child, IndividualElement):
                    children.append(get_individual_data(child))
    return children


def get_spouses(parser: Parser, person_id: str) -> list[dict[str, Any]] | str:
    """Get spouse(s) of a person. Returns list of spouse dicts or error message."""
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    gender = individual.get_gender()
    spouses = []
    
    for family in parser.get_families(individual):
        if isinstance(family, FamilyElement):
            # If person is husband, get wife; if wife, get husband
            spouse_role = "WIFE" if gender == "M" else "HUSB"
            for spouse in parser.get_family_members(family, spouse_role):
                if isinstance(spouse, IndividualElement):
                    spouses.append(get_individual_data(spouse))
            # Also check the other role in case gender is unknown
            if gender not in ("M", "F"):
                for spouse in parser.get_family_members(family, "HUSB"):
                    if isinstance(spouse, IndividualElement) and spouse != individual:
                        spouses.append(get_individual_data(spouse))
                for spouse in parser.get_family_members(family, "WIFE"):
                    if isinstance(spouse, IndividualElement) and spouse != individual:
                        spouses.append(get_individual_data(spouse))
    
    return spouses


def get_siblings(parser: Parser, person_id: str) -> list[dict[str, Any]] | str:
    """Get siblings of a person (same parents). Returns list of sibling dicts or error message."""
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    siblings = []
    person_pointer = individual.get_pointer()
    
    # Get parents first
    parents = parser.get_parents(individual)
    
    if not parents:
        return []  # No parents means no siblings
    
    # Find all children of each parent
    seen_ids = {person_pointer}
    for parent in parents:
        if isinstance(parent, IndividualElement):
            for family in parser.get_families(parent):
                if isinstance(family, FamilyElement):
                    for child in parser.get_family_members(family, "CHIL"):
                        if isinstance(child, IndividualElement):
                            child_id = child.get_pointer()
                            if child_id not in seen_ids:
                                seen_ids.add(child_id)
                                siblings.append(get_individual_data(child))
    
    return siblings


def get_grandparents(parser: Parser, person_id: str) -> list[dict[str, Any]] | str:
    """Get grandparents of a person. Returns list of grandparent dicts or error message."""
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    grandparents = []
    seen_ids = set()
    
    parents = parser.get_parents(individual)
    for parent in parents:
        if isinstance(parent, IndividualElement):
            for grandparent in parser.get_parents(parent):
                if isinstance(grandparent, IndividualElement):
                    gp_id = grandparent.get_pointer()
                    if gp_id not in seen_ids:
                        seen_ids.add(gp_id)
                        grandparents.append(get_individual_data(grandparent))
    
    return grandparents


def get_aunts_uncles(parser: Parser, person_id: str) -> list[dict[str, Any]] | str:
    """Get aunts and uncles of a person (parents' siblings). Returns list or error message."""
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    aunts_uncles = []
    seen_ids = set()
    
    parents = parser.get_parents(individual)
    for parent in parents:
        if isinstance(parent, IndividualElement):
            parent_id = parent.get_pointer()
            # Get siblings of this parent
            parent_siblings_result = get_siblings(parser, parent_id)
            if isinstance(parent_siblings_result, list):
                for sibling in parent_siblings_result:
                    sib_id = sibling["id"]
                    if sib_id not in seen_ids:
                        seen_ids.add(sib_id)
                        aunts_uncles.append(sibling)
    
    return aunts_uncles


def get_cousins(parser: Parser, person_id: str) -> list[dict[str, Any]] | str:
    """Get cousins of a person (children of aunts/uncles). Returns list or error message."""
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    cousins = []
    seen_ids = set()
    
    aunts_uncles = get_aunts_uncles(parser, person_id)
    if isinstance(aunts_uncles, str):
        return aunts_uncles  # Error message
    
    for au in aunts_uncles:
        au_children = get_children(parser, au["id"])
        if isinstance(au_children, list):
            for child in au_children:
                child_id = child["id"]
                if child_id not in seen_ids:
                    seen_ids.add(child_id)
                    cousins.append(child)
    
    return cousins


# ============================================================================
# Update Person Metadata (Write Operations)
# ============================================================================

def update_person_metadata(
    parser: Parser,
    person_id: str,
    notes: str | None = None,
    occupation: str | None = None,
    birth_place: str | None = None,
    death_place: str | None = None,
    custom_facts: dict[str, str] | None = None,
) -> dict[str, Any] | str:
    """
    Update metadata fields on a person. Returns dict with old/new values for undo,
    or an error message string if not found.
    
    Supported fields: notes, occupation, birthPlace, deathPlace, customFacts
    """
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: '{person_id}'. Please use a valid GEDCOM ID (e.g., '@I1@') or the person's full name."
    
    # Use the actual ID for the change record
    actual_id = individual.get_pointer()
    
    changes = {
        "person_id": actual_id,
        "timestamp": datetime.now().isoformat(),
        "changes": []
    }
    
    # Helper to add or update a tag
    def set_tag_value(tag: str, value: str, old_value: str | None):
        from gedcom.element.element import Element
        # Find existing tag
        existing = None
        for child in individual.get_child_elements():
            if child.get_tag() == tag:
                existing = child
                break
        
        if existing:
            # Store old value for undo
            changes["changes"].append({
                "field": tag,
                "old_value": existing.get_value(),
                "new_value": value
            })
            # Update by creating new element (python-gedcom doesn't have direct set_value)
            # We need to modify the raw value
            existing.set_value(value)
        else:
            # Add new element
            changes["changes"].append({
                "field": tag,
                "old_value": None,
                "new_value": value
            })
            # Create and add new child element
            new_element = Element(level=1, pointer="", tag=tag, value=value)
            individual.add_child_element(new_element)
    
    if notes is not None:
        # Get existing notes
        old_notes = []
        for child in individual.get_child_elements():
            if child.get_tag() == "NOTE":
                old_notes.append(child.get_value())
        set_tag_value("NOTE", notes, "; ".join(old_notes) if old_notes else None)
    
    if occupation is not None:
        old_occu = None
        for child in individual.get_child_elements():
            if child.get_tag() == "OCCU":
                old_occu = child.get_value()
                break
        set_tag_value("OCCU", occupation, old_occu)
    
    if birth_place is not None:
        # Birth place is stored under BIRT > PLAC
        birth_elem = None
        for child in individual.get_child_elements():
            if child.get_tag() == "BIRT":
                birth_elem = child
                break
        
        if birth_elem:
            old_place = None
            plac_elem = None
            for sub in birth_elem.get_child_elements():
                if sub.get_tag() == "PLAC":
                    plac_elem = sub
                    old_place = sub.get_value()
                    break
            
            changes["changes"].append({
                "field": "BIRT.PLAC",
                "old_value": old_place,
                "new_value": birth_place
            })
            
            if plac_elem:
                plac_elem.set_value(birth_place)
            else:
                from gedcom.element.element import Element
                new_plac = Element(level=2, pointer="", tag="PLAC", value=birth_place)
                birth_elem.add_child_element(new_plac)
    
    if death_place is not None:
        # Death place is stored under DEAT > PLAC
        death_elem = None
        for child in individual.get_child_elements():
            if child.get_tag() == "DEAT":
                death_elem = child
                break
        
        if death_elem:
            old_place = None
            plac_elem = None
            for sub in death_elem.get_child_elements():
                if sub.get_tag() == "PLAC":
                    plac_elem = sub
                    old_place = sub.get_value()
                    break
            
            changes["changes"].append({
                "field": "DEAT.PLAC",
                "old_value": old_place,
                "new_value": death_place
            })
            
            if plac_elem:
                plac_elem.set_value(death_place)
            else:
                from gedcom.element.element import Element
                new_plac = Element(level=2, pointer="", tag="PLAC", value=death_place)
                death_elem.add_child_element(new_plac)
    
    if custom_facts:
        for tag, value in custom_facts.items():
            tag_upper = tag.upper()
            old_val = None
            for child in individual.get_child_elements():
                if child.get_tag() == tag_upper:
                    old_val = child.get_value()
                    break
            set_tag_value(tag_upper, value, old_val)
    
    return changes


def apply_undo(parser: Parser, change_record: dict[str, Any]) -> str:
    """
    Apply an undo operation based on a change record.
    Returns success message or error.
    """
    person_id = change_record.get("person_id")
    individual = find_individual(parser, person_id)
    if not individual:
        return f"Person not found: {person_id}"
    
    for change in change_record.get("changes", []):
        field = change["field"]
        old_value = change["old_value"]
        
        # Handle nested fields like BIRT.PLAC
        if "." in field:
            parent_tag, child_tag = field.split(".", 1)
            parent_elem = None
            for child in individual.get_child_elements():
                if child.get_tag() == parent_tag:
                    parent_elem = child
                    break
            
            if parent_elem:
                for sub in parent_elem.get_child_elements():
                    if sub.get_tag() == child_tag:
                        if old_value is None:
                            # Remove the element (if we added it)
                            parent_elem.get_child_elements().remove(sub)
                        else:
                            sub.set_value(old_value)
                        break
        else:
            # Simple tag
            for child in individual.get_child_elements():
                if child.get_tag() == field:
                    if old_value is None:
                        # Remove the element
                        individual.get_child_elements().remove(child)
                    else:
                        child.set_value(old_value)
                    break
    
    return f"Successfully undid changes for {person_id}"


# ============================================================================
# Transaction-Based Undo System
# ============================================================================

# Global transaction state
_active_transaction = None
_transaction_operations = []


def begin_transaction(description: str = "Transaction") -> dict[str, Any]:
    """
    Begin a new transaction for grouping multiple operations.
    
    Args:
        description: Human-readable description of the transaction
    
    Returns:
        dict: Transaction info with 'id' and 'description'
    """
    global _active_transaction, _transaction_operations
    
    if _active_transaction is not None:
        raise RuntimeError(f"Transaction already in progress: {_active_transaction['description']}")
    
    transaction_id = f"txn_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    _active_transaction = {
        "id": transaction_id,
        "description": description,
        "started_at": datetime.now().isoformat()
    }
    _transaction_operations = []
    
    return _active_transaction


def record_operation(operation: dict[str, Any]) -> None:
    """
    Record an operation as part of the current transaction.
    
    Args:
        operation: dict with operation details for undo
    """
    global _transaction_operations
    
    if _active_transaction is None:
        # Not in a transaction, skip
        return
    
    _transaction_operations.append(operation)


def commit_transaction() -> dict[str, Any]:
    """
    Commit the current transaction and return the complete transaction record.
    
    Returns:
        dict: Complete transaction record for undo
    """
    global _active_transaction, _transaction_operations
    
    if _active_transaction is None:
        raise RuntimeError("No active transaction to commit")
    
    transaction_record = {
        **_active_transaction,
        "operations": _transaction_operations.copy(),
        "committed_at": datetime.now().isoformat(),
        "operation_count": len(_transaction_operations)
    }
    
    # Clear transaction state
    _active_transaction = None
    _transaction_operations = []
    
    return transaction_record


def rollback_transaction() -> None:
    """Rollback (cancel) the current transaction without saving."""
    global _active_transaction, _transaction_operations
    
    if _active_transaction is None:
        raise RuntimeError("No active transaction to rollback")
    
    _active_transaction = None
    _transaction_operations = []


def apply_transaction_undo(parser: Parser, transaction_record: dict[str, Any]) -> dict[str, Any]:
    """
    Undo an entire transaction by reversing all operations.
    Operations are reversed in LIFO order (last operation first).
    
    Args:
        parser: GEDCOM parser
        transaction_record: Transaction record from commit_transaction()
    
    Returns:
        dict with 'success', 'operations_undone', and optional 'errors'
    """
    errors = []
    operations_undone = 0
    
    # Reverse operations (LIFO)
    operations = list(reversed(transaction_record.get("operations", [])))
    
    for operation in operations:
        op_type = operation.get("type")
        
        try:
            if op_type == "add_individual":
                # Remove the added individual
                person_id = operation.get("person_id")
                individual = find_individual_by_id(parser, person_id)
                if individual:
                    parser.get_root_element().get_child_elements().remove(individual)
                    operations_undone += 1
                else:
                    errors.append(f"Could not find person to remove: {person_id}")
            
            elif op_type == "add_source":
                # Remove the added source
                source_id = operation.get("source_id")
                source_elem = None
                for element in parser.get_root_child_elements():
                    if element.get_tag() == "SOUR" and element.get_pointer() == source_id:
                        source_elem = element
                        break
                if source_elem:
                    parser.get_root_element().get_child_elements().remove(source_elem)
                    operations_undone += 1
                else:
                    errors.append(f"Could not find source to remove: {source_id}")
            
            elif op_type == "attach_source":
                # Remove the source citation
                person_id = operation.get("person_id")
                event_type = operation.get("event_type")
                individual = find_individual_by_id(parser, person_id)
                
                if individual:
                    # Find the event and remove the SOUR element
                    for child in individual.get_child_elements():
                        if child.get_tag() == event_type:
                            # Find and remove SOUR child
                            sour_to_remove = None
                            for sub in child.get_child_elements():
                                if sub.get_tag() == "SOUR":
                                    sour_to_remove = sub
                                    break
                            if sour_to_remove:
                                child.get_child_elements().remove(sour_to_remove)
                                operations_undone += 1
                            break
                else:
                    errors.append(f"Could not find person for source removal: {person_id}")
            
            elif op_type == "add_family":
                # Remove the added family
                family_id = operation.get("family_id")
                family_elem = None
                for element in parser.get_root_child_elements():
                    if isinstance(element, FamilyElement) and element.get_pointer() == family_id:
                        family_elem = element
                        break
                if family_elem:
                    parser.get_root_element().get_child_elements().remove(family_elem)
                    operations_undone += 1
                    
                    # Remove FAMC/FAMS references from individuals
                    for ref_id in operation.get("referenced_individuals", []):
                        individual = find_individual_by_id(parser, ref_id)
                        if individual:
                            refs_to_remove = []
                            for child in individual.get_child_elements():
                                if child.get_tag() in ("FAMC", "FAMS") and child.get_value() == family_id:
                                    refs_to_remove.append(child)
                            for ref in refs_to_remove:
                                individual.get_child_elements().remove(ref)
                else:
                    errors.append(f"Could not find family to remove: {family_id}")
            
            elif op_type == "update_metadata":
                # Use existing apply_undo for metadata changes
                result = apply_undo(parser, operation.get("change_record", {}))
                if "Successfully" in result:
                    operations_undone += 1
                else:
                    errors.append(result)
            
            else:
                errors.append(f"Unknown operation type: {op_type}")
        
        except Exception as e:
            errors.append(f"Error undoing operation {op_type}: {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "operations_undone": operations_undone,
        "errors": errors if errors else None
    }


# ============================================================================
# Export GEDCOM
# ============================================================================

def export_gedcom_content(parser: Parser) -> str:
    """Export the current GEDCOM parser state to a string."""
    lines = []
    
    def element_to_lines(element, level=0):
        """Recursively convert an element to GEDCOM lines."""
        pointer = element.get_pointer() or ""
        tag = element.get_tag()
        value = element.get_value() or ""
        
        if pointer:
            line = f"{level} {pointer} {tag}"
        else:
            line = f"{level} {tag}"
        
        if value:
            line += f" {value}"
        
        lines.append(line)
        
        for child in element.get_child_elements():
            element_to_lines(child, level + 1)
    
    # Get root element and iterate through children
    root = parser.get_root_element()
    for child in root.get_child_elements():
        element_to_lines(child, 0)
    
    return "\n".join(lines)


def parse_gedcom_file(file_path: str) -> Parser:
    """Parse a GEDCOM file and return the parser."""
    parser = Parser()
    parser.parse_file(file_path, strict=False)
    return parser


def parse_gedcom_content(content: str) -> Parser:
    """Parse GEDCOM content from a string."""
    import tempfile
    import os
    
    # Write content to temp file (python-gedcom requires file path)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False, encoding='utf-8') as f:
        f.write(content)
        temp_path = f.name
    
    try:
        parser = Parser()
        parser.parse_file(temp_path, strict=False)
        return parser
    finally:
        os.unlink(temp_path)


def get_individual_data(element: IndividualElement) -> dict[str, Any]:
    """Extract data from an individual element."""
    first_name, last_name = element.get_name()
    birth_year = element.get_birth_year()
    death_year = -1
    
    # Try to get death year
    death_data = element.get_death_data()
    if death_data and death_data[0]:
        try:
            # Extract year from death date string
            death_str = death_data[0]
            for part in death_str.split():
                if part.isdigit() and len(part) == 4:
                    death_year = int(part)
                    break
        except (ValueError, AttributeError):
            pass
    
    birth_data = element.get_birth_data()
    birth_place = birth_data[1] if birth_data and len(birth_data) > 1 else None
    
    return {
        "id": element.get_pointer(),
        "firstName": first_name,
        "lastName": last_name,
        "fullName": f"{first_name} {last_name}".strip(),
        "gender": element.get_gender(),
        "birthYear": birth_year if birth_year != -1 else None,
        "deathYear": death_year if death_year != -1 else None,
        "birthPlace": birth_place,
    }


def build_ancestor_tree(parser: Parser, person_id: str, max_depth: int = 10) -> dict[str, Any] | None:
    """
    Build an ancestor tree (going UP) from a person of interest.
    Returns a D3.js-compatible hierarchical structure.
    """
    # Find the person
    person = None
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            if element.get_pointer() == person_id:
                person = element
                break
    
    if not person:
        return None
    
    def build_node(individual: IndividualElement, depth: int) -> dict[str, Any]:
        """Recursively build tree node with ancestors as children."""
        node = get_individual_data(individual)
        node["children"] = []
        
        if depth >= max_depth:
            return node
        
        # Find parents using the parser's get_parents method
        parents = parser.get_parents(individual)
        
        for parent in parents:
            if isinstance(parent, IndividualElement):
                parent_node = build_node(parent, depth + 1)
                node["children"].append(parent_node)
        
        # Remove empty children array for leaf nodes
        if not node["children"]:
            del node["children"]
        
        return node
    
    return build_node(person, 0)


def build_descendant_tree(parser: Parser, person_id: str, max_depth: int = 10) -> dict[str, Any] | None:
    """
    Build a descendant tree (going DOWN) from a person of interest.
    Returns a D3.js-compatible hierarchical structure.
    """
    # Find the person
    person = None
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            if element.get_pointer() == person_id:
                person = element
                break
    
    if not person:
        return None
    
    # Build a map of family relationships
    families: dict[str, FamilyElement] = {}
    for element in parser.get_root_child_elements():
        if isinstance(element, FamilyElement):
            families[element.get_pointer()] = element
    
    def get_children(individual: IndividualElement) -> list[IndividualElement]:
        """Get all children of an individual."""
        children = []
        for family in parser.get_families(individual):
            if isinstance(family, FamilyElement):
                for child in parser.get_family_members(family, "CHIL"):
                    if isinstance(child, IndividualElement):
                        children.append(child)
        return children
    
    def build_node(individual: IndividualElement, depth: int) -> dict[str, Any]:
        """Recursively build tree node with descendants as children."""
        node = get_individual_data(individual)
        node["children"] = []
        
        if depth >= max_depth:
            return node
        
        for child in get_children(individual):
            child_node = build_node(child, depth + 1)
            node["children"].append(child_node)
        
        # Remove empty children array for leaf nodes
        if not node["children"]:
            del node["children"]
        
        return node
    
    return build_node(person, 0)


def build_bidirectional_tree(parser: Parser, person_id: str, ancestor_depth: int = 5, descendant_depth: int = 5) -> dict[str, Any] | None:
    """
    Build a bidirectional tree showing both ancestors (parents) and descendants (children)
    from a person of interest. Returns a D3.js-compatible hierarchical structure.
    
    The root person is at the center, with:
    - ancestors on the right (using "children" property for D3 compatibility)
    - descendants on the left (using "descendants" property)
    """
    # Find the person
    person = None
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            if element.get_pointer() == person_id:
                person = element
                break
    
    if not person:
        return None
    
    def get_children_elements(individual: IndividualElement) -> list[IndividualElement]:
        """Get all children of an individual."""
        children = []
        for family in parser.get_families(individual):
            if isinstance(family, FamilyElement):
                for child in parser.get_family_members(family, "CHIL"):
                    if isinstance(child, IndividualElement):
                        children.append(child)
        return children
    
    def build_ancestor_node(individual: IndividualElement, depth: int) -> dict[str, Any]:
        """Recursively build tree node with ancestors as children."""
        node = get_individual_data(individual)
        node["direction"] = "ancestor"
        node["children"] = []
        
        if depth >= ancestor_depth:
            del node["children"]
            return node
        
        parents = parser.get_parents(individual)
        for parent in parents:
            if isinstance(parent, IndividualElement):
                parent_node = build_ancestor_node(parent, depth + 1)
                node["children"].append(parent_node)
        
        if not node["children"]:
            del node["children"]
        
        return node
    
    def build_descendant_node(individual: IndividualElement, depth: int) -> dict[str, Any]:
        """Recursively build tree node with descendants as children."""
        node = get_individual_data(individual)
        node["direction"] = "descendant"
        node["children"] = []
        
        if depth >= descendant_depth:
            del node["children"]
            return node
        
        for child in get_children_elements(individual):
            child_node = build_descendant_node(child, depth + 1)
            node["children"].append(child_node)
        
        if not node["children"]:
            del node["children"]
        
        return node
    
    # Build the root node with both directions
    root_node = get_individual_data(person)
    root_node["direction"] = "root"
    
    # Build ancestors (parents, grandparents, etc.)
    ancestors = []
    for parent in parser.get_parents(person):
        if isinstance(parent, IndividualElement):
            ancestors.append(build_ancestor_node(parent, 1))
    
    if ancestors:
        root_node["ancestors"] = ancestors
    
    # Build descendants (children, grandchildren, etc.)
    descendants = []
    for child in get_children_elements(person):
        descendants.append(build_descendant_node(child, 1))
    
    if descendants:
        root_node["descendants"] = descendants
    
    return root_node


def get_all_individuals(parser: Parser) -> list[dict[str, Any]]:
    """Get a list of all individuals in the GEDCOM file."""
    individuals = []
    
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            individuals.append(get_individual_data(element))
    
    return individuals


def find_root_ancestors(parser: Parser) -> list[dict[str, Any]]:
    """Find individuals who have no parents (root ancestors)."""
    roots = []
    
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            parents = parser.get_parents(element)
            if not parents:
                roots.append(get_individual_data(element))
    
    return roots


def find_youngest_generation(parser: Parser) -> list[dict[str, Any]]:
    """Find individuals who have no children (youngest generation)."""
    youngest = []
    
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            # Check if this person appears as a parent in any family
            is_parent = False
            for family in parser.get_root_child_elements():
                if isinstance(family, FamilyElement):
                    parents = list(parser.get_family_members(family, "HUSB")) + \
                              list(parser.get_family_members(family, "WIFE"))
                    if element in parents:
                        children = list(parser.get_family_members(family, "CHIL"))
                        if children:
                            is_parent = True
                            break
            
            if not is_parent:
                youngest.append(get_individual_data(element))
    
    return youngest


# ============================================================================
# GEDCOM Write Operations - Individual Creation
# ============================================================================

def generate_new_individual_id(parser: Parser) -> str:
    """Generate a new unique individual ID."""
    existing_ids = []
    for element in parser.get_root_child_elements():
        if isinstance(element, IndividualElement):
            pointer = element.get_pointer()
            if pointer:
                # Extract number from @I123@ format
                try:
                    num = int(pointer.strip('@').strip('I'))
                    existing_ids.append(num)
                except (ValueError, AttributeError):
                    pass
    
    max_id = max(existing_ids) if existing_ids else 0
    return f"@I{max_id + 1}@"


def generate_new_family_id(parser: Parser) -> str:
    """Generate a new unique family ID."""
    existing_ids = []
    for element in parser.get_root_child_elements():
        if isinstance(element, FamilyElement):
            pointer = element.get_pointer()
            if pointer:
                # Extract number from @F123@ format
                try:
                    num = int(pointer.strip('@').strip('F'))
                    existing_ids.append(num)
                except (ValueError, AttributeError):
                    pass
    
    max_id = max(existing_ids) if existing_ids else 0
    return f"@F{max_id + 1}@"


def generate_new_source_id(parser: Parser) -> str:
    """Generate a new unique source ID."""
    existing_ids = []
    for element in parser.get_root_child_elements():
        if element.get_tag() == "SOUR" and element.get_pointer():
            pointer = element.get_pointer()
            try:
                num = int(pointer.strip('@').strip('S'))
                existing_ids.append(num)
            except (ValueError, AttributeError):
                pass
    
    max_id = max(existing_ids) if existing_ids else 0
    return f"@S{max_id + 1}@"


def validate_and_correct_date(date_str: str | None) -> tuple[str | None, list[str]]:
    """
    Validate and auto-correct date strings.
    Returns (corrected_date, warnings_list).
    
    Handles formats like:
    - "15 MAR 1850"
    - "MAR 1850"
    - "1850"
    - "ABT 1850"
    - "BEF 1850"
    """
    warnings = []
    if not date_str:
        return None, warnings
    
    date_str = date_str.strip().upper()
    
    # Valid GEDCOM date modifiers
    valid_modifiers = ["ABT", "CAL", "EST", "BEF", "AFT", "BET", "FROM", "TO"]
    
    # Check for basic validity - should contain at least a year
    parts = date_str.split()
    has_year = any(p.isdigit() and len(p) == 4 for p in parts)
    
    if not has_year:
        warnings.append(f"Date '{date_str}' does not contain a valid 4-digit year. Treating as approximate.")
        return f"ABT {date_str}", warnings
    
    # GEDCOM month abbreviations
    valid_months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                   "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    
    # Auto-correct common month name variations
    month_corrections = {
        "JANUARY": "JAN", "FEBRUARY": "FEB", "MARCH": "MAR", "APRIL": "APR",
        "JUNE": "JUN", "JULY": "JUL", "AUGUST": "AUG", "SEPTEMBER": "SEP",
        "OCTOBER": "OCT", "NOVEMBER": "NOV", "DECEMBER": "DEC"
    }
    
    corrected_parts = []
    for part in parts:
        if part in month_corrections:
            corrected = month_corrections[part]
            warnings.append(f"Corrected month '{part}' to '{corrected}'")
            corrected_parts.append(corrected)
        else:
            corrected_parts.append(part)
    
    return " ".join(corrected_parts), warnings


def check_date_consistency(birth_date: str | None, death_date: str | None, 
                          parent_birth_date: str | None = None) -> list[str]:
    """
    Check logical consistency of dates.
    Returns list of warnings/errors.
    """
    warnings = []
    
    def extract_year(date_str: str | None) -> int | None:
        """Extract year from GEDCOM date string."""
        if not date_str:
            return None
        parts = date_str.split()
        for part in parts:
            if part.isdigit() and len(part) == 4:
                return int(part)
        return None
    
    birth_year = extract_year(birth_date)
    death_year = extract_year(death_date)
    parent_birth_year = extract_year(parent_birth_date)
    
    # Check birth before death
    if birth_year and death_year:
        if death_year < birth_year:
            warnings.append(f"ERROR: Death year ({death_year}) is before birth year ({birth_year})")
        elif death_year - birth_year > 120:
            warnings.append(f"WARNING: Age at death ({death_year - birth_year}) exceeds 120 years")
    
    # Check parent age at child's birth
    if birth_year and parent_birth_year:
        parent_age = birth_year - parent_birth_year
        if parent_age < 10:
            warnings.append(f"ERROR: Parent age at child's birth ({parent_age}) is too young (< 10)")
        elif parent_age > 80:
            warnings.append(f"WARNING: Parent age at child's birth ({parent_age}) exceeds 80 years")
    
    return warnings


def detect_circular_ancestry(parser: Parser, person_id: str, potential_parent_id: str) -> bool:
    """
    Check if adding potential_parent as parent of person would create circular ancestry.
    Returns True if circular relationship detected.
    """
    # Build set of all ancestors of potential_parent
    def get_all_ancestors(pid: str, visited: set[str] = None) -> set[str]:
        if visited is None:
            visited = set()
        if pid in visited:
            return visited
        visited.add(pid)
        
        individual = find_individual_by_id(parser, pid)
        if not individual:
            return visited
        
        parents = parser.get_parents(individual)
        for parent in parents:
            if isinstance(parent, IndividualElement):
                get_all_ancestors(parent.get_pointer(), visited)
        
        return visited
    
    ancestors_of_potential_parent = get_all_ancestors(potential_parent_id)
    
    # If person_id is in ancestors of potential_parent, we'd create a cycle
    normalized_person_id = person_id if person_id.startswith('@') else f"@{person_id}@"
    return normalized_person_id in ancestors_of_potential_parent


def add_individual(
    parser: Parser,
    first_name: str,
    last_name: str,
    gender: str = "U",
    birth_date: str | None = None,
    birth_place: str | None = None,
    death_date: str | None = None,
    death_place: str | None = None,
    notes: list[str] | None = None
) -> dict[str, Any]:
    """
    Add a new individual to the GEDCOM file.
    
    Args:
        parser: GEDCOM parser
        first_name: Given name
        last_name: Surname
        gender: 'M', 'F', or 'U' (unknown)
        birth_date: Birth date in GEDCOM format (e.g., "15 MAR 1850")
        birth_place: Birth place
        death_date: Death date in GEDCOM format
        death_place: Death place
        notes: List of notes to add
    
    Returns:
        dict with 'id', 'warnings', and 'success' fields
    """
    from gedcom.element.element import Element
    
    warnings = []
    
    # Validate gender
    if gender not in ('M', 'F', 'U'):
        warnings.append(f"Invalid gender '{gender}', defaulting to 'U' (unknown)")
        gender = 'U'
    
    # Validate and correct dates
    birth_date, birth_warnings = validate_and_correct_date(birth_date)
    warnings.extend(birth_warnings)
    
    death_date, death_warnings = validate_and_correct_date(death_date)
    warnings.extend(death_warnings)
    
    # Check date consistency
    consistency_warnings = check_date_consistency(birth_date, death_date)
    warnings.extend(consistency_warnings)
    
    # Check for ERROR level warnings
    if any("ERROR:" in w for w in warnings):
        return {
            "success": False,
            "warnings": warnings,
            "error": "Date validation failed with errors. Please correct dates."
        }
    
    # Generate new ID
    new_id = generate_new_individual_id(parser)
    
    # Create individual element
    indi = IndividualElement(level=0, pointer=new_id, tag='INDI', value='')
    
    # Add NAME
    name_elem = Element(level=1, pointer='', tag='NAME', value=f"{first_name} /{last_name}/")
    indi.add_child_element(name_elem)
    
    # Add GIVN and SURN substructures
    givn = Element(level=2, pointer='', tag='GIVN', value=first_name)
    surn = Element(level=2, pointer='', tag='SURN', value=last_name)
    name_elem.add_child_element(givn)
    name_elem.add_child_element(surn)
    
    # Add SEX
    sex_elem = Element(level=1, pointer='', tag='SEX', value=gender)
    indi.add_child_element(sex_elem)
    
    # Add BIRT event
    if birth_date or birth_place:
        birth_elem = Element(level=1, pointer='', tag='BIRT', value='')
        indi.add_child_element(birth_elem)
        
        if birth_date:
            date_elem = Element(level=2, pointer='', tag='DATE', value=birth_date)
            birth_elem.add_child_element(date_elem)
        
        if birth_place:
            place_elem = Element(level=2, pointer='', tag='PLAC', value=birth_place)
            birth_elem.add_child_element(place_elem)
    
    # Add DEAT event
    if death_date or death_place:
        death_elem = Element(level=1, pointer='', tag='DEAT', value='')
        indi.add_child_element(death_elem)
        
        if death_date:
            date_elem = Element(level=2, pointer='', tag='DATE', value=death_date)
            death_elem.add_child_element(date_elem)
        
        if death_place:
            place_elem = Element(level=2, pointer='', tag='PLAC', value=death_place)
            death_elem.add_child_element(place_elem)
    
    # Add NOTEs
    if notes:
        for note_text in notes:
            note_elem = Element(level=1, pointer='', tag='NOTE', value=note_text)
            indi.add_child_element(note_elem)
    
    # Add CHAN (change date)
    chan_elem = Element(level=1, pointer='', tag='CHAN', value='')
    indi.add_child_element(chan_elem)
    
    date_elem = Element(level=2, pointer='', tag='DATE', value=datetime.now().strftime("%d %b %Y").upper())
    chan_elem.add_child_element(date_elem)
    
    time_elem = Element(level=3, pointer='', tag='TIME', value=datetime.now().strftime("%H:%M:%S"))
    date_elem.add_child_element(time_elem)
    
    # Add to parser
    parser.get_root_element().add_child_element(indi)
    
    # Invalidate cache so the new individual is properly found
    parser.invalidate_cache()
    
    # Record operation for transaction-based undo
    record_operation({
        "type": "add_individual",
        "person_id": new_id,
        "data": {
            "firstName": first_name,
            "lastName": last_name,
            "gender": gender
        }
    })
    
    return {
        "success": True,
        "id": new_id,
        "warnings": warnings
    }


def create_source_record(
    parser: Parser,
    title: str,
    author: str | None = None,
    publication: str | None = None,
    abbreviation: str | None = None,
    text: str | None = None,
    url: str | None = None,
    repository_name: str | None = None
) -> dict[str, Any]:
    """
    Create a GEDCOM 5.5.1 SOURCE record.
    
    Args:
        parser: GEDCOM parser
        title: Title of the source (required)
        author: Author/originator
        publication: Publication facts
        abbreviation: Short abbreviation
        text: Verbatim text from source
        url: URL (stored in NOTE field)
        repository_name: Name of repository
    
    Returns:
        dict with 'id' and 'success' fields
    """
    from gedcom.element.element import Element
    
    # Generate new source ID
    source_id = generate_new_source_id(parser)
    
    # Create source element
    sour = Element(level=0, pointer=source_id, tag='SOUR', value='')
    
    # Add TITL (required)
    titl = Element(level=1, pointer='', tag='TITL', value=title)
    sour.add_child_element(titl)
    
    # Add AUTH (optional)
    if author:
        auth = Element(level=1, pointer='', tag='AUTH', value=author)
        sour.add_child_element(auth)
    
    # Add PUBL (optional)
    if publication:
        publ = Element(level=1, pointer='', tag='PUBL', value=publication)
        sour.add_child_element(publ)
    
    # Add ABBR (optional)
    if abbreviation:
        abbr = Element(level=1, pointer='', tag='ABBR', value=abbreviation)
        sour.add_child_element(abbr)
    
    # Add TEXT (optional)
    if text:
        text_elem = Element(level=1, pointer='', tag='TEXT', value=text)
        sour.add_child_element(text_elem)
    
    # Add URL as NOTE
    if url:
        note = Element(level=1, pointer='', tag='NOTE', value=f"URL: {url}")
        sour.add_child_element(note)
    
    # Add repository if provided
    if repository_name:
        # For simplicity, we'll add repository name as NOTE
        # Full REPO implementation would require separate REPO records
        repo_note = Element(level=1, pointer='', tag='NOTE', value=f"Repository: {repository_name}")
        sour.add_child_element(repo_note)
    
    # Add CHAN (change date)
    chan_elem = Element(level=1, pointer='', tag='CHAN', value='')
    sour.add_child_element(chan_elem)
    
    date_elem = Element(level=2, pointer='', tag='DATE', value=datetime.now().strftime("%d %b %Y").upper())
    chan_elem.add_child_element(date_elem)
    
    time_elem = Element(level=3, pointer='', tag='TIME', value=datetime.now().strftime("%H:%M:%S"))
    date_elem.add_child_element(time_elem)
    
    # Add to parser
    parser.get_root_element().add_child_element(sour)
    
    # Invalidate cache so the new source is properly found
    parser.invalidate_cache()
    
    # Record operation for transaction-based undo
    record_operation({
        "type": "add_source",
        "source_id": source_id,
        "title": title
    })
    
    return {
        "success": True,
        "id": source_id
    }


def attach_source_citation(
    parser: Parser,
    person_id: str,
    source_id: str,
    event_type: str = "BIRT",
    page: str | None = None,
    quality: int = 3,
    citation_text: str | None = None
) -> dict[str, Any]:
    """
    Attach a source citation to a person's event.
    
    Args:
        parser: GEDCOM parser
        person_id: Individual's GEDCOM ID
        source_id: Source record ID
        event_type: Event tag (BIRT, DEAT, NAME, etc.)
        page: Specific page/location in source
        quality: Quality assessment 0-3 (0=unreliable, 3=primary evidence)
        citation_text: Extracted text from source
    
    Returns:
        dict with 'success' field
    """
    from gedcom.element.element import Element
    
    individual = find_individual(parser, person_id)
    if not individual:
        return {"success": False, "error": f"Person not found: {person_id}"}
    
    # Normalize source_id
    if not source_id.startswith('@'):
        source_id = f"@{source_id}@"
    
    # Find or create the event element
    event_elem = None
    for child in individual.get_child_elements():
        if child.get_tag() == event_type:
            event_elem = child
            break
    
    if not event_elem:
        # Create the event if it doesn't exist
        event_elem = Element(level=1, pointer='', tag=event_type, value='')
        individual.add_child_element(event_elem)
    
    # Create SOUR citation
    sour_elem = Element(level=2, pointer='', tag='SOUR', value=source_id)
    event_elem.add_child_element(sour_elem)
    
    # Add PAGE (specific location in source)
    if page:
        page_elem = Element(level=3, pointer='', tag='PAGE', value=page)
        sour_elem.add_child_element(page_elem)
    
    # Add QUAY (quality assessment)
    if quality in (0, 1, 2, 3):
        quay_elem = Element(level=3, pointer='', tag='QUAY', value=str(quality))
        sour_elem.add_child_element(quay_elem)
    
    # Add DATA with extracted text
    if citation_text:
        data_elem = Element(level=3, pointer='', tag='DATA', value='')
        sour_elem.add_child_element(data_elem)
        
        text_elem = Element(level=4, pointer='', tag='TEXT', value=citation_text)
        data_elem.add_child_element(text_elem)
    
    # Record operation for transaction-based undo
    record_operation({
        "type": "attach_source",
        "person_id": individual.get_pointer(),
        "source_id": source_id,
        "event_type": event_type
    })
    
    return {"success": True}


def create_family_record(
    parser: Parser,
    husband_id: str | None = None,
    wife_id: str | None = None,
    marriage_date: str | None = None,
    marriage_place: str | None = None
) -> dict[str, Any]:
    """
    Create a new family record.
    
    Args:
        parser: GEDCOM parser
        husband_id: Husband's GEDCOM ID (optional)
        wife_id: Wife's GEDCOM ID (optional)
        marriage_date: Marriage date in GEDCOM format
        marriage_place: Marriage place
    
    Returns:
        dict with 'id' and 'success' fields
    """
    from gedcom.element.element import Element
    
    # Generate new family ID
    family_id = generate_new_family_id(parser)
    
    # Create family element
    fam = FamilyElement(level=0, pointer=family_id, tag='FAM', value='')
    
    # Add HUSB (husband)
    if husband_id:
        if not husband_id.startswith('@'):
            husband_id = f"@{husband_id}@"
        husb = Element(level=1, pointer='', tag='HUSB', value=husband_id)
        fam.add_child_element(husb)
    
    # Add WIFE
    if wife_id:
        if not wife_id.startswith('@'):
            wife_id = f"@{wife_id}@"
        wife = Element(level=1, pointer='', tag='WIFE', value=wife_id)
        fam.add_child_element(wife)
    
    # Add MARR event
    if marriage_date or marriage_place:
        marr_elem = Element(level=1, pointer='', tag='MARR', value='')
        fam.add_child_element(marr_elem)
        
        if marriage_date:
            date_elem = Element(level=2, pointer='', tag='DATE', value=marriage_date)
            marr_elem.add_child_element(date_elem)
        
        if marriage_place:
            place_elem = Element(level=2, pointer='', tag='PLAC', value=marriage_place)
            marr_elem.add_child_element(place_elem)
    
    # Add to parser
    parser.get_root_element().add_child_element(fam)
    
    # Invalidate cache so the new family is found by get_families()
    parser.invalidate_cache()
    
    # Record operation for transaction-based undo
    referenced_individuals = []
    if husband_id:
        referenced_individuals.append(husband_id)
    if wife_id:
        referenced_individuals.append(wife_id)
    
    record_operation({
        "type": "add_family",
        "family_id": family_id,
        "referenced_individuals": referenced_individuals
    })
    
    return {
        "success": True,
        "id": family_id
    }


def add_child_to_family(
    parser: Parser,
    family_id: str,
    child_id: str
) -> dict[str, Any]:
    """
    Add a child to an existing family record.
    
    Args:
        parser: GEDCOM parser
        family_id: Family's GEDCOM ID
        child_id: Child's GEDCOM ID
    
    Returns:
        dict with 'success' field
    """
    from gedcom.element.element import Element
    
    # Normalize IDs
    if not family_id.startswith('@'):
        family_id = f"@{family_id}@"
    if not child_id.startswith('@'):
        child_id = f"@{child_id}@"
    
    # Find family
    family = None
    for element in parser.get_root_child_elements():
        if isinstance(element, FamilyElement) and element.get_pointer() == family_id:
            family = element
            break
    
    if not family:
        return {"success": False, "error": f"Family not found: {family_id}"}
    
    # Add CHIL reference
    chil = Element(level=1, pointer='', tag='CHIL', value=child_id)
    family.add_child_element(chil)
    
    # Also add FAMC reference to child
    child = find_individual_by_id(parser, child_id)
    if child:
        famc = Element(level=1, pointer='', tag='FAMC', value=family_id)
        child.add_child_element(famc)
    
    # Invalidate cache so relationships are properly found
    parser.invalidate_cache()
    
    return {"success": True}


def add_family_relationship(
    parser: Parser,
    parent_id: str,
    child_id: str,
    check_circular: bool = True
) -> dict[str, Any]:
    """
    Add a parent-child relationship.
    Creates or updates family records as needed.
    
    Args:
        parser: GEDCOM parser
        parent_id: Parent's GEDCOM ID
        child_id: Child's GEDCOM ID
        check_circular: Whether to check for circular ancestry
    
    Returns:
        dict with 'success', 'family_id', and optional 'warnings' fields
    """
    warnings = []
    
    # Normalize IDs
    if not parent_id.startswith('@'):
        parent_id = f"@{parent_id}@"
    if not child_id.startswith('@'):
        child_id = f"@{child_id}@"
    
    # Check for circular ancestry
    if check_circular and detect_circular_ancestry(parser, child_id, parent_id):
        return {
            "success": False,
            "error": f"Cannot add relationship: would create circular ancestry. {parent_id} is a descendant of {child_id}."
        }
    
    # Validate parent/child ages
    parent = find_individual_by_id(parser, parent_id)
    child = find_individual_by_id(parser, child_id)
    
    if parent and child:
        parent_birth = parent.get_birth_data()
        child_birth = child.get_birth_data()
        
        if parent_birth and child_birth:
            parent_birth_date = parent_birth[0] if parent_birth else None
            child_birth_date = child_birth[0] if child_birth else None
            
            date_warnings = check_date_consistency(
                child_birth_date,
                None,
                parent_birth_date
            )
            warnings.extend(date_warnings)
            
            if any("ERROR:" in w for w in warnings):
                return {
                    "success": False,
                    "error": "Age validation failed. Parent too young to have child.",
                    "warnings": warnings
                }
    
    # Find parent's gender
    parent_gender = parent.get_gender() if parent else 'U'
    
    # Check if child already has parents in a family
    existing_family = None
    if child:
        for child_elem in child.get_child_elements():
            if child_elem.get_tag() == "FAMC":
                # Child already has a family
                existing_family_id = child_elem.get_value()
                for element in parser.get_root_child_elements():
                    if isinstance(element, FamilyElement) and element.get_pointer() == existing_family_id:
                        existing_family = element
                        break
                break
    
    if existing_family:
        # Add parent to existing family
        # Check if parent slot is available
        has_husband = False
        has_wife = False
        
        for fam_child in existing_family.get_child_elements():
            if fam_child.get_tag() == "HUSB":
                has_husband = True
            elif fam_child.get_tag() == "WIFE":
                has_wife = True
        
        # Add parent based on gender and availability
        from gedcom.element.element import Element
        
        if parent_gender == 'M' and not has_husband:
            husb = Element(level=1, pointer='', tag='HUSB', value=parent_id)
            existing_family.add_child_element(husb)
        elif parent_gender == 'F' and not has_wife:
            wife = Element(level=1, pointer='', tag='WIFE', value=parent_id)
            existing_family.add_child_element(wife)
        elif not has_husband:
            husb = Element(level=1, pointer='', tag='HUSB', value=parent_id)
            existing_family.add_child_element(husb)
        elif not has_wife:
            wife = Element(level=1, pointer='', tag='WIFE', value=parent_id)
            existing_family.add_child_element(wife)
        else:
            return {
                "success": False,
                "error": f"Family {existing_family.get_pointer()} already has both parents."
            }
        
        # Add FAMS reference to parent
        if parent:
            fams = Element(level=1, pointer='', tag='FAMS', value=existing_family.get_pointer())
            parent.add_child_element(fams)
        
        return {
            "success": True,
            "family_id": existing_family.get_pointer(),
            "warnings": warnings
        }
    else:
        # Create new family
        family_result = create_family_record(
            parser,
            husband_id=parent_id if parent_gender == 'M' else None,
            wife_id=parent_id if parent_gender == 'F' else None
        )
        
        if not family_result["success"]:
            return family_result
        
        family_id = family_result["id"]
        
        # Add child to family
        child_result = add_child_to_family(parser, family_id, child_id)
        
        if not child_result["success"]:
            return child_result
        
        # Add FAMS reference to parent
        if parent:
            from gedcom.element.element import Element
            fams = Element(level=1, pointer='', tag='FAMS', value=family_id)
            parent.add_child_element(fams)
        
        return {
            "success": True,
            "family_id": family_id,
            "warnings": warnings
        }


def add_spouse_relationship(
    parser: Parser,
    spouse1_id: str,
    spouse2_id: str,
    marriage_date: str | None = None,
    marriage_place: str | None = None
) -> dict[str, Any]:
    """
    Add a spouse relationship.
    Creates a new family record linking the spouses.
    
    Args:
        parser: GEDCOM parser
        spouse1_id: First spouse's GEDCOM ID
        spouse2_id: Second spouse's GEDCOM ID
        marriage_date: Marriage date in GEDCOM format
        marriage_place: Marriage place
    
    Returns:
        dict with 'success' and 'family_id' fields
    """
    from gedcom.element.element import Element
    
    # Normalize IDs
    if not spouse1_id.startswith('@'):
        spouse1_id = f"@{spouse1_id}@"
    if not spouse2_id.startswith('@'):
        spouse2_id = f"@{spouse2_id}@"
    
    # Get individuals
    spouse1 = find_individual_by_id(parser, spouse1_id)
    spouse2 = find_individual_by_id(parser, spouse2_id)
    
    if not spouse1:
        return {"success": False, "error": f"Spouse 1 not found: {spouse1_id}"}
    if not spouse2:
        return {"success": False, "error": f"Spouse 2 not found: {spouse2_id}"}
    
    # Determine husband/wife based on gender
    gender1 = spouse1.get_gender()
    gender2 = spouse2.get_gender()
    
    husband_id = None
    wife_id = None
    
    if gender1 == 'M' and gender2 == 'F':
        husband_id = spouse1_id
        wife_id = spouse2_id
    elif gender1 == 'F' and gender2 == 'M':
        husband_id = spouse2_id
        wife_id = spouse1_id
    elif gender1 == 'M':
        husband_id = spouse1_id
        wife_id = spouse2_id
    elif gender2 == 'M':
        husband_id = spouse2_id
        wife_id = spouse1_id
    else:
        # Default assignment
        husband_id = spouse1_id
        wife_id = spouse2_id
    
    # Create family record
    family_result = create_family_record(
        parser,
        husband_id=husband_id,
        wife_id=wife_id,
        marriage_date=marriage_date,
        marriage_place=marriage_place
    )
    
    if not family_result["success"]:
        return family_result
    
    family_id = family_result["id"]
    
    # Add FAMS references to both spouses
    fams1 = Element(level=1, pointer='', tag='FAMS', value=family_id)
    spouse1.add_child_element(fams1)
    
    fams2 = Element(level=1, pointer='', tag='FAMS', value=family_id)
    spouse2.add_child_element(fams2)
    
    return {
        "success": True,
        "family_id": family_id
    }


# ============================================================================
# Duplicate Detection
# ============================================================================

def calculate_person_similarity(existing: dict[str, Any], candidate: dict[str, Any]) -> float:
    """
    Calculate similarity score (0.0 to 1.0) between existing person and candidate.
    
    Weights:
    - Name similarity: 35%
    - Birth year proximity: 25%
    - Birth place match: 20%
    - Gender match: 10%
    - Death year proximity: 10%
    
    Args:
        existing: PersonMetadata dict from get_person_full_details()
        candidate: dict with 'fullName', 'birthYear', 'birthPlace', 'gender', 'deathYear'
    
    Returns:
        float: Similarity score 0.0 to 1.0
    """
    score = 0.0
    
    # 1. NAME MATCHING (35 points) - Use Levenshtein distance
    name_score = 0.0
    if candidate.get('fullName') and existing.get('fullName'):
        # SequenceMatcher ratio: 0.0 (completely different) to 1.0 (identical)
        ratio = SequenceMatcher(
            None,
            existing['fullName'].lower(),
            candidate['fullName'].lower()
        ).ratio()
        name_score = ratio * 0.35
    score += name_score
    
    # 2. BIRTH YEAR PROXIMITY (25 points)
    if existing.get('birthYear') and candidate.get('birthYear'):
        year_diff = abs(existing['birthYear'] - candidate['birthYear'])
        if year_diff == 0:
            score += 0.25
        elif year_diff <= 1:
            score += 0.20  # Off by 1 year (record errors common)
        elif year_diff <= 3:
            score += 0.15  # Off by 2-3 years
        elif year_diff <= 5:
            score += 0.10  # Off by 4-5 years
        # else: 0 points for >5 year difference
    
    # 3. BIRTH PLACE MATCHING (20 points)
    if existing.get('birthPlace') and candidate.get('birthPlace'):
        place1 = existing['birthPlace'].lower().strip()
        place2 = candidate['birthPlace'].lower().strip()
        
        # Exact match
        if place1 == place2:
            score += 0.20
        # Contains match (e.g., "Boston, MA" contains "Boston")
        elif place2 in place1 or place1 in place2:
            score += 0.15
        # Split into components and check overlap
        else:
            parts1 = set(p.strip() for p in place1.split(','))
            parts2 = set(p.strip() for p in place2.split(','))
            if parts1 and parts2:
                overlap = len(parts1 & parts2) / max(len(parts1), len(parts2))
                score += overlap * 0.20
    
    # 4. GENDER MATCH (10 points)
    if existing.get('gender') and candidate.get('gender'):
        if existing['gender'] == candidate['gender']:
            score += 0.10
        elif 'U' not in (existing['gender'], candidate['gender']):
            # Penalty for definite gender mismatch (unless one is unknown)
            score -= 0.05
    
    # 5. DEATH YEAR PROXIMITY (10 points)
    if existing.get('deathYear') and candidate.get('deathYear'):
        year_diff = abs(existing['deathYear'] - candidate['deathYear'])
        if year_diff == 0:
            score += 0.10
        elif year_diff <= 2:
            score += 0.07
        elif year_diff <= 5:
            score += 0.04
    
    return max(0.0, min(1.0, score))  # Clamp to [0.0, 1.0]


def find_potential_duplicates(
    parser: Parser,
    candidate: dict[str, Any],
    threshold: float = 0.60
) -> list[dict[str, Any]]:
    """
    Find all existing persons that could be duplicates of the candidate.
    
    Args:
        parser: GEDCOM parser
        candidate: dict with 'fullName', 'birthYear', 'birthPlace', 'gender', 'deathYear'
        threshold: Minimum similarity score to include (default 0.60 = 60%)
    
    Returns:
        list of dicts: [
            {
                'person': PersonMetadata dict,
                'similarity': float,
                'percentage': int  # 0-100
            },
            ...
        ]
        Sorted by similarity score (highest first)
    """
    matches = []
    
    # Get all individuals
    individuals = get_all_individuals(parser)
    
    for person in individuals:
        # Get full details for better comparison
        details = get_person_full_details(parser, person['id'])
        
        if isinstance(details, dict):  # Not an error string
            score = calculate_person_similarity(details, candidate)
            
            if score >= threshold:
                matches.append({
                    'person': details,
                    'similarity': score,
                    'percentage': int(score * 100)
                })
    
    # Sort by score descending (best matches first)
    matches.sort(key=lambda x: x['similarity'], reverse=True)
    
    return matches
