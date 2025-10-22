#!/usr/bin/env python3
"""
Streamlit Chat UI with Proper MCP Agent Pattern
LLM reasons and calls tools automatically - no hardcoded tool mapping
Following the pattern from client.py
"""

import streamlit as st
import json
import asyncio
import os
from pathlib import Path
from datetime import datetime
import copy
from typing import Dict, Any, List, Optional
import nest_asyncio
from dotenv import load_dotenv
import re

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LLM imports
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage

# Apply nest_asyncio
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="JSON State Manager - MCP Agent",
    page_icon="🤖",
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
        line-height: 1.6;
        max-height: 600px;
        overflow-y: auto;
        white-space: pre;
    }
    .json-key {
        color: #9cdcfe;
        font-weight: 600;
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
    }
    .json-bracket {
        color: #ffd700;
        font-weight: bold;
    }
    .chat-message {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .user-message {
        background-color: #2b5ce6;
        color: white;
    }
    .assistant-message {
        background-color: #f0f0f0;
        color: #333;
    }
    .tool-call {
        background-color: #fff3cd;
        color: #856404;
        padding: 5px 10px;
        border-radius: 5px;
        margin: 5px 0;
        font-family: monospace;
        font-size: 12px;
    }
    .thinking {
        color: #6c757d;
        font-style: italic;
        padding: 5px;
    }
</style>
""", unsafe_allow_html=True)


def format_json_html(json_obj: dict, indent: int = 0) -> str:
    """Format JSON with HTML for syntax highlighting and proper indentation."""
    html_parts = []
    spaces = "  " * indent
    
    if isinstance(json_obj, dict):
        html_parts.append('<span class="json-bracket">{</span>\n')
        items = list(json_obj.items())
        for i, (key, value) in enumerate(items):
            html_parts.append(f'{spaces}  <span class="json-key">"{key}"</span>: ')
            if isinstance(value, dict):
                html_parts.append(format_json_html(value, indent + 1))
            elif isinstance(value, list):
                html_parts.append(format_json_list_html(value, indent + 1))
            elif isinstance(value, str):
                html_parts.append(f'<span class="json-string">"{value}"</span>')
            elif isinstance(value, (int, float)):
                html_parts.append(f'<span class="json-number">{value}</span>')
            elif isinstance(value, bool):
                html_parts.append(f'<span class="json-boolean">{str(value).lower()}</span>')
            elif value is None:
                html_parts.append('<span class="json-null">null</span>')
            else:
                html_parts.append(str(value))
            
            if i < len(items) - 1:
                html_parts.append(',')
            html_parts.append('\n')
        html_parts.append(f'{spaces}<span class="json-bracket">}}</span>')
    else:
        html_parts.append(str(json_obj))
    
    return ''.join(html_parts)


def format_json_list_html(json_list: list, indent: int = 0) -> str:
    """Format JSON list with HTML for syntax highlighting."""
    html_parts = []
    spaces = "  " * indent
    
    html_parts.append('<span class="json-bracket">[</span>')
    
    if json_list and all(not isinstance(item, (dict, list)) for item in json_list):
        # Simple list, display inline
        items_html = []
        for item in json_list:
            if isinstance(item, str):
                items_html.append(f'<span class="json-string">"{item}"</span>')
            elif isinstance(item, (int, float)):
                items_html.append(f'<span class="json-number">{item}</span>')
            elif isinstance(item, bool):
                items_html.append(f'<span class="json-boolean">{str(item).lower()}</span>')
            elif item is None:
                items_html.append('<span class="json-null">null</span>')
            else:
                items_html.append(str(item))
        html_parts.append(', '.join(items_html))
    else:
        # Complex list, display with line breaks
        html_parts.append('\n')
        for i, item in enumerate(json_list):
            html_parts.append(f'{spaces}  ')
            if isinstance(item, dict):
                html_parts.append(format_json_html(item, indent + 1))
            elif isinstance(item, list):
                html_parts.append(format_json_list_html(item, indent + 1))
            elif isinstance(item, str):
                html_parts.append(f'<span class="json-string">"{item}"</span>')
            elif isinstance(item, (int, float)):
                html_parts.append(f'<span class="json-number">{item}</span>')
            elif isinstance(item, bool):
                html_parts.append(f'<span class="json-boolean">{str(item).lower()}</span>')
            elif item is None:
                html_parts.append('<span class="json-null">null</span>')
            else:
                html_parts.append(str(item))
            
            if i < len(json_list) - 1:
                html_parts.append(',')
            html_parts.append('\n')
        html_parts.append(f'{spaces}')
    
    html_parts.append('<span class="json-bracket">]</span>')
    return ''.join(html_parts)


class MCPAgent:
    """MCP Agent that uses LLM to reason about and automatically call tools."""
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """Initialize the MCP agent with LLM."""
        self.tools_info = []
        self.llm = ChatOpenAI(
            model=llm_model,
            temperature=0.1,  # Very low temperature for consistent tool calling
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.conversation_history = []
        self.max_iterations = 5
        
    async def get_available_tools(self) -> List[Dict]:
        """Get available tools from MCP server."""
        server_params = StdioServerParameters(
            command="python3",
            args=[str(Path(__file__).parent / "json_state_server.py")]
        )
        
        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    
                    self.tools_info = []
                    for tool in tools_result.tools:
                        self.tools_info.append({
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                        })
                    
                    return self.tools_info
        except Exception as e:
            st.error(f"Failed to get tools: {e}")
            return []
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict = None) -> Dict:
        """Call an MCP tool directly."""
        server_params = StdioServerParameters(
            command="python3",
            args=[str(Path(__file__).parent / "json_state_server.py")]
        )
        
        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments or {})
                    
                    if result.content and len(result.content) > 0:
                        content = result.content[0].text
                        try:
                            return json.loads(content)
                        except:
                            return {"result": content}
                    return {"error": "No result"}
        except Exception as e:
            return {"error": f"Tool call failed: {str(e)}"}
    
    def create_tools_prompt(self) -> str:
        """Create a detailed prompt about available tools."""
        tools_desc = []
        for tool in self.tools_info:
            params = []
            if tool['parameters'] and 'properties' in tool['parameters']:
                for param, info in tool['parameters']['properties'].items():
                    params.append(f"{param}: {info.get('type', 'any')}")
            param_str = f"({', '.join(params)})" if params else "()"
            tools_desc.append(f"- {tool['name']}{param_str}: {tool['description']}")
        return "\n".join(tools_desc)
    
    def extract_tool_calls(self, text: str) -> List[Dict]:
        """Extract all tool calls from LLM response."""
        tool_calls = []
        
        # Pattern to match tool calls
        patterns = [
            r'<tool>(\w+)\((.*?)\)</tool>',
            r'```tool\n(\w+)\((.*?)\)\n```',
            r'Tool:\s*(\w+)\((.*?)\)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                tool_name = match.group(1)
                args_str = match.group(2).strip()
                
                # Parse arguments
                arguments = {}
                if args_str:
                    # Try to parse as key=value pairs
                    arg_pattern = r'(\w+)=(["\']?)([^,"\']*)\2'
                    for arg_match in re.finditer(arg_pattern, args_str):
                        key = arg_match.group(1)
                        value = arg_match.group(3)
                        # Try to parse JSON values
                        try:
                            value = json.loads(value)
                        except:
                            pass
                        arguments[key] = value
                
                tool_calls.append({
                    "name": tool_name,
                    "arguments": arguments
                })
        
        return tool_calls
    
    async def run(self, user_input: str) -> tuple[str, List[str]]:
        """Process user input with LLM reasoning and automatic tool calling."""
        tool_calls_made = []
        
        # Get available tools if not loaded
        if not self.tools_info:
            await self.get_available_tools()
        
        # Build conversation with tool information
        tools_desc = self.create_tools_prompt()
        
        system_prompt = f"""You are a helpful AI assistant that manages JSON state through natural language.

Available tools for JSON manipulation:
{tools_desc}

When the user asks to modify JSON, you should:
1. Understand what they want to change
2. Call the appropriate tool(s) using: <tool>tool_name(param=value)</tool>
3. Wait for results and explain what happened

Examples:
- To update a value: <tool>update_value(path="specs.Overview.description", value="New text")</tool>
- To add a key: <tool>add_key(parent_path="specs", key="Version", value="2.0")</tool>
- To delete: <tool>delete_key(path="specs.Settings.model")</tool>
- To get state: <tool>get_state()</tool>

Be conversational and helpful. Explain what you're doing."""
        
        # Add to conversation history
        self.conversation_history.append(HumanMessage(content=user_input))
        
        # Get LLM response
        messages = [SystemMessage(content=system_prompt)] + self.conversation_history[-10:]  # Keep last 10 messages
        
        response = self.llm.invoke(messages)
        response_text = response.content
        
        # Extract and execute tool calls
        tool_calls = self.extract_tool_calls(response_text)
        
        if tool_calls:
            # Execute each tool call
            results = []
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                arguments = tool_call["arguments"]
                
                tool_calls_made.append(f"{tool_name}({arguments})")
                
                # Execute tool
                result = await self.call_mcp_tool(tool_name, arguments)
                results.append(f"Result of {tool_name}: {json.dumps(result, indent=2)}")
            
            # If tools were called, get a follow-up response
            if results:
                follow_up = f"Tool execution results:\n" + "\n".join(results) + "\n\nPlease provide a user-friendly summary."
                messages.append(AIMessage(content=response_text))
                messages.append(HumanMessage(content=follow_up))
                
                final_response = self.llm.invoke(messages)
                response_text = final_response.content
        
        # Add to history
        self.conversation_history.append(AIMessage(content=response_text))
        
        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return response_text, tool_calls_made
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []


# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'agent' not in st.session_state:
    st.session_state.agent = MCPAgent()

if 'json_state' not in st.session_state:
    state_file = Path(__file__).parent / "state.json"
    if state_file.exists():
        with open(state_file, 'r') as f:
            st.session_state.json_state = json.load(f)
    else:
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

if 'tool_calls_history' not in st.session_state:
    st.session_state.tool_calls_history = []

# Main UI
st.title("🤖 JSON State Manager - Proper MCP Agent")
st.markdown("LLM reasons and calls tools automatically - just like client.py!")

# Two columns
col1, col2 = st.columns([1, 1])

# Left: Chat
with col1:
    st.subheader("💬 Natural Language Interface")
    
    # Chat display
    chat_container = st.container(height=500)
    
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-message user-message">👤 {msg["content"]}</div>', 
                          unsafe_allow_html=True)
            else:
                # Show thinking process if tool calls were made
                if "tool_calls" in msg and msg["tool_calls"]:
                    st.markdown('<div class="thinking">🤔 Agent used tools:</div>', unsafe_allow_html=True)
                    for tool_call in msg["tool_calls"]:
                        st.markdown(f'<div class="tool-call">🔧 {tool_call}</div>', 
                                  unsafe_allow_html=True)
                
                st.markdown(f'<div class="chat-message assistant-message">🤖 {msg["content"]}</div>', 
                          unsafe_allow_html=True)
    
    # Input
    user_input = st.chat_input("Tell me what to change in the JSON...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Process with agent
        with st.spinner("🧠 Agent is reasoning and may call tools..."):
            response, tool_calls = asyncio.run(st.session_state.agent.run(user_input))
            
            # Reload state from file
            state_file = Path(__file__).parent / "state.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    st.session_state.json_state = json.load(f)
        
        # Add response
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "tool_calls": tool_calls
        })
        
        if tool_calls:
            st.session_state.tool_calls_history.extend(tool_calls)
        
        st.rerun()

# Right: JSON State
with col2:
    st.subheader("📄 JSON State")
    
    # Tabs
    tab1, tab2 = st.tabs(["Current State", "Tool History"])
    
    with tab1:
        # Refresh button
        if st.button("🔄 Refresh"):
            state_file = Path(__file__).parent / "state.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    st.session_state.json_state = json.load(f)
            st.rerun()
        
        # Display JSON with proper formatting
        formatted_json = format_json_html(st.session_state.json_state)
        st.markdown(f'<div class="json-container"><pre>{formatted_json}</pre></div>', 
                   unsafe_allow_html=True)
        
        # Download (use plain JSON for download)
        json_str = json.dumps(st.session_state.json_state, indent=2)
        st.download_button(
            "📥 Download",
            data=json_str,
            file_name=f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with tab2:
        if st.session_state.tool_calls_history:
            st.write(f"**{len(st.session_state.tool_calls_history)} tool calls made**")
            for call in reversed(st.session_state.tool_calls_history[-10:]):
                st.code(call, language="python")
        else:
            st.info("No tools called yet")

# Sidebar
with st.sidebar:
    st.header("🎯 MCP Agent Info")
    
    st.info("""
    **How this works:**
    
    1. You type natural language
    2. LLM analyzes your request
    3. LLM decides which tools to use
    4. Tools modify the JSON state
    5. UI updates automatically
    
    **No hardcoded mappings!**
    The LLM reasons about everything.
    """)
    
    st.divider()
    
    # Get tools info
    if st.button("📦 Load Available Tools"):
        with st.spinner("Getting tools..."):
            tools = asyncio.run(st.session_state.agent.get_available_tools())
            if tools:
                st.success(f"Found {len(tools)} tools")
                for tool in tools:
                    st.write(f"• **{tool['name']}**")
    
    st.divider()
    
    # Controls
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.agent.clear_history()
        st.rerun()
    
    if st.button("🔄 Reset JSON"):
        default_state = {
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
        st.session_state.json_state = default_state
        state_file = Path(__file__).parent / "state.json"
        with open(state_file, 'w') as f:
            json.dump(default_state, f, indent=2)
        st.rerun()
    
    st.divider()
    
    st.subheader("💡 Try These")
    examples = [
        "Show the current state",
        "Change the description to 'AI Platform v2'",
        "Add a Version field with value 2.0",
        "Update temperature to 0.7",
        "Delete the model field",
        "Add a new Features array"
    ]
    
    for ex in examples:
        if st.button(f"→ {ex}", key=hash(ex)):
            st.session_state.messages.append({"role": "user", "content": ex})
            response, tool_calls = asyncio.run(st.session_state.agent.run(ex))
            
            state_file = Path(__file__).parent / "state.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    st.session_state.json_state = json.load(f)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "tool_calls": tool_calls
            })
            
            if tool_calls:
                st.session_state.tool_calls_history.extend(tool_calls)
            
            st.rerun()
