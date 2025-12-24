# devops_agent/k8s_tools/local_k8s_describe_pod.py
"""
Kubernetes Describe Pod Tool (Local)

This tool allows the LLM to get detailed information about a specific pod in the LOCAL cluster.
"""

import requests
from typing import Dict, Any
from urllib.parse import quote
from .k8s_base import K8sTool
from .k8s_config import k8s_config

class LocalK8sDescribePodTool(K8sTool):
    """
    Tool to get detailed information about a specific pod in the LOCAL cluster.
    """
    name = "local_k8s_describe_pod"
    description = "DESCRIBE a pod in the LOCAL cluster. Returns comprehensive details including status, containers, images, restart counts, conditions, and events."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Name of the pod to describe."
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace of the pod. Defaults to 'default'."
                }
            },
            "required": ["pod_name"]
        }

    def run(self, pod_name: str, namespace: str = "default", **kwargs) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        api_url = k8s_config.get_api_url()
        headers = k8s_config.get_headers()
        verify_ssl = k8s_config.get_verify_ssl()

        safe_name = quote(pod_name)
        safe_ns = quote(namespace)
        
        # 1. Get Pod Details
        url = f"{api_url}/api/v1/namespaces/{safe_ns}/pods/{safe_name}"
        res = safe_k8s_request("GET", url, headers, verify_ssl)
        
        if not res["success"]:
            return res

        pod_data = res["data"]

        # 2. Get Pod Events
        events_url = f"{api_url}/api/v1/namespaces/{safe_ns}/events?fieldSelector=involvedObject.name={safe_name},involvedObject.namespace={safe_ns},involvedObject.uid={pod_data['metadata']['uid']}"
        events_res = safe_k8s_request("GET", events_url, headers, verify_ssl)
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

        metadata = pod_data.get('metadata', {})
        spec = pod_data.get('spec', {})
        status = pod_data.get('status', {})

        containers = []
        for c_spec in spec.get('containers', []):
            c_status = next((CS for CS in status.get('containerStatuses', []) if CS['name'] == c_spec['name']), {})
            containers.append({
                "name": c_spec['name'],
                "image": c_spec['image'],
                "ready": c_status.get('ready', False),
                "restart_count": c_status.get('restartCount', 0),
                "state": c_status.get('state', {}),
                "ports": [p.get('containerPort') for p in c_spec.get('ports', [])]
            })

        details = {
            "name": metadata.get('name'),
            "namespace": metadata.get('namespace'),
            "node_name": spec.get('nodeName'),
            "start_time": status.get('startTime'),
            "phase": status.get('phase'),
            "pod_ip": status.get('podIP'),
            "host_ip": status.get('hostIP'),
            "labels": metadata.get('labels', {}),
            "containers": containers,
            "conditions": status.get('conditions', []),
            "events": events
        }

        return {
            "success": True,
            "pod": details
        }
