# agentic_docker/agent.py
"""
Agent Orchestrator

This is the central coordinator that manages the entire flow:
1. Takes user query in natural language
2. Asks LLM to select appropriate tool and parameters
3. Applies safety checks for dangerous operations
4. Executes the tool via MCP client
5. Formats and returns the result to the user

This orchestrates the communication between all system components.
"""

# Import required modules from our project
from .llm.ollama_client import get_tool_call, ensure_model_exists
from .mcp.client import call_tool, test_connection
from .safety import confirm_action_auto
from .tools import get_tools_schema
# Import typing utilities for type hints
from typing import Dict, Any

def process_query(query: str) -> str:
    """
    Process a user's natural language query and return the result.
    
    This function orchestrates the entire workflow:
    1. Validates system readiness (LLM and MCP server)
    2. Asks LLM to choose appropriate tool and parameters
    3. Applies safety confirmation for dangerous operations
    4. Executes the tool via MCP client
    5. Formats and returns the result
    
    Args:
        query (str): The user's natural language request
        
    Returns:
        str: Formatted result message for the user
    """
    # Step 1: Validate system readiness
    print("🔍 Checking system readiness...")
    
    # Check if LLM model is available
    if not ensure_model_exists():
        return "❌ LLM model not available. Please install the required model with 'ollama pull phi3:mini'"
    
    # Check if MCP server is running
    if not test_connection():
        return "❌ MCP server not running. Please start it with 'agentic-docker server'"
    
    print("✅ System ready. Processing query...")
    
    # Step 2: Get available tools schema for the LLM
    tools_schema = get_tools_schema()
    
    # Step 3: Ask LLM to choose tool and parameters
    print(f"🤖 Querying LLM for: '{query}'")
    tool_call = get_tool_call(query, tools_schema)
    
    # Handle cases where LLM couldn't understand the query
    if not tool_call:
        return "❌ Sorry, I couldn't understand your request or find an appropriate tool for it."
    
    # Extract tool name and arguments from LLM response
    tool_name = tool_call["name"]
    arguments = tool_call["arguments"]
    
    print(f"🎯 Selected tool: {tool_name}")
    print(f"   Arguments: {arguments}")
    
    # Step 4: Apply safety checks for dangerous operations
    print(f"🛡️  Checking safety requirements...")
    if not confirm_action_auto(tool_name, arguments):
        return "🛑 Action cancelled by user."
    
    # Step 5: Execute the tool via MCP client
    print(f"🚀 Executing tool via MCP server...")
    result = call_tool(tool_name, arguments)
    
    # Step 6: Format and return the result
    print(f"📊 Processing result...")
    return format_result(tool_name, result)

def format_result(tool_name: str, result: Dict[str, Any]) -> str:
    """
    Format the tool execution result into a user-friendly message.
    
    This function takes the raw result from the tool execution and formats
    it in a way that's easy for users to understand, with appropriate
    success/failure messages and structured data display.
    
    Args:
        tool_name (str): The name of the tool that was executed
        result (Dict[str, Any]): The raw result from the tool execution
        
    Returns:
        str: Formatted result message for the user
    """
    # Check if the operation was successful
    if result.get("success"):
        # Handle successful results differently based on the tool
        if tool_name == "docker_list_containers":
            # Special formatting for container listing
            containers = result.get("containers", [])
            count = result.get("count", 0)
            
            if not containers:
                return "✅ Success! No containers found."
            
            # Format container list nicely
            formatted_lines = []
            formatted_lines.append(f"✅ Success! Found {count} container(s):")
            
            for container in containers:
                status_emoji = get_status_emoji(container["status"])
                line = f"   {status_emoji} {container['name']} ({container['id']}) - {container['image']} [{container['status']}]"
                formatted_lines.append(line)
            
            return "\n".join(formatted_lines)
        
        elif tool_name == "docker_run_container":
            # Special formatting for container creation
            container_id = result.get("container_id", "unknown")
            container_name = result.get("name", "unknown")
            message = result.get("message", f"Container {container_name} started successfully.")
            return f"✅ {message}\n   Container ID: {container_id}\n   Name: {container_name}"
        
        elif tool_name == "docker_stop_container":
            # Special formatting for container stopping
            container_id = result.get("container_id", "unknown")
            container_name = result.get("name", "unknown")
            message = result.get("message", f"Container {container_name} stopped successfully.")
            return f"✅ {message}\n   Container ID: {container_id}\n   Name: {container_name}"
        
        else:
            # Generic success message for other tools
            return f"✅ Success! {result.get('message', 'Operation completed successfully.')}"
    
    else:
        # Handle failed operations
        error_msg = result.get("error", "Unknown error occurred")
        return f"❌ Operation failed: {error_msg}"

def get_status_emoji(status: str) -> str:
    """
    Get an appropriate emoji for container status.
    
    Args:
        status (str): The container status (e.g., "running", "exited")
        
    Returns:
        str: An emoji representing the status
    """
    status_map = {
        "running": "🟢",
        "exited": "🔴",
        "created": "🟡",
        "paused": "⏸️",
        "restarting": "🔄",
        "removing": "🧹",
        "dead": "💀"
    }
    return status_map.get(status.lower(), "❓")

def process_query_with_error_handling(query: str) -> str:
    """
    Process a query with comprehensive error handling.
    
    This wrapper function adds an extra layer of error handling
    to catch any unexpected issues during the entire process.
    
    Args:
        query (str): The user's natural language request
        
    Returns:
        str: Formatted result message for the user
    """
    try:
        return process_query(query)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        return "❌ Operation cancelled by user (Ctrl+C)"
    except Exception as e:
        # Handle any unexpected errors
        return f"❌ Unexpected error occurred: {str(e)}\nPlease check your system and try again."

def get_system_status() -> Dict[str, Any]:
    """
    Get the current status of the system components.
    
    This function checks if all required components are available
    and ready to process queries.
    
    Returns:
        Dict[str, Any]: Status information for LLM, MCP server, and tools
    """
    # Import the MODEL constant from the ollama client to ensure consistency
    from .llm.ollama_client import MODEL
    
    llm_available = ensure_model_exists()
    mcp_available = test_connection()
    # FIXED: get_tools_schema() returns list of dicts, not tool objects
    tools_schema = get_tools_schema()
    available_tools = [tool['name'] for tool in tools_schema]
    
    return {
        "llm": {
            "available": llm_available,
            # Use the actual configured model name from ollama_client.py, not hardcoded
            "model": MODEL
        },
        "mcp_server": {
            "available": mcp_available,
            "url": "http://127.0.0.1:8080"
        },
        "tools": {
            "available": available_tools,
            "count": len(available_tools)
        }
    }

def process_query_with_status_check(query: str) -> str:
    """
    Process a query with pre-check of system status.
    
    This function checks system status before processing the query
    and provides helpful error messages if components are unavailable.
    
    Args:
        query (str): The user's natural language request
        
    Returns:
        str: Formatted result message for the user
    """
    status = get_system_status()
    
    if not status["llm"]["available"]:
        return f"❌ LLM not available. Please ensure Ollama is running and model '{status['llm']['model']}' is installed."
    
    if not status["mcp_server"]["available"]:
        return f"❌ MCP server not available. Please start it with 'agentic-docker server'."
    
    if not status["tools"]["available"]:
        return f"❌ No tools available. Please check your tool configuration."
    
    # If all systems are go, process the query normally
    return process_query_with_error_handling(query)

# Example workflow:
"""
User query: "List all containers"
1. process_query("List all containers")
2. get_tool_call() → {"name": "docker_list_containers", "arguments": {}}
3. confirm_action_auto() → True (no confirmation needed for list)
4. call_tool() → {"success": True, "containers": [...], "count": 2}
5. format_result() → "✅ Success! Found 2 container(s):..."
"""

# The agent is the "brain" that coordinates all components:
# - LLM Client: Decides which tool to use
# - Safety Layer: Confirms dangerous operations  
# - MCP Client: Executes the chosen tool
# - Formatting: Makes results user-friendly