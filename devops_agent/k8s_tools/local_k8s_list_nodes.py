# devops_agent/k8s_tools/local_k8s_list_nodes.py
"""
Kubernetes List Nodes Tool

This tool allows the LLM to list Kubernetes nodes in the cluster.
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

class LocalK8sListNodesTool(K8sTool):
    """
    Tool for listing Kubernetes nodes in the LOCAL cluster.
    """
    name = "local_k8s_list_nodes"
    
    # Provide a human-readable description of what this tool does
    # The LLM will use this description to understand when to use this tool
    description = "List all Kubernetes nodes in the LOCAL cluster. Use this when user says 'local machine', 'local nodes', or just 'nodes' without specifying remote."
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Define the JSON Schema for this tool's parameters.
        
        This tool doesn't require any parameters - it always lists all nodes.
        
        The schema follows JSON Schema specification and tells the LLM
        what arguments this tool can accept.
        """
        return {
            # This is a JSON Schema object definition
            "type": "object",
            # Properties that the tool accepts
            "properties": {
                "label_selector": {
                    "type": "string",
                    "description": "Filter nodes by labels (e.g., 'node-role.kubernetes.io/worker='). Use standard Kubernetes label selector syntax."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of nodes to return. Default is 50."
                }
            },
            # List of required parameters (empty)
            "required": []
        }

    def run(self, label_selector: str = None, limit: int = 50, **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        api_url = k8s_config.get_api_url()
        headers = k8s_config.get_headers()
        verify_ssl = k8s_config.get_verify_ssl()

        url = f"{api_url}/api/v1/nodes"
        params = {}
        if label_selector: params['labelSelector'] = label_selector
        if limit: params['limit'] = limit

        res = safe_k8s_request("GET", url, headers, verify_ssl, params=params)
        
        if not res["success"]:
            return res

        data = res["data"]
        nodes_list = data.get("items", [])
        formatted_nodes = []
        
        for node in nodes_list:
            metadata = node.get("metadata", {})
            status = node.get("status", {})
            spec = node.get("spec", {})
            
            conditions = status.get("conditions", [])
            ready_condition = next((c for c in conditions if c.get("type") == "Ready"), {})
            is_ready = ready_condition.get("status") == "True"
            
            roles = self._get_node_roles(metadata.get("labels", {}))
            addresses = status.get("addresses", [])
            internal_ip = next((addr.get("address") for addr in addresses if addr.get("type") == "InternalIP"), "N/A")
            hostname = next((addr.get("address") for addr in addresses if addr.get("type") == "Hostname"), "N/A")
            
            formatted_nodes.append({
                "name": metadata.get("name", "unknown"),
                "status": "Ready" if is_ready else "NotReady",
                "roles": roles,
                "internal_ip": internal_ip,
                "hostname": hostname,
                "kubelet_version": status.get("nodeInfo", {}).get("kubeletVersion", "unknown"),
                "cpu": status.get("capacity", {}).get("cpu", "N/A"),
                "memory": status.get("capacity", {}).get("memory", "N/A"),
                "os": status.get("nodeInfo", {}).get("osImage", "unknown"),
            })
        
        return {
            "success": True,
            "nodes": formatted_nodes,
            "count": len(formatted_nodes)
        }
    
    def _get_node_roles(self, labels: Dict[str, Any]) -> str:
        """
        Helper method to extract node roles from labels.
        
        Args:
            labels (dict): The labels section from the node metadata
            
        Returns:
            str: Comma-separated list of roles (e.g., "control-plane,master" or "worker")
        """
        roles = []
        
        # Check for common role labels
        if "node-role.kubernetes.io/control-plane" in labels:
            roles.append("control-plane")
        if "node-role.kubernetes.io/master" in labels:
            roles.append("master")
        if "node-role.kubernetes.io/worker" in labels:
            roles.append("worker")
        
        # If no roles found, check for other role labels
        if not roles:
            for key in labels:
                if key.startswith("node-role.kubernetes.io/"):
                    role = key.replace("node-role.kubernetes.io/", "")
                    if role:
                        roles.append(role)
        
        # If still no roles, default to "worker"
        if not roles:
            roles.append("worker")
        
        return ",".join(roles)
