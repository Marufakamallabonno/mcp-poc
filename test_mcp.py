#!/usr/bin/env python
"""Test script to verify MCP setup"""

import asyncio
import os
from dotenv import load_dotenv
from mcp_use import MCPClient

async def test_mcp_connection():
    """Test MCP server connections"""
    load_dotenv()
    
    config_file = "server/mcpconfig_working.json"
    
    print("Testing MCP Setup...")
    print("-" * 50)
    
    try:
        # Create MCP client
        print("1. Creating MCP client...")
        client = MCPClient.from_config_file(config_file)
        
        # List available servers
        print("2. Available MCP servers:")
        for server_name in client.sessions:
            print(f"   - {server_name}")
        
        print("\n3. Testing server connections...")
        
        # Test each server
        for server_name in client.sessions:
            try:
                session = client.sessions[server_name]
                # Get available tools for each server
                tools = await session.list_tools()
                print(f"\n   {server_name} server:")
                print(f"   ✓ Connected successfully")
                print(f"   ✓ Available tools: {len(tools.tools) if tools.tools else 0}")
                if tools.tools:
                    for tool in tools.tools[:3]:  # Show first 3 tools
                        print(f"      - {tool.name}")
                    if len(tools.tools) > 3:
                        print(f"      ... and {len(tools.tools) - 3} more")
            except Exception as e:
                print(f"\n   {server_name} server:")
                print(f"   ✗ Failed to connect: {e}")
        
        print("\n" + "-" * 50)
        print("✅ MCP setup test complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Clean up
        if 'client' in locals() and client.sessions:
            await client.close_all_sessions()

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())

