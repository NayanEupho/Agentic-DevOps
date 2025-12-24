
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import quote
from .k8s_base import K8sTool
from .k8s_config import k8s_config

class RemoteK8sGetLogsTool(K8sTool):
    name = "remote_k8s_get_logs"
    description = "Get logs from a pod in the REMOTE cluster. Use this to debug failures or check application output. ALWAYS specify pod_name."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Name of the pod to get logs from."
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace of the pod. Defaults to 'default'."
                },
                "container_name": {
                    "type": "string",
                    "description": "Optional: Specific container name. If omitted, K8s returns logs for the first container."
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to fetch from the end of the log. Defaults to 100."
                }
            },
            "required": ["pod_name"]
        }

    def run(self, pod_name: str, namespace: str = "default", container_name: str = None, lines: int = 100, **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        safe_name = quote(pod_name)
        safe_ns = quote(namespace)
        url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{safe_ns}/pods/{safe_name}/log"
        
        params = {"tailLines": lines}
        if container_name: params["container"] = container_name
            
        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl(), params=params)
        
        if not res["success"]:
            # Handle multi-container ambiguity hint (status 400 with specific text)
            if res.get("status_code") == 400 and "container" in str(res.get("raw_error", "")):
                return {"success": False, "error": "Pod has multiple containers. Please specify 'container_name'."}
            return res

        logs = res["data"]
        if not logs: logs = "(No logs found or empty)"

        return {
            "success": True,
            "logs": logs[:100000],
            "pod_name": pod_name,
            "namespace": namespace,
            "lines_fetched": lines
        }


class RemoteK8sListEventsTool(K8sTool):
    name = "remote_k8s_list_events"
    description = "List Kubernetes events for a namespace or specific resource in the REMOTE cluster. Crucial for debugging 'Pending' pods or scheduling issues."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace to list events from. Defaults to 'default'."
                },
                "resource_name": {
                    "type": "string",
                    "description": "Optional: Name of a specific resource (pod, deployment, etc.) to filter events for."
                }
            },
            "required": []
        }

    def run(self, namespace: str = "default", resource_name: str = None, **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        safe_ns = quote(namespace)
        url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{safe_ns}/events"
        
        params = {}
        if resource_name:
            params["fieldSelector"] = f"involvedObject.name={resource_name}"
        
        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl(), params=params)
        if not res["success"]:
            return res

        data = res["data"]
        events = []
        for item in data.get('items', []):
            events.append({
                "reason": item.get('reason'),
                "message": item.get('message'),
                "type": item.get('type'),
                "object": item.get('involvedObject', {}).get('kind') + "/" + item.get('involvedObject', {}).get('name'),
                "count": item.get('count', 1),
                "last_timestamp": item.get('lastTimestamp') or item.get('eventTime')
            })
        
        events.sort(key=lambda x: x['last_timestamp'] or "", reverse=True)

        return {
            "success": True,
            "events": events[:20],
            "count": len(events)
        }
