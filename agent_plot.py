from typing import TypedDict, Dict, List, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os
import ast
import json
from pathlib import Path
import subprocess
import tempfile
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from datetime import datetime
from langchain_openai import AzureChatOpenAI

load_dotenv()

class GraphState(TypedDict, total=False):
    """State schema for the LangGraph workflow for graph plotting.
    
    Note: Using total=False makes all fields optional at type-checking level,
    but in practice, all fields except 'test_data' are typically provided.
    The code uses .get() with defaults to handle optional fields safely.
    """
    error: str
    messages: List[tuple]  # Changed from 'message' to 'messages' and to List[tuple]
    generation: str
    iterations: int
    execution_method: str
    test_data: Dict[str, Any]  # User-provided test data for code execution (optional, defaults to {'numbers': [1, 2, 3]})
    plot_path: str  # Path where the generated plot is saved
    
    
def validate_code(code_str: str) -> bool:
    """Validate the code string."""
    try:
        ast.parse(code_str)
        return True
    except Exception:
        return False
    
def execute_with_exec(code_str: str, test_data: Dict[str, Any], plot_path: str = None) -> Dict[str, Any]:
    """Execute the code string with the test data for plotting.
    
    Args:
        code_str: Python code to execute (should create a plot)
        test_data: Data variables available in the namespace
        plot_path: Path where to save the plot
    """
    if not validate_code(code_str):
        raise ValueError("Invalid code string")
    
    if plot_path is None:
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_path = f"plots/generated_plot_{timestamp}.png"
    
    # Ensure plots directory exists
    plot_dir = Path(plot_path).parent
    plot_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create namespace with test_data and matplotlib
        namespace = {
            **test_data,
            'plt': plt,
            'matplotlib': matplotlib,
            'plot_path': plot_path
        }
        
        print("Executing plot code...")
        print(f"Test data: {test_data}")
        print(f"Plot will be saved to: {plot_path}")
        
        # Execute the code
        exec(code_str, namespace)
        
        # Save the plot
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close()  # Close the figure to free memory
        
        # Return success with plot path
        return {'result': 'Plot created successfully', 'plot_path': plot_path}
    except Exception as e:
        # Clean up any open figures
        plt.close('all')
        return {'error': str(e)}
    
def execute_with_subprocess(code_str: str, test_data: Dict[str, Any], plot_path: str = None) -> Dict[str, Any]:
    """Execute the code string with the test data for plotting using subprocess.
    
    Args:
        code_str: Python code to execute (should create a plot)
        test_data: Data variables available in the namespace
        plot_path: Path where to save the plot
    """
    if not validate_code(code_str):
        raise ValueError("Invalid code string")
    
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
            # Create a script that unpacks test_data and creates plot
            script_content = (
                f"import json\n"
                f"import sys\n"
                f"import os\n"
                f"import matplotlib\n"
                f"matplotlib.use('Agg')\n"
                f"import matplotlib.pyplot as plt\n"
                f"from pathlib import Path\n"
                f"\n"
                f"input_data = json.loads(sys.argv[1])\n"
                f"plot_path = sys.argv[2]\n"
                f"\n"
                f"# Unpack all test_data keys as local variables\n"
                f"for key, value in input_data.items():\n"
                f"    globals()[key] = value\n"
                f"\n"
                f"# Execute the plot code\n"
                f"{code_str}\n"
                f"\n"
                f"# Save the plot\n"
                f"plt.savefig(plot_path, dpi=150, bbox_inches='tight')\n"
                f"plt.close()\n"
                f"\n"
                f"# Return success with plot path\n"
                f"print(json.dumps({{'result': 'Plot created successfully', 'plot_path': plot_path}}))\n"
            )
            
            temp_file.write(script_content)
            script_path = temp_file.name
        
        input_json = json.dumps(test_data)
        result = subprocess.run(
            ['python', script_path, input_json, plot_path],
            capture_output=True,
            text=True,
            check=False,  # Don't raise on error, check manually
            timeout=60  # Longer timeout for plot generation
        )
        
        if result.returncode != 0:
            error_msg = f"Subprocess failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f"\nSTDERR: {result.stderr}"
            if result.stdout:
                error_msg += f"\nSTDOUT: {result.stdout}"
            return {'error': error_msg}
        
        # Try to parse the JSON output
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            return {'error': f"Failed to parse JSON output: {e}\nOutput: {result.stdout}"}
            
    except subprocess.TimeoutExpired:
        return {'error': 'Subprocess execution timed out after 60 seconds'}
    except Exception as e:
        return {'error': f"Subprocess execution error: {str(e)}"}
    finally:
        if script_path and Path(script_path).exists():
            try:
                Path(script_path).unlink()
            except Exception:
                pass  # Ignore cleanup errors

def generate(state: GraphState) -> GraphState:
    messages = state.get("messages", [])
    error = state.get("error", "")
    iterations = state.get("iterations", 0)
    
    # Validate messages
    if not messages or len(messages) == 0:
        return {
            "generation": "",
            "messages": messages,
            "error": "No messages provided",
            "iterations": iterations,
            "execution_method": state.get("execution_method", "exec"),
            "test_data": state.get("test_data"),
            "plot_path": state.get("plot_path", ""),
        }
    
    # Get question from first message
    question = messages[0][1] if isinstance(messages[0], tuple) and len(messages[0]) > 1 else str(messages[0])
    
    # Get test_data structure to inform the LLM about available variables
    test_data = state.get("test_data")
    test_data_context = ""
    if test_data:
        # Create a description of available variables from test_data
        variable_descriptions = []
        for key, value in test_data.items():
            if isinstance(value, list):
                variable_descriptions.append(f"  - {key}: a list with {len(value)} items (example: {value[:3]}{'...' if len(value) > 3 else ''})")
            elif isinstance(value, dict):
                variable_descriptions.append(f"  - {key}: a dictionary with keys: {list(value.keys())[:5]}{'...' if len(value) > 5 else ''}")
            else:
                variable_descriptions.append(f"  - {key}: {type(value).__name__} (value: {value})")
        
        test_data_context = "\n\nAVAILABLE VARIABLES FROM TEST DATA:\n" + "\n".join(variable_descriptions) + "\n\nIMPORTANT: Use these exact variable names in your code. The code will be executed with these variables already available."
    else:
        test_data_context = "\n\nDEFAULT TEST DATA: The code will be executed with a variable 'numbers' containing [1, 2, 3]. Use this variable name in your code."
    
    code_gen_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a coding assistant specialized in creating data visualizations. 
         The user wants you to generate Python code that creates a plot/graph.
         
         IMPORTANT REQUIREMENTS:
         1. You MUST use matplotlib.pyplot (imported as 'plt') to create the plot
         2. The code should be complete and executable - it should create and configure the plot
         3. DO NOT call plt.savefig() or plt.show() - that will be handled automatically
         4. Include proper labels, titles, and styling to make the plot informative
         5. Use the variables from test_data to create the plot
         6. If there were previous errors, fix them
         
         Example of good code:
         ```
         import matplotlib.pyplot as plt
         plt.figure(figsize=(10, 6))
         plt.plot(x_values, y_values, marker='o', linestyle='-', linewidth=2)
         plt.xlabel('X Axis Label')
         plt.ylabel('Y Axis Label')
         plt.title('Plot Title')
         plt.grid(True, alpha=0.3)
         plt.legend()
         ```
         
         {test_data_context}"""),
        ("human", "{question}"),
        ("human", "Previous errors if any: {error}")
    ])
      

    subscription_key = os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("PIVOTLY_AZURE_OPENAI_ENDPOINT")
    
    # Debug: Check if values are loaded
    if not subscription_key:
        print("ERROR: PIVOTLY_AZURE_OPENAI_API_KEY not found in environment")
        return {
            "generation": "",
            "messages": messages,
            "error": "Azure API key not found",
            "iterations": iterations,
            "execution_method": state.get("execution_method", "exec"),
            "test_data": state.get("test_data"),
            "plot_path": state.get("plot_path", ""),
        }
    
    if not azure_endpoint:
        print("ERROR: PIVOTLY_AZURE_OPENAI_ENDPOINT not found in environment")
        return {
            "generation": "",
            "messages": messages,
            "error": "Azure endpoint not found",
            "iterations": iterations,
            "execution_method": state.get("execution_method", "exec"),
            "test_data": state.get("test_data"),
            "plot_path": state.get("plot_path", ""),
        }

    # Ensure endpoint doesn't have trailing slash
    azure_endpoint = azure_endpoint.rstrip('/')

    # Use AzureChatOpenAI for Azure OpenAI endpoints
    # The deployment_name should match your Azure OpenAI deployment name
    try:
        llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=subscription_key,
            api_version="2024-12-01-preview",
            deployment_name="gpt-5-mini"  # This should match your deployment name in Azure
        )
    except Exception as e:
        print(f"Failed to create LLM: {e}")
        return {
            "generation": "",
            "messages": messages,
            "error": f"LLM creation failed: {str(e)}",
            "iterations": iterations,
            "execution_method": state.get("execution_method", "exec"),
            "test_data": state.get("test_data"),
            "plot_path": state.get("plot_path", ""),
        }
        
    if llm:
        print("LLM created successfully")
    else:
        print("LLM creation failed")
    
    # Format the prompt with the actual values including test_data context
    formatted_messages = code_gen_prompt.format_messages(
        question=question, 
        error=error,
        test_data_context=test_data_context
    )
    
    try:
        # Invoke the LLM with properly formatted messages
        response = llm.invoke(formatted_messages)
        print(f"Attempt {iterations + 1}")
        return {
            "generation": response.content,
            "messages": messages,
            "error": "",
            "iterations": iterations,
            "execution_method": state.get("execution_method", "exec"),
            "test_data": state.get("test_data"),
            "plot_path": state.get("plot_path", ""),
        }
    except Exception as e:
        print(f"Error invoking LLM: {e}")
        return {
            "generation": "",
            "messages": messages,
            "error": f"LLM invocation failed: {str(e)}",
            "iterations": iterations,
            "execution_method": state.get("execution_method", "exec"),
            "test_data": state.get("test_data"),
            "plot_path": state.get("plot_path", ""),
        }
    
    
def code_check(state: GraphState) -> GraphState:
    code_solution = state.get("generation", "")
    iterations = state.get("iterations", 0)
    # Use user-provided test_data if available, otherwise use default
    # Handle None case explicitly
    test_data = state.get("test_data")
    if test_data is None:
        test_data = {'numbers': [1, 2, 3]}
    
    execution_method = (execute_with_subprocess if state.get("execution_method") == "subprocess" else execute_with_exec)
    
    # Generate plot path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_path = state.get("plot_path") or f"plots/generated_plot_{timestamp}.png"
    
    # Clean the code solution - remove markdown code blocks if present
    code_solution_clean = code_solution.strip()
    if code_solution_clean.startswith("```"):
        # Remove markdown code blocks
        lines = code_solution_clean.split("\n")
        # Remove first line (```python or ```)
        lines = lines[1:]
        # Remove last line (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code_solution_clean = "\n".join(lines).strip()
    
    # For plot generation, we want the full code, not just the last line
    # But remove plt.savefig() and plt.show() if present
    lines = code_solution_clean.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip plt.savefig() and plt.show() calls
        if "plt.savefig" in stripped or "plt.show" in stripped:
            continue
        # Keep the line
        cleaned_lines.append(line)
    code_solution_clean = "\n".join(cleaned_lines).strip()
    
    try:
        result = execution_method(code_solution_clean, test_data, plot_path)
        if "error" in result:
            print(f"Attempt {iterations + 1} failed with error: {result['error']}")
            print(f"Generated code was: {code_solution_clean[:200]}...")  # Show first 200 chars
            return {**state, "error": result.get('error', 'Execution failed'), "iterations": iterations + 1, "plot_path": plot_path}
        else:
            saved_plot_path = result.get('plot_path', plot_path)
            print(f"Attempt {iterations + 1} succeeded!")
            print(f"Plot saved to: {saved_plot_path}")
            return {**state, "error": "no", "iterations": iterations + 1, "plot_path": saved_plot_path}
    except Exception as e:
        print(f"Attempt {iterations + 1} failed with error: {str(e)}")
        print(f"Generated code was: {code_solution_clean[:200]}...")
        return {**state, "error": str(e), "iterations": iterations + 1, "plot_path": plot_path}

def should_retry(state: GraphState) -> str:
    error = state.get("error", "")
    iterations = state.get("iterations", 0)
    
    if error == "no":
        return "END"
    if iterations < 3:
        print(f"Retrying after attempt {iterations}")
        return "generate"
    print(f"Giving up after {iterations} attempts")
    return "END"


workflow = StateGraph(GraphState)
workflow.add_node("generate", generate)
workflow.add_node("code_check", code_check)
# Should_retry is used in conditional edges, not as a node
workflow.add_edge(START, "generate")
workflow.add_edge("generate", "code_check")

workflow.add_conditional_edges(
    "code_check",
    should_retry,
    {
        "generate": "generate",
        "END": END
    }
)

app = workflow.compile()

if __name__ == "__main__":
    # Test the agent with plot generation
    test_data = {
        "x_values": [2, 4, 6, 8, 10],
        "y_values": [1, 3, 5, 7, 9]
    }
    
    test_state = {
        "messages": [("human", "Create a line plot with x_values on x-axis and y_values on y-axis")],
        "error": "",
        "generation": "",
        "iterations": 0,
        "execution_method": "exec",
        "test_data": test_data
    }
    
    result = app.invoke(test_state)
    print("\n" + "="*50)
    print("Final result:")
    print("="*50)
    print(f"  Plot path: {result.get('plot_path', 'Not generated')}")
    print(f"  Error: {result.get('error', 'None')}")
    print(f"  Iterations: {result.get('iterations', 0)}")
    
    # Example with scatter plot
    print("\n" + "="*50)
    print("Example with scatter plot:")
    print("="*50)
    
    scatter_test_data = {
        "x": [1, 2, 3, 4, 5],
        "y": [2, 4, 6, 8, 10]
    }
    
    scatter_test_state = {
        "messages": [("human", "Create a scatter plot with x and y values")],
        "error": "",
        "generation": "",
        "iterations": 0,
        "execution_method": "subprocess",
        "test_data": scatter_test_data
    }
    
    result_scatter = app.invoke(scatter_test_state)
    print("\nFinal result with scatter plot:")
    print(f"  Plot path: {result_scatter.get('plot_path', 'Not generated')}")
    print(f"  Error: {result_scatter.get('error', 'None')}")
    print(f"  Iterations: {result_scatter.get('iterations', 0)}")