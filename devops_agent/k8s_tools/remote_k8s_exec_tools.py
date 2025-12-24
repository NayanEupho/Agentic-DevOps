
import subprocess
import shlex
from typing import Dict, Any, List
from .k8s_base import K8sTool

# Allow-list of safe commands to prevent total destruction via exec
SAFE_COMMANDS = ["ls", "cat", "ps", "env", "printenv", "top", "date", "whoami", "ip", "netstat", "df", "du", "tail", "head", "grep", "echo"]

class RemoteK8sExecTool(K8sTool):
    name = "remote_k8s_exec"
    description = "Execute a SAFE read-only command inside a container in the REMOTE cluster. Allowed: ls, cat, ps, env, etc. Use this to inspect files or checking running processes."

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Name of the pod."
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace of the pod."
                },
                "container_name": {
                    "type": "string",
                    "description": "Optional: valid container name if pod has multiple."
                },
                "command": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command to run as a list of strings, e.g. ['cat', '/app/config.json']."
                }
            },
            "required": ["pod_name", "namespace", "command"]
        }

    def run(self, pod_name: str, namespace: str, command: List[str], container_name: str = None, **kwargs) -> Dict[str, Any]:
        try:
            # 1. Safety Check
            if not command:
                return {"success": False, "error": "Command list cannot be empty."}
            
            base_cmd = command[0]
            if base_cmd not in SAFE_COMMANDS:
                return {
                    "success": False, 
                    "error": f"Command '{base_cmd}' is NOT in the safe allow-list. Allowed: {', '.join(SAFE_COMMANDS)}"
                }

            # 2. Construct kubectl command
            # We assume 'kubectl' is available in PATH and configured for the remote context
            # OR we need to pass a kubeconfig. 
            # Ideally we reuse the token mechanism, but kubectl requires a kubeconfig file.
            # Assuming the environment has a valid KUBECONFIG or we construct arguments.
            # For this Phase, we'll try standard `kubectl exec` assuming the machine running this agent has context.
            # IF NOT, we might need to supply --token and --server flags if supported by kubectl directly?
            # kubectl doesn't support passing token easily without config. 
            # We will try using the flags: --server and --token if available in k8s_config.
            
            from .k8s_config import k8s_config
            
            # Security Note: Passing token in CLI args is visible in process list, but acceptable for this prototype.
            # Better: Write a temp kubeconfig file.
            
            import tempfile
            import os
            
            # Create a localized kubeconfig for this execution
            # This is robust and secure way to use kubectl with the known token
            kubeconfig_yaml = f"""
apiVersion: v1
clusters:
- cluster:
    insecure-skip-tls-verify: {str(not k8s_config.get_verify_ssl()).lower()}
    server: {k8s_config.get_api_url()}
  name: remote-cluster
contexts:
- context:
    cluster: remote-cluster
    user: agent-user
  name: remote-context
current-context: remote-context
kind: Config
users:
- name: agent-user
  user:
    token: {k8s_config.token}
"""
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".yaml") as tmp_kc:
                tmp_kc.write(kubeconfig_yaml)
                tmp_kc_path = tmp_kc.name
            
            try:
                # Construct Args
                k_args = [
                    "kubectl", "exec", 
                    pod_name,
                    "-n", namespace,
                    "--kubeconfig", tmp_kc_path
                ]
                
                if container_name:
                    k_args.extend(["-c", container_name])
                    
                k_args.append("--")
                k_args.extend(command)
                
                # Execute
                result = subprocess.run(
                    k_args,
                    capture_output=True,
                    text=True,
                    timeout=15 # Security timeout
                )
                
                if result.returncode != 0:
                    return {
                        "success": False, 
                        "error": f"Exec failed (Exit {result.returncode}): {result.stderr}",
                        "stdout": result.stdout
                    }
                
                return {
                    "success": True,
                    "output": result.stdout,
                    "command_executed": " ".join(command)
                }
                
            finally:
                # Cleanup
                if os.path.exists(tmp_kc_path):
                    os.remove(tmp_kc_path)

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out."}
        except Exception as e:
            return {"success": False, "error": str(e)}
