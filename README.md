# Sync Paperpile to Notion

A comprehensive tool to sync academic papers from Paperpile to Notion with full PDF content embedding and extraction.

## ✨ Features

### Core Functionality
- **Paperpile Integration**: Automatic sync of BibTeX export from Paperpile
- **Notion Database Sync**: Create and update paper entries in Notion database  
- **Google Drive PDF Linking**: Automatic PDF discovery and linking from Google Drive
- **PDF Content Embedding**: Full PDF content extraction and embedding into Notion pages

### Advanced PDF Processing
- **Structured Text Extraction**: Enhanced academic paper formatting with PyMuPDF
- **Figure Caption Recognition**: Consolidates multi-line figure captions
- **Mathematical Equation Detection**: Proper formatting of mathematical notation
- **Citation Processing**: Special handling of references and session information
- **Image Extraction**: Extracts and saves images from PDFs
- **Content Splitting**: Automatic text splitting to handle Notion's 2000 character limit

### Content Types Supported
- PDF embed blocks with Google Drive preview links
- Extracted markdown content as formatted Notion blocks
- Headings, paragraphs, code blocks, and dividers
- Academic paper structure preservation
- Enhanced content recognition for figures, equations, and citations

### Why Extract Markdown from PDFs for Notion?

While Notion allows you to preview PDFs stored in Google Drive through its connected app feature, saving the actual text content (as markdown) directly into Notion can offer several advantages:

- All-in-One Workspace: Users who prefer to keep everything inside Notion—without relying on external storage or integrations—can have easy access to the paper's content.
- Privacy & Simplicity: No need to connect your Google Drive account if you just want the paper's text in Notion.
- Potential for Enhanced Notion AI: Extracted markdown content may allow Notion AI features such as summarization and improved search, which might not be fully available for embedded PDF files.
- Better Organization: Text content is searchable, editable, and can be structured alongside your notes, citations, and other research materials.

This tool makes it simple to keep full, formatted paper content inside Notion, maximizing both convenience and the power of Notion's workspace.

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/link-paperpile-notion.git
cd link-paperpile-notion

# Install dependencies (choose one method)

# Method 1: Using pip with requirements.txt
pip install -r requirements.txt

# Method 2: Using pip with editable install
pip install -e .
```

### 2. Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:
- `PAPERPILE_EXPORT_URL`: Your Paperpile BibTeX export URL (see [Paperpile Setup](#-paperpile-setup) section for detailed instructions)
- `NOTION_TOKEN`: Your Notion integration token
- `NOTION_DB_ID`: Your Notion database ID

### 3. Run

```bash
python main.py
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

#### Required
```properties
# Get this from Paperpile's Integrations tab (see Paperpile Setup section)
PAPERPILE_EXPORT_URL=https://paperpile.com/eb/your-export-url
NOTION_TOKEN=secret_your-integration-token
NOTION_DB_ID=your-database-id
```

#### Optional
```properties
# Authors database for relation linking
AUTHORS_DB_ID=your-authors-database-id

# Google Drive integration for PDF linking
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Processing limits for testing
LIMIT_MODE=true
LIMIT_COUNT=10

# PDF processing options
PDF_MAX_PAGES=25
PDF_INCLUDE_PAGE_NUMBERS=false

# Test mode (parse only, skip Notion operations)
TEST_MODE=true
```
## 📋 Notion Database Setup

### Required Properties

Your Notion database must have these properties:

| Property | Type | Description |
|----------|------|-------------|
| **Title** | Title | Paper title |
| **PubType** | Select | Publication type (Journal, Conference, etc.) |
| **Year** | Number | Publication year |
| **Venue** | Text | Journal/conference name |
| **DOI** | URL | Digital Object Identifier |
| **URL** | URL | Paper URL |
| **Abstract** | Text | Paper abstract |

### Optional Properties

| Property | Type | Description |
|----------|------|-------------|
| **PDF (Drive)** | URL | Google Drive PDF links |
| **Drive File ID** | Text | Internal file tracking |
| **Authors** | Relation | Links to Authors database |

### Creating the Database

1. Create a new Notion database
2. Add the required properties above
3. Create a Notion integration at [notion.so/my-integrations](https://notion.so/my-integrations)
4. Share your database with the integration
5. Copy the database ID from the URL

## 🔗 Paperpile Setup

To sync your papers from Paperpile, you'll need to get your personal BibTeX export URL:

### Step 1: Access Paperpile Integrations

1. **Open Paperpile** in your web browser
2. **Navigate to any paper** in your library
3. **Click on the "Integrations" tab** in the paper's side panel (usually located on the right side when viewing a paper)

### Step 2: Get Your BibTeX Export URL

1. In the **Integrations tab**, look for the **"Export"** or **"BibTeX"** section
2. You should see an option like **"Export all papers as BibTeX"** or similar
3. **Copy the provided URL** - this is your personal export link that will always contain your latest papers

The URL will look something like:
```
https://paperpile.com/eb/abcd1234efgh5678
```

### Step 3: Add to Environment File

1. Add the copied URL to your `.env` file:
   ```properties
   PAPERPILE_EXPORT_URL=https://paperpile.com/eb/your-actual-export-url
   ```

### Notes:
- This URL is **personal and private** - don't share it publicly
- The URL automatically updates when you add or modify papers in Paperpile
- You only need to set this up once

## 📁 Google Drive Setup (Optional)

For automatic PDF linking:

1. Create a Google Cloud Project
2. Enable the Google Drive API
3. Create a service account
4. Download the service account JSON key
5. Share your PDF folder with the service account email
6. Set `GOOGLE_APPLICATION_CREDENTIALS` in your `.env` file

## 📖 Usage Examples

### Basic Sync
```bash
python main.py
```

### Test Mode (No Notion Updates)
```bash
TEST_MODE=true python main.py
```

### Limited Processing (for testing)
```bash
LIMIT_MODE=true LIMIT_COUNT=5 python main.py
```

### Process with PDF Content Extraction
```bash
PDF_MAX_PAGES=10 python main.py
```

## 🕒 Automated Scheduling

For regular synchronization, you can set up cyclical updates using your system's scheduling tools.

### For macOS:

1. Open the terminal.
2. Edit the crontab file:
   ```bash
   crontab -e
   ```
3. Add the following entry to run a script every hour (adjust timing as needed):
   ```bash
   0 * * * * /path/to/your/script.sh
   ```
4. Save and exit the editor.

### For Windows:

1. Open Task Scheduler.
2. Create a new basic task and give it a name.
3. Set the trigger (e.g., daily, hourly, etc.).
4. Set the action to run a program or script.
5. Browse to the script or program you want to run and finish the setup.

### For GitHub Actions (Recommended):

The repository includes a GitHub Actions workflow that automatically runs the sync on a daily schedule. This is the easiest way to set up automated synchronization without managing your own server infrastructure.

#### How it works:
- **Schedule**: Runs daily at 02:00 UTC
- **Manual Trigger**: Can be triggered manually from the GitHub Actions tab
- **Environment**: Uses Python 3.11 with all required dependencies
- **Security**: Credentials are stored as GitHub repository secrets

#### Setup:
1. Fork this repository to your GitHub account
2. Go to your forked repository's **Settings** → **Secrets and variables** → **Actions**
3. Add the following repository secrets:
   - `PAPERPILE_EXPORT_URL`: Your Paperpile BibTeX export URL
   - `NOTION_TOKEN`: Your Notion integration token  
   - `NOTION_DB_ID`: Your Notion database ID
   - `AUTHORS_DB_ID` (optional): Your authors database ID
   - `GOOGLE_APPLICATION_CREDENTIALS_JSON` (optional): Your Google service account JSON as a string

#### The workflow file:
```yaml
name: Sync Paperpile to Notion

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 02:00 UTC
  workflow_dispatch:      # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install -r requirements.txt
    - run: python main.py
      env:
        PAPERPILE_EXPORT_URL: ${{ secrets.PAPERPILE_EXPORT_URL }}
        NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
        NOTION_DB_ID: ${{ secrets.NOTION_DB_ID }}
        # ... other secrets
```

📁 **Workflow location**: [`.github/workflows/sync-paperpile-notion.yml`](.github/workflows/sync-paperpile-notion.yml)

#### Monitoring:
- View sync logs in the **Actions** tab of your GitHub repository
- Receive email notifications for failed runs (configurable in GitHub settings)
- Manual runs can be triggered anytime from the Actions tab

## 🏗️ Architecture

The tool is built with a modular architecture:

- **`main.py`**: Main entry point and BibTeX processing
- **`src/link_paperpile_notion/`**: Core modules
  - **`core.py`**: Notion API integration
  - **`drive_client.py`**: Google Drive and PDF processing
  - **`notion_client.py`**: Notion page creation and updates
  - **`notion_blocks.py`**: Notion block formatting

### PDF Processing Pipeline

1. **Search & Download**: Find PDFs in Google Drive by filename patterns
2. **Content Extraction**: Extract structured text using PyMuPDF
3. **Content Enhancement**: Detect and format figures, equations, citations
4. **Block Creation**: Convert to Notion blocks with proper formatting
5. **Embedding**: Add PDF embed and extracted content to Notion pages

## 🔧 Advanced Configuration

### PDF Processing Options

```properties
# Maximum pages to extract (default: 25)
PDF_MAX_PAGES=10

# Include page numbers in content (default: false)
PDF_INCLUDE_PAGE_NUMBERS=true
```

### Content Processing

The tool automatically handles:
- **Figure Captions**: Multi-line captions are consolidated
- **Mathematical Equations**: Detected and preserved with proper formatting  
- **Citations**: References formatted appropriately
- **Code Blocks**: Syntax highlighting preserved
- **Text Splitting**: Long content split to meet Notion's 2000 char limit

## 🤝 Contributing

Contributions are welcome! Areas for enhancement:

- Additional content type detection
- Enhanced figure and table processing
- Multi-language support
- Custom formatting rules
- Better error handling and logging

## 📄 License

MIT License - see LICENSE file for details.

## 🐛 Issues & Support

If you encounter issues:

1. Check that all environment variables are set correctly
2. Verify Notion database permissions and structure
3. Ensure Google Drive API credentials are valid
4. Enable debug mode with appropriate test flags

For bugs and feature requests, please open an issue on GitHub.
