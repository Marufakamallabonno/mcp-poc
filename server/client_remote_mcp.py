import asyncio
import nest_asyncio
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
import json

# Load environment variables
load_dotenv()

# Allow nested event loops
nest_asyncio.apply()

# Remote server configuration for MCP-use
# Note: These servers need to support SSE/WebSocket connections
REMOTE_CONFIG = {
    "mcpServers": {
        "weather": {
            "transport": "sse",  # Try SSE transport
            "url": "https://mcp-poc-multi-tool.fastmcp.app/sse"
        },
        "rag": {
            "transport": "sse",
            "url": "https://mcp-poc-rag.fastmcp.app/sse"
        },
        "expense_tracker": {
            "transport": "sse",
            "url": "https://expense-tracker-by-niloy.fastmcp.app/sse"
        }
    }
}

# Alternative: Try WebSocket transport
REMOTE_CONFIG_WS = {
    "mcpServers": {
        "weather": {
            "transport": "ws",
            "url": "wss://mcp-poc-multi-tool.fastmcp.app/ws"
        },
        "rag": {
            "transport": "ws",
            "url": "wss://mcp-poc-rag.fastmcp.app/ws"
        },
        "expense_tracker": {
            "transport": "ws",
            "url": "wss://expense-tracker-by-niloy.fastmcp.app/ws"
        }
    }
}

async def test_remote_connection():
    """Test different connection methods to remote servers."""
    print("🔍 Testing remote FastMCP cloud servers...")
    
    # Test 1: Try SSE endpoints
    print("\n1. Testing SSE endpoints...")
    try:
        client = MCPClient.from_dict(REMOTE_CONFIG)
        print("✅ SSE configuration accepted")
        await client.close_all_sessions()
        return REMOTE_CONFIG
    except Exception as e:
        print(f"❌ SSE failed: {e}")
    
    # Test 2: Try WebSocket endpoints
    print("\n2. Testing WebSocket endpoints...")
    try:
        client = MCPClient.from_dict(REMOTE_CONFIG_WS)
        print("✅ WebSocket configuration accepted")
        await client.close_all_sessions()
        return REMOTE_CONFIG_WS
    except Exception as e:
        print(f"❌ WebSocket failed: {e}")
    
    # Test 3: Try standard HTTP with different paths
    print("\n3. Testing alternative HTTP paths...")
    alt_paths = ["/api", "/mcp/sse", "/events", ""]
    for path in alt_paths:
        test_config = {
            "mcpServers": {
                "weather": {
                    "transport": "http",
                    "url": f"https://mcp-poc-multi-tool.fastmcp.app{path}"
                }
            }
        }
        try:
            client = MCPClient.from_dict(test_config)
            print(f"✅ Path '{path}' accepted")
            await client.close_all_sessions()
            return test_config
        except Exception as e:
            print(f"❌ Path '{path}' failed")
            continue
    
    return None

async def main():
    """Main function with remote FastMCP cloud servers."""
    # Set up OpenAI API key
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found")
        print("Please set your OpenAI API key in the .env file")
        return
    
    print("🌐 FastMCP Cloud Client with GPT Integration")
    print("="*50)
    
    # Test which configuration works
    working_config = await test_remote_connection()
    
    if not working_config:
        print("\n❌ Could not connect to remote servers!")
        print("\n📝 Troubleshooting:")
        print("1. The FastMCP cloud servers may not support direct MCP connections")
        print("2. They might require authentication tokens")
        print("3. The endpoints might be different than expected")
        print("\n💡 Alternative: Use the FastMCP Python client directly:")
        print("   python server/client_fastmcp_cloud.py")
        return
    
    print(f"\n✅ Connected using configuration: {json.dumps(working_config, indent=2)}")
    
    try:
        # Create MCP client with working configuration
        client = MCPClient.from_dict(working_config)
        
        # Initialize GPT
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        
        # Create MCP agent
        agent = MCPAgent(
            llm=llm,
            client=client,
            max_steps=15,
            memory_enabled=True
        )
        
        print("\n===== FastMCP Cloud Chat with GPT =====")
        print("Connected to remote servers on FastMCP cloud")
        print("Type 'exit' to quit, 'clear' to clear history")
        print("="*40)
        
        # Interactive chat loop
        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            
            if user_input.lower() == 'clear':
                agent.clear_conversation_history()
                print("✅ History cleared")
                continue
            
            print("\nAssistant: ", end="", flush=True)
            
            try:
                response = await agent.run(user_input)
                print(response)
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    except Exception as e:
        print(f"\n❌ Failed to initialize client: {e}")
    
    finally:
        if 'client' in locals() and client:
            try:
                await client.close_all_sessions()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(main())
