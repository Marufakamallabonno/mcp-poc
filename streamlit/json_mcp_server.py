#!/usr/bin/env python
"""
JSON State MCP Server
A Model Context Protocol (MCP) server for manipulating JSON state.
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path
from deepdiff import DeepDiff
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("JSON State Manager")

# In-memory JSON state
current_state: Dict[str, Any] = {}
state_history: List[Dict[str, Any]] = []

# File path for persistent storage
STATE_FILE = Path("streamlit/state.json")

def load_state():
    """Load state from file if exists"""
    global current_state
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            current_state = json.load(f)
    return current_state

def save_state():
    """Save current state to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(current_state, f, indent=2)
    return current_state

def get_json_diff(old_state: Dict, new_state: Dict) -> Dict:
    """Get the difference between two JSON states"""
    diff = DeepDiff(old_state, new_state, verbose_level=2)
    return diff.to_dict() if diff else {}

@mcp.tool()
def get_current_state() -> Dict[str, Any]:
    """
    Get the current JSON state.
    
    Returns:
        Current JSON state
    """
    global current_state
    if not current_state:
        load_state()
    return current_state

@mcp.tool()
def set_initial_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set the initial JSON state.
    
    Args:
        state: The initial JSON state to set
    
    Returns:
        The newly set state
    """
    global current_state, state_history
    
    # Save previous state to history
    if current_state:
        state_history.append(current_state.copy())
    
    current_state = state
    save_state()
    
    return {
        "success": True,
        "state": current_state,
        "message": "Initial state set successfully"
    }

@mcp.tool()
def update_value(path: str, value: Any) -> Dict[str, Any]:
    """
    Update a value in the JSON state using dot notation path.
    
    Args:
        path: Dot notation path to the value (e.g., "specs.Overview.description")
        value: New value to set
    
    Returns:
        Updated state with diff information
    """
    global current_state, state_history
    
    if not current_state:
        load_state()
    
    # Save current state to history
    old_state = json.loads(json.dumps(current_state))
    state_history.append(old_state)
    
    # Parse the path and update the value
    keys = path.split('.')
    current = current_state
    
    try:
        # Navigate to the parent of the target
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Update the value
        old_value = current.get(keys[-1])
        current[keys[-1]] = value
        
        # Save state
        save_state()
        
        # Get diff
        diff = get_json_diff(old_state, current_state)
        
        return {
            "success": True,
            "path": path,
            "old_value": old_value,
            "new_value": value,
            "state": current_state,
            "diff": diff,
            "message": f"Updated {path} successfully"
        }
        
    except Exception as e:
        # Restore old state on error
        current_state = old_state
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to update {path}"
        }

@mcp.tool()
def add_key(parent_path: str, key: str, value: Any) -> Dict[str, Any]:
    """
    Add a new key-value pair to the JSON state.
    
    Args:
        parent_path: Dot notation path to the parent object (empty string for root)
        key: New key to add
        value: Value for the new key
    
    Returns:
        Updated state with diff information
    """
    global current_state, state_history
    
    if not current_state:
        load_state()
    
    # Save current state to history
    old_state = json.loads(json.dumps(current_state))
    state_history.append(old_state)
    
    try:
        if parent_path:
            # Navigate to the parent
            keys = parent_path.split('.')
            current = current_state
            for k in keys:
                if k not in current:
                    current[k] = {}
                current = current[k]
        else:
            current = current_state
        
        # Add the new key
        current[key] = value
        
        # Save state
        save_state()
        
        # Get diff
        diff = get_json_diff(old_state, current_state)
        
        return {
            "success": True,
            "parent_path": parent_path,
            "key": key,
            "value": value,
            "state": current_state,
            "diff": diff,
            "message": f"Added key '{key}' successfully"
        }
        
    except Exception as e:
        # Restore old state on error
        current_state = old_state
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to add key '{key}'"
        }

@mcp.tool()
def delete_key(path: str) -> Dict[str, Any]:
    """
    Delete a key from the JSON state.
    
    Args:
        path: Dot notation path to the key to delete
    
    Returns:
        Updated state with diff information
    """
    global current_state, state_history
    
    if not current_state:
        load_state()
    
    # Save current state to history
    old_state = json.loads(json.dumps(current_state))
    state_history.append(old_state)
    
    keys = path.split('.')
    
    try:
        # Navigate to the parent
        current = current_state
        for key in keys[:-1]:
            current = current[key]
        
        # Delete the key
        deleted_value = current.pop(keys[-1], None)
        
        # Save state
        save_state()
        
        # Get diff
        diff = get_json_diff(old_state, current_state)
        
        return {
            "success": True,
            "path": path,
            "deleted_value": deleted_value,
            "state": current_state,
            "diff": diff,
            "message": f"Deleted {path} successfully"
        }
        
    except Exception as e:
        # Restore old state on error
        current_state = old_state
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to delete {path}"
        }

@mcp.tool()
def rename_key(path: str, new_name: str) -> Dict[str, Any]:
    """
    Rename a key in the JSON state.
    
    Args:
        path: Dot notation path to the key to rename
        new_name: New name for the key
    
    Returns:
        Updated state with diff information
    """
    global current_state, state_history
    
    if not current_state:
        load_state()
    
    # Save current state to history
    old_state = json.loads(json.dumps(current_state))
    state_history.append(old_state)
    
    keys = path.split('.')
    
    try:
        # Navigate to the parent
        current = current_state
        for key in keys[:-1]:
            current = current[key]
        
        # Rename the key
        old_key = keys[-1]
        if old_key in current:
            current[new_name] = current.pop(old_key)
            
            # Save state
            save_state()
            
            # Get diff
            diff = get_json_diff(old_state, current_state)
            
            return {
                "success": True,
                "old_path": path,
                "new_name": new_name,
                "state": current_state,
                "diff": diff,
                "message": f"Renamed '{old_key}' to '{new_name}' successfully"
            }
        else:
            return {
                "success": False,
                "message": f"Key '{old_key}' not found"
            }
            
    except Exception as e:
        # Restore old state on error
        current_state = old_state
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to rename {path}"
        }

@mcp.tool()
def update_multiple(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply multiple updates to the JSON state in a single operation.
    
    Args:
        updates: List of update operations, each containing 'path' and 'value'
    
    Returns:
        Updated state with diff information
    """
    global current_state, state_history
    
    if not current_state:
        load_state()
    
    # Save current state to history
    old_state = json.loads(json.dumps(current_state))
    state_history.append(old_state)
    
    results = []
    
    try:
        for update in updates:
            path = update.get('path')
            value = update.get('value')
            
            if not path:
                continue
            
            keys = path.split('.')
            current = current_state
            
            # Navigate to the parent
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Update the value
            old_value = current.get(keys[-1])
            current[keys[-1]] = value
            
            results.append({
                "path": path,
                "old_value": old_value,
                "new_value": value
            })
        
        # Save state
        save_state()
        
        # Get diff
        diff = get_json_diff(old_state, current_state)
        
        return {
            "success": True,
            "updates": results,
            "state": current_state,
            "diff": diff,
            "message": f"Applied {len(results)} updates successfully"
        }
        
    except Exception as e:
        # Restore old state on error
        current_state = old_state
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to apply updates"
        }

@mcp.tool()
def get_state_history() -> List[Dict[str, Any]]:
    """
    Get the history of state changes.
    
    Returns:
        List of previous states
    """
    return state_history

@mcp.tool()
def clear_state() -> Dict[str, Any]:
    """
    Clear the current JSON state.
    
    Returns:
        Empty state
    """
    global current_state, state_history
    
    # Save current state to history
    if current_state:
        state_history.append(current_state.copy())
    
    current_state = {}
    save_state()
    
    return {
        "success": True,
        "state": current_state,
        "message": "State cleared successfully"
    }

def main():
    """Run the MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()
