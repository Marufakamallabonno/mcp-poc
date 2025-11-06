# Graph Plotter MCP Server

An MCP (Model Context Protocol) server that provides advanced graph plotting capabilities using matplotlib and Azure OpenAI for intelligent plot generation.

## Features

### 🎨 Intelligent Plot Generation

- Natural language to plot generation using Azure OpenAI
- Automatically understands user intent and creates appropriate visualizations
- Supports complex plotting requirements with multiple data series

### 📊 Plot Types Supported

- Line plots
- Scatter plots
- Bar charts
- Histograms
- Pie charts (via LLM)
- Custom visualizations based on user descriptions

### 🛠️ Tools Available

1. **`create_plot`** - Generate plots using natural language

   - Uses Azure OpenAI to understand plotting requirements
   - Automatically retries on errors
   - Supports custom data and execution methods

2. **`create_simple_plot`** - Direct plot creation without LLM

   - Fast, deterministic plot generation
   - Supports line, scatter, bar, and histogram types
   - No AI required

3. **`list_saved_plots`** - List all saved plot files

   - Shows file details, sizes, and timestamps
   - Useful for managing generated plots

4. **`get_plot_image`** - Retrieve saved plots as base64
   - Returns plot images for display or embedding
   - Useful for web applications

## Installation

### Prerequisites

```bash
# Install required packages
pip install fastmcp matplotlib langchain-openai python-dotenv

# Or use the project's pyproject.toml
uv sync
```

### Environment Variables

Create a `.env` file with your Azure OpenAI credentials:

```env
PIVOTLY_AZURE_OPENAI_API_KEY=your-api-key-here
PIVOTLY_AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
```

## Usage

### Running the Server

#### Option 1: Stdio Transport (for local testing)

```bash
python server/graph_plotter.py
```

#### Option 2: HTTP Transport

```bash
python server/graph_plotter.py --transport http --port 8003
```

#### Option 3: Using MCP Configuration

```bash
# Using the configuration file
mcp run --config server/graph_plotter_config.json graph_plotter
```

### Testing the Server

Run the test client to verify everything works:

```bash
python server/test_graph_plotter.py
```

### Using with an MCP Client

#### Example 1: Create a plot with natural language

```python
from fastmcp import Client

async with Client({"command": "python", "args": ["server/graph_plotter.py"]}) as client:
    result = await client.call_tool(
        "create_plot",
        {
            "query": "Create a beautiful line plot showing sales growth over 12 months",
            "data": {
                "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                "sales": [100, 120, 140, 135, 160, 180,
                         195, 210, 225, 240, 260, 280]
            }
        }
    )
    print(f"Plot saved to: {result['plot_path']}")
```

#### Example 2: Create a simple plot directly

```python
result = await client.call_tool(
    "create_simple_plot",
    {
        "plot_type": "scatter",
        "x_data": [1, 2, 3, 4, 5],
        "y_data": [2, 4, 6, 8, 10],
        "title": "Linear Relationship",
        "x_label": "X Values",
        "y_label": "Y Values"
    }
)
```

## Architecture

The server uses a combination of:

1. **FastMCP** - For the MCP server implementation
2. **Matplotlib** - For plot generation
3. **LangGraph** - For the plotting workflow (from original agent_plot.py)
4. **Azure OpenAI** - For understanding natural language plot requests
5. **Subprocess isolation** - Optional secure execution of plotting code

## Execution Methods

The server supports two execution methods:

1. **`exec` mode** (default) - Faster, runs in the same process
2. **`subprocess` mode** - More secure, runs plotting code in isolation

## Output Format

All plotting tools return:

```json
{
  "result": "Plot created successfully",
  "plot_path": "plots/generated_plot_20241106_150000.png",
  "plot_base64": "iVBORw0KGgoAAAANS..." // Base64 encoded image
}
```

## Error Handling

- Automatic retry mechanism (up to 3 attempts by default)
- Clear error messages for debugging
- Graceful fallback for missing Azure credentials (simple plots still work)

## Directory Structure

```
server/
├── graph_plotter.py           # Main MCP server
├── test_graph_plotter.py      # Test client
├── graph_plotter_config.json  # MCP configuration
└── GRAPH_PLOTTER_README.md    # This file

plots/                         # Generated plots directory (auto-created)
├── generated_plot_*.png      # LLM-generated plots
└── simple_plot_*.png          # Direct plots
```

## Troubleshooting

### Azure OpenAI Connection Issues

- Verify your API key and endpoint in `.env`
- Ensure the endpoint doesn't have a trailing slash
- Check that your deployment name is "gpt-5-mini" or update in code

### Plot Generation Failures

- Check that matplotlib is installed: `pip install matplotlib`
- Verify the plots directory has write permissions
- For subprocess mode, ensure Python is in PATH

### MCP Connection Issues

- For stdio: Check that the server starts without errors
- For HTTP: Verify the port is not in use
- Check firewall settings if using remote connections

## Advanced Usage

### Custom Plot Types

The LLM can generate complex custom visualizations. Example:

```python
result = await client.call_tool(
    "create_plot",
    {
        "query": "Create a subplot with 4 different charts showing quarterly data analysis",
        "data": {
            "q1": [10, 20, 30],
            "q2": [15, 25, 35],
            "q3": [20, 30, 40],
            "q4": [25, 35, 45]
        }
    }
)
```

### Batch Processing

Process multiple plots efficiently:

```python
plots_to_create = [
    {"query": "Line plot of dataset A", "data": {...}},
    {"query": "Bar chart of dataset B", "data": {...}},
    {"query": "Scatter plot of dataset C", "data": {...}}
]

for plot_config in plots_to_create:
    result = await client.call_tool("create_plot", plot_config)
    print(f"Created: {result['plot_path']}")
```

## License

This server is part of the MCP POC project and follows the project's licensing terms.
