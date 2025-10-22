#!/usr/bin/env python3
"""
JSON State MCP Server
A Model Context Protocol (MCP) server for managing JSON state operations.
Following the pattern of expense_tracker.py
"""

import json
import copy
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("JSON State Manager")

# Path to the JSON state file
STATE_FILE = Path(__file__).parent / "state.json"
HISTORY_FILE = Path(__file__).parent / "history.jsonl"

def load_state() -> Dict[str, Any]:
    """Load the current state from file"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_state(state: Dict[str, Any]) -> None:
    """Save the current state to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def log_change(operation: str, before: Dict, after: Dict, details: Dict) -> None:
    """Log changes to history file"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "details": details,
        "before": before,
        "after": after,
        "diff": generate_diff(before, after)
    }
    
    with open(HISTORY_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def generate_diff(before: Dict, after: Dict) -> Dict:
    """Generate a diff between two states"""
    diff = {
        "added": {},
        "removed": {},
        "modified": {}
    }
    
    def flatten_dict(d: Dict, parent_key: str = '') -> Dict:
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    flat_before = flatten_dict(before)
    flat_after = flatten_dict(after)
    
    # Find added keys
    for key in flat_after:
        if key not in flat_before:
            diff["added"][key] = flat_after[key]
    
    # Find removed keys
    for key in flat_before:
        if key not in flat_after:
            diff["removed"][key] = flat_before[key]
    
    # Find modified values
    for key in flat_before:
        if key in flat_after and flat_before[key] != flat_after[key]:
            diff["modified"][key] = {
                "old": flat_before[key],
                "new": flat_after[key]
            }
    
    return diff

def get_nested_value(data: Dict, path: str) -> Any:
    """Get a value from nested dictionary using dot notation"""
    keys = path.split('.')
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current

def set_nested_value(data: Dict, path: str, value: Any) -> Dict:
    """Set a value in nested dictionary using dot notation"""
    keys = path.split('.')
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return data

def delete_nested_key(data: Dict, path: str) -> Dict:
    """Delete a key from nested dictionary using dot notation"""
    keys = path.split('.')
    current = data
    for key in keys[:-1]:
        if key not in current:
            return data
        current = current[key]
    if keys[-1] in current:
        del current[keys[-1]]
    return data

@mcp.tool()
def update_value(path: str, value: Any) -> Dict[str, Any]:
    """
    Update a value in the JSON state.
    
    Args:
        path: Dot-separated path to the value (e.g., 'specs.Overview.description')
        value: New value to set (can be string, number, boolean, list, or dict)
    
    Returns:
        Updated state and operation details
    """
    before_state = load_state()
    after_state = copy.deepcopy(before_state)
    
    # Handle JSON string values
    if isinstance(value, str):
        try:
            # Try to parse as JSON if it looks like JSON
            if value.strip().startswith('{') or value.strip().startswith('['):
                value = json.loads(value)
        except:
            pass  # Keep as string if not valid JSON
    
    set_nested_value(after_state, path, value)
    save_state(after_state)
    
    details = {
        "path": path,
        "old_value": get_nested_value(before_state, path),
        "new_value": value
    }
    
    log_change("update_value", before_state, after_state, details)
    
    return {
        "success": True,
        "operation": "update_value",
        "path": path,
        "new_value": value,
        "state": after_state
    }

@mcp.tool()
def add_key(parent_path: str, key: str, value: Any) -> Dict[str, Any]:
    """
    Add a new key to the JSON state.
    
    Args:
        parent_path: Dot-separated path to parent object (empty string for root)
        key: Name of the new key
        value: Value for the new key
    
    Returns:
        Updated state and operation details
    """
    before_state = load_state()
    after_state = copy.deepcopy(before_state)
    
    # Handle JSON string values
    if isinstance(value, str):
        try:
            if value.strip().startswith('{') or value.strip().startswith('['):
                value = json.loads(value)
        except:
            pass
    
    if parent_path:
        parent = get_nested_value(after_state, parent_path)
        if parent is None:
            # Create parent path if it doesn't exist
            set_nested_value(after_state, parent_path, {})
            parent = get_nested_value(after_state, parent_path)
        
        if isinstance(parent, dict):
            parent[key] = value
    else:
        after_state[key] = value
    
    save_state(after_state)
    
    details = {
        "parent_path": parent_path,
        "key": key,
        "value": value
    }
    
    log_change("add_key", before_state, after_state, details)
    
    return {
        "success": True,
        "operation": "add_key",
        "parent_path": parent_path,
        "key": key,
        "value": value,
        "state": after_state
    }

@mcp.tool()
def delete_key(path: str) -> Dict[str, Any]:
    """
    Delete a key from the JSON state.
    
    Args:
        path: Dot-separated path to the key to delete
    
    Returns:
        Updated state and operation details
    """
    before_state = load_state()
    after_state = copy.deepcopy(before_state)
    
    old_value = get_nested_value(before_state, path)
    delete_nested_key(after_state, path)
    save_state(after_state)
    
    details = {
        "path": path,
        "deleted_value": old_value
    }
    
    log_change("delete_key", before_state, after_state, details)
    
    return {
        "success": True,
        "operation": "delete_key",
        "path": path,
        "deleted_value": old_value,
        "state": after_state
    }

@mcp.tool()
def rename_key(path: str, new_name: str) -> Dict[str, Any]:
    """
    Rename a key in the JSON state.
    
    Args:
        path: Dot-separated path to the key to rename
        new_name: New name for the key
    
    Returns:
        Updated state and operation details
    """
    before_state = load_state()
    after_state = copy.deepcopy(before_state)
    
    keys = path.split('.')
    if len(keys) > 1:
        parent_path = '.'.join(keys[:-1])
        parent = get_nested_value(after_state, parent_path)
        old_key = keys[-1]
    else:
        parent = after_state
        old_key = keys[0]
    
    if isinstance(parent, dict) and old_key in parent:
        parent[new_name] = parent.pop(old_key)
        save_state(after_state)
        
        details = {
            "path": path,
            "old_name": old_key,
            "new_name": new_name
        }
        
        log_change("rename_key", before_state, after_state, details)
        
        return {
            "success": True,
            "operation": "rename_key",
            "path": path,
            "new_name": new_name,
            "state": after_state
        }
    
    return {
        "success": False,
        "error": f"Key not found at path: {path}",
        "state": before_state
    }

@mcp.tool()
def get_state() -> Dict[str, Any]:
    """
    Get the current JSON state.
    
    Returns:
        Current state
    """
    state = load_state()
    return {
        "success": True,
        "state": state
    }

@mcp.tool()
def reset_state(initial_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Reset the JSON state to initial or provided state.
    
    Args:
        initial_state: Optional initial state to set (if None, uses empty dict)
    
    Returns:
        New state
    """
    before_state = load_state()
    after_state = initial_state if initial_state else {}
    
    save_state(after_state)
    
    details = {
        "reset_to": "provided_state" if initial_state else "empty"
    }
    
    log_change("reset_state", before_state, after_state, details)
    
    return {
        "success": True,
        "operation": "reset_state",
        "state": after_state
    }

@mcp.tool()
def get_history(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the history of changes.
    
    Args:
        limit: Maximum number of entries to return
    
    Returns:
        List of history entries
    """
    if not HISTORY_FILE.exists():
        return []
    
    entries = []
    with open(HISTORY_FILE, 'r') as f:
        for line in f:
            entries.append(json.loads(line))
    
    # Return the most recent entries
    return entries[-limit:]

def main():
    """Run the MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()
