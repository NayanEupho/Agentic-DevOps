import requests
import httpx
from typing import Dict, Any, Optional
import urllib.parse

def safe_k8s_request(method: str, url: str, headers: Dict[str, str], verify: bool, timeout: int = 10, json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    [LEGACY] Synchronous Kubernetes API request. Use async_safe_k8s_request for new tools.
    """
    try:
        if params:
            url_parts = list(urllib.parse.urlparse(url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            query.update(params)
            url_parts[4] = urllib.parse.urlencode(query)
            url = urllib.parse.urlunparse(url_parts)

        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, verify=verify, timeout=timeout)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=headers, verify=verify, timeout=timeout, json=json_data)
        elif method.upper() == "PUT":
            resp = requests.put(url, headers=headers, verify=verify, timeout=timeout, json=json_data)
        elif method.upper() == "PATCH":
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/strategic-merge-patch+json"
            resp = requests.patch(url, headers=headers, verify=verify, timeout=timeout, json=json_data)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, headers=headers, verify=verify, timeout=timeout)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}

        if not resp.ok:
            try: raw_error = resp.json()
            except Exception: raw_error = {"message": resp.text}
            return {"success": False, "error": f"K8s API Error ({resp.status_code})", "raw_error": raw_error, "status_code": resp.status_code}

        is_json = "application/json" in resp.headers.get("Content-Type", "").lower()
        data = resp.json() if is_json else resp.text
        return {"success": True, "data": data, "status_code": resp.status_code}

    except requests.exceptions.Timeout: return {"success": False, "error": "Kubernetes API timeout."}
    except requests.exceptions.ConnectionError: return {"success": False, "error": "Could not connect to Kubernetes API."}
    except Exception as e: return {"success": False, "error": f"Unexpected error: {str(e)}"}

async def async_safe_k8s_request(method: str, url: str, headers: Dict[str, str], verify: bool, timeout: int = 15, json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    [NON-BLOCKING] Asynchronous Kubernetes API request using pooled httpx client.
    Captures raw error payloads for the ErrorAnalyzer.
    """
    try:
        # Use shared client from MCP layer if possible, or create a local one with pooling
        from ..mcp.client import get_async_client
        client = get_async_client()

        # Build final URL with params
        if params:
            url_parts = list(urllib.parse.urlparse(url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            query.update(params)
            url_parts[4] = urllib.parse.urlencode(query)
            url = urllib.parse.urlunparse(url_parts)

        # Handle specific K8s Patch headers
        if method.upper() == "PATCH" and "Content-Type" not in headers:
            headers["Content-Type"] = "application/strategic-merge-patch+json"

        response = await client.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json_data,
            timeout=timeout,
            # verify=verify # httpx handles verify differently, usually passed to client init but can be per request too
        )

        if not response.is_success:
            try: raw_error = response.json()
            except Exception: raw_error = {"message": response.text}
            
            return {
                "success": False,
                "error": f"K8s API Error ({response.status_code})",
                "raw_error": raw_error,
                "status_code": response.status_code
            }

        is_json = "application/json" in response.headers.get("Content-Type", "").lower()
        data = response.json() if is_json else response.text

        return {
            "success": True,
            "data": data,
            "status_code": response.status_code
        }

    except httpx.TimeoutException:
        return {"success": False, "error": "Kubernetes API timeout (Async)."}
    except httpx.ConnectError:
        return {"success": False, "error": "Could not connect to Kubernetes API (Async)."}
    except Exception as e:
        return {"success": False, "error": f"Unexpected async error: {str(e)}"}
