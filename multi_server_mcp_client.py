import asyncio
from mcp.types import Tool
import nest_asyncio
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
from fastmcp import Client
from openai import OpenAI
import json

# Load environment variables
load_dotenv()

# Allow nested event loops to prevent "Already running asyncio" errors
nest_asyncio.apply()




config = {
  "mcpServers": {
    "weather": {
      "transport": "http",
      "url": "https://mcp-poc-multi-tool.fastmcp.app/mcp"
    },
    "rag": {
      "transport": "http",
      "url": "https://mcp-poc-rag.fastmcp.app/mcp"
    },
    "expense_tracker": {
      "transport": "http",
      "url": "https://expense-tracker-by-niloy.fastmcp.app/mcp"
    }
  }
}

    
    
def llm_client(message:str):
    """
    Send a message to the LLM and return the response.
    """
    # Initialize the OpenAI client
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Send the message to the LLM
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system",
                    "content":"You are an intelligent assistant. You will execute tasks as prompted",
                    "role": "user", "content": message}],
        max_tokens=250,
        temperature=0.2
    )

    # Extract and return the response content
    return response.choices[0].message.content.strip()
    
    
    
def get_prompt_to_identify_tool_and_arguments(query, tools):
    tools_description = "\n".join([f"- {tool.name}, {tool.description}, {tool.inputSchema} " for tool in tools])
    
    return  ("You are a helpful assistant with access to these tools:\n\n"
                f"{tools_description}\n"
                
                "Choose the appropriate tool based on the user's question. \n"
                f"User's Question: {query}\n"
                        
                "If no tool is needed, reply directly.\n\n"
                "IMPORTANT: When you need to use a tool, you must ONLY respond with "                
                "the exact JSON object format below, nothing else:\n"
                "Keep the values in str "
                
                "{\n"
                '    "tool": "tool-name",\n'
                '    "arguments": {\n'
                '        "argument-name": "value"\n'
                "    }\n"
                "}\n\n")


async def main():
    """Run a chat using MCPAgent with GPT integration."""
    # Set up OpenAI API key
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key in the .env file")
        return
    
    server_type = "local" if USE_LOCAL_SERVERS else "remote"
    print(f"Initializing MCP client with {server_type} servers...")

    
    try:
        # Create MCP client from config file
        client = Client(config)
        async with client:
            print(f"Client has been initialized")
            
            print(f"Listing tools....")
            tool_objs = await client.list_tools()
            
            user_input = "show me all the expenses in table format"
            
            print(f"Thinking...")
            
            prompt = get_prompt_to_identify_tool_and_arguments(user_input,tool_objs)
            
            llm_response = llm_client(prompt)
            
            if llm_response.find("tool") != -1:
                tool_call = json.loads(llm_response)
                print(f"Calling {tool_call['tool']} tool.....")
                result = await client.call_tool(tool_call["tool"], arguments=tool_call["arguments"])
                final_response = llm_client(user_input + "\n\n" + result.content[0].text)
                print(f"Result: \n{final_response}")
            else:
                print(f"Response: \n{llm_response}")

    except Exception as e:
        print(f"Error: {e}")
        if "405" in str(e) or "HTTP" in str(e):
            print("\n💡 The remote servers are not accessible. Switching to local servers...")
            print("Please restart the application.")
        else:
            print("Make sure your configuration is correct and servers are accessible.")
        
    finally:
        # Clean up
        if 'client' in locals() and client and hasattr(client, 'sessions'):
            try:
                await client.close_all_sessions()
                print("\n✅ Sessions closed successfully")
            except:
                pass

if __name__ == "__main__":
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a task
            loop.create_task(main())
        else:
            # If loop exists but not running, run it
            loop.run_until_complete(main())
    except RuntimeError:
        # No event loop exists, create a new one
        asyncio.run(main())