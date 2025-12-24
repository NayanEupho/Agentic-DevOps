# devops_agent/k8s_tools/local_k8s_list_pods.py
"""
Kubernetes List Pods Tool

This tool allows the LLM to list Kubernetes pods in a specific namespace or across all namespaces.
It uses HTTP requests to the Kubernetes API (configured via k8s_config).
"""

# Import requests library for HTTP communication with K8s API
import requests
# Import our base K8sTool class that this tool must inherit from
from .k8s_base import K8sTool
# Import configuration
from .k8s_config import k8s_config
# Import typing utilities for type hints
from typing import Dict, Any

class LocalK8sListPodsTool(K8sTool):
    """
    Tool for listing Kubernetes pods in the LOCAL cluster.
    
    This tool can list:
    - Pods in a specific namespace (default: "default")
    - Pods across all namespaces
    
    It communicates with the Kubernetes API via the configured URL.
    """
    
    # Define the unique name for this tool
    # This name will be used by the LLM to call this specific tool
    name = "local_k8s_list_pods"
    
    # Provide a human-readable description of what this tool does
    # The LLM will use this description to understand when to use this tool
    description = "List Kubernetes pods in a namespace or across all namespaces. Use status_phase (enum) for lightning-fast filtering by pod state (Running, Pending, etc.)."
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Define the JSON Schema for this tool's parameters.
        
        This tool accepts optional parameters:
        - 'namespace': string - the namespace to list pods from (default: "default")
        - 'all_namespaces': boolean - if True, list pods from all namespaces
        - 'node_name': string - (Optional) List only pods running on this specific node.
        
        The schema follows JSON Schema specification and tells the LLM
        what arguments this tool can accept.
        """
        return {
            # This is a JSON Schema object definition
            "type": "object",
            # Properties that the tool accepts
            "properties": {
                # 'namespace' parameter: string type, defaults to "default"
                "namespace": {
                    "type": "string",
                    "default": "default",
                    "description": "The Kubernetes namespace to list pods from. Defaults to 'default'."
                },
                # 'all_namespaces' parameter: boolean type, defaults to False
                "all_namespaces": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, list pods from all namespaces. Overrides the 'namespace' parameter."
                },
                # 'node_name' parameter: string type, optional
                "node_name": {
                    "type": "string",
                    "description": "Filter pods by node name. Example: 'kc-m1'."
                },
                # 'status_phase' parameter: string type, optional
                "status_phase": {
                    "type": "string",
                    "enum": ["Pending", "Running", "Succeeded", "Failed", "Unknown"],
                    "description": "Filter pods by their phase (e.g., 'Running', 'Pending'). HIGHLY RECOMMENDED for speed and accuracy."
                },
                # 'label_selector' parameter: string type, optional
                "label_selector": {
                    "type": "string",
                    "description": "Filter pods by labels (e.g., 'app=nginx', 'env=prod'). Use standard Kubernetes label selector syntax."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of items to return. Default is 50."
                }
            },
            # List of required parameters (empty list means all parameters are optional)
            "required": []
        }

    def run(self, namespace: str = "default", all_namespaces: bool = False, node_name: str = None, status_phase: str = None, label_selector: str = None, limit: int = 50) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        api_url = k8s_config.get_api_url()
        headers = k8s_config.get_headers()
        verify_ssl = k8s_config.get_verify_ssl()

        if all_namespaces:
            url = f"{api_url}/api/v1/pods"
        else:
            url = f"{api_url}/api/v1/namespaces/{namespace}/pods"
        
        params = {}
        field_selectors = []
        if node_name: field_selectors.append(f"spec.nodeName={node_name}")
        if status_phase: field_selectors.append(f"status.phase={status_phase}")
        if field_selectors: params['fieldSelector'] = ",".join(field_selectors)
        if label_selector: params['labelSelector'] = label_selector
        if limit: params['limit'] = limit
        
        res = safe_k8s_request("GET", url, headers, verify_ssl, params=params)
        
        if not res["success"]:
            return res

        data = res["data"]
        pods_list = data.get("items", [])
        formatted_pods = []
        
        for pod in pods_list:
            metadata = pod.get("metadata", {})
            status = pod.get("status", {})
            spec = pod.get("spec", {})
            
            formatted_pods.append({
                "name": metadata.get("name", "unknown"),
                "namespace": metadata.get("namespace", "unknown"),
                "phase": status.get("phase", "Unknown"),
                "pod_ip": status.get("podIP", "N/A"),
                "node": spec.get("nodeName", "N/A"),
                "containers": len(spec.get("containers", [])),
                "ready": self._get_ready_status(status),
            })
        
        return {
            "success": True,
            "pods": formatted_pods,
            "count": len(formatted_pods),
            "namespace": "all" if all_namespaces else namespace,
            "filtered_by_node": node_name,
            "filtered_by_status": status_phase,
            "filtered_by_labels": label_selector
        }
    
    def _get_ready_status(self, status: Dict[str, Any]) -> str:
        """
        Helper method to determine if a pod is ready.
        
        Args:
            status (dict): The status section from the pod spec
            
        Returns:
            str: Ready status as a string (e.g., "2/2", "0/1")
        """
        conditions = status.get("conditions", [])
        container_statuses = status.get("containerStatuses", [])
        
        if not container_statuses:
            return "0/0"
        
        # Count ready containers
        ready_count = sum(1 for cs in container_statuses if cs.get("ready", False))
        total_count = len(container_statuses)
        
        return f"{ready_count}/{total_count}"
