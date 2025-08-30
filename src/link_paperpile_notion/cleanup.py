"""
Cleanup utilities for temporary files created during PDF processing.
"""
import os
import re
from pathlib import Path
from typing import Dict

def clean_temporary_files(file_meta: Dict) -> None:
    """Clean up temporary files created during PDF processing."""
    cleanup_enabled = os.environ.get("CLEANUP_TEMP_FILES", "true").lower() in ("true", "1", "yes")
    if not cleanup_enabled:
        print(f"[cleanup] Cleanup disabled - keeping temporary files")
        return
    
    # Use the data directory from main
    DATA_DIR = Path("data")
    
    files_to_delete = []
    total_size = 0
    
    # Basic markdown file
    if file_meta.get('markdown_file'):
        md_path = Path(file_meta['markdown_file'])
        if md_path.exists():
            size = md_path.stat().st_size
            files_to_delete.append((md_path, size))
            total_size += size
    
    # Enhanced markdown file with images (removed - images not used)
    # Extracted images (removed - images not used)
    
    # Temporary PDF file (if downloaded)
    pdf_filename = file_meta.get('name', '')
    if pdf_filename:
        safe_filename = re.sub(r'[^\w\-\.]', '_', pdf_filename)
        temp_pdf_path = DATA_DIR / safe_filename
        if temp_pdf_path.exists():
            size = temp_pdf_path.stat().st_size
            files_to_delete.append((temp_pdf_path, size))
            total_size += size
    
    # Delete files
    deleted_count = 0
    for file_path, size in files_to_delete:
        try:
            file_path.unlink()
            deleted_count += 1
            print(f"[cleanup] Deleted: {file_path.name} ({size:,} bytes)")
        except Exception as e:
            print(f"[cleanup] Failed to delete {file_path.name}: {e}")
    
    if deleted_count > 0:
        print(f"[cleanup] ✅ Cleaned up {deleted_count} files, freed {total_size:,} bytes ({total_size/1_000_000:.1f}MB)")
    else:
        print(f"[cleanup] No temporary files to clean up")
