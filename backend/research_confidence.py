"""Research confidence scoring system for autonomous genealogy research."""

from typing import Any


# TODO: Make thresholds configurable via settings
CONFIDENCE_THRESHOLD_AUTO_ADD = 0.90  # 90%+ auto-add with notification
CONFIDENCE_THRESHOLD_SUGGEST = 0.75  # 75-89% suggest with one-click accept
CONFIDENCE_THRESHOLD_REVIEW = 0.60   # 60-74% suggest for careful review


def calculate_research_confidence(finding: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate confidence score for autonomous research finding.
    
    Args:
        finding: {
            'sources': [
                {
                    'type': 'wikidata'|'newspaper'|'book'|'web'|'wikipedia',
                    'url': str,
                    'title': str,
                    ...
                }
            ],
            'data': {
                'birthDate': str,
                'birthDatePrecision': 'EXACT'|'MONTH_YEAR'|'YEAR_ONLY'|'CIRCA'|'RANGE',
                'birthPlace': str,
                'deathDate': str,
                'deathDatePrecision': 'EXACT'|'MONTH_YEAR'|'YEAR_ONLY'|'CIRCA'|'RANGE',
                ...
            },
            'conflicts': [
                {'field': str, 'values': [...]},
                ...
            ]
        }
    
    Returns:
        {
            'score': float (0.0 to 1.0),
            'level': 'auto-add'|'suggest'|'review'|'low-confidence',
            'breakdown': {
                'source_score': float,
                'specificity_score': float,
                'authority_score': float,
                'consistency_score': float
            },
            'badge_color': 'green'|'yellow'|'orange'|'gray'
        }
    """
    
    # 1. SOURCE MULTIPLICITY (30%)
    num_sources = len(finding.get('sources', []))
    if num_sources >= 4:
        source_score = 1.00
    elif num_sources == 3:
        source_score = 0.80
    elif num_sources == 2:
        source_score = 0.60
    elif num_sources == 1:
        source_score = 0.30
    else:
        source_score = 0.0
    
    # Penalty for conflicts
    conflicts = len(finding.get('conflicts', []))
    source_score = max(0.0, source_score - (conflicts * 0.20))
    
    # 2. DATA SPECIFICITY (25%)
    specificity_scores = []
    SPECIFICITY_MAP = {
        'EXACT': 1.00,           # Day, month, year
        'MONTH_YEAR': 0.75,      # Month and year
        'YEAR_ONLY': 0.50,       # Year only
        'CIRCA': 0.40,           # Approximate year
        'RANGE': 0.30,           # Date range
        None: 0.0
    }
    
    data = finding.get('data', {})
    for field in ['birthDatePrecision', 'deathDatePrecision']:
        date_precision = data.get(field)
        specificity_scores.append(SPECIFICITY_MAP.get(date_precision, 0.0))
    
    # Also consider place specificity
    for field in ['birthPlace', 'deathPlace']:
        place = data.get(field)
        if place:
            # More specific places (with commas) score higher
            parts = [p.strip() for p in place.split(',')]
            if len(parts) >= 3:  # City, County, State/Country
                specificity_scores.append(1.0)
            elif len(parts) == 2:  # City, State
                specificity_scores.append(0.75)
            else:  # Single location
                specificity_scores.append(0.50)
        else:
            specificity_scores.append(0.0)
    
    specificity_score = sum(specificity_scores) / len(specificity_scores) if specificity_scores else 0.0
    
    # 3. SOURCE AUTHORITY (25%)
    SOURCE_AUTHORITY = {
        'government_record': 1.00,  # Birth/death certificates
        'census': 0.85,             # Census records
        'wikidata': 0.90,           # Structured, curated data
        'newspaper': 0.75,          # Historical newspapers (obituaries)
        'book': 0.70,               # Published genealogies
        'wikipedia': 0.65,          # Wikipedia articles
        'family_tree': 0.50,        # Other users' trees
        'web': 0.30                 # General web content
    }
    
    authority_scores = [
        SOURCE_AUTHORITY.get(src.get('type', 'web'), 0.30)
        for src in finding.get('sources', [])
    ]
    authority_score = sum(authority_scores) / len(authority_scores) if authority_scores else 0.0
    
    # 4. DATA CONSISTENCY (20%)
    # Inverse of conflicts - no conflicts = 1.0
    consistency_score = max(0.0, 1.0 - (conflicts * 0.35))
    
    # FINAL CONFIDENCE
    confidence = (
        source_score * 0.30 +
        specificity_score * 0.25 +
        authority_score * 0.25 +
        consistency_score * 0.20
    )
    
    confidence = round(confidence, 2)
    
    # Determine confidence level
    if confidence >= CONFIDENCE_THRESHOLD_AUTO_ADD:
        level = 'auto-add'
        badge_color = 'green'
    elif confidence >= CONFIDENCE_THRESHOLD_SUGGEST:
        level = 'suggest'
        badge_color = 'yellow'
    elif confidence >= CONFIDENCE_THRESHOLD_REVIEW:
        level = 'review'
        badge_color = 'orange'
    else:
        level = 'low-confidence'
        badge_color = 'gray'
    
    return {
        'score': confidence,
        'level': level,
        'breakdown': {
            'source_score': round(source_score * 0.30, 3),
            'specificity_score': round(specificity_score * 0.25, 3),
            'authority_score': round(authority_score * 0.25, 3),
            'consistency_score': round(consistency_score * 0.20, 3)
        },
        'badge_color': badge_color
    }


def determine_date_precision(date_str: str | None) -> str:
    """
    Determine the precision level of a date string.
    
    Returns: 'EXACT'|'MONTH_YEAR'|'YEAR_ONLY'|'CIRCA'|'RANGE'|None
    """
    if not date_str:
        return None
    
    date_str = date_str.strip().upper()
    
    # Check for modifiers
    if any(mod in date_str for mod in ['ABT', 'ABOUT', 'CIRCA', 'CA', 'EST']):
        return 'CIRCA'
    
    if any(mod in date_str for mod in ['BET', 'BETWEEN', 'FROM', 'TO']):
        return 'RANGE'
    
    # Count components (day, month, year)
    parts = date_str.split()
    
    # Valid GEDCOM months
    months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 
              'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    
    has_year = any(p.isdigit() and len(p) == 4 for p in parts)
    has_month = any(p in months for p in parts)
    has_day = any(p.isdigit() and 1 <= int(p) <= 31 for p in parts if p.isdigit())
    
    if has_day and has_month and has_year:
        return 'EXACT'
    elif has_month and has_year:
        return 'MONTH_YEAR'
    elif has_year:
        return 'YEAR_ONLY'
    
    return None


def assess_source_quality(source_type: str, data: dict[str, Any]) -> int:
    """
    Assess GEDCOM QUAY (quality assessment) score for a source.
    
    Args:
        source_type: Type of source
        data: Additional context about the source
    
    Returns:
        int: Quality score 0-3
            0 = Unreliable evidence or estimated data
            1 = Questionable reliability
            2 = Secondary evidence
            3 = Direct and primary evidence
    """
    # Map source types to GEDCOM quality scores
    QUALITY_MAP = {
        'government_record': 3,  # Primary evidence
        'census': 3,             # Primary evidence
        'wikidata': 2,           # Secondary but reliable
        'newspaper': 2,          # Secondary evidence
        'book': 2,               # Secondary evidence
        'wikipedia': 1,          # Questionable (no peer review)
        'family_tree': 1,        # Questionable
        'web': 0                 # Unreliable
    }
    
    base_quality = QUALITY_MAP.get(source_type, 0)
    
    # Adjust based on data specificity
    if data.get('has_citations'):
        base_quality = min(3, base_quality + 1)
    
    if data.get('is_transcription'):
        base_quality = max(0, base_quality - 1)
    
    return base_quality


def format_confidence_message(confidence_result: dict[str, Any], person_name: str) -> str:
    """
    Format a human-readable confidence message.
    
    Args:
        confidence_result: Result from calculate_research_confidence()
        person_name: Name of the person being researched
    
    Returns:
        str: Formatted message
    """
    score = confidence_result['score']
    level = confidence_result['level']
    breakdown = confidence_result['breakdown']
    
    percentage = int(score * 100)
    
    level_messages = {
        'auto-add': f"✓ High confidence ({percentage}%) - Ready to add {person_name} to tree",
        'suggest': f"⚡ Good confidence ({percentage}%) - Recommend adding {person_name} with review",
        'review': f"⚠ Moderate confidence ({percentage}%) - Please review {person_name} carefully",
        'low-confidence': f"❓ Low confidence ({percentage}%) - Manual verification needed for {person_name}"
    }
    
    message = level_messages.get(level, f"Confidence: {percentage}%")
    
    # Add breakdown
    message += f"\n\nScore breakdown:"
    message += f"\n  • Source quality: {breakdown['source_score']:.2f}"
    message += f"\n  • Data specificity: {breakdown['specificity_score']:.2f}"
    message += f"\n  • Source authority: {breakdown['authority_score']:.2f}"
    message += f"\n  • Data consistency: {breakdown['consistency_score']:.2f}"
    
    return message


def deduplicate_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate sources by comparing URLs and titles.
    
    Args:
        sources: List of source dicts with 'url', 'title', 'type' fields
    
    Returns:
        list: Deduplicated sources with merged metadata
    """
    seen_urls = {}
    seen_titles = {}
    unique_sources = []
    
    for source in sources:
        url = source.get('url', '').strip().lower()
        title = source.get('title', '').strip().lower()
        
        # Check for duplicate URL
        if url and url in seen_urls:
            # Merge with existing source
            existing = seen_urls[url]
            if 'access_dates' not in existing:
                existing['access_dates'] = []
            if 'access_date' in source:
                existing['access_dates'].append(source['access_date'])
            continue
        
        # Check for duplicate title (fuzzy match)
        duplicate_found = False
        if title:
            for existing_title, existing_source in seen_titles.items():
                # Simple similarity: check if one title contains the other
                if title in existing_title or existing_title in title:
                    if 'access_dates' not in existing_source:
                        existing_source['access_dates'] = []
                    if 'access_date' in source:
                        existing_source['access_dates'].append(source['access_date'])
                    duplicate_found = True
                    break
        
        if not duplicate_found:
            unique_sources.append(source)
            if url:
                seen_urls[url] = source
            if title:
                seen_titles[title] = source
    
    return unique_sources
