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
from langchain_openai import AzureChatOpenAI

load_dotenv()

class GraphState(TypedDict, total=False):
    """State schema for the LangGraph workflow.
    
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
    
    
def validate_code(code_str: str) -> bool:
    """Validate the code string."""
    try:
        ast.parse(code_str)
        return True
    except Exception:
        return False
    
def execute_with_exec(code_str: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the code string with the test data."""
    if not validate_code(code_str):
        raise ValueError("Invalid code string")
    try:
        namespace = test_data
        print(f"Executing code: {code_str}")
        print(f"Test data: {test_data}")
        exec(f"result = {code_str}", namespace)
        return {'result': namespace['result']}
    except Exception as e:
        return {'error': str(e)}
    
def execute_with_subprocess(code_str: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the code string with the test data."""
    if not validate_code(code_str):
        raise ValueError("Invalid code string")
    
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as temp_file:
            # Create a generic script that unpacks test_data into local variables
            # This allows the code to access variables like 'numbers', 'data', etc.
            script_content = (
                f"import json\n"
                f"import sys\n"
                f"import os\n"
                f"input_data = json.loads(sys.argv[1])\n"
                f"# Unpack all test_data keys as local variables\n"
                f"for key, value in input_data.items():\n"
                f"    globals()[key] = value\n"
                f"result = {code_str}\n"
                f"print(json.dumps({{'result': result}}))\n"
            )
            
            temp_file.write(script_content)
            script_path = temp_file.name
        
        input_json = json.dumps(test_data)
        result = subprocess.run(
            ['python', script_path, input_json],
            capture_output=True,
            text=True,
            check=False,  # Don't raise on error, check manually
            timeout=30  # Add timeout to prevent hanging
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
        return {'error': 'Subprocess execution timed out after 30 seconds'}
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
        ("system", """You are a coding assistant. Answer the user question by providing executable Python code. The code must be a
         complete expression, for example:
         'sum(x**2 for x in numbers)'. Don't include variable initializations or test code,
         just the core expression. If there were previous errors, fix them.
         
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
    
    # Try to extract just the expression if the LLM generated more than needed
    # Sometimes LLM includes comments or extra code
    if "\n" in code_solution_clean:
        # If multiline, try to find the actual expression
        lines = [line.strip() for line in code_solution_clean.split("\n") if line.strip() and not line.strip().startswith("#")]
        if lines:
            # Take the last line that looks like an expression
            code_solution_clean = lines[-1]
    
    try:
        result = execution_method(code_solution_clean, test_data)
        if "error" in result:
            print(f"Attempt {iterations + 1} failed with error: {result['error']}")
            print(f"Generated code was: {code_solution_clean}")
            return {**state, "error": result.get('error', 'Execution failed'), "iterations": iterations + 1}
        else:
            print(f"Attempt {iterations + 1} succeeded with result: {result.get('result', 'No result')}")
            return {**state, "error": "no", "iterations": iterations + 1}
    except Exception as e:
        print(f"Attempt {iterations + 1} failed with error: {str(e)}")
        print(f"Generated code was: {code_solution_clean}")
        return {**state, "error": str(e), "iterations": iterations + 1}

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
    # Test the agent with default test data
    test_data = {
        "x_values": [2, 4, 6, 8, 10],
        "y_values": [1, 3, 5, 7, 9]
    }
    
    test_state = {
        "messages": [("human", "Write code that takes a list of numbers and returns their sum")],
        "error": "",
        "generation": "",
        "iterations": 0,
        "execution_method": "exec",
        "test_data": test_data
    }
    
    result = app.invoke(test_state)
    print("\nFinal result:")
    print(f"  Generation: {result.get('generation', 'No generation')}")
    print(f"  Error: {result.get('error', 'None')}")
    print(f"  Iterations: {result.get('iterations', 0)}")
    
    # Example with custom test data
    print("\n" + "="*50)
    print("Example with custom test data:")
    print("="*50)
    
    custom_test_state = {
        "messages": [("human", "Write code that calculates the sum of squares of numbers")],
        "error": "",
        "generation": "",
        "iterations": 0,
        "execution_method": "subprocess",
        "test_data": {'numbers': [5, 10, 15, 20]}  # Custom test data
    }
    
    result_custom = app.invoke(custom_test_state)
    print("\nFinal result with custom test data:")
    print(f"  Generation: {result_custom.get('generation', 'No generation')}")
    print(f"  Error: {result_custom.get('error', 'None')}")
    print(f"  Iterations: {result_custom.get('iterations', 0)}")