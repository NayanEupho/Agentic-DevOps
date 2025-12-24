# devops_agent/k8s_tools/remote_k8s_service_tools.py
"""
Remote Kubernetes Service Tools

This module implements tools to interact with Kubernetes Services (svc) in a remote cluster.
"""

import requests
from typing import Dict, Any, List
from urllib.parse import quote
from .k8s_base import K8sTool
from .k8s_config import k8s_config

class RemoteK8sListServicesTool(K8sTool):
    """
    Tool to list Kubernetes services in a remote cluster.
    """
    name = "remote_k8s_list_services"
    description = "List Kubernetes Services (svc). Can list all services in a SPECIFIC NAMESPACE (e.g. 'kube-system') or across ALL namespaces. Use this for general listing/overview."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace to list services from. Defaults to 'default'."
                },
                "all_namespaces": {
                    "type": "boolean",
                    "description": "If true, list services from all namespaces."
                },
                "label_selector": {
                    "type": "string",
                    "description": "Filter services by labels. Use standard Kubernetes label selector syntax."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of services to return. Default is 50."
                }
            },
            "required": []
        }

    def run(self, namespace: str = "default", all_namespaces: bool = False, label_selector: str = None, limit: int = 50, **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        # Handle empty string namespace from LLM
        if not namespace and not all_namespaces:
            namespace = "default"

        # Construct API URL
        if all_namespaces:
            url = f"{k8s_config.get_api_url()}/api/v1/services" 
        elif namespace:
             safe_ns = quote(namespace)
             url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{safe_ns}/services"
        else:
             url = f"{k8s_config.get_api_url()}/api/v1/namespaces/default/services"

        # Prepare query parameters
        params = {}
        if label_selector: params['labelSelector'] = label_selector
        if limit: params['limit'] = limit
        
        # If there are params, append them to URL for safe_k8s_request (which currently doesn't take params separately)
        # TODO: Update safe_k8s_request to handle params, or append here.
        if params:
            import urllib.parse
            url += "?" + urllib.parse.urlencode(params)

        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        if not res["success"]:
            return res

        data = res["data"]
        services = []
        for item in data.get('items', []):
            metadata = item.get('metadata', {})
            spec = item.get('spec', {})
            
            ports = []
            for p in spec.get('ports', []):
                ports.append(f"{p.get('port')}:{p.get('targetPort')}/{p.get('protocol')}")

            services.append({
                "name": metadata.get('name'),
                "namespace": metadata.get('namespace'),
                "type": spec.get('type'),
                "cluster_ip": spec.get('clusterIP'),
                "external_ips": spec.get('externalIPs', []),
                "ports": ports,
                "creation_timestamp": metadata.get('creationTimestamp')
            })

        return {
            "success": True,
            "services": services,
            "count": len(services),
            "scope": "all namespaces" if all_namespaces else f"namespace '{namespace}'"
        }

class RemoteK8sGetServiceTool(K8sTool):
    """
    Tool to get detailed info about a specific Kubernetes service.
    """
    name = "remote_k8s_get_service"
    description = "Get detailed configuration/status for a SINGLE SPECIFIC Kubernetes Service. REQUIRED: User MUST provide the service name explicitly (e.g. 'get service pos'). If no name is given, do NOT guess. Use list_services instead if name is unknown."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to retrieve."
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace of the service. Defaults to 'default'."
                }
            },
            "required": ["service_name"]
        }

    def run(self, service_name: str = None, namespace: str = "default", **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        if not service_name:
            return {"success": False, "error": "Service name is required."}
        
        if not namespace: namespace = "default"

        safe_name = quote(service_name)
        safe_ns = quote(namespace)
        url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{safe_ns}/services/{safe_name}"

        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        if not res["success"]:
            return res

        data = res["data"]
        metadata = data.get('metadata', {})
        spec = data.get('spec', {})
        status = data.get('status', {})

        details = {
            "name": metadata.get('name'),
            "namespace": metadata.get('namespace'),
            "labels": metadata.get('labels', {}),
            "annotations": metadata.get('annotations', {}),
            "selector": spec.get('selector', {}),
            "type": spec.get('type'),
            "cluster_ip": spec.get('clusterIP'),
            "external_ips": spec.get('externalIPs', []),
            "load_balancer_ip": status.get('loadBalancer', {}).get('ingress', []),
            "ports": spec.get('ports', []),
            "session_affinity": spec.get('sessionAffinity')
        }

        return {
            "success": True,
            "service": details
        }

class RemoteK8sDescribeServiceTool(K8sTool):
    """
    Tool to describe a Kubernetes service.
    """
    name = "remote_k8s_describe_service"
    description = "DESCRIBE a service. Returns detailed configuration, status, endpoints (if possible via endpoints API), and event log. Use when user asks 'describe service <name>'."
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service."
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace. Defaults to 'default'."
                }
            },
            "required": ["service_name"]
        }

    def run(self, service_name: str, namespace: str = "default", **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        safe_name = quote(service_name)
        safe_ns = quote(namespace)
        
        # 1. Get Service Details
        url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{safe_ns}/services/{safe_name}"
        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        
        if not res["success"]:
            return res

        data = res["data"]

        # 2. Get Events
        events_url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{safe_ns}/events?fieldSelector=involvedObject.name={safe_name},involvedObject.namespace={safe_ns},involvedObject.kind=Service"
        events_res = safe_k8s_request("GET", events_url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        events = []
        if events_res["success"]:
            for e in events_res["data"].get('items', []):
                events.append({
                    "type": e.get('type'),
                    "reason": e.get('reason'),
                    "message": e.get('message'),
                    "count": e.get('count', 1),
                    "last_timestamp": e.get('lastTimestamp')
                })
        
        # 3. Get Endpoints
        ep_url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{safe_ns}/endpoints/{safe_name}"
        ep_res = safe_k8s_request("GET", ep_url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        endpoints_list = []
        if ep_res["success"]:
            ep_data = ep_res["data"]
            for subset in ep_data.get('subsets', []):
                for addr in subset.get('addresses', []):
                    endpoints_list.append(f"{addr.get('ip')}")

        metadata = data.get('metadata', {})
        spec = data.get('spec', {})

        details = {
            "name": metadata.get('name'),
            "namespace": metadata.get('namespace'),
            "labels": metadata.get('labels', {}),
            "annotations": metadata.get('annotations', {}),
            "selector": spec.get('selector', {}),
            "type": spec.get('type'),
            "cluster_ip": spec.get('clusterIP'),
            "external_ips": spec.get('externalIPs', []),
            "ports": spec.get('ports', []),
            "endpoints": endpoints_list,
            "events": events
        }

        return {
            "success": True,
            "service": details
        }
