"""
Simple MCP Server for Graph Plotting
User query -> LLM generates code -> Subprocess executes -> Returns plot path
"""

from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional
import subprocess
import tempfile
from pathlib import Path
import json
from datetime import datetime
import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Initialize MCP server
mcp = FastMCP("simple_graph_plotter")

async def generate_plot_code(query: str, data: Dict[str, Any]) -> str:
    """Generate matplotlib code using Azure OpenAI based on user query."""
    
    # Get Azure credentials
    subscription_key = os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("PIVOTLY_AZURE_OPENAI_ENDPOINT")
    
    if not subscription_key or not azure_endpoint:
        raise ValueError("Azure OpenAI credentials not found")
    
    azure_endpoint = azure_endpoint.rstrip('/')
    
    # Create data context for LLM
    data_context = ""
    if data:
        variable_descriptions = []
        for key, value in data.items():
            if isinstance(value, list):
                variable_descriptions.append(f"  - {key}: list with {len(value)} items")
            else:
                variable_descriptions.append(f"  - {key}: {type(value).__name__}")
        
        data_context = "\n\nAvailable variables:\n" + "\n".join(variable_descriptions)
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a matplotlib code generator. Generate Python code to create the requested plot.
         
         RULES:
         1. Use matplotlib.pyplot (imported as plt)
         2. DO NOT include plt.savefig() or plt.show()
         3. Use the exact variable names provided
         4. Return ONLY Python code, no explanations
         
         {data_context}"""),
        ("human", "{query}")
    ])
    
    # Initialize LLM
    llm = AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=subscription_key,
        api_version="2024-12-01-preview",
        deployment_name="gpt-5-mini"
    )
    
    # Generate code
    response = await llm.ainvoke(
        prompt.format_messages(query=query, data_context=data_context)
    )
    
    # Clean response
    code = response.content.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        lines = lines[1:]  # Remove first line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove last line
        code = "\n".join(lines).strip()
    
    return code


def execute_plot_subprocess(code: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute plot code using subprocess and return plot path."""
    
    # Generate plot filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_path = f"plots/mcp_plot_{timestamp}.png"
    
    # Ensure plots directory exists
    Path("plots").mkdir(exist_ok=True)
    
    script_path = None
    try:
        # Create temporary Python script
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as temp_file:
            script_content = f"""
import json
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Get data from arguments
data = json.loads(sys.argv[1])
plot_path = sys.argv[2]

# Make data available as variables
for key, value in data.items():
    globals()[key] = value

# Execute plot code
{code}

# Save plot
plt.savefig(plot_path, dpi=150, bbox_inches='tight')
plt.close()

print(json.dumps({{'success': True, 'plot_path': plot_path}}))
"""
            temp_file.write(script_content)
            script_path = temp_file.name
        
        # Run subprocess
        result = subprocess.run(
            ['python', script_path, json.dumps(data), plot_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return {'error': f"Execution failed: {result.stderr}"}
        
        # Parse result
        try:
            output = json.loads(result.stdout.strip())
            return {'plot_path': output['plot_path']}
        except:
            return {'error': "Failed to parse output"}
            
    except subprocess.TimeoutExpired:
        return {'error': 'Execution timed out'}
    except Exception as e:
        return {'error': str(e)}
    finally:
        # Clean up temp file
        if script_path and Path(script_path).exists():
            Path(script_path).unlink()


@mcp.tool()
async def plot_graph(
    query: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate a plot based on user query and data.
    
    Args:
        query: What kind of plot to create (e.g., "Create a line plot of x vs y")
        data: Dictionary containing the data to plot (e.g., {"x": [1,2,3], "y": [4,5,6]})
    
    Returns:
        Dictionary with plot_path or error
    """
    
    # Use default data if none provided
    if data is None:
        data = {'numbers': [1, 2, 3, 4, 5]}
    
    try:
        # Generate code using LLM
        code = await generate_plot_code(query, data)
        
        # Execute code using subprocess
        result = execute_plot_subprocess(code, data)
        
        if 'error' in result:
            # Try once more if failed
            code = await generate_plot_code(query + f"\nPrevious error: {result['error']}", data)
            result = execute_plot_subprocess(code, data)
        
        return result
        
    except Exception as e:
        return {'error': str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
