"""GEDCOM file parsing and D3.js tree conversion utilities."""

from datetime import datetime
from typing import Any
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
