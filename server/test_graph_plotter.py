#!/usr/bin/env python3
"""
Test client for the Graph Plotter MCP Server
This script tests the graph plotting functionality of the MCP server.
"""

import asyncio
import json
from pathlib import Path
from fastmcp import Client
from dotenv import load_dotenv
import os
import base64

# Load environment variables
load_dotenv()

# Server configuration - FastMCP Client expects this format
GRAPH_PLOTTER_SERVER = {
    "command": "python",
    "args": ["/home/sol-73/Niloy/My_git/mcp-poc/server/graph_plotter.py"]
}

# Alternative configuration for HTTP transport
GRAPH_PLOTTER_HTTP = "http://localhost:8003/mcp"


async def test_stdio_server():
    """Test the graph plotter server using stdio transport."""
    print("=" * 60)
    print("Testing Graph Plotter MCP Server (stdio)")
    print("=" * 60)
    
    try:
        # Connect to the server using stdio
        async with Client(GRAPH_PLOTTER_SERVER) as client:
            print("\n✓ Connected to Graph Plotter server via stdio")
            
            # List available tools
            tools = await client.list_tools()
            print(f"\n📊 Available tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', 'No description')[:100]}...")
            
            # Test 1: Create a line plot with LLM
            print("\n" + "="*40)
            print("Test 1: Creating line plot with LLM")
            print("="*40)
            
            result = await client.call_tool(
                "create_plot",
                {
                    "query": "Create a line plot showing temperature changes over days of the week",
                    "data": {
                        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                        "temperature": [20, 22, 25, 23, 21, 24, 26]
                    },
                    "execution_method": "exec"
                }
            )
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✓ Plot created successfully!")
                print(f"  Saved to: {result.get('plot_path', 'N/A')}")
                if result.get('plot_base64'):
                    print(f"  Base64 image size: {len(result['plot_base64'])} characters")
            
            # Test 2: Create a scatter plot with LLM
            print("\n" + "="*40)
            print("Test 2: Creating scatter plot with LLM")
            print("="*40)
            
            result = await client.call_tool(
                "create_plot",
                {
                    "query": "Create a scatter plot showing the relationship between study hours and test scores",
                    "data": {
                        "study_hours": [1, 2, 3, 4, 5, 6, 7, 8],
                        "test_scores": [55, 60, 65, 70, 75, 82, 88, 95]
                    },
                    "plot_type": "scatter"
                }
            )
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✓ Plot created successfully!")
                print(f"  Saved to: {result.get('plot_path', 'N/A')}")
            
            # Test 3: Create a simple bar chart (no LLM)
            print("\n" + "="*40)
            print("Test 3: Creating simple bar chart (no LLM)")
            print("="*40)
            
            result = await client.call_tool(
                "create_simple_plot",
                {
                    "plot_type": "bar",
                    "x_data": ["Product A", "Product B", "Product C", "Product D"],
                    "y_data": [150, 200, 175, 225],
                    "title": "Sales by Product",
                    "x_label": "Products",
                    "y_label": "Sales ($)"
                }
            )
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✓ Plot created successfully!")
                print(f"  Saved to: {result.get('plot_path', 'N/A')}")
            
            # Test 4: Create a histogram
            print("\n" + "="*40)
            print("Test 4: Creating histogram")
            print("="*40)
            
            import random
            random.seed(42)
            normal_data = [random.gauss(100, 15) for _ in range(1000)]
            
            result = await client.call_tool(
                "create_simple_plot",
                {
                    "plot_type": "histogram",
                    "x_data": normal_data,
                    "title": "Distribution of Test Scores",
                    "x_label": "Score",
                    "y_label": "Frequency"
                }
            )
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✓ Plot created successfully!")
                print(f"  Saved to: {result.get('plot_path', 'N/A')}")
            
            # Test 5: List saved plots
            print("\n" + "="*40)
            print("Test 5: Listing saved plots")
            print("="*40)
            
            result = await client.call_tool("list_saved_plots", {})
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✓ Found {result.get('total', 0)} plots in {result.get('directory', 'N/A')}")
                for plot in result.get('plots', [])[:5]:  # Show first 5
                    print(f"  - {plot['filename']} ({plot['size_kb']:.1f} KB)")
            
            # Test 6: Get a plot image
            if result.get('plots') and len(result['plots']) > 0:
                print("\n" + "="*40)
                print("Test 6: Getting plot image")
                print("="*40)
                
                first_plot = result['plots'][0]
                image_result = await client.call_tool(
                    "get_plot_image",
                    {"plot_path": first_plot['path']}
                )
                
                if "error" in image_result:
                    print(f"❌ Error: {image_result['error']}")
                else:
                    print(f"✓ Retrieved image: {image_result['filename']}")
                    print(f"  Base64 size: {len(image_result.get('plot_base64', ''))} characters")
            
            # List resources
            print("\n" + "="*40)
            print("Available Resources (Examples)")
            print("="*40)
            
            resources = await client.list_resources()
            for resource in resources:
                print(f"  - {resource['uri']}: {resource.get('name', 'No name')}")
            
    except Exception as e:
        print(f"\n❌ Failed to connect or test server: {e}")
        import traceback
        traceback.print_exc()


async def test_http_server():
    """Test the graph plotter server using HTTP transport."""
    print("\n" * 2)
    print("=" * 60)
    print("Testing Graph Plotter MCP Server (HTTP)")
    print("=" * 60)
    print("\nNote: Make sure the server is running with:")
    print('  python server/graph_plotter.py --transport http --port 8003')
    print("\n")
    
    try:
        # Connect to the server using HTTP
        async with Client(GRAPH_PLOTTER_HTTP) as client:
            print("✓ Connected to Graph Plotter server via HTTP")
            
            # Quick test - create a simple plot
            result = await client.call_tool(
                "create_simple_plot",
                {
                    "plot_type": "line",
                    "x_data": [1, 2, 3, 4, 5],
                    "y_data": [1, 4, 9, 16, 25],
                    "title": "Quadratic Function",
                    "x_label": "X",
                    "y_label": "Y = X²"
                }
            )
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✓ Plot created successfully!")
                print(f"  Saved to: {result.get('plot_path', 'N/A')}")
            
    except Exception as e:
        print(f"❌ Could not connect to HTTP server: {e}")
        print("  Make sure the server is running on port 8003")


async def main():
    """Main test function."""
    print("\n🎨 Graph Plotter MCP Server Test Suite")
    print("=" * 60)
    
    # Check for Azure OpenAI credentials
    if not os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY"):
        print("\n⚠️  Warning: PIVOTLY_AZURE_OPENAI_API_KEY not found")
        print("  LLM-based plot generation will not work")
        print("  Simple plots will still work")
    
    if not os.getenv("PIVOTLY_AZURE_OPENAI_ENDPOINT"):
        print("\n⚠️  Warning: PIVOTLY_AZURE_OPENAI_ENDPOINT not found")
        print("  LLM-based plot generation will not work")
    
    # Test stdio transport
    await test_stdio_server()
    
    # Optionally test HTTP transport
    # Uncomment the following line if you want to test HTTP transport
    # await test_http_server()
    
    print("\n" + "=" * 60)
    print("✅ Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
