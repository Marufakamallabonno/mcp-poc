# 🧠 Model Context Protocol (MCP) – Local & Deployed Integration

A comprehensive collection of **Model Context Protocol (MCP)** servers built with **FastMCP**, demonstrating how to create, integrate, and deploy AI-powered tools that work seamlessly with LLMs such as **Claude**, **GPT-4**, and **Gemini**.

## 🚀 Features

This project includes **4 production-ready MCP servers**:

1. **🌦️ Weather Server** - Real-time weather data and alerts from the National Weather Service
2. **📊 Google Sheets Server** - Complete spreadsheet automation and management
3. **💰 Expense Tracker** - SQLite-backed personal finance management
4. **📚 Knowledge Base (RAG)** - Simple retrieval-augmented generation system

## 📋 Prerequisites

- **Python 3.13+** (required)
- **uv** - Fast Python package installer (recommended)
- **Git** - For version control
- **OpenAI API Key** or **Groq API Key** (for the client)

### For Google Sheets Server:
- Google Cloud Project with Sheets API enabled
- Service Account credentials JSON file

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Marufakamallabonno/mcp-poc.git
cd MCP-CRASH-Course
```

### 2. Install uv (if not already installed)

**Windows (PowerShell):**
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Sync Dependencies

```bash
uv sync
```

This will install all required packages from `pyproject.toml`.

## ⚙️ Configuration

### 1. MCP Servers Configuration

The main configuration file is located at `server/mcpconfig.json` If you want to use it locally. Update the paths if needed:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["run", "--with", "mcp[cli]", "mcp", "run", "path/to/weather.py"]
    },
    "google_sheets": {
      "command": "uv",
      "args": ["run", "--with", "google-api-python-client", "--with", "google-auth", "--with", "google-auth-oauthlib", "--with", "mcp[cli]", "mcp", "run", "path/to/google_sheet.py"],
      "env": {
        "SERVICE_ACCOUNT_PATH": "path/to/your/service-account.json",
        "SPREADSHEET_ID": "your-spreadsheet-id"
      }
    },
    "expense_tracker": {
      "command": "uv",
      "args": ["run", "--with", "mcp[cli]", "mcp", "run", "path/to/expense_tracker.py"]
    },
    "rag": {
      "command": "uv",
      "args": ["run", "--with", "mcp[cli]", "mcp", "run", "path/to/rag.py"]
    }
  }
}
```

### 2. Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
# OR
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Google Sheets Setup (Optional)

If using the Google Sheets server:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Google Sheets API** and **Google Drive API**
4. Create a **Service Account**
5. Download the credentials JSON file
6. Place it in `server/keys/` directory
7. Update the path in `mcpconfig.json`

### 4. Knowledge Base Setup (Optional)

Edit `server/data/kb.json` to add your Q&A pairs:

```json
[
  {
    "question": "What is MCP?",
    "answer": "Model Context Protocol is a standard for AI tools..."
  }
]
```

## 🎯 Usage

### Option 1: Interactive Client with LLM

Run the interactive chat client that connects all MCP servers:

```bash
cd MCP-CRASH-Course
uv run server/client.py
```

This starts an interactive chat session where you can:
- Ask about weather for any location
- Manage Google Sheets
- Track expenses
- Query the knowledge base

**Example conversations:**
```
You: What's the weather in San Francisco?
You: Create a new spreadsheet called "Budget 2025"
You: Add an expense of $50 for groceries today
You: What is MCP?
```

### Option 2: Test Individual Servers

Test each MCP server independently:

```bash
# Weather Server
uv run --with mcp[cli] mcp dev server/weather.py

# Google Sheets Server
uv run --with google-api-python-client --with google-auth --with google-auth-oauthlib --with mcp[cli] mcp dev server/google_sheet.py

# Expense Tracker
uv run --with mcp[cli] mcp dev server/expense_tracker.py

# Knowledge Base
uv run --with mcp[cli] mcp dev server/rag.py
```

### Option 3: Use with Claude Desktop

1. Copy `server/mcpconfig.json` to Claude's config directory:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux:** `~/.config/Claude/claude_desktop_config.json`

2. Restart Claude Desktop

3. The MCP tools will appear in Claude's tool menu

## 📦 Available MCP Servers

### 1. Weather Server (`weather.py`)

**Tools:**
- `get_alerts` - Get weather alerts for a US state
- `get_forecast` - Get weather forecast for coordinates
- Additional weather-related tools

**Example:**
```python
# Get weather alerts for California
get_alerts(state="CA")
```

### 2. Google Sheets Server (`google_sheet.py`)

**Tools:**
- `get_sheet_data` - Read data from sheets
- `update_cells` - Update cell values
- `batch_update_cells` - Update multiple ranges at once
- `create_spreadsheet` - Create new spreadsheets
- `create_sheet` - Add new sheet tabs
- `list_sheets` - List all sheets in a spreadsheet
- `list_spreadsheets` - List all spreadsheets in Drive
- `copy_sheet` - Copy sheets between spreadsheets
- `rename_sheet` - Rename sheet tabs
- `add_rows` / `add_columns` - Add dimensions
- `share_spreadsheet` - Share with users
- `get_sheet_formulas` - Extract formulas
- `get_multiple_sheet_data` - Batch read operations
- `get_multiple_spreadsheet_summary` - Multi-spreadsheet summaries

**Resources:**
- `spreadsheet://{spreadsheet_id}/info` - Get spreadsheet metadata

### 3. Expense Tracker (`expense_tracker.py`)

**Tools:**
- `add_expense` - Add a new expense
- `get_expenses` - Retrieve expenses by date range
- `update_expense` - Modify an existing expense
- `delete_expense` - Remove an expense
- `get_summary` - Get spending summary by category
- `export_expenses` - Export to CSV/JSON

**Database:** Uses SQLite (`expense.db`) for persistent storage

### 4. Knowledge Base RAG (`rag.py`)

**Tools:**
- `get_knowledge_base` - Retrieve all Q&A pairs
- `search_knowledge` - Search for specific topics
- `add_knowledge` - Add new Q&A pairs

**Data:** Stored in `server/data/kb.json`


## 🔧 Troubleshooting

### JSON Parsing Errors

**Issue:** `SyntaxError: Unexpected token... is not valid JSON`

**Solution:** This happens when MCP servers use `print()` statements. Use `sys.stderr.write()` instead:

```python
import sys
# Instead of: print("message")
sys.stderr.write("message\n")
```

### File Lock Errors

**Issue:** `The process cannot access the file because it is being used by another process`

**Solution:**
1. Close Claude Desktop or any MCP clients
2. Kill running Python processes
3. Delete `.venv` and run `uv sync` again

### Google Sheets Authentication

**Issue:** Permission denied or quota exceeded

**Solution:**
1. Verify service account JSON is valid
2. Share your spreadsheet with the service account email
3. Enable Google Sheets API in Cloud Console
4. Check Drive storage quota

### Module Not Found

**Issue:** `ModuleNotFoundError: No module named 'X'`

**Solution:**
```bash
uv sync  # Reinstall all dependencies
```

## 🎓 Learning Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [FastMCP Guide](https://github.com/jlowin/fastmcp)
- [Google Sheets API](https://developers.google.com/sheets/api)

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Add new MCP servers
- Improve existing tools
- Fix bugs
- Update documentation

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Powered by [Model Context Protocol](https://modelcontextprotocol.io/)
- Weather data from [National Weather Service API](https://www.weather.gov/documentation/services-web-api)

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Happy MCP Building! 🚀**
