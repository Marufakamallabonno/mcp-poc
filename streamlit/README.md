# 🔄 JSON State Chat Manager

A Streamlit-based chat interface that allows natural language interactions to directly update a front-end JSON state. This demonstrates two-way sync where users can ask the bot to modify JSON values and see the UI update live.

## Features

- **Natural Language JSON Editing**: Chat with AI to modify JSON configuration
- **Live Updates**: JSON state updates in real-time as you chat
- **Diff Tracking**: Visual diff display showing exactly what changed
- **Change History**: Complete audit log of all modifications
- **Two-Way Sync**: Changes made through chat immediately reflect in the UI
- **MCP Integration**: Uses Model Context Protocol for structured tool calling

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Streamlit UI  │────▶│   MCP Client    │────▶│  JSON MCP Server│
│   (Chat + JSON) │◀────│   (LangChain)   │◀────│    (Tools)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        ▲                                                 │
        │                                                 ▼
        └──────────────────────────────────────── state.json
```

## Installation

1. Install dependencies:
```bash
pip install streamlit langchain-openai python-dotenv deepdiff
```

2. Set up your OpenAI API key in `.env`:
```bash
OPENAI_API_KEY=your_api_key_here
```

## Usage

### Option 1: Using the run script
```bash
cd /home/ahmed/Projects/MCP/mcp-poc
./streamlit/run.sh
```

### Option 2: Direct Streamlit command
```bash
streamlit run streamlit/chat_json_app.py
```

The app will open at `http://localhost:8501`

## How It Works

1. **Chat Interface** (Left Panel):
   - Type natural language commands to modify the JSON
   - Examples: "Change the prompt name to 'New Analyzer'"
   - Quick action buttons for common operations

2. **JSON Display** (Right Panel):
   - Shows current JSON state with syntax highlighting
   - Updates automatically when changes are made
   - Download button to export current state

3. **Change History** (Bottom):
   - Shows diff of each change
   - Tracks timestamp and command for each modification
   - Visual indicators for added, removed, and modified fields

## Example Commands

### Update Values
- "Change the prompt name to 'New Analyzer'"
- "Set temperature to 0.5"
- "Update the model to gpt-4"

### Add Fields
- "Add a version field with value 2.0"
- "Add a new tag called 'production'"

### Delete Fields
- "Remove the FigmaReference"
- "Delete the Testing section"

### Rename Keys
- "Rename CreatedBy to Author"
- "Change Model key to ModelName"

### Complex Operations
- "Set temperature to 0.7 and change model to gpt-4"
- "Enable supervisory AI check and set evaluation criteria to strict"

## MCP Tools Available

The JSON MCP Server provides these tools:

1. **get_current_state**: Retrieve current JSON state
2. **update_value**: Modify a value at a specific path
3. **add_key**: Add new key-value pairs
4. **delete_key**: Remove keys from the JSON
5. **rename_key**: Rename existing keys
6. **update_multiple**: Batch updates for efficiency
7. **get_state_history**: View previous states

## JSON Path Notation

Use dot notation to specify paths in the JSON:
- `specs.Overview.description` - Access nested values
- `specs.LLMandOutputSettings.Temperature` - Deep nesting
- `specs.Testing.Enabled` - Boolean values
- `specs.PromptMetaDataTab.Tags[0]` - Array elements

## State Persistence

- JSON state is saved to `streamlit/current_state.json`
- State persists across sessions
- Diff history is maintained during the session
- Download option available for exporting state

## Technical Details

### Components

1. **streamlit/chat_json_app.py**: Main Streamlit application
2. **streamlit/json_mcp_server.py**: MCP server with JSON manipulation tools
3. **streamlit/current_state.json**: Persistent JSON state storage

### Dependencies

- **Streamlit**: Web UI framework
- **LangChain**: LLM orchestration
- **OpenAI**: Language model for understanding commands
- **DeepDiff**: JSON difference calculation
- **MCP**: Model Context Protocol for tool calling

## Customization

### Modify Initial JSON State

Edit the initial state in `chat_json_app.py`:
```python
st.session_state.json_state = {
    "your": "custom",
    "json": "structure"
}
```

### Change LLM Model

Update the model in the MCP client initialization:
```python
llm = ChatOpenAI(model="gpt-4", temperature=0)
```

### Add Custom Tools

Extend `json_mcp_server.py` with additional tools:
```python
@mcp.tool()
def your_custom_tool(param: str) -> Dict:
    # Your tool logic here
    pass
```

## Troubleshooting

1. **MCP not available**: Install with `pip install mcp-use`
2. **OpenAI API errors**: Check your API key in `.env`
3. **JSON parsing errors**: Ensure valid JSON structure
4. **State not persisting**: Check file permissions for `streamlit/current_state.json`

## Future Enhancements

- [ ] Undo/Redo functionality
- [ ] JSON schema validation
- [ ] Export diff history
- [ ] Multi-user collaboration
- [ ] JSON tree view with expand/collapse
- [ ] Real-time collaborative editing
- [ ] Integration with Pivotly Core for persistence

## License

This demo is part of the MCP POC project for Pivotly.
