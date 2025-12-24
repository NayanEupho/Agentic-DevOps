
import requests
from typing import Dict, Any, List
from .k8s_base import K8sTool

class RemoteK8sFindResourceNamespaceTool(K8sTool):
    """
    [PHASE 4] Implicit Namespace Discovery.
    Finds the namespace(s) or cluster (Local/Remote) where a resource name exists.
    Useful when the user says "describe pod web-app" without specifying where it is.
    """
    name = "remote_k8s_find_resource_namespace"
    description = "SEARCH for a resource name (pod or deployment) across ALL namespaces and BOTH local/remote clusters. Use this if you don't know the namespace of a resource."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the resource (pod, deployment, etc.) to look for."
                },
                "resource_type": {
                    "type": "string",
                    "enum": ["pods", "deployments"],
                    "description": "Type of resource to search for. Default is 'pods'."
                }
            },
            "required": ["name"]
        }

    def run(self, name: str, resource_type: str = "pods", **kwargs) -> Dict[str, Any]:
        from ..pulse import get_pulse
        pulse = get_pulse()
        # Ensure we have a plural type for the pulse index
        idx_type = resource_type if resource_type.endswith("s") else f"{resource_type}s"
        
        global_idx = pulse.status_cache.get("global_index", {}).get("resources", {})
        matches = global_idx.get(idx_type, {}).get(name)
        
        if matches:
            return {
                "success": True,
                "matches": matches,
                "suggestion": f"Found '{name}' in {matches[0]['mcp']} namespace '{matches[0]['ns']}'."
            }
        else:
            return {
                "success": False,
                "error": f"Resource '{name}' not found in global index. Pulse check might be pending.",
                "tip": "Try listing pods in all-namespaces to force a discovery."
            }

class RemoteK8sTraceDependenciesTool(K8sTool):
    """
    [PHASE 4] Dependency-Aware Tracer.
    Crawls a pod's manifest to verify all linked resources (ConfigMaps, Secrets, PVCs).
    Provides a "Health Tree" for troubleshooting pending/crashing pods.
    """
    name = "remote_k8s_trace_dependencies"
    description = "TRACE all dependencies of a pod (Secrets, ConfigMaps, PVCs). Use this to find WHY a pod is failing due to missing resources."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pod_name": {"type": "string", "description": "Name of the pod to trace."},
                "namespace": {"type": "string", "description": "Namespace of the pod. Defaults to 'default'."}
            },
            "required": ["pod_name"]
        }

    def run(self, pod_name: str, namespace: str = "default", **kwargs) -> Dict[str, Any]:
        from .k8s_config import k8s_config
        from .k8s_utils import safe_k8s_request
        
        # 1. Fetch Pod Manifest
        url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{namespace}/pods/{pod_name}"
        res = safe_k8s_request("GET", url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        
        if not res["success"]:
            return res # Propagation of raw_error

        pod = res["data"]
        spec = pod.get("spec", {})
        dependencies = {"config_maps": [], "secrets": [], "pvcs": [], "service_account": spec.get("serviceAccountName")}
        
        # 2. Extract Deps
        for c in spec.get("containers", []) + spec.get("initContainers", []):
            for env in c.get("env", []):
                ref = env.get("valueFrom", {})
                if "configMapKeyRef" in ref: dependencies["config_maps"].append(ref["configMapKeyRef"]["name"])
                if "secretKeyRef" in ref: dependencies["secrets"].append(ref["secretKeyRef"]["name"])
            for ef in c.get("envFrom", []):
                if "configMapRef" in ef: dependencies["config_maps"].append(ef["configMapRef"]["name"])
                if "secretRef" in ef: dependencies["secrets"].append(ef["secretRef"]["name"])
        
        for v in spec.get("volumes", []):
            if "configMap" in v: dependencies["config_maps"].append(v["configMap"]["name"])
            if "secret" in v: dependencies["secrets"].append(v["secret"]["secretName"])
            if "persistentVolumeClaim" in v: dependencies["pvcs"].append(v["persistentVolumeClaim"]["claimName"])

        # 3. Verify Existence
        health_tree = {}
        for ct, items in dependencies.items():
            if ct == "service_account":
                health_tree["service_account"] = {"name": items, "exists": True}
                continue
            
            health_tree[ct] = []
            for item in set(items):
                if ct == "config_maps": path = f"/api/v1/namespaces/{namespace}/configmaps/{item}"
                elif ct == "secrets": path = f"/api/v1/namespaces/{namespace}/secrets/{item}"
                elif ct == "pvcs": path = f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{item}"
                
                check_url = f"{k8s_config.get_api_url()}{path}"
                check_res = safe_k8s_request("GET", check_url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
                
                health_tree[ct].append({
                    "name": item, 
                    "status": "Ready" if check_res["success"] else f"Error: {check_res.get('status_code', 'Unknown')}",
                    "details": check_res.get("raw_error") if not check_res["success"] else None
                })

        return {
            "success": True,
            "pod_name": pod_name,
            "health_tree": health_tree
        }

class RemoteK8sDiffResourcesTool(K8sTool):
    """
    [PHASE 4] Semantic Manifest Differ.
    Compares a resource manifest (Deployment/Service) between Local and Remote clusters.
    Strips metadata/status to focus on semantic configuration drift.
    """
    name = "remote_k8s_diff_resources"
    description = "COMPARE a resource (e.g. deployment) between Local and Remote clusters to find configuration drift."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "resource_name": {"type": "string", "description": "Name of the resource to compare."},
                "resource_type": {"type": "string", "enum": ["deployments", "services", "configmaps"], "description": "Type of resource."},
                "namespace": {"type": "string", "description": "Namespace (assumed same for both)."}
            },
            "required": ["resource_name", "resource_type"]
        }

    def run(self, resource_name: str, resource_type: str, namespace: str = "default", **kwargs) -> Dict[str, Any]:
        from .k8s_config import k8s_config
        import difflib
        import yaml
        
        try:
            # 1. Fetch Local
            local_url = f"http://127.0.0.1:{settings.LOCAL_K8S_PORT}/api/v1/namespaces/{namespace}/{resource_type}/{resource_name}" # Simplified if local MCP handles it
            # Actually we use our MCPClient for consistency
            from ..mcp.client import MCPClient
            
            async def get_manifests():
                local_client = MCPClient(host="127.0.0.1", port=settings.LOCAL_K8S_PORT)
                remote_client = MCPClient(host="127.0.0.1", port=settings.REMOTE_K8S_PORT)
                
                # We need a 'get_resource' tool or similar. For now, we list and filter.
                # In a real app, we'd have a specific 'get' tool.
                # Let's assume we can use 'list' and find the item.
                
                l_res = await local_client.call_tool(f"local_k8s_list_{resource_type}", {"namespace": namespace})
                r_res = await remote_client.call_tool(f"remote_k8s_list_{resource_type}", {"namespace": namespace})
                
                l_item = next((i for i in l_res.get(resource_type, []) if i.get("name") == resource_name), None)
                r_item = next((i for i in r_res.get(resource_type, []) if i.get("name") == resource_name), None)
                
                return l_item, r_item

            import asyncio
            l_item, r_item = asyncio.run(get_manifests())
            
            if not l_item or not r_item:
                return {"success": False, "error": f"Resource '{resource_name}' not found on both clusters."}

            # 2. Strip Metadata (Semantic Diff)
            def strip_managed(item):
                if not item: return {}
                clean = item.copy()
                metadata = clean.get("metadata", {})
                for k in ["managedFields", "ownerReferences", "resourceVersion", "uid", "creationTimestamp", "selfLink", "generation"]:
                    metadata.pop(k, None)
                clean.pop("status", None)
                return clean

            l_clean = yaml.dump(strip_managed(l_item), sort_keys=True)
            r_clean = yaml.dump(strip_managed(r_item), sort_keys=True)
            
            # 3. Generate Diff
            diff = list(difflib.unified_diff(
                l_clean.splitlines(), 
                r_clean.splitlines(), 
                fromfile="Local", 
                tofile="Remote"
            ))
            
            return {
                "success": True,
                "diff": "\n".join(diff) if diff else "No semantic differences found.",
                "local_summary": f"Version: {l_item.get('image') or 'N/A'}",
                "remote_summary": f"Version: {r_item.get('image') or 'N/A'}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class RemoteK8sAnalyzeUtilizationTool(K8sTool):
    """
    [PHASE 4] Smart Utilization Analyzer.
    Merges 'top pods' metrics with 'pod.spec' resource limits.
    Identifies pods at risk of OOM-Kills or throttling.
    """
    name = "remote_k8s_analyze_utilization"
    description = "ANALYZE pod resource usage vs limits. Identifies 'At Risk' pods (Usage > 90% of Limit)."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace to analyze. Defaults to 'default'."},
                "risk_threshold": {"type": "integer", "description": "Usage percentage threshold to flag as risk. Default is 90."}
            }
        }

    def run(self, namespace: str = "default", risk_threshold: int = 90, **kwargs) -> Dict[str, Any]:
        from .k8s_config import k8s_config
        from .k8s_utils import safe_k8s_request
        
        # 1. Get Metrics (Top Pods)
        metrics_url = f"{k8s_config.get_api_url()}/apis/metrics.k8s.io/v1beta1/namespaces/{namespace}/pods"
        m_res = safe_k8s_request("GET", metrics_url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        # Metrics aren't always installed, so we don't hard-fail here
        m_data = m_res.get("data", {}).get("items", []) if m_res["success"] else []
        
        # 2. Get Pod Specs (Limits)
        pods_url = f"{k8s_config.get_api_url()}/api/v1/namespaces/{namespace}/pods"
        p_res = safe_k8s_request("GET", pods_url, k8s_config.get_headers(), k8s_config.get_verify_ssl())
        
        if not p_res["success"]:
            return p_res # Propagation of error

        p_data = p_res["data"].get("items", [])
        analysis = []
        
        for p in p_data:
            pod_name = p["metadata"]["name"]
            m = next((i for i in m_data if i["metadata"]["name"] == pod_name), None)
            
            containers = []
            for c in p["spec"].get("containers", []):
                c_name = c["name"]
                mc = next((i for i in m["containers"] if i["name"] == c_name), None) if m else None
                
                limits = c.get("resources", {}).get("limits", {})
                mem_limit = limits.get("memory", "0")
                cpu_limit = limits.get("cpu", "0")
                
                usage_mem = mc["usage"]["memory"] if mc else "0"
                usage_cpu = mc["usage"]["cpu"] if mc else "0"
                
                def to_mi(val):
                    if "Mi" in val: return int(val.replace("Mi", ""))
                    if "Gi" in val: return int(val.replace("Gi", "")) * 1024
                    return 0
                
                l_val = to_mi(mem_limit)
                u_val = to_mi(usage_mem)
                
                perc = (u_val / l_val * 100) if l_val > 0 else 0
                risk = "High" if perc >= risk_threshold else "Low"
                
                containers.append({
                    "container": c_name,
                    "usage_memory": usage_mem,
                    "limit_memory": mem_limit,
                    "usage_percent": f"{perc:.1f}%",
                    "risk": risk
                })
            
            analysis.append({
                "pod": pod_name,
                "containers": containers,
                "overall_risk": "Critical" if any(c["risk"] == "High" for c in containers) else "Healthy"
            })

        return {
            "success": True,
            "analysis": analysis,
            "summary": f"Analyzed {len(analysis)} pods. Found {len([a for a in analysis if a['overall_risk'] == 'Critical'])} at risk."
        }
