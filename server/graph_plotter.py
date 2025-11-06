"""
MCP Server for Graph Plotting
This server provides tools to generate various types of plots/graphs using matplotlib
based on user queries and data.
"""

from typing import Any, Dict, List, Optional
import json
import tempfile
from pathlib import Path
import subprocess
import ast
from datetime import datetime
import base64
import io

# MCP imports
from mcp.server.fastmcp import FastMCP

# Matplotlib imports
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

# LangGraph and LangChain imports
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

# Environment variables
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("graph_plotter")

# ==================== Helper Functions ====================

def validate_code(code_str: str) -> bool:
    """Validate the Python code string."""
    try:
        ast.parse(code_str)
        return True
    except Exception:
        return False


def execute_plot_code(code_str: str, data: Dict[str, Any], plot_path: str = None) -> Dict[str, Any]:
    """Execute the plot code with provided data.
    
    Args:
        code_str: Python code to execute (should create a plot)
        data: Data variables available in the namespace
        plot_path: Path where to save the plot
    
    Returns:
        Dictionary with result or error
    """
    if not validate_code(code_str):
        return {'error': 'Invalid Python code'}
    
    if plot_path is None:
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_path = f"plots/generated_plot_{timestamp}.png"
    
    # Ensure plots directory exists
    plot_dir = Path(plot_path).parent
    plot_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create namespace with data and matplotlib
        namespace = {
            **data,
            'plt': plt,
            'matplotlib': matplotlib,
            'plot_path': plot_path
        }
        
        # Execute the code
        exec(code_str, namespace)
        
        # Save the plot
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        
        # Convert plot to base64 for returning
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plot_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        plt.close()  # Close the figure to free memory
        
        # Return success with plot path and base64 data
        return {
            'result': 'Plot created successfully',
            'plot_path': plot_path,
            'plot_base64': plot_base64
        }
    except Exception as e:
        # Clean up any open figures
        plt.close('all')
        return {'error': str(e)}


def execute_plot_subprocess(code_str: str, data: Dict[str, Any], plot_path: str = None) -> Dict[str, Any]:
    """Execute the plot code using subprocess for isolation.
    
    Args:
        code_str: Python code to execute (should create a plot)
        data: Data variables available in the namespace
        plot_path: Path where to save the plot
    
    Returns:
        Dictionary with result or error
    """
    if not validate_code(code_str):
        return {'error': 'Invalid Python code'}
    
    if plot_path is None:
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_path = f"plots/generated_plot_{timestamp}.png"
    
    # Ensure plots directory exists
    plot_dir = Path(plot_path).parent
    plot_dir.mkdir(parents=True, exist_ok=True)
    
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as temp_file:
            # Create a script that unpacks data and creates plot
            script_content = f"""
import json
import sys
import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

input_data = json.loads(sys.argv[1])
plot_path = sys.argv[2]

# Unpack all data keys as local variables
for key, value in input_data.items():
    globals()[key] = value

# Execute the plot code
{code_str}

# Save the plot
plt.savefig(plot_path, dpi=150, bbox_inches='tight')

# Convert plot to base64
buffer = io.BytesIO()
plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
buffer.seek(0)
plot_base64 = base64.b64encode(buffer.read()).decode('utf-8')

plt.close()

# Return success with plot path and base64 data
result = {{
    'result': 'Plot created successfully',
    'plot_path': plot_path,
    'plot_base64': plot_base64
}}
print(json.dumps(result))
"""
            temp_file.write(script_content)
            script_path = temp_file.name
        
        input_json = json.dumps(data)
        result = subprocess.run(
            ['python', script_path, input_json, plot_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=60
        )
        
        if result.returncode != 0:
            error_msg = f"Subprocess failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f"\nSTDERR: {result.stderr}"
            return {'error': error_msg}
        
        # Parse the JSON output
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            return {'error': f"Failed to parse output: {e}\nOutput: {result.stdout}"}
            
    except subprocess.TimeoutExpired:
        return {'error': 'Execution timed out after 60 seconds'}
    except Exception as e:
        return {'error': f"Subprocess execution error: {str(e)}"}
    finally:
        if script_path and Path(script_path).exists():
            try:
                Path(script_path).unlink()
            except Exception:
                pass


async def generate_plot_code(query: str, data: Dict[str, Any], previous_error: str = "") -> str:
    """Generate matplotlib code using Azure OpenAI based on user query.
    
    Args:
        query: User's request for the plot
        data: Available data for plotting
        previous_error: Any previous error to fix
    
    Returns:
        Generated Python code string
    """
    # Get Azure OpenAI credentials
    subscription_key = os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("PIVOTLY_AZURE_OPENAI_ENDPOINT")
    
    if not subscription_key or not azure_endpoint:
        raise ValueError("Azure OpenAI credentials not found in environment")
    
    # Ensure endpoint doesn't have trailing slash
    azure_endpoint = azure_endpoint.rstrip('/')
    
    # Create context about available data
    data_context = ""
    if data:
        variable_descriptions = []
        for key, value in data.items():
            if isinstance(value, list):
                variable_descriptions.append(
                    f"  - {key}: a list with {len(value)} items (example: {value[:3]}{'...' if len(value) > 3 else ''})"
                )
            elif isinstance(value, dict):
                variable_descriptions.append(
                    f"  - {key}: a dictionary with keys: {list(value.keys())[:5]}{'...' if len(value) > 5 else ''}"
                )
            else:
                variable_descriptions.append(f"  - {key}: {type(value).__name__} (value: {value})")
        
        data_context = (
            "\n\nAVAILABLE VARIABLES FROM DATA:\n" + 
            "\n".join(variable_descriptions) + 
            "\n\nIMPORTANT: Use these exact variable names in your code. "
            "The code will be executed with these variables already available."
        )
    else:
        data_context = (
            "\n\nDEFAULT DATA: The code will be executed with a variable 'numbers' "
            "containing [1, 2, 3]. Use this variable name in your code."
        )
    
    # Create prompt
    code_gen_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a coding assistant specialized in creating data visualizations. 
         Generate Python code that creates a plot/graph using matplotlib.
         
         IMPORTANT REQUIREMENTS:
         1. You MUST use matplotlib.pyplot (imported as 'plt') to create the plot
         2. The code should be complete and executable - it should create and configure the plot
         3. DO NOT call plt.savefig() or plt.show() - that will be handled automatically
         4. Include proper labels, titles, and styling to make the plot informative
         5. Use the variables from data to create the plot
         6. If there were previous errors, fix them
         7. Return ONLY the Python code, no markdown formatting or explanations
         
         Example of good code:
         import matplotlib.pyplot as plt
         plt.figure(figsize=(10, 6))
         plt.plot(x_values, y_values, marker='o', linestyle='-', linewidth=2)
         plt.xlabel('X Axis Label')
         plt.ylabel('Y Axis Label')
         plt.title('Plot Title')
         plt.grid(True, alpha=0.3)
         plt.legend()
         
         {data_context}"""),
        ("human", "{query}"),
        ("human", "Previous errors if any: {error}")
    ])
    
    # Initialize Azure OpenAI
    llm = AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=subscription_key,
        api_version="2024-12-01-preview",
        deployment_name="gpt-5-mini"
    )
    
    # Format and invoke the prompt
    formatted_messages = code_gen_prompt.format_messages(
        query=query,
        error=previous_error,
        data_context=data_context
    )
    
    response = await llm.ainvoke(formatted_messages)
    
    # Clean the response
    code = response.content.strip()
    if code.startswith("```"):
        # Remove markdown code blocks
        lines = code.split("\n")
        lines = lines[1:]  # Remove first line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove last line
        code = "\n".join(lines).strip()
    
    # Remove plt.savefig() and plt.show() if present
    lines = code.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if "plt.savefig" in stripped or "plt.show" in stripped:
            continue
        cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines).strip()


# ==================== MCP Tools ====================

@mcp.tool()
async def create_plot(
    query: str,
    data: Optional[Dict[str, Any]] = None,
    plot_type: Optional[str] = "auto",
    execution_method: str = "exec",
    max_retries: int = 3
) -> Dict[str, Any]:
    """Create a plot/graph based on user query and data.
    
    Args:
        query: Natural language description of the plot to create
        data: Dictionary of data to use for plotting (e.g., {"x": [1,2,3], "y": [4,5,6]})
        plot_type: Type of plot (auto, line, scatter, bar, histogram, pie, etc.)
        execution_method: Method to execute code ("exec" or "subprocess")
        max_retries: Maximum number of retries on error
    
    Returns:
        Dictionary containing:
        - result: Success message
        - plot_path: Path where plot is saved
        - plot_base64: Base64 encoded plot image
        - error: Error message if failed
    
    Examples:
        - create_plot("Create a line plot of x vs y", {"x": [1,2,3], "y": [4,5,6]})
        - create_plot("Make a bar chart showing sales by month", {"months": ["Jan", "Feb"], "sales": [100, 150]})
    """
    # Use default data if none provided
    if data is None:
        data = {'numbers': [1, 2, 3, 4, 5]}
    
    # Choose execution method
    execute_func = execute_plot_subprocess if execution_method == "subprocess" else execute_plot_code
    
    # Generate and execute with retries
    last_error = ""
    for attempt in range(max_retries):
        try:
            # Generate code
            code = await generate_plot_code(query, data, last_error)
            
            # Execute code
            result = execute_func(code, data)
            
            if "error" in result:
                last_error = result['error']
                if attempt == max_retries - 1:
                    return {"error": f"Failed after {max_retries} attempts: {last_error}"}
                continue
            else:
                return result
                
        except Exception as e:
            last_error = str(e)
            if attempt == max_retries - 1:
                return {"error": f"Failed after {max_retries} attempts: {last_error}"}
    
    return {"error": "Unexpected error in plot generation"}


@mcp.tool()
async def create_simple_plot(
    plot_type: str,
    x_data: List[float],
    y_data: Optional[List[float]] = None,
    title: str = "",
    x_label: str = "X",
    y_label: str = "Y",
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """Create a simple plot with direct parameters (no LLM needed).
    
    Args:
        plot_type: Type of plot ("line", "scatter", "bar", "histogram")
        x_data: X-axis data points
        y_data: Y-axis data points (optional for histogram)
        title: Plot title
        x_label: X-axis label
        y_label: Y-axis label
        save_path: Optional path to save the plot
    
    Returns:
        Dictionary with result, plot_path, and plot_base64
    """
    if save_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f"plots/simple_plot_{timestamp}.png"
    
    # Ensure plots directory exists
    plot_dir = Path(save_path).parent
    plot_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        plt.figure(figsize=(10, 6))
        
        if plot_type == "line":
            if y_data is None:
                y_data = x_data
                x_data = list(range(len(y_data)))
            plt.plot(x_data, y_data, marker='o', linestyle='-', linewidth=2)
        elif plot_type == "scatter":
            if y_data is None:
                y_data = x_data
                x_data = list(range(len(y_data)))
            plt.scatter(x_data, y_data, alpha=0.6, s=50)
        elif plot_type == "bar":
            if y_data is None:
                y_data = x_data
                x_data = list(range(len(y_data)))
            plt.bar(x_data, y_data, alpha=0.7)
        elif plot_type == "histogram":
            plt.hist(x_data, bins='auto', alpha=0.7, edgecolor='black')
        else:
            plt.close()
            return {"error": f"Unsupported plot type: {plot_type}"}
        
        plt.title(title or f"{plot_type.capitalize()} Plot")
        plt.xlabel(x_label)
        plt.ylabel(y_label)
        plt.grid(True, alpha=0.3)
        
        # Save the plot
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plot_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        plt.close()
        
        return {
            'result': 'Plot created successfully',
            'plot_path': save_path,
            'plot_base64': plot_base64
        }
        
    except Exception as e:
        plt.close('all')
        return {'error': str(e)}


@mcp.tool()
async def list_saved_plots(directory: str = "plots") -> Dict[str, Any]:
    """List all saved plots in the specified directory.
    
    Args:
        directory: Directory to search for plots (default: "plots")
    
    Returns:
        Dictionary with list of plot files and their details
    """
    try:
        plot_dir = Path(directory)
        if not plot_dir.exists():
            return {"plots": [], "message": f"Directory {directory} does not exist"}
        
        plot_files = []
        for file_path in plot_dir.glob("*.png"):
            plot_files.append({
                "filename": file_path.name,
                "path": str(file_path),
                "size_kb": file_path.stat().st_size / 1024,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            })
        
        plot_files.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "plots": plot_files,
            "total": len(plot_files),
            "directory": str(plot_dir.absolute())
        }
        
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def get_plot_image(plot_path: str) -> Dict[str, Any]:
    """Get a saved plot as base64 encoded image.
    
    Args:
        plot_path: Path to the plot file
    
    Returns:
        Dictionary with base64 encoded image
    """
    try:
        file_path = Path(plot_path)
        if not file_path.exists():
            return {"error": f"Plot file not found: {plot_path}"}
        
        with open(file_path, "rb") as f:
            plot_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            "plot_path": str(file_path),
            "plot_base64": plot_base64,
            "filename": file_path.name
        }
        
    except Exception as e:
        return {"error": str(e)}


# ==================== MCP Resources ====================

@mcp.resource("plot://example/line")
def example_line_plot() -> str:
    """Example of creating a line plot"""
    return """
    Example Line Plot:
    
    Request:
    {
        "query": "Create a line plot showing temperature over time",
        "data": {
            "time": [1, 2, 3, 4, 5],
            "temperature": [20, 22, 25, 23, 21]
        }
    }
    
    This will create a line plot with time on x-axis and temperature on y-axis.
    """


@mcp.resource("plot://example/scatter")
def example_scatter_plot() -> str:
    """Example of creating a scatter plot"""
    return """
    Example Scatter Plot:
    
    Request:
    {
        "query": "Create a scatter plot of height vs weight",
        "data": {
            "height": [160, 170, 180, 165, 175],
            "weight": [60, 70, 80, 65, 75]
        }
    }
    
    This will create a scatter plot showing the relationship between height and weight.
    """


@mcp.resource("plot://example/bar")
def example_bar_plot() -> str:
    """Example of creating a bar chart"""
    return """
    Example Bar Chart:
    
    Request:
    {
        "query": "Create a bar chart of sales by month",
        "data": {
            "months": ["Jan", "Feb", "Mar", "Apr"],
            "sales": [1000, 1500, 1200, 1800]
        }
    }
    
    This will create a bar chart showing sales for each month.
    """


# ==================== Main ====================

if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="stdio")  # Can also use "sse" or "http" with host and port
