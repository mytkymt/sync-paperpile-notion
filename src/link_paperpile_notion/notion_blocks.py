"""
Notion block creation utilities for content embedding.
"""
import re
from typing import Dict, List

def create_pdf_embed_block(drive_link: str) -> Dict:
    """Create a PDF embed block."""
    return {
        "object": "block",
        "type": "embed",
        "embed": {
            "url": drive_link
        }
    }

def create_divider_block() -> Dict:
    """Create a divider block."""
    return {
        "object": "block",
        "type": "divider",
        "divider": {}
    }

def create_heading_block(text: str, level: int = 2) -> Dict:
    """Create a heading block."""
    heading_type = f"heading_{level}"
    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": [{"text": {"content": text}}]
        }
    }

def create_paragraph_block(text: str) -> Dict:
    """Create a paragraph block."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"text": {"content": text}}]
        }
    }

def create_code_block(text: str, language: str = "text") -> Dict:
    """Create a code block."""
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [{"text": {"content": text}}],
            "language": language
        }
    }

def split_long_text(text: str, max_length: int = 2000) -> List[str]:
    """Split long text into chunks for Notion blocks."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by sentences first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def create_paragraph_blocks(text: str) -> List[Dict]:
    """Create multiple paragraph blocks from long text."""
    chunks = split_long_text(text)
    return [create_paragraph_block(chunk) for chunk in chunks]

def markdown_to_notion_blocks(markdown_content: str) -> List[Dict]:
    """Convert markdown content to Notion blocks."""
    if not markdown_content or not markdown_content.strip():
        return []
    
    blocks = []
    lines = markdown_content.split('\n')
    current_paragraph = ""
    in_code_block = False
    code_block_lines = []
    code_language = "text"
    
    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                if code_block_lines:
                    code_content = '\n'.join(code_block_lines)
                    blocks.append(create_code_block(code_content, code_language))
                code_block_lines = []
                in_code_block = False
            else:
                # Start code block
                if current_paragraph.strip():
                    blocks.extend(create_paragraph_blocks(current_paragraph.strip()))
                    current_paragraph = ""
                in_code_block = True
                # Extract language from ```python, ```javascript, etc.
                lang_match = re.match(r'```(\w+)', line.strip())
                code_language = lang_match.group(1) if lang_match else "text"
            continue
        
        if in_code_block:
            code_block_lines.append(line)
            continue
        
        # Handle headings
        if line.startswith('# '):
            if current_paragraph.strip():
                blocks.extend(create_paragraph_blocks(current_paragraph.strip()))
                current_paragraph = ""
            blocks.append(create_heading_block(line[2:].strip(), 1))
        elif line.startswith('## '):
            if current_paragraph.strip():
                blocks.extend(create_paragraph_blocks(current_paragraph.strip()))
                current_paragraph = ""
            blocks.append(create_heading_block(line[3:].strip(), 2))
        elif line.startswith('### '):
            if current_paragraph.strip():
                blocks.extend(create_paragraph_blocks(current_paragraph.strip()))
                current_paragraph = ""
            blocks.append(create_heading_block(line[4:].strip(), 3))
        
        # Handle dividers
        elif line.strip() == '---':
            if current_paragraph.strip():
                blocks.extend(create_paragraph_blocks(current_paragraph.strip()))
                current_paragraph = ""
            blocks.append(create_divider_block())
        
        # Handle empty lines
        elif not line.strip():
            if current_paragraph.strip():
                blocks.extend(create_paragraph_blocks(current_paragraph.strip()))
                current_paragraph = ""
        
        # Regular content
        else:
            current_paragraph += line + "\n"
    
    # Handle any remaining content
    if in_code_block and code_block_lines:
        code_content = '\n'.join(code_block_lines)
        blocks.append(create_code_block(code_content, code_language))
    
    if current_paragraph.strip():
        blocks.extend(create_paragraph_blocks(current_paragraph.strip()))
    
    return blocks
