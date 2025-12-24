
import requests
from typing import Dict, Any, List
from urllib.parse import quote
from .k8s_base import K8sTool
from .k8s_config import k8s_config

class RemoteK8sTopNodesTool(K8sTool):
    name = "remote_k8s_top_nodes"
    description = "Get CPU and Memory usage for all nodes in the REMOTE cluster. Use this when user asks about cluster load or performance."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    def run(self, **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        url = f"{k8s_config.get_api_url()}/apis/metrics.k8s.io/v1beta1/nodes"
        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        
        if not res["success"]:
            if res.get("status_code") == 404:
                return {"success": False, "error": "Metrics API not found. Metrics Server might not be installed."}
            return res

        data = res["data"]
        nodes = []
        for item in data.get('items', []):
            nodes.append({
                "name": item.get('metadata', {}).get('name'),
                "cpu_usage": item.get('usage', {}).get('cpu'),
                "memory_usage": item.get('usage', {}).get('memory')
            })

        return {
            "success": True,
            "nodes": nodes,
            "count": len(nodes)
        }

class RemoteK8sTopPodsTool(K8sTool):
    name = "remote_k8s_top_pods"
    description = "Get CPU and Memory usage for pods. Can filter by namespace. Useful for finding resource hogs."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace to get metrics for. Defaults to all namespaces if omitted (might be restricted)."
                }
            },
            "required": []
        }

    def run(self, namespace: str = None, **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        if namespace:
            safe_ns = quote(namespace)
            url = f"{k8s_config.get_api_url()}/apis/metrics.k8s.io/v1beta1/namespaces/{safe_ns}/pods"
        else:
            url = f"{k8s_config.get_api_url()}/apis/metrics.k8s.io/v1beta1/pods"
        
        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        if not res["success"]:
            if res.get("status_code") == 404:
                return {"success": False, "error": "Metrics API not found or path invalid."}
            return res

        data = res["data"]
        pods = []
        for item in data.get('items', []):
            pods.append({
                "name": item.get('metadata', {}).get('name'),
                "namespace": item.get('metadata', {}).get('namespace'),
                "containers": item.get('containers', [])
            })

        return {
            "success": True,
            "pods": pods[:50],
            "count": len(pods),
            "scope": f"namespace '{namespace}'" if namespace else "all namespaces"
        }
