"""
Link Paperpile to Notion

A comprehensive tool to sync academic papers from Paperpile to Notion with full PDF content embedding and extraction.
"""
from .core import notion_create_page_with_pdf, add_pdf_content_to_notion_page, add_pdf_content_for_entry
from .notion_client import (
    notion_create_page, notion_update_page, notion_query_by_uid,
    notion_get_property, notion_update_pdf_fields, notion_add_blocks
)
from .drive_client import (
    build_drive_service, drive_find_pdf, drive_find_pdf_with_content,
    extract_pdf_metadata_and_content
)
from .notion_blocks import (
    create_pdf_embed_block, create_divider_block, create_heading_block,
    create_paragraph_block, markdown_to_notion_blocks
)
from .cleanup import clean_temporary_files

__version__ = "0.1.0"
