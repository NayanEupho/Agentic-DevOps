# devops_agent/mcp/client.py
"""
MCP (Model Context Protocol) Client

This client sends JSON-RPC 2.0 requests to the MCP server to execute Docker tools.
It handles the communication protocol, request formatting, and response parsing.
It supports both synchronous (legacy) and asynchronous execution.
"""

import requests
import httpx
import json
import asyncio
from typing import Dict, Any, Optional

# Configuration
# Configuration
from ..settings import settings

MCP_URL = f"http://{settings.MCP_SERVER_HOST}:{settings.DOCKER_PORT}"
K8S_MCP_URL = f"http://{settings.MCP_SERVER_HOST}:{settings.LOCAL_K8S_PORT}"
REMOTE_K8S_MCP_URL = f"http://{settings.MCP_SERVER_HOST}:{settings.REMOTE_K8S_PORT}"

# -----------------------------------------------------------------------------
# ASYNCHRONOUS IMPLEMENTATION (New & Optimized)
# -----------------------------------------------------------------------------

_SHARED_ASYNC_CLIENT: Optional[httpx.AsyncClient] = None

def get_async_client() -> httpx.AsyncClient:
    """Get or create a shared asynchronous client for connection pooling."""
    global _SHARED_ASYNC_CLIENT
    if _SHARED_ASYNC_CLIENT is None or _SHARED_ASYNC_CLIENT.is_closed:
        # Optimized for "Lightning Fast" targets:
        # - Pool size: 20 to handle parallel tool calls and background pulses
        # - Keep-alive: 30s to reuse connections to local/remote MCPs
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        _SHARED_ASYNC_CLIENT = httpx.AsyncClient(timeout=30.0, limits=limits)
    return _SHARED_ASYNC_CLIENT

async def close_async_client():
    """Cleanly close the shared client during shutdown."""
    global _SHARED_ASYNC_CLIENT
    if _SHARED_ASYNC_CLIENT:
        await _SHARED_ASYNC_CLIENT.aclose()
        _SHARED_ASYNC_CLIENT = None

async def call_tool_async(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool asynchronously using a shared, pooled httpx client."""
    # Determine URL based on tool name
    url = MCP_URL
    if tool_name.startswith("local_k8s_") or tool_name.startswith("k8s_"):
        url = K8S_MCP_URL
    elif tool_name.startswith("remote_k8s_"):
        url = REMOTE_K8S_MCP_URL
    elif tool_name == "chat":
        url = MCP_URL
        
    payload = {
        "jsonrpc": "2.0",
        "method": tool_name,
        "params": arguments,
        "id": 1
    }
    
    try:
        client = get_async_client()
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "original_response": result
            }
        
        return result.get("result", {"success": False, "error": "No result returned"})
            
    except httpx.ConnectError:
         return {
            "success": False,
            "error": f"Cannot connect to MCP server at {url}. Is it running?"
        }
    except httpx.TimeoutException:
        return {"success": False, "error": "Request timed out"}
    except Exception as e:
        return {"success": False, "error": f"Async error: {str(e)}"}

# -----------------------------------------------------------------------------
# SYNCHRONOUS IMPLEMENTATION (Legacy compatibility)
# -----------------------------------------------------------------------------

def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return _sync_call(MCP_URL, tool_name, arguments)

def call_k8s_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return _sync_call(K8S_MCP_URL, tool_name, arguments)

def call_remote_k8s_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return _sync_call(REMOTE_K8S_MCP_URL, tool_name, arguments)

def _sync_call(url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Internal synchronous helper using requests."""
    payload = {
        "jsonrpc": "2.0",
        "method": tool_name,
        "params": arguments,
        "id": 1
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
            
        return result.get("result", {"success": False, "error": "No result"})
        
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Cannot connect to server at {url}"}
    except Exception as e:
        return {"success": False, "error": f"Error: {str(e)}"}

def test_connection() -> bool:
    """Test Docker MCP connection."""
    res = call_tool("docker_list_containers", {})
    return "error" not in res or "Cannot connect" not in res.get("error", "")

def test_k8s_connection() -> bool:
    res = call_k8s_tool("local_k8s_list_pods", {"namespace": "default"})
    return "error" not in res or "Cannot connect" not in res.get("error", "")

def test_remote_k8s_connection() -> bool:
    res = call_remote_k8s_tool("remote_k8s_list_pods", {"namespace": "default"})
    return "error" not in res or "Cannot connect" not in res.get("error", "")