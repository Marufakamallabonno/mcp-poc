
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import os

load_dotenv()

subscription_key = os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("PIVOTLY_AZURE_OPENAI_ENDPOINT")

# Debug: Check if values are loaded
if not subscription_key:
    print("ERROR: PIVOTLY_AZURE_OPENAI_API_KEY not found in environment")
if not azure_endpoint:
    print("ERROR: PIVOTLY_AZURE_OPENAI_ENDPOINT not found in environment")

# Ensure endpoint doesn't have trailing slash
azure_endpoint = azure_endpoint.rstrip('/')

# Use AzureChatOpenAI for Azure OpenAI endpoints
# The deployment_name should match your Azure OpenAI deployment name
llm = AzureChatOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=subscription_key,
    api_version="2024-12-01-preview",
    deployment_name="gpt-5-mini"  # This should match your deployment name in Azure
)
    
if llm:
    print("LLM created successfully")
    # Use proper message format for invoke
    response = llm.invoke([HumanMessage(content="Tell me a joke and include some emojis")])
    print(f"\nResponse: {response.content}")
else:
    print("LLM creation failed")