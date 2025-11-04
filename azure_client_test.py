import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

subscription_key = os.getenv("PIVOTLY_AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("PIVOTLY_AZURE_OPENAI_ENDPOINT")

client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=azure_endpoint,
    api_key=subscription_key
)

if client:
    print("Client created successfully")
else:
    print("Client creation failed")