from .wikipedia import search_wikipedia
from .wikidata import search_wikidata
from .newspapers import search_newspapers
from .books import search_books
from .gedcom_tree import (
    get_person_metadata,
    get_person_parents,
    get_person_children,
    get_person_spouses,
    get_person_siblings,
    get_person_grandparents,
    get_person_aunts_uncles,
    get_person_cousins,
    update_person_metadata,
    undo_last_change,
    set_gedcom_accessors,
)

__all__ = [
    "search_wikipedia",
    "search_wikidata", 
    "search_newspapers",
    "search_books",
    # GEDCOM tree tools
    "get_person_metadata",
    "get_person_parents",
    "get_person_children",
    "get_person_spouses",
    "get_person_siblings",
    "get_person_grandparents",
    "get_person_aunts_uncles",
    "get_person_cousins",
    "update_person_metadata",
    "undo_last_change",
    "set_gedcom_accessors",
]
