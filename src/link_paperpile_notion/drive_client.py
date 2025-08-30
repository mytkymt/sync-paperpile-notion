"""
Google Drive client functions for PDF search and content extraction.
"""
import os
import re
import json
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Optional, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Check for PyMuPDF availability
try:
    import fitz
    _PYMUPDF_AVAILABLE = True
except ImportError:
    _PYMUPDF_AVAILABLE = False
    print("[warning] PyMuPDF not available - PDF content extraction disabled")

def build_drive_service():
    """Build Google Drive service client."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("[drive] Google Drive libraries not available")
        return None
    
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"[drive] Checking credentials path: {cred_path}")
    if not cred_path or not Path(cred_path).exists():
        print("[drive] Google Drive credentials not found")
        return None
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        service = build("drive", "v3", credentials=credentials)
        print("[drive] Successfully built Google Drive service")
        return service
    except Exception as e:
        print(f"[drive] Failed to build service: {e}")
        return None

def normalize_title(title: str) -> str:
    """Normalize title for PDF search."""
    if not title:
        return ""
    # Remove common patterns and normalize
    title = re.sub(r'[^\w\s-]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def expected_pdf_name(entry: Dict) -> str:
    """Generate expected PDF filename based on entry metadata."""
    authors = entry.get("authors", [])
    year = str(entry.get("year", "")).strip()
    title = normalize_title(entry.get("title", ""))
    
    if authors and year and title:
        first_author = authors[0]["last"]
        if len(authors) > 1:
            author_part = f"{first_author} et al."
        else:
            author_part = first_author
        
        # Truncate title if too long
        title_part = title[:50] + "..." if len(title) > 50 else title
        return f"{author_part} {year} - {title_part}.pdf"
    
    return "Unknown.pdf"

def generate_pdf_search_patterns(entry: Dict) -> List[str]:
    """Generate multiple search patterns for PDF files."""
    patterns = []
    authors = entry.get("authors", [])
    year = str(entry.get("year", "")).strip()
    title = normalize_title(entry.get("title", ""))
    
    if not authors:
        return patterns
    
    first_last = authors[0]["last"]
    
    # Pattern 1: Author Year Title (truncated)
    if title and len(title) > 10:
        title_short = title.split()[0:6]  # First 6 words
        title_part = " ".join(title_short)
        patterns.append(f"{first_last} {year} {title_part} .pdf")
    
    # Pattern 2: Author Year - Full title
    if title:
        patterns.append(f"{first_last} {year} - {title}.pdf")
    
    # Pattern 3: Just Author Year
    patterns.append(f"{first_last} {year}.pdf")
    
    # Pattern 4: Multiple authors
    if len(authors) > 1:
        patterns.append(f"{first_last} et al {year}.pdf")
        patterns.append(f"{first_last} et al. {year}.pdf")
    
    # Pattern 5: Title only (if unique enough)
    if title and len(title) > 15:
        patterns.append(f"{title}.pdf")
    
    return patterns

def drive_search_by_pattern(service, pattern: str) -> Optional[Dict]:
    """Search Google Drive for PDF by filename pattern."""
    try:
        # Escape special characters for Drive search
        search_pattern = pattern.replace("'", "\\'")
        q = f"name contains '{search_pattern}' and mimeType='application/pdf' and trashed=false"
        
        resp = service.files().list(
            q=q,
            fields="files(id,name,size,webViewLink,modifiedTime)",
            pageSize=10
        ).execute()
        
        files = resp.get("files", [])
        if files:
            # Return the first match (most relevant)
            return files[0]
    except Exception as e:
        print(f"[drive] Search error for pattern '{pattern}': {e}")
    
    return None

def drive_find_pdf(service, entry: Dict) -> Optional[Dict]:
    """Find PDF file in Google Drive for a given entry."""
    if service is None:
        return None
    
    authors = entry.get("authors", [])
    year = str(entry.get("year", "")).strip()
    title = normalize_title(entry.get("title", ""))
    first_last = authors[0]["last"] if authors else ""
    
    # Show what we're searching for
    print(f"🔍 [PDF SEARCH] Looking for: {entry.get('title', 'Unknown Title')}")
    print(f"   👤 Author: {first_last} {('et al.' if len(authors) > 1 else '')}")
    print(f"   📅 Year: {year}")
    print(f"   🎯 Primary pattern: {expected_pdf_name(entry)}")
    
    # Strategy 1: Try exact filename matches
    patterns = generate_pdf_search_patterns(entry)
    for pattern in patterns:
        file_meta = drive_search_by_pattern(service, pattern.replace('.pdf', ''))
        if file_meta:
            print(f"✅ [PDF FOUND] Using pattern: {pattern}")
            print(f"   📄 File: {file_meta['name']}")
            print(f"   📦 Size: {int(file_meta.get('size', 0)) / 1_000_000:.1f} MB")
            return file_meta
    
    # Strategy 2: Search by components (author + year)
    search_terms = []
    if first_last and len(first_last) > 2:
        search_terms.append(first_last)
    if year and year != "None":
        search_terms.append(year)
    
    if search_terms:
        combined_search = " ".join(search_terms)
        file_meta = drive_search_by_pattern(service, combined_search)
        if file_meta:
            print(f"✅ [PDF FOUND] Using components: {combined_search}")
            print(f"   📄 File: {file_meta['name']}")
            return file_meta
    
    # Strategy 3: Try title-only search as last resort
    if title and len(title) > 10:
        title_words = title.split()[:4]  # First 4 words
        title_search = " ".join(title_words)
        file_meta = drive_search_by_pattern(service, title_search)
        if file_meta:
            print(f"✅ [PDF FOUND] Using title: {title_search}")
            print(f"   📄 File: {file_meta['name']}")
            return file_meta
    
    # No PDF found
    print(f"❌ [PDF NOT FOUND] No matching PDF found in Google Drive")
    return None

def extract_pdf_metadata_and_content(service, file_id: str, filename: str = "") -> Optional[Dict]:
    """Download PDF from Google Drive and extract metadata + content using PyMuPDF."""
    if not _PYMUPDF_AVAILABLE:
        print(f"[pdf] PyMuPDF not available - skipping content extraction")
        return None
    
    try:
        print(f"[pdf] Downloading PDF for content extraction...")
        # Download PDF content
        file_content = service.files().get_media(fileId=file_id).execute()
        
        # Open with PyMuPDF
        doc = fitz.open(stream=file_content, filetype="pdf")
        
        # Extract metadata
        pdf_metadata = doc.metadata
        metadata = {
            'page_count': len(doc),
            'title': pdf_metadata.get('title', '').strip(),
            'author': pdf_metadata.get('author', '').strip(),
            'subject': pdf_metadata.get('subject', '').strip(),
        }
        
        print(f"[pdf] PDF has {metadata['page_count']} pages")
        
        # Extract content as markdown using structured extraction (configurable page limit)
        max_pages_env = os.environ.get("PDF_MAX_PAGES", "10")
        try:
            max_pages_limit = int(max_pages_env)
        except:
            max_pages_limit = 10  # Default to 10 pages
        max_pages = min(max_pages_limit, len(doc))
        print(f"[pdf] Extracting content from first {max_pages} pages (limit: {max_pages_limit})")
        markdown_content = ""
        text_content = ""
        
        for page_num in range(max_pages):
            page = doc.load_page(page_num)
            
            # Use structured text extraction with font information for better quality
            try:
                text_dict = page.get_text("dict")
                structured_md = format_structured_text(text_dict, page_num + 1)
                if structured_md.strip():
                    markdown_content += structured_md
            except:
                # Fallback to simple markdown conversion
                include_page_numbers = os.environ.get("PDF_INCLUDE_PAGE_NUMBERS", "false").lower() in ("true", "1", "yes")
                try:
                    page_md = page.get_text("markdown")
                    if page_md.strip():
                        if include_page_numbers:
                            markdown_content += f"\n\n## Page {page_num + 1}\n\n{page_md.strip()}"
                        else:
                            markdown_content += f"\n\n{page_md.strip()}"
                except:
                    # Final fallback to plain text
                    page_text = page.get_text("text")
                    if page_text.strip():
                        if include_page_numbers:
                            markdown_content += f"\n\n## Page {page_num + 1}\n\n{page_text.strip()}"
                        else:
                            markdown_content += f"\n\n{page_text.strip()}"
            
            # Also get plain text for summary
            page_text = page.get_text("text")
            if page_text.strip():
                text_content += page_text + "\n"
        
        # Generate a summary (first 500 chars of text with better cleaning)
        summary = ""
        if text_content.strip():
            # Clean up text for summary
            clean_text = re.sub(r'\s+', ' ', text_content.strip())
            summary = clean_text[:500] + "..." if len(clean_text) > 500 else clean_text
        
        # File size info
        file_size = len(file_content)
        size_mb = file_size / 1_000_000
        
        result = {
            'metadata': metadata,
            'markdown_content': markdown_content.strip(),
            'text_summary': summary,
            'page_count': metadata['page_count'],
            'size_bytes': file_size,
            'size_mb': round(size_mb, 1),
            'extraction_info': {
                'pages_extracted': max_pages,
                'total_pages': metadata['page_count'],
                'content_length': len(markdown_content),
                'extraction_method': 'structured_text_dict',
            }
        }
        
        doc.close()
        
        print(f"[pdf] Extracted structured content from {max_pages}/{metadata['page_count']} pages")
        print(f"[pdf] Content length: {len(markdown_content)} chars (structured extraction)")
        print(f"[pdf] File size: {size_mb:.1f}MB")
        
        return result
        
    except Exception as e:
        print(f"[pdf] Error processing PDF: {e}")
        return None

def drive_find_pdf_with_content(service, entry: Dict) -> Optional[Dict]:
    """Enhanced version that finds PDF and extracts content/metadata."""
    file_meta = drive_find_pdf(service, entry)
    if file_meta and _PYMUPDF_AVAILABLE:
        print(f"📥 [PDF PROCESSING] Extracting content from: {file_meta['name']}")
        # Extract PDF content and metadata
        pdf_data = extract_pdf_metadata_and_content(service, file_meta['id'], file_meta['name'])
        if pdf_data:
            # Merge PDF data into file metadata
            file_meta.update(pdf_data)
            pages_extracted = pdf_data.get('extraction_info', {}).get('pages_extracted', 0)
            content_length = pdf_data.get('extraction_info', {}).get('content_length', 0)
            print(f"✅ [PDF SUCCESS] Content extraction completed!")
            print(f"   📄 Pages processed: {pages_extracted}")
            print(f"   📝 Content length: {content_length:,} characters")
        else:
            print(f"❌ [PDF ERROR] Content extraction failed")
    elif file_meta and not _PYMUPDF_AVAILABLE:
        print(f"⚠️  [PDF WARNING] PyMuPDF not available - skipping content extraction")
    
    return file_meta

def clean_paragraph_text(text: str) -> str:
    """Clean up paragraph text by removing unnecessary line breaks and formatting."""
    if not text:
        return text
    
    # Remove excessive whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Don't break sentences unnecessarily - only break at proper sentence boundaries
    # Join lines that don't end with sentence-ending punctuation
    lines = text.split('\n')
    cleaned_lines = []
    current_paragraph = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            if current_paragraph:
                cleaned_lines.append(current_paragraph.strip())
                current_paragraph = ""
            continue
        
        # If the previous line doesn't end with sentence punctuation, join with current line
        if current_paragraph and not re.search(r'[.!?;:]\s*$', current_paragraph):
            current_paragraph += " " + line
        else:
            if current_paragraph:
                cleaned_lines.append(current_paragraph.strip())
            current_paragraph = line
    
    # Don't forget the last paragraph
    if current_paragraph:
        cleaned_lines.append(current_paragraph.strip())
    
    return '\n\n'.join(cleaned_lines)


def is_figure_caption(text: str) -> bool:
    """Check if text is a figure caption."""
    text_lower = text.lower()
    return (text_lower.startswith('figure ') or 
            text_lower.startswith('fig.') or
            text_lower.startswith('table ') or
            text_lower.startswith('equation ') or
            re.match(r'^(figure|fig\.?|table|equation)\s+\d+', text_lower))


def is_citation_or_footer(text: str) -> bool:
    """Check if text is citation, session info, or footer material."""
    text_lower = text.lower().strip()
    
    # Session information
    if 'session' in text_lower and ('brain' in text_lower or 'taste' in text_lower):
        return True
    
    # Conference/journal info
    if re.match(r'.*\d{4}.*', text) and ('uist' in text_lower or 'acm' in text_lower or 'ieee' in text_lower):
        return True
    
    # Page numbers
    if re.match(r'^\d{3,4}$', text.strip()):
        return True
    
    # Permission statements
    if 'permission' in text_lower and ('make digital' in text_lower or 'copyright' in text_lower):
        return True
    
    # DOI, ISBN, etc.
    if re.match(r'.*(doi|isbn|issn).*:', text_lower):
        return True
    
    return False


def is_mathematical_equation(text: str) -> bool:
    """Check if text contains mathematical equations."""
    # Look for mathematical symbols and patterns
    math_patterns = [
        r'[=<>≤≥≠±∞∑∏∫]',  # Mathematical operators
        r'[α-ωΑ-Ω]',  # Greek letters
        r'\^?\d+\s*=\s*',  # Equation patterns
        r'[a-zA-Z]_[a-zA-Z0-9]+',  # Subscripts
        r'[a-zA-Z]\^[a-zA-Z0-9]+',  # Superscripts
        r'log\s+[a-zA-Z]',  # Logarithms
        r'\([0-9]+\)$'  # Equation numbers
    ]
    
    return any(re.search(pattern, text) for pattern in math_patterns)


def format_structured_text(text_dict: Dict, page_num: int) -> str:
    """Format text from PyMuPDF text dict with better structure preservation."""
    # Check if page numbers should be included
    include_page_numbers = os.environ.get("PDF_INCLUDE_PAGE_NUMBERS", "false").lower() in ("true", "1", "yes")
    
    if include_page_numbers:
        result = f"\n\n---\n\n## Page {page_num}\n\n"
    else:
        result = "\n\n"  # Just add some spacing without page numbers
    
    # Collect text blocks first, then process them for better paragraph structure
    text_blocks = []
    
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:  # Text block
            block_lines = []
            
            for line in block.get("lines", []):
                line_text = ""
                max_font_size = 0
                is_bold = False
                is_italic = False
                
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        font_size = span.get("size", 12)
                        font_flags = span.get("flags", 0)
                        max_font_size = max(max_font_size, font_size)
                        
                        # Check formatting flags
                        if font_flags & 16:  # Bold
                            is_bold = True
                        if font_flags & 2:   # Italic
                            is_italic = True
                        
                        line_text += text + " "
                
                if line_text.strip():
                    block_lines.append({
                        'text': line_text.strip(),
                        'font_size': max_font_size,
                        'is_bold': is_bold,
                        'is_italic': is_italic
                    })
            
            if block_lines:
                text_blocks.append(block_lines)
    
    # Process blocks to create better structure
    figure_caption_buffer = []  # Buffer to collect multi-line figure captions
    
    for block_lines in text_blocks:
        # Group consecutive lines with similar formatting
        current_group = []
        
        for line_info in block_lines:
            clean_text = line_info['text']
            max_font_size = line_info['font_size']
            is_bold = line_info['is_bold']
            is_italic = line_info['is_italic']
            
            # Check for special content types
            if is_citation_or_footer(clean_text):
                # Output any accumulated paragraph text first
                if current_group:
                    paragraph_text = " ".join([item['text'] for item in current_group])
                    paragraph_text = clean_paragraph_text(paragraph_text)
                    if paragraph_text:
                        result += paragraph_text + "\n\n"
                    current_group = []
                
                # Skip citation/footer content or format it specially
                if len(clean_text) > 20:  # Only include substantial citation text
                    result += f"*{clean_text}*\n\n"
                continue
            
            # Handle figure captions - they often span multiple lines
            if is_figure_caption(clean_text):
                # Output any accumulated paragraph text first
                if current_group:
                    paragraph_text = " ".join([item['text'] for item in current_group])
                    paragraph_text = clean_paragraph_text(paragraph_text)
                    if paragraph_text:
                        result += paragraph_text + "\n\n"
                    current_group = []
                
                figure_caption_buffer.append(clean_text)
                continue
            
            # If we have accumulated figure caption parts, output them
            if figure_caption_buffer:
                caption_text = " ".join(figure_caption_buffer)
                result += f"**{caption_text}**\n\n"
                figure_caption_buffer = []
            
            # Handle mathematical equations
            if is_mathematical_equation(clean_text):
                # Output any accumulated paragraph text first
                if current_group:
                    paragraph_text = " ".join([item['text'] for item in current_group])
                    paragraph_text = clean_paragraph_text(paragraph_text)
                    if paragraph_text:
                        result += paragraph_text + "\n\n"
                    current_group = []
                
                # Format equation with proper spacing
                if re.search(r'\([0-9]+\)$', clean_text):
                    # Numbered equation
                    result += f"```\n{clean_text}\n```\n\n"
                else:
                    # Inline equation
                    result += f"*{clean_text}*\n\n"
                continue
            
            # Determine if this is a heading
            is_heading = False
            heading_level = ""
            
            # Large font or bold large text = main heading
            if max_font_size > 16 or (is_bold and max_font_size > 14):
                is_heading = True
                heading_level = "# "
            # Medium font or bold medium text = subheading  
            elif max_font_size > 13 or (is_bold and max_font_size > 11):
                is_heading = True
                heading_level = "## "
            # Small bold text = minor heading or emphasis
            elif is_bold and len(clean_text) < 100:  # Short bold text likely a heading
                is_heading = True
                heading_level = "### "
            
            if is_heading:
                # Output any accumulated paragraph text first
                if current_group:
                    paragraph_text = " ".join([item['text'] for item in current_group])
                    paragraph_text = clean_paragraph_text(paragraph_text)
                    if paragraph_text:
                        result += paragraph_text + "\n\n"
                    current_group = []
                
                # Output the heading
                result += f"\n{heading_level}{clean_text}\n\n"
            else:
                # Accumulate regular text for paragraph formation
                current_group.append(line_info)
        
        # Output any remaining paragraph text
        if current_group:
            paragraph_text = " ".join([item['text'] for item in current_group])
            paragraph_text = clean_paragraph_text(paragraph_text)
            if paragraph_text:
                # Apply formatting for special cases
                first_item = current_group[0]
                if first_item['is_italic']:
                    paragraph_text = f"*{paragraph_text}*"
                elif first_item['is_bold']:
                    paragraph_text = f"**{paragraph_text}**"
                
                result += paragraph_text + "\n\n"
        
        # Output any remaining figure captions
        if figure_caption_buffer:
            caption_text = " ".join(figure_caption_buffer)
            result += f"**{caption_text}**\n\n"
            figure_caption_buffer = []
    
    return result
