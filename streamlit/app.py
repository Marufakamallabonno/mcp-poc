#!/usr/bin/env python3
"""
Streamlit Chat UI with Live JSON State Updates via MCP
"""

import streamlit as st
import json
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import copy
from typing import Dict, Any, Optional
import nest_asyncio
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / "server"))

from mcp_use import MCPAgent, MCPClient
from langchain_openai import ChatOpenAI

# Apply nest_asyncio to allow asyncio in Streamlit
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="JSON State Chat Manager",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .json-container {
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 20px;
        border-radius: 10px;
        font-family: 'Courier New', monospace;
        font-size: 14px;
        max-height: 600px;
        overflow-y: auto;
    }
    .chat-message {
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .user-message {
        background-color: #2b5ce6;
        color: white;
        text-align: right;
    }
    .assistant-message {
        background-color: #f0f0f0;
        color: #333;
    }
    .diff-added {
        background-color: #d4f4dd;
        color: #22863a;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .diff-removed {
        background-color: #ffeef0;
        color: #d73a49;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .diff-modified {
        background-color: #fff3cd;
        color: #856404;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'json_state' not in st.session_state:
    # Initialize with the provided example JSON
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
            "Invocation": {
                "DirectAPICall": "https://api.pivotly.ai/prompt/run",
                "PromptAsStepInPivotlyConnect": "Available under AI Tools → Prompt Step"
            },
            "PromptMetaDataTab": {
                "PromptName": "Submittal Requirement Extractor",
                "PromptCode": "SUBMITTAL_EXTRACT_V1",
                "Tags": ["construction", "contract", "AI"],
                "CreatedBy": "Ahmed Rafi",
                "VersionNumber": "1.0"
            }
        }
    }
    # Save initial state to file
    state_file = Path(__file__).parent / "state.json"
    with open(state_file, 'w') as f:
        json.dump(st.session_state.json_state, f, indent=2)

if 'history' not in st.session_state:
    st.session_state.history = []

if 'mcp_client' not in st.session_state:
    st.session_state.mcp_client = None

if 'mcp_agent' not in st.session_state:
    st.session_state.mcp_agent = None

# MCP Configuration file path
MCP_CONFIG_FILE = Path(__file__).parent / "mcp_config.json"

def create_mcp_config():
    """Create MCP configuration file for JSON state server"""
    config = {
        "mcpServers": {
            "json_state": {
                "command": "uv",
                "args": [
                    "run",
                    "--with",
                    "mcp[cli]",
                    "mcp",
                    "run",
                    str(Path(__file__).parent / "json_state_server.py")
                ]
            }
        }
    }
    
    with open(MCP_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    return MCP_CONFIG_FILE

async def initialize_mcp():
    """Initialize MCP client and agent"""
    try:
        # Create config if it doesn't exist
        if not MCP_CONFIG_FILE.exists():
            create_mcp_config()
        
        # Initialize MCP client
        client = MCPClient.from_config_file(str(MCP_CONFIG_FILE))
        
        # Initialize LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Create MCP agent with custom system prompt
        system_prompt = """You are a JSON State Manager assistant. Your role is to help users modify a JSON state object through natural language commands.

You have access to the following MCP tools:
- update_value: Update a value at a specific path (e.g., "specs.Overview.description")
- add_key: Add a new key to an object
- delete_key: Remove a key from the JSON
- rename_key: Rename an existing key
- get_state: Get the current JSON state
- get_history: View recent changes

When users ask to modify the JSON, interpret their intent and use the appropriate tool. Always be precise with paths using dot notation.

Examples:
- "Change the description to 'New description'" → Use update_value with the correct path
- "Add a new field called Version with value 2.0" → Use add_key
- "Remove the SecurityRules field" → Use delete_key
- "Rename PromptName to Name" → Use rename_key

After each operation, confirm what was changed. Be concise and helpful."""
        
        agent = MCPAgent(
            llm=llm,
            client=client,
            max_steps=10,
            memory_enabled=True,
            system_prompt=system_prompt
        )
        
        return client, agent
    except Exception as e:
        st.error(f"Failed to initialize MCP: {e}")
        return None, None

async def process_message(user_input: str):
    """Process user message through MCP agent"""
    try:
        # Initialize MCP if not already done
        if st.session_state.mcp_agent is None:
            with st.spinner("Initializing MCP connection..."):
                client, agent = await initialize_mcp()
                if agent:
                    st.session_state.mcp_client = client
                    st.session_state.mcp_agent = agent
                else:
                    return "Failed to initialize MCP. Please check your configuration."
        
        # Get response from agent
        response = await st.session_state.mcp_agent.run(user_input)
        
        # Load the updated state from file
        state_file = Path(__file__).parent / "state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                st.session_state.json_state = json.load(f)
        
        return response
    except Exception as e:
        return f"Error processing message: {str(e)}"

def display_json_diff(before: Dict, after: Dict):
    """Display the difference between two JSON states"""
    def flatten_dict(d: Dict, parent_key: str = '') -> Dict:
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    flat_before = flatten_dict(before)
    flat_after = flatten_dict(after)
    
    changes = []
    
    # Find added keys
    for key in flat_after:
        if key not in flat_before:
            changes.append(f'<span class="diff-added">+ {key}: {json.dumps(flat_after[key])}</span>')
    
    # Find removed keys
    for key in flat_before:
        if key not in flat_after:
            changes.append(f'<span class="diff-removed">- {key}: {json.dumps(flat_before[key])}</span>')
    
    # Find modified values
    for key in flat_before:
        if key in flat_after and flat_before[key] != flat_after[key]:
            changes.append(f'<span class="diff-modified">~ {key}: {json.dumps(flat_before[key])} → {json.dumps(flat_after[key])}</span>')
    
    if changes:
        st.markdown("**Changes:**", unsafe_allow_html=True)
        for change in changes:
            st.markdown(change, unsafe_allow_html=True)

# Main UI Layout
st.title("🔄 JSON State Chat Manager")
st.markdown("Chat with AI to modify your JSON state in real-time")

# Create two columns for chat and JSON display
col1, col2 = st.columns([1, 1])

# Left column: Chat Interface
with col1:
    st.subheader("💬 Chat Interface")
    
    # Chat container
    chat_container = st.container(height=500)
    
    with chat_container:
        # Display chat messages
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f'<div class="chat-message user-message">👤 {message["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-message assistant-message">🤖 {message["content"]}</div>', unsafe_allow_html=True)
    
    # Chat input
    user_input = st.chat_input("Type your command (e.g., 'Change the description to...')")
    
    if user_input:
        # Store the previous state for comparison
        before_state = copy.deepcopy(st.session_state.json_state)
        
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Process the message
        with st.spinner("Processing..."):
            response = asyncio.run(process_message(user_input))
        
        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Check if state changed and log the diff
        if st.session_state.json_state != before_state:
            diff_entry = {
                "timestamp": datetime.now().isoformat(),
                "command": user_input,
                "before": before_state,
                "after": st.session_state.json_state
            }
            st.session_state.history.append(diff_entry)
        
        # Rerun to update the UI
        st.rerun()

# Right column: JSON Display
with col2:
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["📄 Current State", "📊 History", "🔧 Manual Edit"])
    
    with tab1:
        st.subheader("📄 Current JSON State")
        
        # Display JSON with syntax highlighting
        json_str = json.dumps(st.session_state.json_state, indent=2)
        st.markdown(f'<div class="json-container"><pre>{json_str}</pre></div>', unsafe_allow_html=True)
        
        # Download button
        st.download_button(
            label="📥 Download JSON",
            data=json_str,
            file_name=f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with tab2:
        st.subheader("📊 Change History")
        
        if st.session_state.history:
            # Show recent changes
            for i, entry in enumerate(reversed(st.session_state.history[-5:])):
                with st.expander(f"Change {len(st.session_state.history) - i}: {entry['command'][:50]}..."):
                    st.text(f"Time: {entry['timestamp']}")
                    display_json_diff(entry['before'], entry['after'])
        else:
            st.info("No changes yet. Start chatting to modify the JSON!")
    
    with tab3:
        st.subheader("🔧 Manual JSON Editor")
        
        # Text area for manual editing
        edited_json = st.text_area(
            "Edit JSON directly:",
            value=json.dumps(st.session_state.json_state, indent=2),
            height=400
        )
        
        col3, col4 = st.columns(2)
        with col3:
            if st.button("✅ Apply Changes", use_container_width=True):
                try:
                    new_state = json.loads(edited_json)
                    before_state = copy.deepcopy(st.session_state.json_state)
                    st.session_state.json_state = new_state
                    
                    # Save to file
                    state_file = Path(__file__).parent / "state.json"
                    with open(state_file, 'w') as f:
                        json.dump(new_state, f, indent=2)
                    
                    # Log the change
                    diff_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "command": "Manual edit",
                        "before": before_state,
                        "after": new_state
                    }
                    st.session_state.history.append(diff_entry)
                    
                    st.success("JSON updated successfully!")
                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
        
        with col4:
            if st.button("🔄 Reset to Default", use_container_width=True):
                if st.session_state.mcp_agent:
                    # Reset through MCP
                    asyncio.run(process_message("Reset the JSON state to empty"))
                    st.rerun()

# Sidebar with examples and help
with st.sidebar:
    st.header("📚 Help & Examples")
    
    st.subheader("Example Commands:")
    examples = [
        "Change the description in Overview to 'New AI Platform'",
        "Add a new field called Version with value 2.0 to specs",
        "Update the temperature in LLMandOutputSettings to 0.7",
        "Delete the SecurityRules field from PromptAsConfigurableObject",
        "Rename the field PromptName to Name in PromptMetaDataTab",
        "Add a new object called Features with an array of features",
        "Change CreatedBy to 'John Doe'",
        "Update the model in LLMandOutputSettings to gpt-4-turbo"
    ]
    
    for example in examples:
        if st.button(f"💡 {example[:40]}...", key=f"ex_{example[:20]}", use_container_width=True):
            # Process the example command
            st.session_state.messages.append({"role": "user", "content": example})
            response = asyncio.run(process_message(example))
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    st.divider()
    
    st.subheader("🔧 Controls")
    
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        if st.session_state.mcp_agent:
            st.session_state.mcp_agent.clear_conversation_history()
        st.rerun()
    
    if st.button("🔄 Reset JSON to Default", use_container_width=True):
        # Reset to the original example JSON
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
        state_file = Path(__file__).parent / "state.json"
        with open(state_file, 'w') as f:
            json.dump(st.session_state.json_state, f, indent=2)
        st.rerun()
    
    st.divider()
    
    st.info("""
    **How it works:**
    1. Type natural language commands in the chat
    2. AI interprets and executes JSON operations via MCP
    3. The JSON state updates automatically
    4. All changes are logged with diffs
    """)

# Cleanup on app close
def cleanup():
    """Clean up MCP connections"""
    if st.session_state.mcp_client and st.session_state.mcp_client.sessions:
        asyncio.run(st.session_state.mcp_client.close_all_sessions())

# Footer
st.divider()
st.markdown("Built with Streamlit + MCP + OpenAI | Real-time JSON state management through natural language")
