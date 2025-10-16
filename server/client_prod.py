import asyncio
import nest_asyncio
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

# Load environment variables
load_dotenv()

# Allow nested event loops to prevent "Already running asyncio" errors
nest_asyncio.apply()

# Option 1: Use local servers (more reliable)
USE_LOCAL_SERVERS = False

if USE_LOCAL_SERVERS:
    # Use local servers from mcpconfig.json
    config_file = "server/mcpconfig.json"
else:
    # Use remote servers from config_client.json
    config_file = "server/config_client.json"

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
        client = MCPClient.from_config_file(config_file)
        
        # Initialize GPT as the LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",  # Use gpt-4o-mini for cost efficiency
            temperature=0.7
        )
        
        # Create MCP agent with GPT integration
        agent = MCPAgent(
            llm=llm,
            client=client,
            max_steps=15,
            memory_enabled=True,  # Enable built-in conversation memory
        )

        print("\n===== Interactive MCP Chat with GPT =====")
        if USE_LOCAL_SERVERS:
            print("Connected to local servers:")
            print("- Weather server")
            print("- Google Sheets server") 
            print("- RAG server")
        else:
            print("Connected to remote servers:")
            print("- Weather: https://mcp-poc-multi-tool.fastmcp.app/mcp")
            print("- RAG: https://mcp-poc-rag.fastmcp.app/mcp") 
            print("- Expense Tracker: https://expense-tracker-by-niloy.fastmcp.app/mcp")
        
        print("\nType 'exit' or 'quit' to end the conversation")
        print("Type 'clear' to clear conversation history")
        print("Type 'tools' to list available tools")
        print("==========================================\n")

        # Main chat loop
        while True:
            # Get user input
            user_input = input("\nYou: ")

            # Check for exit command
            if user_input.lower() in ["exit", "quit"]:
                print("Ending conversation...")
                break

            # Check for clear history command
            if user_input.lower() == "clear":
                agent.clear_conversation_history()
                print("Conversation history cleared.")
                continue
            
            # Check for tools command
            if user_input.lower() == "tools":
                print("\nListing available tools...")
                response = await agent.run("What tools are available? List them with their descriptions.")
                print(f"\nAssistant: {response}")
                continue

            # Get response from agent
            print("\nAssistant: ", end="", flush=True)

            try:
                # Run the agent with the user input (memory handling is automatic)
                response = await agent.run(user_input)
                print(response)

            except Exception as e:
                print(f"\n❌ Error: {e}")
                if "405" in str(e):
                    print("💡 Tip: Remote servers may be unavailable. Try using local servers instead.")

    except Exception as e:
        print(f"❌ Failed to initialize MCP client: {e}")
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