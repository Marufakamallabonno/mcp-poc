import streamlit as st
import json
import asyncio
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any, Optional
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepdiff import DeepDiff

# Try to import MCP components
try:
    from mcp_use import MCPAgent, MCPClient
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    st.warning("MCP components not available. Using mock mode.")

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="JSON State Chat Manager",
    page_icon="🔄",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stChat {
        height: 600px;
    }
    .json-container {
        background-color: #1e1e1e;
        border-radius: 10px;
        padding: 20px;
        font-family: 'Monaco', 'Courier New', monospace;
        color: #d4d4d4;
        height: 600px;
        overflow-y: auto;
    }
    .diff-container {
        background-color: #2d2d30;
        border-radius: 5px;
        padding: 10px;
        margin-top: 10px;
        font-family: 'Monaco', 'Courier New', monospace;
        font-size: 12px;
    }
    .diff-added {
        color: #4ec9b0;
        background-color: #003b00;
    }
    .diff-removed {
        color: #f48771;
        background-color: #3b0000;
    }
    .diff-modified {
        color: #dcdcaa;
        background-color: #3b3b00;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'json_state' not in st.session_state:
    # Load initial JSON
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
            "PromptConfigurationUISpecification": {
                "Tabs": ["MetaData", "Instructions", "APIandSecurity", "LLMandOutput", "Testing"]
            },
            "PromptMetaDataTab": {
                "PromptName": "Submittal Requirement Extractor",
                "PromptCode": "SUBMITTAL_EXTRACT_V1",
                "Tags": ["construction", "contract", "AI"],
                "CreatedBy": "Ahmed Rafi",
                "VersionNumber": "1.0"
            },
            "InstructionsPromptTemplateTab": {
                "PromptTemplateText": "Analyze the provided construction contract and extract all submittal requirements.",
                "Variables": [
                    {
                        "VariableName": "document_text",
                        "Description": "Full text of the contract document",
                        "Required": True
                    }
                ]
            },
            "APIandSecurity": {
                "APIExampleCall": "curl -X POST https://api.pivotly.ai/prompt/run -d '{\"prompt_id\":\"SUBMITTAL_EXTRACT_V1\",\"variables\":{\"document_text\":\"...\"}}'",
                "SystemAccess": "Authenticated API users",
                "ParticipationRules": "Admin and Project Engineers"
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
            },
            "MonitoringAndUsage": {
                "AuditLogging": True,
                "UsageMetrics": "Enabled",
                "QuotaLimit": "100 calls/day"
            },
            "Navigation": {
                "FigmaReference": "https://www.figma.com/design/wx4YMHcQFaxpSENQSMwQZD/Pivotly?node-id=142-94&p=f"
            },
            "Execution": {
                "description": "At runtime, variables are replaced and the final prompt is sent to the selected LLM for response."
            },
            "ExampleUseCase": {
                "client": "J.F. Brennan",
                "purpose": "Extract and manage submittal requirements from construction proposals."
            },
            "LaterRequirementsAndFeatures": {
                "SupervisoryAICheck": "Optional QA validation for AI responses.",
                "RAGQueries": "Enable retrieval from stored Pivotly documents."
            },
            "SupervisoryAICheck": {
                "Enabled": False,
                "EvaluationCriteria": "Keyword presence and semantic similarity",
                "FallbackAction": "RetryWithModifiedInput"
            },
            "RAGQueries": {
                "Enabled": True,
                "Query": "Find related project specifications for submittal validation."
            }
        }
    }

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'diff_history' not in st.session_state:
    st.session_state.diff_history = []

if 'mcp_client' not in st.session_state:
    st.session_state.mcp_client = None

if 'mcp_agent' not in st.session_state:
    st.session_state.mcp_agent = None

# Save initial state to file for MCP server
state_file = Path("streamlit/state.json")
with open(state_file, 'w') as f:
    json.dump(st.session_state.json_state, f, indent=2)

def format_diff(diff: Dict) -> str:
    """Format diff for display"""
    if not diff:
        return "No changes"
    
    formatted = []
    
    if 'values_changed' in diff:
        for path, change in diff['values_changed'].items():
            formatted.append(f"**Modified:** `{path}`")
            formatted.append(f"  - Old: `{change.get('old_value')}`")
            formatted.append(f"  - New: `{change.get('new_value')}`")
    
    if 'dictionary_item_added' in diff:
        for path in diff['dictionary_item_added']:
            formatted.append(f"**Added:** `{path}`")
    
    if 'dictionary_item_removed' in diff:
        for path in diff['dictionary_item_removed']:
            formatted.append(f"**Removed:** `{path}`")
    
    return "\n".join(formatted) if formatted else "No changes"

async def initialize_mcp():
    """Initialize MCP client and agent"""
    if st.session_state.mcp_client is None:
        # Create MCP config for our JSON server
        config = {
            "json_server": {
                "command": "python",
                "args": ["-m", "streamlit.json_mcp_server"],
                "cwd": "/home/ahmed/Projects/MCP/mcp-poc"
            }
        }
        
        # Save config
        config_file = Path("streamlit/mcp_config.json")
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Initialize client
        st.session_state.mcp_client = MCPClient.from_config_file(str(config_file))
        
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Create agent with custom system prompt
        system_prompt = """You are a JSON State Manager assistant. Your role is to help users modify a JSON configuration state through natural language commands.

When users ask to modify the JSON, use the appropriate MCP tools:
- update_value: To change an existing value
- add_key: To add a new key-value pair
- delete_key: To remove a key
- rename_key: To rename a key
- update_multiple: For multiple changes at once

Always:
1. Understand the user's intent clearly
2. Use dot notation for paths (e.g., "specs.Overview.description")
3. Preserve data types (strings, numbers, booleans, arrays, objects)
4. Confirm the changes made
5. Be concise in your responses

Examples:
- "Change the prompt name to 'New Analyzer'" → update_value("specs.PromptAsConfigurableObject.PromptName", "New Analyzer")
- "Add a new field called version with value 2.0" → add_key("specs", "version", "2.0")
- "Delete the FigmaReference" → delete_key("specs.Navigation.FigmaReference")
- "Rename CreatedBy to Author" → rename_key("specs.PromptMetaDataTab.CreatedBy", "Author")
"""
        
        st.session_state.mcp_agent = MCPAgent(
            llm=llm,
            client=st.session_state.mcp_client,
            system_prompt=system_prompt,
            max_steps=10
        )
        
        # Set initial state in MCP server
        await st.session_state.mcp_agent.run(
            f"Set the initial state to: {json.dumps(st.session_state.json_state)}"
        )

async def process_message(user_input: str) -> str:
    """Process user message through MCP agent"""
    try:
        # Get response from agent
        response = await st.session_state.mcp_agent.run(user_input)
        
        # Load updated state from file
        with open(state_file, 'r') as f:
            new_state = json.load(f)
        
        # Calculate diff
        diff = DeepDiff(st.session_state.json_state, new_state, verbose_level=2)
        
        if diff:
            # Update session state
            old_state = st.session_state.json_state.copy()
            st.session_state.json_state = new_state
            
            # Add to diff history
            st.session_state.diff_history.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "command": user_input,
                "diff": diff.to_dict() if diff else {},
                "old_state": old_state,
                "new_state": new_state
            })
        
        return response
        
    except Exception as e:
        return f"Error: {str(e)}"

# Main UI
st.title("🔄 JSON State Chat Manager")
st.markdown("Chat with AI to modify your JSON configuration in real-time")

# Create two columns
col1, col2 = st.columns([1, 1])

# Left column - Chat Interface
with col1:
    st.subheader("💬 Chat Interface")
    
    # Display chat messages
    chat_container = st.container(height=500)
    
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type a command (e.g., 'Change the prompt name to New Analyzer')"):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Process with MCP
        with st.spinner("Processing..."):
            # Initialize MCP if needed
            if st.session_state.mcp_agent is None:
                asyncio.run(initialize_mcp())
            
            # Get response
            response = asyncio.run(process_message(prompt))
            
            # Add assistant message
            st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Rerun to update UI
        st.rerun()
    
    # Example commands
    with st.expander("📝 Example Commands"):
        st.markdown("""
        - **Update value:** "Change the prompt name to 'New Analyzer'"
        - **Update multiple:** "Set temperature to 0.5 and max tokens to 2048"
        - **Add key:** "Add a new field called version with value 2.0"
        - **Delete key:** "Remove the FigmaReference field"
        - **Rename key:** "Rename CreatedBy to Author"
        - **Complex update:** "Change the model to gpt-4 and enable supervisory AI check"
        """)

# Right column - JSON Display
with col2:
    st.subheader("📋 JSON State")
    
    # JSON viewer
    json_container = st.container(height=500)
    with json_container:
        st.json(st.session_state.json_state, expanded=True)
    
    # Download JSON button
    json_str = json.dumps(st.session_state.json_state, indent=2)
    st.download_button(
        label="📥 Download JSON",
        data=json_str,
        file_name=f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )

# Diff History Section
st.markdown("---")
st.subheader("📊 Change History")

if st.session_state.diff_history:
    # Show latest changes
    latest_diff = st.session_state.diff_history[-1]
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**Latest Change:** {latest_diff['command']}")
        st.markdown(f"*Timestamp: {latest_diff['timestamp']}*")
    
    with col2:
        if st.button("🗑️ Clear History"):
            st.session_state.diff_history = []
            st.rerun()
    
    # Display formatted diff
    with st.expander("View Changes", expanded=True):
        st.markdown(format_diff(latest_diff['diff']))
    
    # Full history
    if len(st.session_state.diff_history) > 1:
        with st.expander(f"Full History ({len(st.session_state.diff_history)} changes)"):
            for i, diff in enumerate(reversed(st.session_state.diff_history[:-1]), 1):
                st.markdown(f"**{i}. {diff['command']}** - *{diff['timestamp']}*")
                st.markdown(format_diff(diff['diff']))
                st.markdown("---")
else:
    st.info("No changes yet. Start chatting to modify the JSON state!")

# Footer
st.markdown("---")
st.caption("Built with Streamlit, MCP, and OpenAI")
