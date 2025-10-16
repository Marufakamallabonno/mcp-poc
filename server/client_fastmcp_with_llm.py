import asyncio
import json
from fastmcp import Client
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain.tools import Tool
from typing import Dict, List, Any, Optional
import re

# Load environment variables
load_dotenv()

# FastMCP Cloud servers
REMOTE_SERVERS = {
    "weather": "https://mcp-poc-multi-tool.fastmcp.app/mcp",
    "rag": "https://mcp-poc-rag.fastmcp.app/mcp",
    "expense_tracker": "https://expense-tracker-by-niloy.fastmcp.app/mcp"
}

class FastMCPAgentWithLLM:
    """Agent that uses LLM to reason about and call FastMCP cloud tools."""
    
    def __init__(self, servers: Dict[str, str], llm_model: str = "gpt-4o-mini"):
        """Initialize the agent with FastMCP servers and LLM."""
        self.servers = servers
        self.clients = {}
        self.tools_info = {}
        # Lower temperature for more consistent tool calling
        self.llm = ChatOpenAI(model=llm_model, temperature=0.1)
        self.conversation_history = []
        self.debug = False  # Set to True to see LLM responses
        
    async def connect_all_servers(self):
        """Connect to all available FastMCP cloud servers."""
        print("🔌 Connecting to FastMCP cloud servers...")
        
        for name, url in self.servers.items():
            try:
                client = Client(url)
                self.clients[name] = client
                
                # Get tools info for this server
                async with client:
                    tools = await client.list_tools()
                    self.tools_info[name] = []
                    
                    for tool in tools:
                        # According to FastMCP docs, tools have name, description, and inputSchema
                        tool_info = {
                            "server": name,
                            "name": tool.name,
                            "description": tool.description if hasattr(tool, 'description') else "",
                            "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                        }
                        self.tools_info[name].append(tool_info)
                    
                    print(f"✅ Connected to {name}: {len(tools)} tools available")
                    
                    # List the actual tools found
                    for tool in tools[:5]:  # Show first 5 tools
                        print(f"   - {tool.name}")
                    
            except Exception as e:
                print(f"❌ Failed to connect to {name}: {e}")
        
        if not self.clients:
            raise Exception("No servers could be connected!")
    
    def create_tools_prompt(self) -> str:
        """Create a detailed prompt about available tools."""
        tools_list = []
        
        for server_name, tools in self.tools_info.items():
            for tool in tools:
                # Build parameter description
                params_desc = []
                if tool['parameters'] and 'properties' in tool['parameters']:
                    required = tool['parameters'].get('required', [])
                    for param_name, param_info in tool['parameters']['properties'].items():
                        param_type = param_info.get('type', 'any')
                        is_required = param_name in required
                        params_desc.append(f"{param_name}: {param_type}{'*' if is_required else ''}")
                
                param_str = f"({', '.join(params_desc)})" if params_desc else "()"
                tools_list.append(f"{server_name}.{tool['name']}{param_str} - {tool['description']}")
        
        return "\n".join(tools_list)
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict = None) -> Any:
        """Call a specific tool on a specific server."""
        if server_name not in self.clients:
            raise Exception(f"Server {server_name} not connected")
        
        client = self.clients[server_name]
        
        # Clean up arguments - remove None values and empty strings
        if arguments:
            arguments = {k: v for k, v in arguments.items() if v is not None and v != ""}
        
        async with client:
            try:
                result = await client.call_tool(tool_name, arguments=arguments or {})
                # Handle the result based on its type
                if hasattr(result, 'content'):
                    # If result has content attribute, extract it
                    if isinstance(result.content, list) and len(result.content) > 0:
                        return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                    return str(result.content)
                return str(result)
            except Exception as e:
                print(f"Error calling tool {tool_name}: {e}")
                raise
    
    def parse_tool_call(self, text: str) -> Optional[Dict]:
        """Parse tool call from LLM response."""
        # Multiple patterns to catch different formats
        patterns = [
            r'<tool_call>\s*(\w+)\.(\w+)\((.*?)\)\s*</tool_call>',  # XML style
            r'TOOL_CALL:\s*(\w+)\.(\w+)\((.*?)\)',  # Original format
            r'Tool:\s*(\w+)\.(\w+)\((.*?)\)',  # Alternative format
            r'```tool\s*(\w+)\.(\w+)\((.*?)\)```',  # Code block format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                server_name = match.group(1).lower()
                tool_name = match.group(2)
                args_str = match.group(3).strip()
                
                # Parse arguments
                arguments = {}
                if args_str:
                    # Try JSON-style parsing first
                    if '{' in args_str:
                        try:
                            arguments = json.loads(args_str)
                        except:
                            pass
                    
                    # Fallback to key=value parsing
                    if not arguments and '=' in args_str:
                        arg_pattern = r'(\w+)\s*=\s*["\']?([^,"\']*)["\'"]?'
                        for arg_match in re.finditer(arg_pattern, args_str):
                            key = arg_match.group(1)
                            value = arg_match.group(2).strip()
                            arguments[key] = value
                    
                    # If just a single value (e.g., for state parameter)
                    elif not arguments and args_str and not '=' in args_str:
                        # Try to infer the parameter name
                        clean_value = args_str.strip('"\'')
                        if tool_name.lower() == 'get_alerts' or 'weather' in server_name:
                            arguments['state'] = clean_value
                        elif 'knowledge' in tool_name.lower():
                            # Knowledge base typically doesn't need parameters
                            pass
                
                return {
                    "server": server_name,
                    "tool": tool_name,
                    "arguments": arguments
                }
        
        return None
    
    async def run(self, user_input: str) -> str:
        """Process user input using LLM reasoning and tool calling."""
        # Add user message to history
        self.conversation_history.append(HumanMessage(content=user_input))
        
        # Create comprehensive system prompt
        tools_description = self.create_tools_prompt()
        
        system_prompt = f"""You are an AI assistant with access to tools through FastMCP servers.

AVAILABLE TOOLS:
{tools_description}

CRITICAL INSTRUCTIONS:
1. When the user asks about weather, policies, knowledge, or expenses, you MUST use the appropriate tool
2. You have FULL ACCESS to these tools - never say you don't have access
3. Format tool calls using this exact format:
   <tool_call>server.tool_name(param1=value1, param2=value2)</tool_call>

EXAMPLES:
- Weather query: <tool_call>weather.get_alerts(state=NY)</tool_call>
- Company policy query: <tool_call>rag.get_knowledge_base()</tool_call>
- Expense query: Use appropriate expense_tracker tool

PROCESS:
1. Analyze what the user is asking
2. If it relates to any available tool, USE IT IMMEDIATELY
3. Format the tool call properly
4. Wait for the result before giving your final answer

Remember: You MUST use tools when they're relevant. Don't ask for permission or say you'll check - just do it."""
        
        # Get initial LLM response
        messages = [SystemMessage(content=system_prompt)] + self.conversation_history
        llm_response = self.llm.invoke(messages)
        response_text = llm_response.content
        
        if self.debug:
            print(f"\n[DEBUG] LLM Response:\n{response_text}\n")
        
        # Check for tool call
        tool_call = self.parse_tool_call(response_text)
        
        if tool_call:
            try:
                print(f"\n🔧 Executing: {tool_call['server']}.{tool_call['tool']}({tool_call['arguments']})")
                
                # Execute the tool
                result = await self.call_tool(
                    tool_call['server'],
                    tool_call['tool'],
                    tool_call['arguments']
                )
                
                # Create a follow-up message with the result
                tool_result_message = f"""
Tool executed successfully.
Result: {result}

Now provide a helpful response to the user based on this information."""
                
                # Get final response from LLM
                self.conversation_history.append(AIMessage(content=response_text))
                self.conversation_history.append(HumanMessage(content=tool_result_message))
                
                final_messages = [SystemMessage(content="You are a helpful assistant. Use the tool result to answer the user's question.")] + self.conversation_history
                final_response = self.llm.invoke(final_messages)
                response_text = final_response.content
                
            except Exception as e:
                response_text = f"I encountered an error while using the tool: {str(e)}\n\nPlease try rephrasing your question or ask about something else."
        
        # Add final response to history
        self.conversation_history.append(AIMessage(content=response_text))
        
        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return response_text
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []

async def main():
    """Main function with LLM-powered FastMCP cloud interaction."""
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key in the .env file")
        return
    
    print("🤖 FastMCP Cloud Client with GPT Integration")
    print("="*50)
    
    # Create agent
    agent = FastMCPAgentWithLLM(REMOTE_SERVERS)
    
    try:
        # Connect to all servers
        await agent.connect_all_servers()
        
        print("\n===== Interactive Chat with GPT + FastMCP =====")
        print("The AI assistant can now use tools from FastMCP cloud servers")
        print("\nCommands:")
        print("- 'exit' or 'quit': End conversation")
        print("- 'clear': Clear conversation history")
        print("- 'tools': See available tools")
        print("- 'debug': Toggle debug mode")
        print("="*50)
        
        # Interactive chat loop
        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
            
            if user_input.lower() == 'clear':
                agent.clear_history()
                print("✅ Conversation history cleared")
                continue
            
            if user_input.lower() == 'tools':
                print("\n📋 Available Tools:")
                print(agent.create_tools_prompt())
                continue
            
            if user_input.lower() == 'debug':
                agent.debug = not agent.debug
                print(f"✅ Debug mode: {'ON' if agent.debug else 'OFF'}")
                continue
            
            # Get response from agent
            print("\nAssistant: ", end="", flush=True)
            
            try:
                response = await agent.run(user_input)
                print(response)
            except Exception as e:
                print(f"\n❌ Error: {e}")
                if agent.debug:
                    import traceback
                    traceback.print_exc()
    
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        if "--debug" in str(e).lower():
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())