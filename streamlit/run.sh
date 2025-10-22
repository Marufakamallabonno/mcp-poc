#!/bin/bash

# Streamlit JSON Chat Manager Runner Script

echo "🔄 Starting JSON State Chat Manager..."
echo "=================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install -q streamlit langchain-openai python-dotenv deepdiff

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY not set in environment"
    echo "Please set it in your .env file or export it"
fi

# Run the Streamlit app
echo "Starting Streamlit app..."
echo "=================================="
streamlit run streamlit/chat_json_app.py --server.port 8501 --server.headless true
