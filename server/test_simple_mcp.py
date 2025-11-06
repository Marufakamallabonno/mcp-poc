#!/usr/bin/env python3
"""
Simple test for the Simple Graph MCP Server
"""

import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

async def test_direct():
    """Test the MCP server functions directly"""
    print("Testing Simple Graph MCP Server")
    print("="*50)
    
    # Import the server module
    import simple_graph_mcp
    
    # Test data
    test_data = {
        "x": [1, 2, 3, 4, 5],
        "y": [2, 4, 6, 8, 10]
    }
    
    # Test 1: Line plot
    print("\nTest 1: Line plot")
    result = await simple_graph_mcp.plot_graph(
        "Create a line plot with x on x-axis and y on y-axis",
        test_data
    )
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"✅ Plot saved to: {result['plot_path']}")
    
    # Test 2: Bar chart
    print("\nTest 2: Bar chart")
    bar_data = {
        "categories": ["A", "B", "C", "D"],
        "values": [10, 25, 15, 30]
    }
    
    result = await simple_graph_mcp.plot_graph(
        "Create a bar chart with categories and values",
        bar_data
    )
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"✅ Plot saved to: {result['plot_path']}")
    
    # Test 3: Scatter plot
    print("\nTest 3: Scatter plot")
    result = await simple_graph_mcp.plot_graph(
        "Make a scatter plot of x vs y",
        test_data
    )
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"✅ Plot saved to: {result['plot_path']}")
    
    print("\n" + "="*50)
    print("✅ Tests completed!")


if __name__ == "__main__":
    # Check Azure credentials
    if not os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY"):
        print("❌ Error: PIVOTLY_AZURE_OPENAI_API_KEY not found")
        exit(1)
    
    if not os.getenv("PIVOTLY_AZURE_OPENAI_ENDPOINT"):
        print("❌ Error: PIVOTLY_AZURE_OPENAI_ENDPOINT not found")
        exit(1)
    
    asyncio.run(test_direct())
