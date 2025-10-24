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
from typing import Dict, Any
import nest_asyncio
from dotenv import load_dotenv

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_use import MCPAgent, MCPClient

# LLM imports
from langchain_openai import ChatOpenAI
# from langchain.schema import HumanMessage, SystemMessage, AIMessage  # Unused - using MCPAgent instead

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
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Courier New', monospace;
        font-size: 14px;
        max-height: 600px;
        overflow-y: auto;
        line-height: 1.6;
    }
    .json-key {
        color: #9cdcfe;
        font-weight: 500;
    }
    .json-string {
        color: #ce9178;
    }
    .json-number {
        color: #b5cea8;
    }
    .json-boolean {
        color: #569cd6;
    }
    .json-null {
        color: #569cd6;
        font-style: italic;
    }
    .chat-message {
        padding: 12px 16px;
        border-radius: 12px;
        margin-bottom: 12px;
        animation: fadeIn 0.3s ease-in;
        transition: all 0.2s ease;
    }
    .chat-message:hover {
        transform: translateY(-1px);
    }
    .user-message {
        background-color: #e8f0fe;
        color: #1a1a1a;
        margin-left: 20%;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
        border: 1px solid #c8d7e8;
    }
    .user-message .timestamp {
        text-align: right;
    }
    .user-message:hover {
        background-color: #dde7f3;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12);
    }
    .assistant-message {
        background-color: #f1f3f5;
        color: #1a1a1a;
        margin-right: 20%;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
        border: 1px solid #e1e4e8;
    }
    .assistant-message:hover {
        background-color: #e9ecef;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .timestamp {
        font-size: 0.75em;
        opacity: 0.7;
        margin-bottom: 6px;
        font-weight: 500;
    }
    .user-message .timestamp {
        color: #6c757d;
    }
    .assistant-message .timestamp {
        color: #6c757d;
    }
    .message-content {
        line-height: 1.5;
    }
    .thinking-dots {
        display: inline-block;
    }
    .thinking-dots::after {
        content: '...';
        animation: dots 1.5s steps(4, end) infinite;
    }
    @keyframes dots {
        0%, 20% { content: ''; }
        40% { content: '.'; }
        60% { content: '..'; }
        80%, 100% { content: '...'; }
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
                    except json.JSONDecodeError:
                        return {"result": content}
                return {"error": "No result returned"}
                
    except Exception as e:
        return {"error": f"MCP call failed: {str(e)}"}

async def process_with_llm_and_mcp(user_input: str) -> str:
    """Process user input with LLM and execute MCP operations"""
    llm = get_llm()
    
    client = MCPClient.from_config_file("mcp_config.json")
    agent = MCPAgent(
        llm=llm,
        client=client,
        max_steps=15,
        memory_enabled=True,
    )
    
    try:
        response = await agent.run(user_input)
    finally:
        # Ensure proper cleanup of the client
        try:
            # Close the client if it has a close method
            if hasattr(client, 'close'):
                await client.close()
            elif hasattr(client, 'cleanup'):
                await client.cleanup()
        except Exception:
            pass  # Ignore cleanup errors
    
    # IMPORTANT: Always reload the state from file after MCP operations
    # This ensures we get the latest state that the MCP server has written
    state_file = Path(__file__).parent / "state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                fresh_state = json.load(f)
                # Update session state with the fresh state from file
                st.session_state.json_state = fresh_state
        except (json.JSONDecodeError, IOError):
            # If file read fails, try to extract from response as fallback
            pass
    
    # Also try to extract JSON from the response as a secondary method
    # This is useful if the MCP server returns the state in the response
    try:
        # Look for JSON in the response
        import re
        json_pattern = r'\{[\s\S]*\}'
        json_matches = re.findall(json_pattern, response)
        
        if json_matches:
            # Try to parse the last JSON match (most likely the updated state)
            for json_match in reversed(json_matches):
                try:
                    potential_state = json.loads(json_match)
                    # Check if this looks like our state structure
                    if isinstance(potential_state, dict):
                        # Check if it has the expected structure (e.g., "specs" key or similar)
                        if any(key in potential_state for key in ["specs", "state", "data"]):
                            # Only update if we didn't already get it from file
                            if 'fresh_state' not in locals():
                                st.session_state.json_state = potential_state
                            break
                        elif "state" in potential_state and isinstance(potential_state["state"], dict):
                            if 'fresh_state' not in locals():
                                st.session_state.json_state = potential_state["state"]
                            break
                        elif "result" in potential_state and isinstance(potential_state["result"], dict):
                            if 'fresh_state' not in locals():
                                st.session_state.json_state = potential_state["result"]
                            break
                except json.JSONDecodeError:
                    continue
    except Exception:
        # If we can't extract JSON, just return the response as is
        pass
    
    return response
    
    
    
    
    

def format_json_with_highlighting(obj, indent=0):
    """Format JSON with HTML syntax highlighting"""
    html_parts = []
    spaces = "&nbsp;" * (indent * 2)
    
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        html_parts.append("{<br>")
        items = list(obj.items())
        for i, (key, value) in enumerate(items):
            next_spaces = "&nbsp;" * ((indent + 1) * 2)
            html_parts.append(f'{next_spaces}<span class="json-key">"{key}"</span>: ')
            html_parts.append(format_json_with_highlighting(value, indent + 1))
            if i < len(items) - 1:
                html_parts.append(",")
            html_parts.append("<br>")
        html_parts.append(f"{spaces}}}")
    elif isinstance(obj, list):
        if not obj:
            return "[]"
        html_parts.append("[<br>")
        for i, item in enumerate(obj):
            next_spaces = "&nbsp;" * ((indent + 1) * 2)
            html_parts.append(next_spaces)
            html_parts.append(format_json_with_highlighting(item, indent + 1))
            if i < len(obj) - 1:
                html_parts.append(",")
            html_parts.append("<br>")
        html_parts.append(f"{spaces}]")
    elif isinstance(obj, str):
        escaped = obj.replace('"', '\\"').replace('\n', '\\n')
        html_parts.append(f'<span class="json-string">"{escaped}"</span>')
    elif isinstance(obj, (int, float)):
        html_parts.append(f'<span class="json-number">{obj}</span>')
    elif isinstance(obj, bool):
        html_parts.append(f'<span class="json-boolean">{str(obj).lower()}</span>')
    elif obj is None:
        html_parts.append('<span class="json-null">null</span>')
    else:
        html_parts.append(str(obj))
    
    return "".join(html_parts)

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

# Initialize column ratio in session state if not present
if 'column_ratio' not in st.session_state:
    # Try to load saved layout preference
    layout_file = Path(__file__).parent / "layout_preference.json"
    if layout_file.exists():
        try:
            with open(layout_file, 'r') as f:
                saved_layout = json.load(f)
                st.session_state.column_ratio = saved_layout.get("column_ratio", 40)
        except (json.JSONDecodeError, IOError):
            st.session_state.column_ratio = 40  # Default: 40% for chat, 60% for JSON
    else:
        st.session_state.column_ratio = 40  # Default: 40% for chat, 60% for JSON

# Create two columns with adjustable ratio
col1_ratio = st.session_state.column_ratio
col2_ratio = 100 - col1_ratio
col1, col2 = st.columns([col1_ratio, col2_ratio])

# Left column: Chat Interface
with col1:
    st.subheader("💬 Chat Interface")
    
    # Chat container with native Streamlit chat messages
    chat_container = st.container(height=520)
    
    with chat_container:
        for message in st.session_state.messages:
            # Use Streamlit's native chat_message for proper markdown handling
            with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
                # Add timestamp
                if "timestamp" in message:
                    st.caption(f"{message['timestamp']}")
                # Display message content - Streamlit handles markdown properly
                st.markdown(message["content"])
        
        # Show typing indicator if processing
        if st.session_state.get('processing', False):
            with st.chat_message("assistant", avatar="🤖"):
                st.caption("Typing...")
                st.markdown("_Thinking..._")
    
    # Chat input
    user_input = st.chat_input("Type your command...")
    
    # Initialize processing state
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'pending_message' not in st.session_state:
        st.session_state.pending_message = None
    
    # Handle new user input
    if user_input and not st.session_state.processing:
        # Add user message immediately with timestamp
        st.session_state.messages.append({
            "role": "user", 
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        st.session_state.pending_message = user_input
        st.session_state.processing = True
        st.rerun()
    
    # Process pending message if exists
    if st.session_state.processing and st.session_state.pending_message:
        # Store previous state
        before_state = copy.deepcopy(st.session_state.json_state)
        
        # Process the message (the typing indicator is already shown above)
        response = asyncio.run(process_with_llm_and_mcp(st.session_state.pending_message))
        
        # Add assistant response with timestamp
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Log changes if state changed
        if st.session_state.json_state != before_state:
            diff_entry = {
                "timestamp": datetime.now().isoformat(),
                "command": st.session_state.pending_message,
                "before": before_state,
                "after": st.session_state.json_state
            }
            st.session_state.history.append(diff_entry)
        
        # Clear processing state
        st.session_state.processing = False
        st.session_state.pending_message = None
        st.rerun()

# Right column: JSON Display
with col2:
    tab1, tab2, tab3 = st.tabs(["📄 Current State", "📊 History", "🔧 Manual Edit"])
    
    with tab1:
        # st.subheader("📄 Current JSON State")
        
        # Always check for the latest state from file
        # This ensures we display the most current state
        state_file = Path(__file__).parent / "state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    file_state = json.load(f)
                    # Check if file state is different from session state
                    if file_state != st.session_state.json_state:
                        st.session_state.json_state = file_state
                        # Show a subtle indicator that state was refreshed
                        st.info("🔄 State refreshed from file", icon="ℹ️")
            except (json.JSONDecodeError, IOError):
                pass  # Keep using session state if file read fails
        
        # Ensure json_state is a dict, not a string
        if isinstance(st.session_state.json_state, str):
            try:
                st.session_state.json_state = json.loads(st.session_state.json_state)
            except json.JSONDecodeError:
                st.error("Invalid JSON in state")
        
        # Display JSON with proper formatting and syntax highlighting in a scrollable container
        json_container = st.container(height=520)
        with json_container:
            if isinstance(st.session_state.json_state, dict):
                # Use st.json for proper JSON display with collapsible sections
                st.json(st.session_state.json_state, expanded=True)
            else:
                # Fallback to text display
                json_str = json.dumps(st.session_state.json_state, indent=2)
                st.markdown(f'<div class="json-container"><pre>{json_str}</pre></div>', 
                           unsafe_allow_html=True)
        
        # Download button
        json_download_str = json.dumps(st.session_state.json_state, indent=2)
        st.download_button(
            label="📥 Download JSON",
            data=json_download_str,
            file_name=f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with tab2:
        st.subheader("📊 Change History")
        
        if st.session_state.history:
            # Add a control to show more/less history
            history_len = len(st.session_state.history)
            
            # Only show slider if there's more than 1 item in history
            if history_len > 1:
                history_count = st.slider(
                    "Number of changes to show:",
                    min_value=1,
                    max_value=min(10, history_len),
                    value=min(5, history_len),
                    key="history_slider"
                )
            else:
                # If only 1 item, just show it without a slider
                history_count = 1
                st.caption("📊 Showing 1 change")
            
            for i, entry in enumerate(reversed(st.session_state.history[-history_count:])):
                change_num = len(st.session_state.history) - i
                
                # Create an expander with better formatting
                with st.expander(
                    f"📝 Change #{change_num}: {entry['command'][:50]}{'...' if len(entry['command']) > 50 else ''}",
                    expanded=(i == 0)  # Expand the most recent change
                ):
                    # Display metadata
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.markdown("**🕐 Time:**")
                        st.text(entry['timestamp'])
                    with col2:
                        st.markdown("**💬 Command:**")
                        st.text(entry['command'])
                    
                    # Display the diff
                    st.markdown("**📊 Changes:**")
                    display_json_diff(entry['before'], entry['after'])
                    
                    # Option to revert to this state
                    if st.button("⏪ Revert to this state", key=f"revert_{change_num}"):
                        st.session_state.json_state = entry['after']
                        st.success(f"Reverted to state from change #{change_num}")
                        st.rerun()
        else:
            st.info("📭 No changes yet. Start chatting to modify the JSON!")
    
    with tab3:        
        # Create two columns for editor and preview
        edit_col1, edit_col2 = st.columns([1, 1])
        
        # Track the current editor session
        if 'editor_session_id' not in st.session_state:
            st.session_state.editor_session_id = 0
        
        with edit_col1:
            st.markdown("#### 🔧 Manual JSON Editor")
            
            # Initialize editor content and reset counter
            if 'editor_content' not in st.session_state:
                st.session_state.editor_content = json.dumps(st.session_state.json_state, indent=2)
            if 'editor_reset_counter' not in st.session_state:
                st.session_state.editor_reset_counter = 0
            
            # Sync editor content with json_state if json_state was updated externally
            # This ensures the editor always reflects the true state after chat operations
            if 'last_json_state_hash' not in st.session_state:
                st.session_state.last_json_state_hash = hash(json.dumps(st.session_state.json_state, sort_keys=True))
            
            current_hash = hash(json.dumps(st.session_state.json_state, sort_keys=True))
            if current_hash != st.session_state.last_json_state_hash:
                # JSON state changed externally (e.g., from chat), update editor
                st.session_state.editor_content = json.dumps(st.session_state.json_state, indent=2)
                st.session_state.last_json_state_hash = current_hash
                st.session_state.editor_reset_counter += 1
            
            # Use reset counter to force widget refresh
            editor_key_suffix = f"_{st.session_state.editor_reset_counter}"
            
            # Try to use ace editor if available, otherwise fallback to text area
            try:
                from streamlit_ace import st_ace
                edited_json = st_ace(
                    value=st.session_state.editor_content,
                    language='json',
                    theme='monokai',
                    key=f'json_ace_editor{editor_key_suffix}',
                    height=400,
                    font_size=14,
                    show_gutter=True,
                    show_print_margin=True,
                    wrap=False,
                    auto_update=True,  # Changed to True for immediate updates
                    annotations=None
                )
            except ImportError:
                # Fallback to standard text area with instructions
                st.info("💡 Tip: Install `streamlit-ace` for a better editing experience: `pip install streamlit-ace`")
                edited_json = st.text_area(
                    "Edit JSON directly:",
                    value=st.session_state.editor_content,
                    height=400,
                    key=f"json_editor{editor_key_suffix}",
                    help="Edit the JSON structure directly. Make sure to maintain valid JSON syntax."
                )
            
            # Always update editor content with the current value
            # This ensures we have the latest content from the editor
            st.session_state.editor_content = edited_json
            
            # Show save status message if exists
            if st.session_state.get('save_message'):
                st.success(st.session_state.save_message)
                # Clear the message after displaying
                del st.session_state.save_message
            
            # Validation and apply buttons
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
            
            with col_btn1:
                if st.button("✅ Apply Changes", type="primary"):
                    try:
                        # Use the current editor content from session state
                        # This ensures we have the latest typed content
                        current_content = st.session_state.editor_content
                        new_state = json.loads(current_content, strict=True)
                        
                        # Check if there are actual changes
                        old_state = st.session_state.json_state.copy()
                        
                        if old_state != new_state:
                            # Update the state
                            st.session_state.json_state = new_state
                            st.session_state.editor_content = json.dumps(new_state, indent=2)
                            st.session_state.last_json_state_hash = hash(json.dumps(new_state, sort_keys=True))
                            
                            # Save to file
                            state_file = Path(__file__).parent / "state.json"
                            with open(state_file, 'w') as f:
                                json.dump(new_state, f, indent=2)
                            
                            # Log the change to history
                            diff_entry = {
                                "timestamp": datetime.now().isoformat(),
                                "command": "Manual edit",
                                "before": old_state,
                                "after": new_state
                            }
                            st.session_state.history.append(diff_entry)
                            
                            # Mark that we just saved
                            st.session_state.just_saved = True
                            st.session_state.save_message = "✅ JSON saved successfully!"
                            
                            # Trigger a rerun to update the UI state
                            st.rerun()
                        else:
                            st.info("ℹ️ No changes to save")
                    except json.JSONDecodeError as e:
                        st.error(f"❌ Invalid JSON: {e}")
                        st.caption("Please fix the JSON syntax errors before applying changes.")
                    
            with col_btn2:
                if st.button("📐 Format JSON"):
                    try:
                        # Use current content from session state
                        current_content = st.session_state.editor_content
                        parsed = json.loads(current_content)
                        formatted = json.dumps(parsed, indent=2, sort_keys=False)
                        st.session_state.editor_content = formatted
                        st.session_state.editor_reset_counter += 1
                        st.success("✅ Formatted!")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("❌ Can't format invalid JSON")
            
            with col_btn3:
                if st.button("🔄 Reset"):
                    # Reset editor content to current saved state
                    st.session_state.editor_content = json.dumps(st.session_state.json_state, indent=2)
                    # Increment counter to force new widget key
                    st.session_state.editor_reset_counter += 1
                    st.rerun()
        
        with edit_col2:
            st.markdown("#### 👁️ Live Preview")
            
            # Show save status if just saved
            if st.session_state.get('just_saved', False):
                st.success("✅ Changes saved to file!")
                st.session_state.just_saved = False
            
            # Create a container for the preview
            preview_container = st.container()
            
            with preview_container:
                # Try to parse and display the edited JSON
                try:
                    # ALWAYS show what's currently in the editor
                    # Use the session state which has the latest content
                    preview_state = json.loads(st.session_state.editor_content)
                    
                    # Show status based on whether content matches saved state
                    if preview_state != st.session_state.json_state:
                        # There are unsaved changes
                        st.warning("⚠️ Unsaved changes")
                        st.caption("Click 'Apply Changes' to save these changes to file")
                    else:
                        # Content matches saved state
                        st.success("✅ In sync with saved file")
                        st.caption("Editor content matches the saved state")
                    
                    # Always display what's in the editor - this is the live preview
                    st.markdown("**Current editor content:**")
                    st.json(preview_state, expanded=True)
                    
                    # Show a diff if there are unsaved changes
                    if preview_state != st.session_state.json_state:
                        with st.expander("📊 What will change when you save", expanded=False):
                            st.markdown("**Differences from saved file:**")
                            display_json_diff(st.session_state.json_state, preview_state)
                
                except json.JSONDecodeError as e:
                    st.error("❌ Invalid JSON syntax - cannot preview")
                    st.code(str(e), language="text")
                    
                    # Show error location if possible
                    error_msg = str(e)
                    if "line" in error_msg.lower():
                        st.markdown("**Error location in editor:**")
                        lines = st.session_state.editor_content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if f"line {i}" in error_msg.lower():
                                st.code(f"Line {i}: {line}", language="json")
                                break

# Sidebar
with st.sidebar:
    new_ratio = 30
    
    # Update column ratio if changed
    if new_ratio != st.session_state.column_ratio:
        st.session_state.column_ratio = 30
        st.rerun()
    
    st.header("📚 Help & Examples")
    
    st.subheader("Example Commands:")
    examples = [
        "Show me the current state",
        "Update the Temperature.Metric.Value to 30",
        "Change the Country.ID to US",
        "Modify HasPercipitation to true",
        "Delete GeoPosition.Elevation.UnitType"
    ]
    
    for example in examples:
        if st.button(f"💡 {example}", key=f"ex_{example[:20]}"):
            # Add the example as a user message with timestamp
            st.session_state.messages.append({
                "role": "user", 
                "content": example,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            # Set up for processing
            st.session_state.pending_message = example
            st.session_state.processing = True
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
