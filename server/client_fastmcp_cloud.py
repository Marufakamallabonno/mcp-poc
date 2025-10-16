import asyncio
from fastmcp import Client
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# FastMCP Cloud servers
REMOTE_SERVERS = {
    "weather": "https://mcp-poc-multi-tool.fastmcp.app/mcp",
    "rag": "https://mcp-poc-rag.fastmcp.app/mcp",
    "expense_tracker": "https://expense-tracker-by-niloy.fastmcp.app/mcp"
}

async def test_server(name: str, url: str):
    """Test connection to a FastMCP cloud server."""
    print(f"\n📡 Testing {name} server at {url}")
    try:
        client = Client(url)
        async with client:
            # List available tools
            tools = await client.list_tools()
            print(f"✅ Connected to {name}!")
            print(f"   Available tools: {len(tools)} tools")
            for tool in tools[:3]:  # Show first 3 tools
                print(f"   - {tool.name}: {tool.description[:50]}...")
            
            # List resources if available
            resources = await client.list_resources()
            if resources:
                print(f"   Available resources: {len(resources)} resources")
            
            return True
    except Exception as e:
        print(f"❌ Failed to connect to {name}: {e}")
        return False

async def interactive_client(server_url: str, server_name: str):
    """Run an interactive session with a FastMCP cloud server."""
    client = Client(server_url)
    
    async with client:
        print(f"\n===== Connected to {server_name} =====")
        
        # List available operations
        tools = await client.list_tools()
        print(f"Available tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        
        print("\nType 'exit' to quit, or enter a tool name to use it")
        print("="*40)
        
        while True:
            user_input = input(f"\n[{server_name}]> ")
            
            if user_input.lower() == 'exit':
                break
            
            # Find matching tool
            matching_tool = None
            for tool in tools:
                if tool.name.lower() == user_input.lower():
                    matching_tool = tool
                    break
            
            if matching_tool:
                print(f"\nUsing tool: {matching_tool.name}")
                print(f"Description: {matching_tool.description}")
                
                # Get arguments if needed
                args = {}
                if matching_tool.inputSchema and 'properties' in matching_tool.inputSchema:
                    print("\nRequired arguments:")
                    for arg_name, arg_schema in matching_tool.inputSchema['properties'].items():
                        required = arg_name in matching_tool.inputSchema.get('required', [])
                        marker = "*" if required else ""
                        arg_value = input(f"  {arg_name}{marker}: ")
                        if arg_value:
                            args[arg_name] = arg_value
                
                try:
                    # Call the tool
                    result = await client.call_tool(matching_tool.name, arguments=args)
                    print(f"\n📤 Result: {result}")
                except Exception as e:
                    print(f"❌ Error calling tool: {e}")
            else:
                print(f"Tool '{user_input}' not found. Available tools:")
                for tool in tools:
                    print(f"  - {tool.name}")

async def main():
    """Main function to interact with FastMCP cloud servers."""
    print("🚀 FastMCP Cloud Client")
    print("="*50)
    
    # Test all servers
    print("\n1️⃣  Testing connections to FastMCP cloud servers...")
    working_servers = {}
    
    for name, url in REMOTE_SERVERS.items():
        if await test_server(name, url):
            working_servers[name] = url
    
    if not working_servers:
        print("\n❌ No servers are accessible!")
        print("\nPossible issues:")
        print("1. The servers might be down or not deployed")
        print("2. The URLs might have changed")
        print("3. Network connectivity issues")
        return
    
    # Let user choose a server
    print(f"\n✅ {len(working_servers)} server(s) available")
    print("\nChoose a server to interact with:")
    
    server_list = list(working_servers.items())
    for i, (name, url) in enumerate(server_list, 1):
        print(f"{i}. {name} - {url}")
    print(f"{len(server_list) + 1}. Test all servers")
    print("0. Exit")
    
    choice = input("\nEnter your choice: ")
    
    try:
        choice_num = int(choice)
        if choice_num == 0:
            print("Goodbye!")
            return
        elif choice_num == len(server_list) + 1:
            # Test all servers
            for name, url in working_servers.items():
                await test_server(name, url)
        elif 1 <= choice_num <= len(server_list):
            # Interactive session with chosen server
            server_name, server_url = server_list[choice_num - 1]
            await interactive_client(server_url, server_name)
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")

if __name__ == "__main__":
    asyncio.run(main())
