"""
Core integration functions for unified PDF processing and Notion page creation.
"""
import time
from typing import Dict, Optional
from .notion_client import (
    notion_create_page, notion_update_pdf_fields, notion_add_blocks
)
from .drive_client import drive_find_pdf_with_content
from .notion_blocks import (
    create_pdf_embed_block, create_divider_block, 
    create_heading_block, markdown_to_notion_blocks
)
from .cleanup import clean_temporary_files

def notion_create_page_with_pdf(token: str, dbid: str, entry: Dict, authors_db: Optional[str], service) -> str:
    """
    Create a Notion page with integrated PDF processing.
    This combines page creation, PDF search, content extraction, and embedding in one operation.
    """
    print(f"🔍 [CREATE+PDF] Creating page with integrated PDF processing...")
    print(f"   📄 Title: {entry.get('title', 'Unknown')[:60]}...")
    
    # Step 1: Create the basic Notion page
    page_id = notion_create_page(token, dbid, entry, authors_db)
    
    # Step 2: Search for PDF and extract content
    if service is not None:
        print(f"🔍 [CREATE+PDF] Searching for PDF during page creation...")
        file_meta = drive_find_pdf_with_content(service, entry)
        
        if file_meta:
            try:
                # Step 3: Update PDF fields in Notion
                notion_update_pdf_fields(token, page_id, file_meta["id"], file_meta.get("webViewLink", ""))
                print(f"✅ [CREATE+PDF] Updated PDF fields in Notion")
                
                # Step 4: Add PDF content to the page
                add_pdf_content_to_notion_page(token, page_id, file_meta)
                print(f"✅ [CREATE+PDF] Added PDF content to page")
                
                # Step 5: Clean up temporary files
                clean_temporary_files(file_meta)
                
            except Exception as e:
                print(f"❌ [CREATE+PDF] Error during PDF processing: {e}")
                # Still clean up files even if there was an error
                if file_meta:
                    clean_temporary_files(file_meta)
        else:
            print(f"❌ [CREATE+PDF] No PDF found for this entry")
    else:
        print(f"⚠️  [CREATE+PDF] Google Drive service not available")
    
    return page_id

def add_pdf_content_to_notion_page(token: str, page_id: str, file_meta: Dict) -> None:
    """Add PDF content (embed + markdown) to a Notion page."""
    blocks = []
    
    # 1. Add PDF embed if we have a web view link
    web_view_link = file_meta.get("webViewLink")
    if web_view_link:
        blocks.append(create_pdf_embed_block(web_view_link))
        blocks.append(create_divider_block())
        print(f"[content] Added PDF embed block")
    
    # 2. Add extracted text content if available
    markdown_content = file_meta.get("markdown_content")
    if markdown_content and markdown_content.strip():
        # Add heading for extracted content
        blocks.append(create_heading_block("📄 Extracted Content", 2))
        
        # Convert markdown to Notion blocks
        markdown_blocks = markdown_to_notion_blocks(markdown_content)
        blocks.extend(markdown_blocks)
        print(f"[content] Converted {len(markdown_blocks)} blocks from markdown content")
    else:
        print(f"[content] No markdown content available to add")
    
    # 3. Add summary information if available
    if file_meta.get('text_summary'):
        blocks.append(create_divider_block())
        blocks.append(create_heading_block("📊 Document Summary", 2))
        
        # Create summary block
        summary_text = f"**Pages**: {file_meta.get('page_count', 'Unknown')}\n"
        summary_text += f"**File Size**: {file_meta.get('size_mb', 'Unknown')} MB\n"
        if file_meta.get('metadata', {}).get('title'):
            summary_text += f"**PDF Title**: {file_meta['metadata']['title']}\n"
        if file_meta.get('metadata', {}).get('author'):
            summary_text += f"**PDF Author**: {file_meta['metadata']['author']}\n"
        summary_text += f"\n{file_meta['text_summary']}"
        
        summary_blocks = markdown_to_notion_blocks(summary_text)
        blocks.extend(summary_blocks)
        print(f"[content] Added document summary")
    
    # 4. Add all blocks to the page (in batches if needed)
    if blocks:
        # Notion API allows up to 100 blocks per request
        batch_size = 100
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            notion_add_blocks(token, page_id, batch)
            if len(blocks) > batch_size:
                print(f"[content] Added blocks {i+1}-{min(i+batch_size, len(blocks))} of {len(blocks)}")
                time.sleep(0.5)  # Rate limiting
        
        print(f"✅ [content] Successfully added {len(blocks)} blocks to Notion page")
    else:
        print(f"[content] No blocks to add to Notion page")


def add_pdf_content_for_entry(token: str, dbid: str, service, entry: Dict) -> None:
    """Add PDF content for a specific entry by UID."""
    from .notion_client import notion_query_by_uid
    
    # Find the Notion page for this entry
    page_id = notion_query_by_uid(token, dbid, entry["uid"])
    if not page_id:
        print(f"❌ [PDF-ENTRY] Page not found for UID: {entry['uid']}")
        return
    
    print(f"🔍 [PDF-ENTRY] Processing PDF for: {entry.get('title', 'Unknown')[:60]}...")
    
    # Search for PDF and extract content
    if service is not None:
        file_meta = drive_find_pdf_with_content(service, entry)
        
        if file_meta:
            try:
                # Update PDF fields in Notion
                from .notion_client import notion_update_pdf_fields
                notion_update_pdf_fields(token, page_id, file_meta["id"], file_meta.get("webViewLink", ""))
                print(f"✅ [PDF-ENTRY] Updated PDF fields")
                
                # Add PDF content to the page
                add_pdf_content_to_notion_page(token, page_id, file_meta)
                print(f"✅ [PDF-ENTRY] Added PDF content")
                
                # Clean up temporary files
                clean_temporary_files(file_meta)
                
            except Exception as e:
                print(f"❌ [PDF-ENTRY] Error during PDF processing: {e}")
                # Still clean up files even if there was an error
                if file_meta:
                    clean_temporary_files(file_meta)
        else:
            print(f"❌ [PDF-ENTRY] No PDF found for this entry")
    else:
        print(f"⚠️  [PDF-ENTRY] Google Drive service not available")
