#!/usr/bin/env python3
"""
Streamlit Chat UI with MCP JSON State Management
Following the pattern from client.py and expense_tracker.py
"""

import streamlit as st
import json
import asyncio
import os
from pathlib import Path
from datetime import datetime
import copy
from typing import Dict, Any, Optional
import nest_asyncio
from dotenv import load_dotenv

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LLM imports
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage

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

# Custom CSS
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
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'json_state' not in st.session_state:
    # Load initial state from file if exists
    state_file = Path(__file__).parent / "state.json"
    if state_file.exists():
        with open(state_file, 'r') as f:
            st.session_state.json_state = json.load(f)
    else:
        # Default initial state
        st.session_state.json_state = {
            "specs": {
                "Overview": {
                    "description": "Pivotly Prompt enables structured use of generative AI"
                },
                "Settings": {
                    "temperature": 0.3,
                    "model": "gpt-4"
                }
            }
        }

if 'history' not in st.session_state:
    st.session_state.history = []

# Initialize LLM
@st.cache_resource
def get_llm():
    """Initialize the LLM"""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call an MCP tool through the server"""
    # Define server parameters for our JSON state server
    server_params = StdioServerParameters(
        command="python3",
        args=[str(Path(__file__).parent / "json_state_server.py")]
    )
    
    try:
        # Connect to the server
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the connection
                await session.initialize()
                
                # Call the tool
                result = await session.call_tool(tool_name, arguments=arguments)
                
                # Parse the result
                if result.content and len(result.content) > 0:
                    # Get the text content from the result
                    content = result.content[0].text
                    # Try to parse as JSON if possible
                    try:
                        return json.loads(content)
                    except:
                        return {"result": content}
                return {"error": "No result returned"}
                
    except Exception as e:
        return {"error": f"MCP call failed: {str(e)}"}

async def process_with_llm_and_mcp(user_input: str) -> str:
    """Process user input with LLM and execute MCP operations"""
    llm = get_llm()
    
    # Create system prompt with current state context
    current_state_context = json.dumps(st.session_state.json_state, indent=2)[:500]
    
    system_prompt = f"""You are a JSON State Manager assistant. You help users modify a JSON state through natural language.

When users ask to modify JSON, interpret their intent and provide a structured response with the operation to perform.

Available operations:
1. update_value: Update a value at a path (e.g., "specs.Overview.description")
2. add_key: Add a new key to an object
3. delete_key: Remove a key
4. rename_key: Rename an existing key
5. get_state: Get current state

Respond with a JSON object containing:
- operation: the operation to perform
- parameters: the parameters for the operation

Examples:
User: "Change the description to 'New description'"
Response: {{"operation": "update_value", "parameters": {{"path": "specs.Overview.description", "value": "New description"}}}}

User: "Add a Version field with value 2.0"
Response: {{"operation": "add_key", "parameters": {{"parent_path": "specs", "key": "Version", "value": "2.0"}}}}

User: "Delete the SecurityRules field"
Response: {{"operation": "delete_key", "parameters": {{"path": "specs.PromptAsConfigurableObject.SecurityRules"}}}}

User: "Show me the current state"
Response: {{"operation": "get_state", "parameters": {{}}}}

Current JSON structure context:
{current_state_context}

Always respond with valid JSON containing operation and parameters."""
    
    # Get LLM response
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ]
    
    try:
        llm_response = llm.invoke(messages)
        response_text = llm_response.content
        
        # Try to parse the LLM response as JSON
        try:
            operation_data = json.loads(response_text)
            operation = operation_data.get("operation")
            parameters = operation_data.get("parameters", {})
            
            # Execute the MCP operation
            if operation == "update_value":
                result = await call_mcp_tool("update_value", parameters)
            elif operation == "add_key":
                result = await call_mcp_tool("add_key", parameters)
            elif operation == "delete_key":
                result = await call_mcp_tool("delete_key", parameters)
            elif operation == "rename_key":
                result = await call_mcp_tool("rename_key", parameters)
            elif operation == "get_state":
                result = await call_mcp_tool("get_state", {})
            else:
                return f"Unknown operation: {operation}"
            
            # Update local state if successful
            if result.get("success") and "state" in result:
                st.session_state.json_state = result["state"]
                
                # Format success message
                if operation == "update_value":
                    return f"✅ Updated value at {parameters.get('path')}"
                elif operation == "add_key":
                    return f"✅ Added key '{parameters.get('key')}' to {parameters.get('parent_path', 'root')}"
                elif operation == "delete_key":
                    return f"✅ Deleted key at {parameters.get('path')}"
                elif operation == "rename_key":
                    return f"✅ Renamed key to '{parameters.get('new_name')}'"
                else:
                    return "✅ Operation completed successfully"
            else:
                return f"Operation failed: {result.get('error', 'Unknown error')}"
                
        except json.JSONDecodeError:
            # If LLM didn't return valid JSON, try to help the user
            return f"I understand you want to modify the JSON, but I couldn't parse the specific operation. Please be more specific about what field you want to change."
            
    except Exception as e:
        return f"Error processing request: {str(e)}"

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
    
    # Find changes
    for key in flat_after:
        if key not in flat_before:
            changes.append(f'<span class="diff-added">+ {key}: {json.dumps(flat_after[key])}</span>')
    
    for key in flat_before:
        if key not in flat_after:
            changes.append(f'<span class="diff-removed">- {key}: {json.dumps(flat_before[key])}</span>')
    
    for key in flat_before:
        if key in flat_after and flat_before[key] != flat_after[key]:
            changes.append(f'<span class="diff-modified">~ {key}: {json.dumps(flat_before[key])} → {json.dumps(flat_after[key])}</span>')
    
    if changes:
        st.markdown("**Changes:**", unsafe_allow_html=True)
        for change in changes:
            st.markdown(change, unsafe_allow_html=True)

# Main UI
st.title("🔄 JSON State Chat Manager")
st.markdown("Chat with AI to modify your JSON state in real-time using MCP")

# Create two columns
col1, col2 = st.columns([1, 1])

# Left column: Chat Interface
with col1:
    st.subheader("💬 Chat Interface")
    
    # Chat container
    chat_container = st.container(height=500)
    
    with chat_container:
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f'<div class="chat-message user-message">👤 {message["content"]}</div>', 
                          unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-message assistant-message">🤖 {message["content"]}</div>', 
                          unsafe_allow_html=True)
    
    # Chat input
    user_input = st.chat_input("Type your command (e.g., 'Change the description to...')")
    
    if user_input:
        # Store previous state
        before_state = copy.deepcopy(st.session_state.json_state)
        
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Process with LLM and MCP
        with st.spinner("Processing..."):
            response = asyncio.run(process_with_llm_and_mcp(user_input))
        
        # Add assistant response
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Log changes if state changed
        if st.session_state.json_state != before_state:
            diff_entry = {
                "timestamp": datetime.now().isoformat(),
                "command": user_input,
                "before": before_state,
                "after": st.session_state.json_state
            }
            st.session_state.history.append(diff_entry)
        
        st.rerun()

# Right column: JSON Display
with col2:
    tab1, tab2, tab3 = st.tabs(["📄 Current State", "📊 History", "🔧 Manual Edit"])
    
    with tab1:
        st.subheader("📄 Current JSON State")
        
        # Display JSON
        json_str = json.dumps(st.session_state.json_state, indent=2)
        st.markdown(f'<div class="json-container"><pre>{json_str}</pre></div>', 
                   unsafe_allow_html=True)
        
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
            for i, entry in enumerate(reversed(st.session_state.history[-5:])):
                with st.expander(f"Change {len(st.session_state.history) - i}: {entry['command'][:50]}..."):
                    st.text(f"Time: {entry['timestamp']}")
                    display_json_diff(entry['before'], entry['after'])
        else:
            st.info("No changes yet. Start chatting to modify the JSON!")
    
    with tab3:
        st.subheader("🔧 Manual JSON Editor")
        
        edited_json = st.text_area(
            "Edit JSON directly:",
            value=json.dumps(st.session_state.json_state, indent=2),
            height=400
        )
        
        if st.button("✅ Apply Changes"):
            try:
                new_state = json.loads(edited_json)
                st.session_state.json_state = new_state
                
                # Save to file
                state_file = Path(__file__).parent / "state.json"
                with open(state_file, 'w') as f:
                    json.dump(new_state, f, indent=2)
                
                st.success("JSON updated successfully!")
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

# Sidebar
with st.sidebar:
    st.header("📚 Help & Examples")
    
    st.subheader("Example Commands:")
    examples = [
        "Change the description to 'New AI Platform'",
        "Add a Version field with value 2.0 to specs",
        "Update the temperature to 0.7",
        "Delete the model field",
        "Show me the current state"
    ]
    
    for example in examples:
        if st.button(f"💡 {example}", key=f"ex_{example[:20]}"):
            st.session_state.messages.append({"role": "user", "content": example})
            response = asyncio.run(process_with_llm_and_mcp(example))
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    st.divider()
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🔄 Reset JSON to Default"):
        st.session_state.json_state = {
            "specs": {
                "Overview": {
                    "description": "Pivotly Prompt enables structured use of generative AI"
                },
                "Settings": {
                    "temperature": 0.3,
                    "model": "gpt-4"
                }
            }
        }
        state_file = Path(__file__).parent / "state.json"
        with open(state_file, 'w') as f:
            json.dump(st.session_state.json_state, f, indent=2)
        st.rerun()
