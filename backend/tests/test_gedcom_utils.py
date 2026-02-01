"""Tests for GEDCOM utilities.

Uses the sample-family.ged file (English and British Monarchs) for testing.
"""

import os
import pytest
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gedcom_utils import (
    # Parsing
    parse_gedcom_file,
    parse_gedcom_content,
    export_gedcom_content,
    # Individual lookup
    find_individual,
    find_individual_by_id,
    find_individual_by_name,
    get_individual_data,
    get_person_full_details,
    get_all_individuals,
    # Relationships
    get_parents,
    get_children,
    get_spouses,
    get_siblings,
    get_grandparents,
    get_aunts_uncles,
    get_cousins,
    # Tree building
    build_ancestor_tree,
    build_descendant_tree,
    build_bidirectional_tree,
    find_root_ancestors,
    find_youngest_generation,
    # Write operations
    add_individual,
    create_source_record,
    attach_source_citation,
    create_family_record,
    add_child_to_family,
    add_family_relationship,
    add_spouse_relationship,
    # Duplicate detection
    calculate_person_similarity,
    find_potential_duplicates,
    # Validation
    validate_and_correct_date,
    check_date_consistency,
    detect_circular_ancestry,
    # Transactions
    begin_transaction,
    commit_transaction,
    rollback_transaction,
    apply_transaction_undo,
    # ID generation
    generate_new_individual_id,
    generate_new_family_id,
    generate_new_source_id,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_gedcom_path():
    """Path to the sample GEDCOM file."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "sample-family.ged"
    )


@pytest.fixture
def parser(sample_gedcom_path):
    """Parse the sample GEDCOM file."""
    return parse_gedcom_file(sample_gedcom_path)


@pytest.fixture
def fresh_parser(sample_gedcom_path):
    """Parse fresh copy of GEDCOM for write tests (doesn't affect other tests)."""
    return parse_gedcom_file(sample_gedcom_path)


# ============================================================================
# Parsing Tests
# ============================================================================

class TestParsing:
    """Tests for GEDCOM parsing functionality."""
    
    def test_parse_gedcom_file(self, sample_gedcom_path):
        """Test parsing a GEDCOM file from path."""
        parser = parse_gedcom_file(sample_gedcom_path)
        assert parser is not None
        
    def test_parse_gedcom_content(self):
        """Test parsing GEDCOM content from string."""
        content = """0 HEAD
1 GEDC
2 VERS 5.5.1
0 @I1@ INDI
1 NAME John /Smith/
1 SEX M
1 BIRT
2 DATE 15 MAR 1850
0 TRLR"""
        parser = parse_gedcom_content(content)
        assert parser is not None
        
        # Verify we can find the individual
        individual = find_individual_by_id(parser, "@I1@")
        assert individual is not None
        
    def test_export_gedcom_content(self, parser):
        """Test exporting GEDCOM to string."""
        content = export_gedcom_content(parser)
        assert content is not None
        assert len(content) > 0
        assert "HEAD" in content
        assert "INDI" in content
        

# ============================================================================
# Individual Lookup Tests
# ============================================================================

class TestIndividualLookup:
    """Tests for finding and retrieving individual data."""
    
    def test_find_individual_by_id_with_at_symbols(self, parser):
        """Test finding individual by ID with @ symbols."""
        # Charles III is @I0@
        individual = find_individual_by_id(parser, "@I0@")
        assert individual is not None
        first_name, last_name = individual.get_name()
        assert "Charles" in first_name
        assert "Windsor" in last_name
        
    def test_find_individual_by_id_without_at_symbols(self, parser):
        """Test finding individual by ID without @ symbols."""
        individual = find_individual_by_id(parser, "I0")
        assert individual is not None
        
    def test_find_individual_by_name_exact(self, parser):
        """Test finding individual by exact name."""
        individual = find_individual_by_name(parser, "Elizabeth II Alexandra Mary Windsor")
        assert individual is not None
        assert individual.get_pointer() == "@I1@"
        
    def test_find_individual_by_name_partial(self, parser):
        """Test finding individual by partial name."""
        individual = find_individual_by_name(parser, "Elizabeth II")
        assert individual is not None
        
    def test_find_individual_by_name_case_insensitive(self, parser):
        """Test that name search is case insensitive."""
        individual = find_individual_by_name(parser, "elizabeth ii")
        assert individual is not None
        
    def test_find_individual_not_found(self, parser):
        """Test that None is returned for non-existent person."""
        individual = find_individual_by_id(parser, "@I99999@")
        assert individual is None
        
    def test_find_individual_hybrid(self, parser):
        """Test find_individual which tries ID first then name."""
        # By ID
        individual = find_individual(parser, "@I0@")
        assert individual is not None
        
        # By name
        individual = find_individual(parser, "George V Windsor")
        assert individual is not None
        
    def test_get_individual_data(self, parser):
        """Test extracting data dictionary from individual."""
        individual = find_individual_by_id(parser, "@I1@")
        data = get_individual_data(individual)
        
        assert data["id"] == "@I1@"
        assert "Elizabeth" in data["firstName"]
        assert data["lastName"] == "Windsor"
        assert data["gender"] == "F"
        assert data["birthYear"] == 1926
        assert data["deathYear"] == 2022
        
    def test_get_person_full_details(self, parser):
        """Test getting comprehensive person details."""
        details = get_person_full_details(parser, "@I0@")
        
        assert isinstance(details, dict)
        assert details["id"] == "@I0@"
        assert "Charles" in details["fullName"]
        assert details["birthYear"] == 1948
        assert "Buckingham Palace" in details["birthPlace"]
        # Charles III has notes
        assert len(details["notes"]) > 0
        
    def test_get_person_full_details_not_found(self, parser):
        """Test error message for non-existent person."""
        result = get_person_full_details(parser, "@I99999@")
        assert isinstance(result, str)
        assert "not found" in result.lower()
        
    def test_get_all_individuals(self, parser):
        """Test retrieving all individuals."""
        individuals = get_all_individuals(parser)
        
        assert isinstance(individuals, list)
        assert len(individuals) > 50  # Sample has many monarchs
        
        # Each should have required fields
        for person in individuals[:5]:
            assert "id" in person
            assert "firstName" in person
            assert "lastName" in person


# ============================================================================
# Relationship Tests
# ============================================================================

class TestRelationships:
    """Tests for family relationship queries."""
    
    def test_get_parents(self, parser):
        """Test getting parents of a person."""
        # Charles III (@I0@) parents are Philip (@I10@) and Elizabeth II (@I1@)
        parents = get_parents(parser, "@I0@")
        
        assert isinstance(parents, list)
        assert len(parents) == 2
        
        parent_ids = [p["id"] for p in parents]
        assert "@I1@" in parent_ids  # Elizabeth II
        
    def test_get_children(self, parser):
        """Test getting children of a person."""
        # Elizabeth II (@I1@) has children including Charles III (@I0@)
        children = get_children(parser, "@I1@")
        
        assert isinstance(children, list)
        assert len(children) >= 1
        
        child_ids = [c["id"] for c in children]
        assert "@I0@" in child_ids  # Charles III
        
    def test_get_spouses(self, parser):
        """Test getting spouses of a person."""
        # Elizabeth II married Philip
        spouses = get_spouses(parser, "@I1@")
        
        assert isinstance(spouses, list)
        assert len(spouses) >= 1
        
    def test_get_siblings(self, parser):
        """Test getting siblings of a person."""
        # Charles III has siblings (Anne, Andrew, Edward)
        siblings = get_siblings(parser, "@I0@")
        
        assert isinstance(siblings, list)
        # Should have at least 1 sibling
        assert len(siblings) >= 1
        
    def test_get_grandparents(self, parser):
        """Test getting grandparents of a person."""
        # Charles III grandparents include George VI
        grandparents = get_grandparents(parser, "@I0@")
        
        assert isinstance(grandparents, list)
        
    def test_get_aunts_uncles(self, parser):
        """Test getting aunts and uncles."""
        aunts_uncles = get_aunts_uncles(parser, "@I0@")
        assert isinstance(aunts_uncles, list)
        
    def test_get_cousins(self, parser):
        """Test getting cousins."""
        cousins = get_cousins(parser, "@I0@")
        assert isinstance(cousins, list)
        
    def test_relationship_not_found(self, parser):
        """Test error handling for non-existent person."""
        result = get_parents(parser, "@I99999@")
        assert isinstance(result, str)
        assert "not found" in result.lower()


# ============================================================================
# Tree Building Tests
# ============================================================================

class TestTreeBuilding:
    """Tests for tree visualization structures."""
    
    def test_build_ancestor_tree(self, parser):
        """Test building ancestor tree."""
        tree = build_ancestor_tree(parser, "@I0@", max_depth=3)
        
        assert tree is not None
        assert tree["id"] == "@I0@"
        # Should have children (ancestors in this tree structure)
        if "children" in tree:
            assert len(tree["children"]) > 0
            
    def test_build_descendant_tree(self, parser):
        """Test building descendant tree."""
        # Start from someone with known descendants
        tree = build_descendant_tree(parser, "@I1@", max_depth=2)
        
        assert tree is not None
        assert tree["id"] == "@I1@"
        
    def test_build_bidirectional_tree(self, parser):
        """Test building bidirectional tree."""
        tree = build_bidirectional_tree(parser, "@I0@", ancestor_depth=2, descendant_depth=2)
        
        assert tree is not None
        assert tree["id"] == "@I0@"
        assert tree["direction"] == "root"
        
    def test_find_root_ancestors(self, parser):
        """Test finding individuals without parents."""
        roots = find_root_ancestors(parser)
        
        assert isinstance(roots, list)
        assert len(roots) > 0
        
    def test_find_youngest_generation(self, parser):
        """Test finding individuals without children."""
        youngest = find_youngest_generation(parser)
        
        assert isinstance(youngest, list)
        assert len(youngest) > 0


# ============================================================================
# Write Operation Tests
# ============================================================================

class TestWriteOperations:
    """Tests for GEDCOM write operations."""
    
    def test_add_individual_basic(self, fresh_parser):
        """Test adding a basic individual."""
        result = add_individual(
            fresh_parser,
            first_name="Johann",
            last_name="Schmidt",
            gender="M"
        )
        
        assert result["success"] is True
        assert "id" in result
        assert result["id"].startswith("@I")
        
        # Verify we can find the new person
        individual = find_individual_by_id(fresh_parser, result["id"])
        assert individual is not None
        
    def test_add_individual_with_dates(self, fresh_parser):
        """Test adding individual with birth/death dates."""
        result = add_individual(
            fresh_parser,
            first_name="Maria",
            last_name="Schmidt",
            gender="F",
            birth_date="15 MAR 1850",
            birth_place="Berlin, Germany",
            death_date="22 DEC 1920",
            death_place="Munich, Germany"
        )
        
        assert result["success"] is True
        
        # Verify details
        details = get_person_full_details(fresh_parser, result["id"])
        assert details["birthYear"] == 1850
        assert "Berlin" in details["birthPlace"]
        
    def test_add_individual_with_notes(self, fresh_parser):
        """Test adding individual with notes."""
        result = add_individual(
            fresh_parser,
            first_name="Hans",
            last_name="Mestern",
            gender="M",
            notes=["Found in Wikidata Q12345", "Immigrant from Germany"]
        )
        
        assert result["success"] is True
        
        details = get_person_full_details(fresh_parser, result["id"])
        assert len(details["notes"]) == 2
        
    def test_add_individual_invalid_gender(self, fresh_parser):
        """Test that invalid gender is corrected with warning."""
        result = add_individual(
            fresh_parser,
            first_name="Test",
            last_name="Person",
            gender="X"  # Invalid
        )
        
        assert result["success"] is True
        assert len(result["warnings"]) > 0
        assert any("gender" in w.lower() for w in result["warnings"])
        
    def test_create_source_record(self, fresh_parser):
        """Test creating a source record."""
        result = create_source_record(
            fresh_parser,
            title="Wikidata Q12345",
            author="Wikidata Contributors",
            publication="Wikidata, 2024",
            url="https://www.wikidata.org/wiki/Q12345"
        )
        
        assert result["success"] is True
        assert result["id"].startswith("@S")
        
    def test_attach_source_citation(self, fresh_parser):
        """Test attaching source to person event."""
        # First create a person
        person_result = add_individual(
            fresh_parser,
            first_name="Test",
            last_name="Person",
            gender="M",
            birth_date="1850"
        )
        
        # Create source
        source_result = create_source_record(
            fresh_parser,
            title="Test Source"
        )
        
        # Attach source
        citation_result = attach_source_citation(
            fresh_parser,
            person_id=person_result["id"],
            source_id=source_result["id"],
            event_type="BIRT",
            quality=2,
            citation_text="Born in 1850"
        )
        
        assert citation_result["success"] is True
        
    def test_create_family_record(self, fresh_parser):
        """Test creating a family record."""
        # Create two people
        person1 = add_individual(fresh_parser, "John", "Smith", "M")
        person2 = add_individual(fresh_parser, "Jane", "Doe", "F")
        
        # Create family
        result = create_family_record(
            fresh_parser,
            husband_id=person1["id"],
            wife_id=person2["id"],
            marriage_date="15 JUN 1875",
            marriage_place="Boston, Massachusetts"
        )
        
        assert result["success"] is True
        assert result["id"].startswith("@F")
        
    def test_add_family_relationship(self, fresh_parser):
        """Test adding parent-child relationship."""
        # Create parent and child
        parent = add_individual(fresh_parser, "John", "Smith", "M", birth_date="1820")
        child = add_individual(fresh_parser, "John Jr", "Smith", "M", birth_date="1850")
        
        # Link them
        result = add_family_relationship(
            fresh_parser,
            parent_id=parent["id"],
            child_id=child["id"]
        )
        
        assert result["success"] is True
        assert "family_id" in result
        
        # Verify relationship
        parents = get_parents(fresh_parser, child["id"])
        parent_ids = [p["id"] for p in parents]
        assert parent["id"] in parent_ids
        
    def test_add_spouse_relationship(self, fresh_parser):
        """Test linking spouses."""
        person1 = add_individual(fresh_parser, "John", "Smith", "M")
        person2 = add_individual(fresh_parser, "Jane", "Smith", "F")
        
        result = add_spouse_relationship(
            fresh_parser,
            spouse1_id=person1["id"],
            spouse2_id=person2["id"],
            marriage_date="1875"
        )
        
        assert result["success"] is True
        
        # Verify relationship
        spouses = get_spouses(fresh_parser, person1["id"])
        spouse_ids = [s["id"] for s in spouses]
        assert person2["id"] in spouse_ids


# ============================================================================
# Duplicate Detection Tests
# ============================================================================

class TestDuplicateDetection:
    """Tests for duplicate detection and similarity scoring."""
    
    def test_calculate_person_similarity_exact_match(self):
        """Test similarity score for identical persons."""
        existing = {
            "fullName": "John Smith",
            "birthYear": 1850,
            "birthPlace": "Boston, Massachusetts",
            "gender": "M",
            "deathYear": 1920
        }
        candidate = existing.copy()
        
        score = calculate_person_similarity(existing, candidate)
        assert score >= 0.95  # Should be nearly 1.0
        
    def test_calculate_person_similarity_partial_match(self):
        """Test similarity score for partial matches."""
        existing = {
            "fullName": "John Smith",
            "birthYear": 1850,
            "birthPlace": "Boston",
            "gender": "M",
            "deathYear": 1920
        }
        candidate = {
            "fullName": "John Smith",
            "birthYear": 1851,  # Off by 1 year
            "birthPlace": "Boston, MA",  # Similar place
            "gender": "M",
            "deathYear": None
        }
        
        score = calculate_person_similarity(existing, candidate)
        assert 0.60 < score < 0.95  # Should be a good match but not perfect
        
    def test_calculate_person_similarity_different_persons(self):
        """Test similarity score for clearly different persons."""
        existing = {
            "fullName": "John Smith",
            "birthYear": 1850,
            "birthPlace": "Boston",
            "gender": "M",
            "deathYear": 1920
        }
        candidate = {
            "fullName": "Mary Johnson",
            "birthYear": 1900,
            "birthPlace": "Chicago",
            "gender": "F",
            "deathYear": 1980
        }
        
        score = calculate_person_similarity(existing, candidate)
        assert score < 0.30  # Should be low
        
    def test_find_potential_duplicates(self, parser):
        """Test finding potential duplicates in existing tree."""
        # Search for Elizabeth II
        candidate = {
            "fullName": "Elizabeth Windsor",
            "birthYear": 1926,
            "birthPlace": "London",
            "gender": "F",
            "deathYear": 2022
        }
        
        duplicates = find_potential_duplicates(parser, candidate, threshold=0.50)
        
        assert isinstance(duplicates, list)
        # Should find Elizabeth II
        if len(duplicates) > 0:
            best_match = duplicates[0]
            assert best_match["percentage"] > 50
            assert "Elizabeth" in best_match["person"]["fullName"]
            
    def test_find_potential_duplicates_no_matches(self, parser):
        """Test when no duplicates are found."""
        candidate = {
            "fullName": "Zzzzz Xxxxxyyy",
            "birthYear": 1111,
            "birthPlace": "Nowhere",
            "gender": "M",
            "deathYear": None
        }
        
        duplicates = find_potential_duplicates(parser, candidate, threshold=0.60)
        assert len(duplicates) == 0


# ============================================================================
# Validation Tests
# ============================================================================

class TestValidation:
    """Tests for date and relationship validation."""
    
    def test_validate_date_valid_full(self):
        """Test validating a fully specified date."""
        corrected, warnings = validate_and_correct_date("15 MAR 1850")
        assert corrected == "15 MAR 1850"
        assert len(warnings) == 0
        
    def test_validate_date_valid_year_only(self):
        """Test validating year-only date."""
        corrected, warnings = validate_and_correct_date("1850")
        assert "1850" in corrected
        
    def test_validate_date_with_modifier(self):
        """Test date with ABT modifier."""
        corrected, warnings = validate_and_correct_date("ABT 1850")
        assert "ABT" in corrected
        assert "1850" in corrected
        
    def test_validate_date_correct_month_name(self):
        """Test auto-correction of month names."""
        corrected, warnings = validate_and_correct_date("15 MARCH 1850")
        assert "MAR" in corrected
        assert len(warnings) > 0  # Should have correction warning
        
    def test_validate_date_no_year(self):
        """Test handling of date without year."""
        corrected, warnings = validate_and_correct_date("15 MAR")
        assert len(warnings) > 0  # Should warn about missing year
        
    def test_check_date_consistency_valid(self):
        """Test valid date consistency."""
        warnings = check_date_consistency("15 MAR 1850", "22 DEC 1920")
        # No errors expected
        assert not any("ERROR" in w for w in warnings)
        
    def test_check_date_consistency_death_before_birth(self):
        """Test detection of death before birth."""
        warnings = check_date_consistency("15 MAR 1920", "22 DEC 1850")
        assert any("ERROR" in w for w in warnings)
        
    def test_check_date_consistency_extreme_age(self):
        """Test warning for extreme age."""
        warnings = check_date_consistency("1800", "2000")  # 200 years
        assert any("WARNING" in w for w in warnings)
        
    def test_detect_circular_ancestry_none(self, parser):
        """Test no circular ancestry for valid relationship."""
        # Charles III (@I0@) and Elizabeth II (@I1@) - valid parent-child
        is_circular = detect_circular_ancestry(parser, "@I0@", "@I1@")
        assert is_circular is False
        
    def test_detect_circular_ancestry_self(self, parser):
        """Test circular ancestry detection for same person."""
        # Person cannot be their own ancestor
        is_circular = detect_circular_ancestry(parser, "@I0@", "@I0@")
        assert is_circular is True


# ============================================================================
# ID Generation Tests
# ============================================================================

class TestIDGeneration:
    """Tests for ID generation."""
    
    def test_generate_new_individual_id(self, parser):
        """Test generating unique individual ID."""
        new_id = generate_new_individual_id(parser)
        
        assert new_id.startswith("@I")
        assert new_id.endswith("@")
        
        # Should not exist in tree
        existing = find_individual_by_id(parser, new_id)
        assert existing is None
        
    def test_generate_new_family_id(self, parser):
        """Test generating unique family ID."""
        new_id = generate_new_family_id(parser)
        
        assert new_id.startswith("@F")
        assert new_id.endswith("@")
        
    def test_generate_new_source_id(self, parser):
        """Test generating unique source ID."""
        new_id = generate_new_source_id(parser)
        
        assert new_id.startswith("@S")
        assert new_id.endswith("@")


# ============================================================================
# Transaction Tests
# ============================================================================

class TestTransactions:
    """Tests for transaction-based undo system."""
    
    def test_begin_and_commit_transaction(self, fresh_parser):
        """Test basic transaction lifecycle."""
        # Begin transaction
        txn = begin_transaction("Test transaction")
        assert txn["id"].startswith("txn_")
        assert txn["description"] == "Test transaction"
        
        # Add a person (operation will be recorded)
        add_individual(fresh_parser, "Test", "Person", "M")
        
        # Commit
        record = commit_transaction()
        assert record["description"] == "Test transaction"
        assert record["operation_count"] >= 1
        
    def test_transaction_rollback(self, fresh_parser):
        """Test rolling back a transaction."""
        begin_transaction("Rollback test")
        
        # Rollback before commit
        rollback_transaction()
        
        # Should be able to start new transaction
        txn = begin_transaction("New transaction")
        assert txn is not None
        commit_transaction()
        
    def test_nested_transaction_error(self, fresh_parser):
        """Test that nested transactions raise error."""
        begin_transaction("First")
        
        with pytest.raises(RuntimeError):
            begin_transaction("Second")
            
        # Cleanup
        rollback_transaction()
        
    def test_commit_without_transaction_error(self):
        """Test that committing without transaction raises error."""
        # Make sure no transaction is active (clean state)
        try:
            rollback_transaction()
        except RuntimeError:
            pass  # No transaction to rollback is fine
            
        with pytest.raises(RuntimeError):
            commit_transaction()
            
    def test_transaction_undo(self, fresh_parser):
        """Test undoing a complete transaction."""
        # Get initial count
        initial_individuals = len(get_all_individuals(fresh_parser))
        
        # Create transaction
        begin_transaction("Add test person")
        result = add_individual(fresh_parser, "Undo", "Test", "M")
        person_id = result["id"]
        record = commit_transaction()
        
        # Verify person was added
        assert find_individual_by_id(fresh_parser, person_id) is not None
        
        # Undo the transaction
        undo_result = apply_transaction_undo(fresh_parser, record)
        
        assert undo_result["success"] is True
        assert undo_result["operations_undone"] >= 1
        
        # Person should be removed
        assert find_individual_by_id(fresh_parser, person_id) is None


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_add_person_with_sources_and_relationships(self, fresh_parser):
        """Test complete workflow of adding person with sources and family."""
        # Begin transaction
        begin_transaction("Add complete family unit")
        
        # Add parent
        parent = add_individual(
            fresh_parser,
            first_name="Johann",
            last_name="Schmidt",
            gender="M",
            birth_date="1820",
            birth_place="Berlin, Germany"
        )
        
        # Add child
        child = add_individual(
            fresh_parser,
            first_name="Karl",
            last_name="Schmidt",
            gender="M",
            birth_date="1850",
            birth_place="Berlin, Germany"
        )
        
        # Create source
        source = create_source_record(
            fresh_parser,
            title="German Church Records",
            author="Lutheran Church",
            url="https://example.com/records"
        )
        
        # Attach source to child's birth
        attach_source_citation(
            fresh_parser,
            person_id=child["id"],
            source_id=source["id"],
            event_type="BIRT",
            quality=3
        )
        
        # Link parent-child
        relationship = add_family_relationship(
            fresh_parser,
            parent_id=parent["id"],
            child_id=child["id"]
        )
        
        # Commit transaction
        record = commit_transaction()
        
        # Verify everything
        assert record["operation_count"] >= 4  # 2 individuals + 1 source + 1 citation + family
        
        # Verify relationship
        parents = get_parents(fresh_parser, child["id"])
        assert len(parents) >= 1
        assert any(p["id"] == parent["id"] for p in parents)
        
    def test_duplicate_detection_workflow(self, parser):
        """Test workflow with duplicate detection."""
        # Search for someone similar to Charles III
        candidate = {
            "fullName": "Charles Windsor",
            "birthYear": 1948,
            "birthPlace": "London, England",
            "gender": "M",
            "deathYear": None
        }
        
        duplicates = find_potential_duplicates(parser, candidate, threshold=0.50)
        
        # Should find Charles III as potential duplicate
        assert len(duplicates) > 0
        
        best_match = duplicates[0]
        assert best_match["percentage"] > 60
        assert "Charles" in best_match["person"]["fullName"]
        
    def test_export_after_modifications(self, fresh_parser):
        """Test that modified GEDCOM can be exported."""
        # Add a person
        add_individual(fresh_parser, "Export", "Test", "M")
        
        # Export
        content = export_gedcom_content(fresh_parser)
        
        # Should contain the new person
        assert "Export" in content
        assert "Test" in content


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
