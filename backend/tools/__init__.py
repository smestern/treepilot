from .wikipedia import search_wikipedia
from .wikidata import search_wikidata
from .newspapers import search_newspapers
from .books import search_books
from .tavily import search_web_tavily
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
    add_person_to_tree,
    link_parent_child,
    link_spouses,
    add_source_to_person,
    begin_person_transaction,
    commit_person_transaction,
    undo_transaction,
)

__all__ = [
    "search_wikipedia",
    "search_wikidata", 
    "search_newspapers",
    "search_books",
    "search_web_tavily",  # Backup web search via Tavily API
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
    # Person management tools
    "add_person_to_tree",
    "link_parent_child",
    "link_spouses",
    "add_source_to_person",
    "begin_person_transaction",
    "commit_person_transaction",
    "undo_transaction",
]
