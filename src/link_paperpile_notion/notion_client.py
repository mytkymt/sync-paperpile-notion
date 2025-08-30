"""
Notion API client functions for creating and updating pages.
"""
import os
import json
import time
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

def notion_headers(token: str) -> Dict[str, str]:
    """Generate headers for Notion API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

def notion_find_or_create_author(token: str, authors_db: str, full_name: str) -> Optional[str]:
    """Find or create an author in the authors database."""
    # Search by name equals full_name
    url = f"{NOTION_API_BASE}/databases/{authors_db}/query"
    payload = {
        "filter": {
            "property": "Name",
            "title": {"equals": full_name}
        },
        "page_size": 1,
    }
    r = requests.post(url, headers=notion_headers(token), data=json.dumps(payload))
    r.raise_for_status()
    results = r.json().get("results", [])
    if results:
        return results[0]["id"]
    
    # Create new author
    url = f"{NOTION_API_BASE}/pages"
    payload = {
        "parent": {"database_id": authors_db},
        "properties": {
            "Name": {"title": [{"text": {"content": full_name}}]},
        }
    }
    r = requests.post(url, headers=notion_headers(token), data=json.dumps(payload))
    r.raise_for_status()
    return r.json().get("id")

def notion_query_by_uid(token: str, dbid: str, uid: str) -> Optional[str]:
    """Query Notion database by UID to find existing page."""
    url = f"{NOTION_API_BASE}/databases/{dbid}/query"
    payload = {
        "filter": {
            "property": "UID",
            "rich_text": {"equals": uid}
        },
        "page_size": 1
    }
    
    r = requests.post(url, headers=notion_headers(token), data=json.dumps(payload))
    if not r.ok:
        raise Exception(f"Notion query failed: {r.status_code} {r.text}")
    
    results = r.json().get("results", [])
    return results[0]["id"] if results else None

def notion_create_page(token: str, dbid: str, entry: Dict, authors_db: Optional[str]) -> str:
    """Create a new page in Notion database."""
    url = f"{NOTION_API_BASE}/pages"
    
    # Build properties
    properties = {
        "Title": {"title": [{"text": {"content": entry.get("title", "Untitled")}}]},
        "UID": {"rich_text": [{"text": {"content": entry["uid"]}}]},
        "Type": {"select": {"name": "Resource"}},
        "PubType": {"select": {"name": entry.get("type_norm", "Other")}},
        "Year": {"number": entry.get("year")},
        "Venue": {"rich_text": [{"text": {"content": entry.get("venue", "")}}]},
    }
    
    # Add DOI if present (as URL format)
    if entry.get("doi"):
        doi_url = f"https://doi.org/{entry['doi']}" if not entry["doi"].startswith("http") else entry["doi"]
        properties["DOI"] = {"url": doi_url}
    
    # Add URL if present
    if entry.get("url"):
        properties["URL"] = {"url": entry["url"]}
    
    # Add authors if present (as relation if authors_db is provided)
    if entry.get("authors") and authors_db:
        author_relation_ids = []
        for author in entry["authors"]:
            author_id = notion_find_or_create_author(token, authors_db, author["full"])
            if author_id:
                author_relation_ids.append(author_id)
        if author_relation_ids:
            properties["Authors"] = {"relation": [{"id": aid} for aid in author_relation_ids]}
    
    payload = {
        "parent": {"database_id": dbid},
        "properties": properties
    }
    
    r = requests.post(url, headers=notion_headers(token), data=json.dumps(payload))
    if not r.ok:
        raise Exception(f"Failed to create page: {r.status_code} {r.text}")
    
    page_id = r.json()["id"]
    print(f"✅ [NOTION] Created page: {entry.get('title', 'Untitled')[:50]}...")
    return page_id

def notion_update_page(token: str, page_id: str, entry: Dict, authors_db: Optional[str], skip_author=False) -> None:
    """Update an existing page in Notion."""
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    
    properties = {
        "Title": {"title": [{"text": {"content": entry.get("title", "Untitled")}}]},
        "Type": {"select": {"name": "Resource"}},
        "PubType": {"select": {"name": entry.get("type_norm", "Other")}},
        "Year": {"number": entry.get("year")},
        "Venue": {"rich_text": [{"text": {"content": entry.get("venue", "")}}]},
    }
    
    if entry.get("doi"):
        doi_url = f"https://doi.org/{entry['doi']}" if not entry["doi"].startswith("http") else entry["doi"]
        properties["DOI"] = {"url": doi_url}
    
    if entry.get("url"):
        properties["URL"] = {"url": entry["url"]}
    
    # Add authors if present (as relation if authors_db is provided)
    if entry.get("authors") and not skip_author and authors_db:
        author_relation_ids = []
        for author in entry["authors"]:
            author_id = notion_find_or_create_author(token, authors_db, author["full"])
            if author_id:
                author_relation_ids.append(author_id)
        if author_relation_ids:
            properties["Authors"] = {"relation": [{"id": aid} for aid in author_relation_ids]}
    
    payload = {"properties": properties}
    
    r = requests.patch(url, headers=notion_headers(token), data=json.dumps(payload))
    if not r.ok:
        raise Exception(f"Failed to update page: {r.status_code} {r.text}")
    
    print(f"✅ [NOTION] Updated page: {entry.get('title', 'Untitled')[:50]}...")

def notion_get_property(token: str, page_id: str, prop_name: str) -> Optional[str]:
    """Get a specific property value from a Notion page."""
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    r = requests.get(url, headers=notion_headers(token))
    
    if not r.ok:
        return None
    
    props = r.json().get("properties", {})
    prop = props.get(prop_name, {})
    
    if prop.get("type") == "rich_text":
        texts = prop.get("rich_text", [])
        return texts[0]["plain_text"] if texts else None
    elif prop.get("type") == "url":
        return prop.get("url")
    
    return None

def notion_update_pdf_fields(token: str, page_id: str, drive_file_id: str, web_view_link: str) -> None:
    """Update PDF-related fields in a Notion page."""
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    
    properties = {
        "Drive File ID": {"rich_text": [{"text": {"content": drive_file_id}}]},
    }
    
    if web_view_link:
        properties["PDF (Drive)"] = {"url": web_view_link}
    
    payload = {"properties": properties}
    
    r = requests.patch(url, headers=notion_headers(token), data=json.dumps(payload))
    if not r.ok:
        raise Exception(f"Failed to update PDF fields: {r.status_code} {r.text}")
    
    print(f"✅ [NOTION] Updated PDF fields for page")

def notion_add_blocks(token: str, page_id: str, blocks: List[Dict]) -> None:
    """Add blocks to a Notion page."""
    url = f"{NOTION_API_BASE}/blocks/{page_id}/children"
    payload = {"children": blocks}
    
    r = requests.patch(url, headers=notion_headers(token), data=json.dumps(payload))
    if not r.ok:
        raise Exception(f"Failed to add blocks: {r.status_code} {r.text}")
