#!/usr/bin/env python3
"""
Simple test for the Graph Plotter MCP Server
This script provides a basic test of the graph plotting functionality.
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
import os
import sys

# Add parent directory to path to import from agent_plot
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_direct_functions():
    """Test the plotting functions directly without MCP."""
    print("=" * 60)
    print("Testing Direct Graph Plotting Functions")
    print("=" * 60)
    
    # Import the server module directly
    import graph_plotter
    
    # Test 1: Simple plot execution
    print("\n1. Testing execute_plot_code function...")
    test_code = """
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
plt.plot([1, 2, 3, 4, 5], [1, 4, 9, 16, 25])
plt.xlabel('X')
plt.ylabel('Y')
plt.title('Test Plot')
plt.grid(True)
"""
    
    result = graph_plotter.execute_plot_code(
        test_code,
        {},
        "plots/test_direct_plot.png"
    )
    
    if "error" in result:
        print(f"  ❌ Error: {result['error']}")
    else:
        print(f"  ✅ Plot created: {result['plot_path']}")
        print(f"  Base64 size: {len(result.get('plot_base64', ''))} chars")
    
    # Test 2: Plot with data
    print("\n2. Testing plot with provided data...")
    test_code_with_data = """
plt.figure(figsize=(10, 6))
plt.bar(categories, values)
plt.xlabel('Category')
plt.ylabel('Value')
plt.title('Bar Chart Test')
"""
    
    test_data = {
        "categories": ["A", "B", "C", "D"],
        "values": [10, 25, 15, 30]
    }
    
    result = graph_plotter.execute_plot_code(
        test_code_with_data,
        test_data,
        "plots/test_bar_plot.png"
    )
    
    if "error" in result:
        print(f"  ❌ Error: {result['error']}")
    else:
        print(f"  ✅ Plot created: {result['plot_path']}")
    
    return True


async def test_with_llm():
    """Test the LLM-based plot generation."""
    print("\n" + "=" * 60)
    print("Testing LLM-based Plot Generation")
    print("=" * 60)
    
    # Check for Azure credentials
    if not os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY"):
        print("  ⚠️  Skipping: Azure OpenAI credentials not found")
        return False
    
    import graph_plotter
    
    # Test LLM code generation
    print("\n3. Testing LLM code generation...")
    
    test_data = {
        "months": ["Jan", "Feb", "Mar", "Apr", "May"],
        "sales": [100, 120, 140, 130, 160]
    }
    
    try:
        code = await graph_plotter.generate_plot_code(
            "Create a line plot showing sales over months",
            test_data
        )
        
        print(f"  ✅ Generated code:")
        print("  " + "\n  ".join(code.split("\n")[:5]))  # Show first 5 lines
        
        # Execute the generated code
        result = graph_plotter.execute_plot_code(
            code,
            test_data,
            "plots/test_llm_plot.png"
        )
        
        if "error" in result:
            print(f"  ❌ Execution error: {result['error']}")
        else:
            print(f"  ✅ Plot created: {result['plot_path']}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_mcp_tools():
    """Test the MCP tool functions directly."""
    print("\n" + "=" * 60)
    print("Testing MCP Tool Functions")
    print("=" * 60)
    
    import graph_plotter
    
    # Test create_simple_plot
    print("\n4. Testing create_simple_plot tool...")
    
    result = await graph_plotter.create_simple_plot(
        plot_type="scatter",
        x_data=[1, 2, 3, 4, 5],
        y_data=[2, 4, 6, 8, 10],
        title="Scatter Plot Test",
        x_label="X Values",
        y_label="Y Values"
    )
    
    if "error" in result:
        print(f"  ❌ Error: {result['error']}")
    else:
        print(f"  ✅ Plot created: {result['plot_path']}")
    
    # Test list_saved_plots
    print("\n5. Testing list_saved_plots tool...")
    
    result = await graph_plotter.list_saved_plots()
    
    if "error" in result:
        print(f"  ❌ Error: {result['error']}")
    else:
        print(f"  ✅ Found {result['total']} plots")
        for plot in result['plots'][:3]:  # Show first 3
            print(f"     - {plot['filename']}")
    
    return True


def run_server_subprocess():
    """Start the MCP server as a subprocess for testing."""
    print("\n" + "=" * 60)
    print("Starting MCP Server (HTTP)")
    print("=" * 60)
    
    # Start server in background
    server_process = subprocess.Popen(
        ["python", "server/graph_plotter.py", "--transport", "http", "--port", "8003"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    print("  Server started with PID:", server_process.pid)
    print("  Waiting for server to initialize...")
    time.sleep(3)  # Give server time to start
    
    # Check if server is running
    if server_process.poll() is None:
        print("  ✅ Server is running")
        return server_process
    else:
        print("  ❌ Server failed to start")
        stdout, stderr = server_process.communicate()
        if stderr:
            print(f"  Error: {stderr.decode()}")
        return None


async def test_http_client():
    """Test the server via HTTP client."""
    print("\n" + "=" * 60)
    print("Testing via HTTP Client")
    print("=" * 60)
    
    try:
        from fastmcp import Client
        
        async with Client("http://localhost:8003/mcp") as client:
            print("  ✅ Connected to server")
            
            # List tools
            tools = await client.list_tools()
            print(f"  Found {len(tools)} tools:")
            for tool in tools:
                print(f"    - {tool['name']}")
            
            # Test a simple plot
            result = await client.call_tool(
                "create_simple_plot",
                {
                    "plot_type": "line",
                    "x_data": [1, 2, 3],
                    "y_data": [1, 4, 9],
                    "title": "HTTP Test Plot"
                }
            )
            
            if "error" in result:
                print(f"  ❌ Plot error: {result['error']}")
            else:
                print(f"  ✅ Plot created: {result.get('plot_path')}")
            
            return True
            
    except Exception as e:
        print(f"  ❌ Client error: {e}")
        return False


async def main():
    """Main test function."""
    print("\n🎨 Graph Plotter MCP Server - Simple Test Suite")
    print("=" * 60)
    
    # Test 1: Direct functions
    test_direct_functions()
    
    # Test 2: LLM-based generation
    await test_with_llm()
    
    # Test 3: MCP tools directly
    await test_mcp_tools()
    
    # Test 4: HTTP server (optional)
    print("\n" + "=" * 60)
    print("HTTP Server Test (Optional)")
    print("=" * 60)
    choice = input("Do you want to test HTTP server? (y/n): ").lower()
    
    if choice == 'y':
        server_process = run_server_subprocess()
        if server_process:
            try:
                await test_http_client()
            finally:
                print("\n  Stopping server...")
                server_process.terminate()
                server_process.wait(timeout=5)
                print("  ✅ Server stopped")
    
    print("\n" + "=" * 60)
    print("✅ Test suite completed!")
    print("=" * 60)
    
    # Show created plots
    plots_dir = Path("plots")
    if plots_dir.exists():
        plot_files = list(plots_dir.glob("test_*.png"))
        if plot_files:
            print(f"\n📊 Created {len(plot_files)} test plots:")
            for plot_file in plot_files:
                print(f"  - {plot_file.name}")


if __name__ == "__main__":
    asyncio.run(main())
