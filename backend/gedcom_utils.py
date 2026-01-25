"""GEDCOM file parsing and D3.js tree conversion utilities."""

from typing import Any
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement
from gedcom.element.family import FamilyElement


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
