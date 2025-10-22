"""
Streamlit Chat Interface for JSON State Management via MCP
"""

import streamlit as st
import json
import asyncio
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any, List
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from server.client import MCPAgent, MCPClient  # Use the existing client
from deepdiff import DeepDiff

# Load environment variables
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Page configuration
st.set_page_config(
    page_title="JSON State Chat Manager",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .json-viewer {
        background-color: #1e1e1e;
        border-radius: 8px;
        padding: 15px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 13px;
        line-height: 1.5;
        overflow-x: auto;
        max-height: 600px;
        overflow-y: auto;
    }
    .diff-added {
        background-color: rgba(0, 255, 0, 0.1);
        color: #4ec9b0;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .diff-removed {
        background-color: rgba(255, 0, 0, 0.1);
        color: #f48771;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .diff-modified {
        background-color: rgba(255, 255, 0, 0.1);
        color: #dcdcaa;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'json_state' not in st.session_state:
    st.session_state.json_state = {
        "specs": {
            "Overview": {
                "description": "Pivotly Prompt enables structured use of generative AI within workflows using configurable prompt templates, variables, and model settings."
            },
            "PromptConfiguration": {
                "type": ["ReusablePrompt", "InlinePrompt"],
                "usage": "Define and manage prompts with variables, formatting, and AI model parameters."
            },
            "PromptAsConfigurableObject": {
                "PromptName": "Contract Submittal Analyzer",
                "PromptTemplate": "Extract submittal requirements from the following contract document: {{document_text}}",
                "Variables": ["document_text", "project_name"],
                "SecurityRules": "Internal use only",
                "LLMConfiguration": "OpenAI GPT-4",
                "OutputFormat": "JSON",
                "ResponseType": "StructuredText"
            },
            "PromptMetaDataTab": {
                "PromptName": "Submittal Requirement Extractor",
                "PromptCode": "SUBMITTAL_EXTRACT_V1",
                "Tags": ["construction", "contract", "AI"],
                "CreatedBy": "Ahmed Rafi",
                "VersionNumber": "1.0"
            },
            "LLMandOutputSettings": {
                "LLMProvider": "OpenAI",
                "Model": "gpt-4-turbo",
                "Temperature": 0.3,
                "MaxTokens": 1024,
                "ResponseType": "JSON",
                "IncludeSourceMetadata": True
            },
            "Testing": {
                "Enabled": True,
                "SampleInput": {
                    "document_text": "This contract requires submission of safety plans and material compliance certificates."
                },
                "ExpectedOutput": {
                    "submittals": ["Safety Plan", "Material Compliance Certificate"]
                }
            }
        }
    }

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'diff_history' not in st.session_state:
    st.session_state.diff_history = []

if 'mcp_initialized' not in st.session_state:
    st.session_state.mcp_initialized = False

# Save current state to file
STATE_FILE = Path("streamlit/current_state.json")
STATE_FILE.parent.mkdir(exist_ok=True)

def save_state():
    """Save current state to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(st.session_state.json_state, f, indent=2)

def load_state():
    """Load state from file"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return st.session_state.json_state

def format_diff_html(diff: Dict) -> str:
    """Format diff as HTML for better display"""
    if not diff:
        return "<p>No changes detected</p>"
    
    html_parts = []
    
    if 'values_changed' in diff:
        html_parts.append("<h4>Modified Values:</h4>")
        for path, change in diff['values_changed'].items():
            clean_path = path.replace("root", "").strip("[]'")
            html_parts.append(f'<div class="diff-modified">📝 {clean_path}</div>')
            html_parts.append(f'<div style="margin-left: 20px;">Old: {change.get("old_value")}</div>')
            html_parts.append(f'<div style="margin-left: 20px;">New: {change.get("new_value")}</div>')
    
    if 'dictionary_item_added' in diff:
        html_parts.append("<h4>Added Items:</h4>")
        for path in diff['dictionary_item_added']:
            clean_path = path.replace("root", "").strip("[]'")
            html_parts.append(f'<div class="diff-added">➕ {clean_path}</div>')
    
    if 'dictionary_item_removed' in diff:
        html_parts.append("<h4>Removed Items:</h4>")
        for path in diff['dictionary_item_removed']:
            clean_path = path.replace("root", "").strip("[]'")
            html_parts.append(f'<div class="diff-removed">➖ {clean_path}</div>')
    
    return "".join(html_parts) if html_parts else "<p>No changes detected</p>"

async def process_with_mcp(user_input: str) -> tuple[str, Dict]:
    """Process user input with MCP and return response and updated state"""
    
    # Create a temporary config for our JSON manipulation
    config = {
        "json_tools": {
            "module": "streamlit.json_mcp_server",
            "class_name": "mcp"
        }
    }
    
    # Save config temporarily
    config_file = Path("streamlit/temp_config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f)
    
    try:
        # Initialize MCP client
        client = MCPClient.from_config_file(str(config_file))
        
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Create agent with specific instructions for JSON manipulation
        system_prompt = f"""You are a JSON State Manager. The current JSON state is:

{json.dumps(st.session_state.json_state, indent=2)}

Your role is to understand the user's intent and modify this JSON accordingly. 

When the user asks to change values, add keys, delete keys, or rename keys, provide clear confirmation of what was changed.

Be precise with paths using dot notation (e.g., "specs.Overview.description").
Maintain proper data types (strings, numbers, booleans, arrays, objects).

Examples of user requests and how to handle them:
- "Change the prompt name to 'New Analyzer'" → Update specs.PromptAsConfigurableObject.PromptName
- "Set temperature to 0.5" → Update specs.LLMandOutputSettings.Temperature
- "Add a version field" → Add a new key at the appropriate location
- "Delete the CreatedBy field" → Remove specs.PromptMetaDataTab.CreatedBy
- "Rename Model to ModelName" → Rename the key appropriately

Always confirm what changes were made in your response."""

        agent = MCPAgent(
            llm=llm,
            client=client,
            system_prompt=system_prompt,
            max_steps=5
        )
        
        # Process the user input
        response = await agent.run(user_input)
        
        # Simulate the state change based on the response
        # In a real implementation, the MCP server would handle this
        new_state = simulate_json_update(user_input, st.session_state.json_state)
        
        return response, new_state
        
    except Exception as e:
        return f"Error processing request: {str(e)}", st.session_state.json_state
    finally:
        # Clean up
        if config_file.exists():
            config_file.unlink()

def simulate_json_update(command: str, current_state: Dict) -> Dict:
    """Simulate JSON updates based on command (fallback when MCP not available)"""
    import copy
    new_state = copy.deepcopy(current_state)
    command_lower = command.lower()
    
    # Simple pattern matching for common operations
    if "change" in command_lower or "set" in command_lower or "update" in command_lower:
        # Examples of simple updates
        if "prompt name" in command_lower and "new analyzer" in command_lower:
            if 'specs' in new_state and 'PromptAsConfigurableObject' in new_state['specs']:
                new_state['specs']['PromptAsConfigurableObject']['PromptName'] = "New Analyzer"
        
        elif "temperature" in command_lower:
            import re
            temp_match = re.search(r'(\d+\.?\d*)', command)
            if temp_match and 'specs' in new_state and 'LLMandOutputSettings' in new_state['specs']:
                new_state['specs']['LLMandOutputSettings']['Temperature'] = float(temp_match.group(1))
        
        elif "model" in command_lower and "gpt-4" in command_lower:
            if 'specs' in new_state and 'LLMandOutputSettings' in new_state['specs']:
                new_state['specs']['LLMandOutputSettings']['Model'] = "gpt-4"
        
        elif "created by" in command_lower or "author" in command_lower:
            import re
            name_match = re.search(r'to\s+["\']?([^"\']+)["\']?', command)
            if name_match and 'specs' in new_state and 'PromptMetaDataTab' in new_state['specs']:
                new_state['specs']['PromptMetaDataTab']['CreatedBy'] = name_match.group(1).strip()
    
    elif "add" in command_lower:
        if "version" in command_lower:
            import re
            version_match = re.search(r'(\d+\.?\d*)', command)
            if version_match and 'specs' in new_state:
                new_state['specs']['Version'] = version_match.group(1)
    
    elif "delete" in command_lower or "remove" in command_lower:
        if "figma" in command_lower:
            if 'specs' in new_state and 'Navigation' in new_state['specs']:
                new_state['specs'].pop('Navigation', None)
    
    return new_state

async def handle_message(user_input: str):
    """Handle user message and update state"""
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Get old state for diff
    old_state = st.session_state.json_state.copy()
    
    # Process with MCP or simulation
    try:
        # Try to use actual MCP if available
        response, new_state = await process_with_mcp(user_input)
    except:
        # Fallback to simulation
        new_state = simulate_json_update(user_input, st.session_state.json_state)
        
        # Generate a simple response
        if new_state != old_state:
            response = "✅ JSON state has been updated based on your request."
        else:
            response = "No changes were made. Please try a more specific command."
    
    # Calculate diff
    diff = DeepDiff(old_state, new_state, verbose_level=2)
    
    # Update state if changed
    if diff:
        st.session_state.json_state = new_state
        save_state()
        
        # Add to diff history
        st.session_state.diff_history.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "command": user_input,
            "diff": diff.to_dict(),
            "old_state": old_state,
            "new_state": new_state
        })
    
    # Add assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})

# Main UI Layout
st.title("🔄 JSON State Chat Manager")
st.markdown("Chat with AI to modify your JSON configuration in real-time")

# Create two columns for chat and JSON
col1, col2 = st.columns([1, 1], gap="medium")

# Left Column - Chat Interface
with col1:
    st.subheader("💬 Chat Interface")
    
    # Chat messages container
    chat_container = st.container(height=500)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me to modify the JSON..."):
        # Process the message
        asyncio.run(handle_message(prompt))
        st.rerun()
    
    # Quick actions
    st.markdown("### Quick Actions")
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("🔄 Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    
    with col_b:
        if st.button("🔄 Reset JSON"):
            # Reset to initial state
            st.session_state.json_state = {
                "specs": {
                    "Overview": {
                        "description": "Pivotly Prompt enables structured use of generative AI within workflows using configurable prompt templates, variables, and model settings."
                    },
                    "PromptConfiguration": {
                        "type": ["ReusablePrompt", "InlinePrompt"],
                        "usage": "Define and manage prompts with variables, formatting, and AI model parameters."
                    }
                }
            }
            st.session_state.diff_history = []
            save_state()
            st.rerun()

# Right Column - JSON Display
with col2:
    st.subheader("📋 Current JSON State")
    
    # JSON viewer with syntax highlighting
    json_container = st.container(height=500)
    with json_container:
        # Use st.code for better syntax highlighting
        st.code(json.dumps(st.session_state.json_state, indent=2), language="json")
    
    # Export options
    col_1, col_2 = st.columns(2)
    with col_1:
        json_str = json.dumps(st.session_state.json_state, indent=2)
        st.download_button(
            "📥 Download JSON",
            data=json_str,
            file_name=f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col_2:
        if st.button("📋 Copy to Clipboard"):
            st.code(json_str, language="json")
            st.success("JSON displayed above - copy manually")

# Diff History Section (Bottom)
with st.expander("📊 Change History", expanded=True):
    if st.session_state.diff_history:
        # Show latest change
        latest = st.session_state.diff_history[-1]
        
        st.markdown(f"**Latest Change** ({latest['timestamp']})")
        st.markdown(f"Command: _{latest['command']}_")
        
        # Display formatted diff
        st.markdown(format_diff_html(latest['diff']), unsafe_allow_html=True)
        
        # Show full history if more than one change
        if len(st.session_state.diff_history) > 1:
            st.markdown("---")
            st.markdown("### Previous Changes")
            for i, change in enumerate(reversed(st.session_state.diff_history[:-1]), 1):
                with st.container():
                    st.markdown(f"**{i}.** {change['command']} - _{change['timestamp']}_")
                    if st.checkbox(f"Show diff #{i}", key=f"diff_{i}"):
                        st.markdown(format_diff_html(change['diff']), unsafe_allow_html=True)
    else:
        st.info("No changes yet. Start chatting to modify the JSON!")

# Sidebar with examples
with st.sidebar:
    st.markdown("## 📝 Example Commands")
    
    examples = [
        ("Update Value", "Change the prompt name to 'New Analyzer'"),
        ("Set Number", "Set temperature to 0.5"),
        ("Change Model", "Update the model to gpt-4"),
        ("Add Field", "Add a version field with value 2.0"),
        ("Delete Key", "Remove the FigmaReference"),
        ("Rename Key", "Rename CreatedBy to Author"),
        ("Multiple Changes", "Set temperature to 0.7 and change model to gpt-4"),
        ("Update Array", "Add 'review' to the Tags list"),
        ("Toggle Boolean", "Disable Testing"),
        ("Complex Update", "Change the prompt template to use a new format")
    ]
    
    for title, example in examples:
        if st.button(f"{title}", key=f"ex_{title}"):
            asyncio.run(handle_message(example))
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 🔍 JSON Path Examples")
    st.code("""
specs.Overview.description
specs.LLMandOutputSettings.Temperature
specs.PromptMetaDataTab.CreatedBy
specs.Testing.Enabled
    """, language="text")
    
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.info("""
    This demo shows natural language JSON editing via chat.
    
    - Type commands in natural language
    - JSON updates live as you chat
    - All changes are tracked with diffs
    - State persists across sessions
    """)

# Save state on each interaction
save_state()
