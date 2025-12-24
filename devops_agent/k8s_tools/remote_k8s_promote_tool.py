
import requests
import yaml
import json
from .k8s_base import K8sTool
from .k8s_config import k8s_config
from ..settings import settings
from typing import Dict, Any, Optional

class RemoteK8sPromoteResourceTool(K8sTool):
    """
    [PHASE 3] Deep Intelligence: Cross-Cluster Promotion Tool.
    Pulls a resource from LOCAL cluster and promotes it to REMOTE cluster
    with "Production-Grade" optimizations (limits, probes, etc.).
    """
    
    name = "remote_k8s_promote_resource"
    description = (
        "Promotes a resource (Deployment/Service/Pod) from LOCAL to REMOTE cluster. "
        "Automatically optimizes the YAML for production (adds limits, probes, etc.). "
        "High Intelligence: Intelligent transformation from dev to prod."
    )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "enum": ["deployment", "service", "pod", "configmap", "secret"],
                    "description": "Type of resource to promote."
                },
                "name": {
                    "type": "string",
                    "description": "Name of the resource in the LOCAL cluster."
                },
                "local_namespace": {
                    "type": "string",
                    "default": "default",
                    "description": "Namespace in the LOCAL cluster."
                },
                "remote_namespace": {
                    "type": "string",
                    "description": "Namespace in the REMOTE cluster (defaults to local_namespace)."
                },
                "optimize": {
                    "type": "boolean",
                    "default": True,
                    "description": "Apply 'Production-Grade' optimizations (limits, probes, etc.)."
                }
            },
            "required": ["resource_type", "name"]
        }

    def run(self, resource_type: str, name: str, local_namespace: str = "default", remote_namespace: str = None, optimize: bool = True) -> Dict[str, Any]:
        from .k8s_utils import safe_k8s_request
        remote_namespace = remote_namespace or local_namespace
        
        # Determine Path
        path_map = {
            "deployment": f"/apis/apps/v1/namespaces/{local_namespace}/deployments/{name}",
            "service": f"/api/v1/namespaces/{local_namespace}/services/{name}",
            "pod": f"/api/v1/namespaces/{local_namespace}/pods/{name}",
            "configmap": f"/api/v1/namespaces/{local_namespace}/configmaps/{name}",
            "secret": f"/api/v1/namespaces/{local_namespace}/secrets/{name}"
        }
        
        if resource_type.lower() not in path_map:
            return {"success": False, "error": f"Unsupported resource type: {resource_type}"}

        url = k8s_config.get_api_url() + path_map[resource_type.lower()]
        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        
        if not res["success"]:
            return res

        resource_yaml = res["data"]
        
        # 2. TRANSFORM
        clean_yaml = self._transform_for_remote(resource_yaml, remote_namespace, optimize)
        
        return {
            "success": True,
            "message": f"Successfully prepared {resource_type} '{name}' for promotion.",
            "local_namespace": local_namespace,
            "remote_target": f"https://10.20.4.221:16443/{remote_namespace}",
            "optimizations_applied": optimize,
            "proposed_yaml": yaml.dump(clean_yaml),
            "action_required": "Please confirm if you want to apply this YAML."
        }

    def _transform_for_remote(self, yaml_obj: Dict[str, Any], remote_ns: str, optimize: bool) -> Dict[str, Any]:
        """Deep Intelligence Transformation Logic."""
        # A. Basic Cleaning (Remove internal metadata)
        if "metadata" in yaml_obj:
            meta = yaml_obj["metadata"]
            for key in ["uid", "resourceVersion", "creationTimestamp", "selfLink", "managedFields"]:
                meta.pop(key, None)
            meta["namespace"] = remote_ns
            
            # Remove status
            yaml_obj.pop("status", None)
            
        # B. Production Optimizations
        if optimize and "spec" in yaml_obj:
            spec = yaml_obj["spec"]
            
            # For Pods/Deployments
            template = None
            if "template" in spec: # Deployment
                template = spec["template"]
            elif "containers" in spec: # Pod
                template = yaml_obj
                
            if template and "spec" in template:
                tspec = template["spec"]
                for container in tspec.get("containers", []):
                    # 1. Image Pull Policy
                    container["imagePullPolicy"] = "Always"
                    
                    # 2. Resource Limits (AI-suggested defaults if missing)
                    if "resources" not in container:
                        container["resources"] = {
                            "limits": {"cpu": "500m", "memory": "512Mi"},
                            "requests": {"cpu": "100m", "memory": "128Mi"}
                        }
                    
                    # 3. Liveness/Readiness Probes (Basic port 80 check if webapp)
                    if "livenessProbe" not in container and "nginx" in container.get("image", "").lower():
                         container["livenessProbe"] = {
                             "httpGet": {"path": "/", "port": 80},
                             "initialDelaySeconds": 5,
                             "periodSeconds": 10
                         }
                         
        return yaml_obj
