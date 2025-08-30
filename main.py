#!/usr/bin/env python3
"""
Link Paperpile to Notion

A comprehensive tool to sync academic papers from Paperpile to Notion with full PDF content embedding and extraction.

Features:
- Automatic sync of BibTeX export from Paperpile
- Create and update paper entries in Notion database  
- Automatic PDF discovery and linking from Google Drive
- Full PDF content extraction and embedding into Notion pages
- Advanced PDF processing with figure, equation, and citation recognition

Author: Yamato Miyatake
License: MIT
"""
import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
import re

# Import our modular components
from src.link_paperpile_notion import (
    notion_create_page_with_pdf, notion_update_page, notion_query_by_uid,
    build_drive_service
)

# Original utility functions (keeping these for now)
from urllib.parse import urlparse, parse_qs
import bibtexparser
from bibtexparser.bparser import BibTexParser
import hashlib
import time

# Constants
BIB_PATH = Path("data/papers.bib")
STATE_PATH = Path("data/state.json")
DATA_DIR = Path("data")

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

def http_download_bib(url: str, output_path: Path) -> bool:
    """Download bibliography file from URL."""
    print(f"[download] Fetching {url}")
    
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        
        # Check if content was modified
        if output_path.exists():
            existing_content = output_path.read_bytes()
            if existing_content == resp.content:
                print(f"[download] Not modified (304)")
                return False
        
        output_path.write_bytes(resp.content)
        print(f"[download] Saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"[download] Error: {e}")
        return False

def parse_bibtex(bib_path: Path) -> List[Dict]:
    """Parse BibTeX file and return list of entries."""
    print(f"[bib] Loading {bib_path}")
    
    with open(bib_path, 'r', encoding='utf-8') as f:
        parser = BibTexParser(common_strings=True)
        bib_db = parser.parse_file(f)
    
    entries = []
    for entry in bib_db.entries:
        # Normalize entry
        normalized = normalize_entry(entry)
        if normalized:
            entries.append(normalized)
    
    return entries

def normalize_entry(entry: Dict) -> Optional[Dict]:
    """Normalize a BibTeX entry."""
    # Extract basic fields
    title = entry.get('title', '').strip()
    if not title:
        return None
    
    # Clean title - remove braces and normalize whitespace
    import re
    title = title.replace('{', '').replace('}', '')
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Extract authors
    authors = []
    author_str = entry.get('author', '')
    if author_str:
        # Clean up the author string first - normalize whitespace and remove line breaks
        author_str = re.sub(r'\s+', ' ', author_str.strip())
        
        # Improved author parsing
        author_names = author_str.split(' and ')
        for name in author_names:
            name = name.strip()
            if name:
                parsed_author = parse_author_name(name)
                if parsed_author:
                    authors.append(parsed_author)
    
    # Extract year
    year = None
    year_str = entry.get('year', '').strip()
    if year_str and year_str.isdigit():
        year = int(year_str)
    
    # Normalize publication type
    entry_type = entry.get('ENTRYTYPE', '').lower()
    type_norm = normalize_pub_type(entry_type)
    
    # Extract venue - normalize whitespace
    venue = entry.get('booktitle') or entry.get('journal') or entry.get('publisher', '')
    venue = venue.strip().replace('{', '').replace('}', '')
    venue = re.sub(r'\s+', ' ', venue).strip()
    
    # Generate UID
    uid = generate_uid(entry)
    
    return {
        'uid': uid,
        'title': title,
        'authors': authors,
        'year': year,
        'type_norm': type_norm,
        'entrytype': entry_type,
        'venue': venue,
        'doi': entry.get('doi', '').strip(),
        'url': entry.get('url', '').strip(),
        'abstract': entry.get('abstract', '').strip(),
    }

def normalize_pub_type(entry_type: str) -> str:
    """Normalize publication type to standard categories."""
    type_map = {
        'article': 'Journal',
        'inproceedings': 'Conference',
        'incollection': 'Chapter',
        'book': 'Book',
        'phdthesis': 'Thesis',
        'mastersthesis': 'Thesis',
        'techreport': 'Report',
        'misc': 'Other',
        'unpublished': 'Other',
    }
    return type_map.get(entry_type.lower(), 'Other')

def generate_uid(entry: Dict) -> str:
    """Generate unique identifier for an entry."""
    # Use DOI if available
    doi = entry.get('doi', '').strip()
    if doi:
        return f"doi:{doi}"
    
    # Use URL if available
    url = entry.get('url', '').strip()
    if url:
        return f"url:{url}"
    
    # Generate from title + author + year
    title = entry.get('title', '').strip().lower()
    author = entry.get('author', '').split(' and ')[0] if entry.get('author') else ''
    year = entry.get('year', '').strip()
    
    content = f"{title}|{author}|{year}"
    hash_obj = hashlib.md5(content.encode('utf-8'))
    return f"hash:{hash_obj.hexdigest()[:12]}"

def tracked_snapshot(entry: Dict) -> str:
    """Create a snapshot hash for tracking changes."""
    # Normalize text fields by removing extra whitespace and newlines
    def normalize_text(text):
        if not text:
            return ''
        # Replace multiple whitespace (including newlines) with single spaces
        import re
        return re.sub(r'\s+', ' ', str(text).strip())
    
    trackable = {
        'title': normalize_text(entry.get('title', '')),
        'authors': [normalize_text(a.get('full', '')) for a in entry.get('authors', [])],
        'year': entry.get('year'),
        'venue': normalize_text(entry.get('venue', '')),
        'doi': normalize_text(entry.get('doi', '')),
        'url': normalize_text(entry.get('url', '')),
    }
    content = json.dumps(trackable, sort_keys=True)
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def load_state() -> Dict:
    """Load previous state."""
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, 'r') as f:
                state = json.load(f)
            print(f"[state] Loaded state with {len(state)} entries")
            return state
        except Exception as e:
            print(f"[state] Error loading state: {e}")
    else:
        print(f"[state] No state file found, starting fresh")
    return {}

def save_state(state: Dict) -> None:
    """Save current state."""
    try:
        with open(STATE_PATH, 'w') as f:
            json.dump(state, f, indent=2)
        print(f"[state] Saved state with {len(state)} entries")
    except Exception as e:
        print(f"[state] Error saving state: {e}")

def diff_entries(prev_state: Dict, current_entries: List[Dict]) -> tuple:
    """Find new and updated entries."""
    new_items = []
    updated_items = []
    
    for entry in current_entries:
        uid = entry['uid']
        current_snapshot = tracked_snapshot(entry)
        
        if uid not in prev_state:
            new_items.append(entry)
        else:
            prev_snapshot = prev_state[uid].get('snapshot', '')
            if prev_snapshot != current_snapshot:
                updated_items.append(entry)
    
    return new_items, updated_items

def is_valid_entry(entry: Dict) -> bool:
    """Check if entry has meaningful content worth importing."""
    # Must have a proper title
    title = entry.get("title", "").strip()
    if not title or len(title) < 5:
        return False
    
    # Skip entries with generic/placeholder titles
    skip_patterns = [
        "ieee xplore full-text pdf",
        "full-text pdf",
        "untitled",
        "no title",
        "unknown",
    ]
    title_lower = title.lower()
    if any(pattern in title_lower for pattern in skip_patterns):
        return False
    
    # Must have at least one of: year, authors, venue, doi, url
    has_metadata = any([
        entry.get("year"),
        entry.get("authors"),
        entry.get("venue", "").strip(),
        entry.get("doi", "").strip(),
        entry.get("url", "").strip(),
    ])
    
    return has_metadata

def parse_author_name(name: str) -> Optional[Dict]:
    """Parse a single author name into first, last, and full components."""
    name = name.strip()
    if not name:
        return None
    
    # Clean up common artifacts
    name = name.replace('{', '').replace('}', '')
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Handle "Last, First Middle" format
    if ',' in name:
        parts = name.split(',', 1)
        last = parts[0].strip()
        first_part = parts[1].strip() if len(parts) > 1 else ''
        
        # Clean and organize first/middle names
        if first_part:
            # Handle cases like "First Middle" or "F. M."
            first_names = first_part.split()
            if first_names:
                first = first_names[0]
                # Include middle names/initials in first name
                if len(first_names) > 1:
                    first = ' '.join(first_names)
            else:
                first = first_part
        else:
            first = ''
        
        full_name = f"{first} {last}".strip() if first else last
        
        return {
            'last': last,
            'first': first,
            'full': full_name
        }
    
    # Handle "First Middle Last" format
    else:
        parts = name.split()
        if len(parts) == 1:
            # Single name - treat as last name
            return {
                'last': parts[0],
                'first': '',
                'full': parts[0]
            }
        elif len(parts) == 2:
            # Two parts: "First Last"
            return {
                'last': parts[1],
                'first': parts[0],
                'full': name
            }
        else:
            # Multiple parts: "First Middle Last" or "First Middle1 Middle2 Last"
            # Take last part as last name, everything else as first name
            last = parts[-1]
            first = ' '.join(parts[:-1])
            
            return {
                'last': last,
                'first': first,
                'full': name
            }

def quiet_log(message: str, quiet_mode: bool = False):
    """Log message only if not in quiet mode."""
    if not quiet_mode:
        print(message)

def main() -> None:
    """Main processing function."""
    load_dotenv()
    
    # Configuration
    export_url = os.environ.get("PAPERPILE_EXPORT_URL")
    notion_token = os.environ.get("NOTION_TOKEN")
    notion_db = os.environ.get("NOTION_DB_ID")
    authors_db = os.environ.get("AUTHORS_DB_ID")  # optional
    
    # Test mode: set TEST_MODE=true to skip Notion operations
    test_mode = os.environ.get("TEST_MODE", "").lower() in ("true", "1", "yes")
    
    # Quiet mode: set QUIET_MODE=true to reduce verbose logging
    quiet_mode = os.environ.get("QUIET_MODE", "").lower() in ("true", "1", "yes")
    
    # Limited processing mode
    limit_mode = os.environ.get("LIMIT_MODE", "").lower() in ("true", "1", "yes")
    limit_count = int(os.environ.get("LIMIT_COUNT", "10"))

    # Validation
    if not export_url:
        raise SystemExit("PAPERPILE_EXPORT_URL is not set")
    if not test_mode and (not notion_token or not notion_db):
        raise SystemExit("NOTION_TOKEN and NOTION_DB_ID are required (unless TEST_MODE=true)")

    print(f"[config] export_url={export_url}")
    print(f"[config] test_mode={test_mode}")
    if limit_mode:
        print(f"[config] limit_mode=true, processing only {limit_count} entries")

    # Download and parse bibliography
    updated = http_download_bib(export_url, BIB_PATH)
    if not updated and not BIB_PATH.exists():
        raise SystemExit("Failed to download and no existing bib present")

    entries = parse_bibtex(BIB_PATH)
    print(f"[bib] parsed entries: {len(entries)}")
    
    # Filter out invalid/empty entries
    valid_entries = [e for e in entries if is_valid_entry(e)]
    skipped_count = len(entries) - len(valid_entries)
    print(f"[filter] valid entries: {len(valid_entries)} (skipped {skipped_count} empty/invalid)")
    
    entries = valid_entries
    
    # Apply limit if enabled
    if limit_mode and len(entries) > limit_count:
        entries = entries[:limit_count]
        print(f"[limit] processing {len(entries)} entries (limited from {len(valid_entries)})")
    
    # Show preview
    if entries:
        preview_entry = entries[0]
        for e in entries[:5]:
            if e.get('title') and len(e.get('title', '')) > 10 and e.get('year'):
                preview_entry = e
                break
        
        print(f"\n[preview] Sample entry:")
        e = preview_entry
        print(f"  Title: {e.get('title', 'N/A')}")
        print(f"  Type: {e.get('type_norm', 'N/A')} (from {e.get('entrytype', 'N/A')})")
        print(f"  Year: {e.get('year', 'N/A')}")
        print(f"  Authors: {[a['full'] for a in e.get('authors', [])]}")
        print(f"  Venue: {e.get('venue', 'N/A')}")
        print(f"  DOI: {e.get('doi', 'N/A')}")
        print(f"  UID: {e.get('uid', 'N/A')}")
        
        if len(entries) > 1:
            type_stats = {}
            for entry in entries:
                type_norm = entry.get('type_norm', 'Unknown')
                type_stats[type_norm] = type_stats.get(type_norm, 0) + 1
            
            print(f"\n[stats] Entry types: {dict(sorted(type_stats.items()))}")
            years = [e.get('year') for e in entries if e.get('year')]
            if years:
                print(f"[stats] Year range: {min(years)}-{max(years)} ({len(years)} entries with years)")
            print(f"[stats] Entries with authors: {sum(1 for e in entries if e.get('authors'))}")
            print(f"[stats] Entries with DOI: {sum(1 for e in entries if e.get('doi'))}")
    
    if test_mode:
        print(f"\n[test] TEST_MODE enabled - skipping Notion operations")
        print(f"[test] Would process {len(entries)} entries")
        return

    # Determine what needs to be processed
    prev_state = load_state()
    new_items, updated_items = diff_entries(prev_state, entries)
    print(f"[diff] new={len(new_items)} updated={len(updated_items)} (of {len(entries)})")

    # Build current state map - preserve existing state and only update changed entries
    curr_state = prev_state.copy()  # Start with existing state
    
    # Update snapshots for all current entries (in case of changes)
    for e in entries:
        curr_state[e["uid"]] = {"snapshot": tracked_snapshot(e)}
    
    print(f"[state] Starting processing with {len(curr_state)} entries tracked")

    # Build Drive service once for all operations
    service = build_drive_service()

    # Process entries with integrated PDF processing
    created, modified = 0, 0
    
    print(f"\n🚀 [PROCESSING] Starting unified PDF processing for {len(new_items + updated_items)} entries...")
    
    # Process new items
    for i, e in enumerate(new_items, 1):
        print(f"\n📄 [NEW {i}/{len(new_items)}] Processing: {e.get('title', 'Unknown')[:60]}...")
        
        page_id = notion_query_by_uid(notion_token, notion_db, e["uid"])
        if page_id:
            print(f"   ⚠️  Page already exists, updating instead")
            notion_update_page(notion_token, page_id, e, authors_db)
            modified += 1
        else:
            # Create page with integrated PDF processing
            notion_create_page_with_pdf(notion_token, notion_db, e, authors_db, service)
            created += 1
        
        # Update state immediately after processing each entry
        curr_state[e["uid"]] = {"snapshot": tracked_snapshot(e)}
        
        # Save only this entry's update to preserve existing state
        updated_state = load_state()  # Load current state from disk
        updated_state[e["uid"]] = {"snapshot": tracked_snapshot(e)}  # Update this entry
        save_state(updated_state)  # Save back
        print(f"   💾 Updated state for: {e['uid']}")
    
    # Process updated items
    for i, e in enumerate(updated_items, 1):
        print(f"\n🔄 [UPDATE {i}/{len(updated_items)}] Processing: {e.get('title', 'Unknown')[:60]}...")
        
        page_id = notion_query_by_uid(notion_token, notion_db, e["uid"])
        if not page_id:
            print(f"   ⚠️  Page missing, creating new one")
            notion_create_page_with_pdf(notion_token, notion_db, e, authors_db, service)
            created += 1
        else:
            # Update page metadata
            notion_update_page(notion_token, page_id, e, authors_db)
            modified += 1
            
            # Immediately process PDF content for this entry
            print(f"   📄 Adding PDF content...")
            from src.link_paperpile_notion import add_pdf_content_for_entry
            try:
                add_pdf_content_for_entry(notion_token, notion_db, service, e)
                print(f"   ✅ PDF content processing completed")
            except Exception as pdf_error:
                print(f"   ⚠️  PDF processing failed: {pdf_error}")
        
        # Update state immediately after processing each entry
        curr_state[e["uid"]] = {"snapshot": tracked_snapshot(e)}
        
        # Save only this entry's update to preserve existing state
        updated_state = load_state()  # Load current state from disk
        updated_state[e["uid"]] = {"snapshot": tracked_snapshot(e)}  # Update this entry
        save_state(updated_state)  # Save back
        print(f"   💾 Updated state for: {e['uid']}")

    print(f"\n📊 [SUMMARY] Processing complete!")
    print(f"   ✅ Created: {created} pages")
    print(f"   🔄 Updated: {modified} pages")
    print(f"   📄 Total processed: {created + modified}")

    print(f"\n[done] ✅ All processing completed successfully!")

if __name__ == "__main__":
    main()
