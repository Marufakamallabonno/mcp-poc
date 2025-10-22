#!/bin/bash

# Streamlit JSON State Chat Manager Runner Script
# Using the proper MCP client pattern

echo "🚀 Starting JSON State Chat Manager..."
echo "=================================="

# Check if .env file exists
if [ ! -f "../.env" ] && [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Please create a .env file with your OPENAI_API_KEY"
    echo "Example: OPENAI_API_KEY=sk-..."
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install dependencies if needed
echo "📦 Checking dependencies..."
pip install -q langchain langchain-openai openai mcp nest-asyncio python-dotenv streamlit

# Create initial state file if it doesn't exist
if [ ! -f "state.json" ]; then
    echo "📄 Creating initial state.json..."
    cat > state.json << 'EOF'
{
  "specs": {
    "Overview": {
      "description": "Pivotly Prompt enables structured use of generative AI within workflows using configurable prompt templates, variables, and model settings."
    },
    "PromptConfiguration": {
      "type": ["ReusablePrompt", "InlinePrompt"],
      "usage": "Define and manage prompts with variables, formatting, and AI model parameters."
    },
    "PromptAsConfigurableObject": {
      "PromptName": "Contract Submittal Analyzer",
      "PromptTemplate": "Extract submittal requirements from the following contract document: {{document_text}}",
      "Variables": ["document_text", "project_name"],
      "SecurityRules": "Internal use only",
      "LLMConfiguration": "OpenAI GPT-4",
      "OutputFormat": "JSON",
      "ResponseType": "StructuredText"
    },
    "Settings": {
      "temperature": 0.3,
      "model": "gpt-4"
    }
  }
}
EOF
fi

# Clear any existing history
> history.jsonl

echo "✅ Setup complete!"
echo ""
echo "🌐 Starting Streamlit app..."
echo "=================================="

# Run the Streamlit app
streamlit run chat_app.py --server.port 8501 --server.address localhost
