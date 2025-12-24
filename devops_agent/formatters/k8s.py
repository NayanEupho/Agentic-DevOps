# devops_agent/formatters/k8s.py
from typing import Dict, Any
from .base import BaseFormatter
from collections import Counter

class KubernetesFormatter(BaseFormatter):
    def can_format(self, tool_name: str) -> bool:
        return "k8s_" in tool_name

    def format(self, tool_name: str, result: Dict[str, Any]) -> str:
        if "list_pods" in tool_name:
             pods = result.get("pods", [])
             ns = result.get("namespace", "unknown")
             scope = "REMOTE" if "remote" in tool_name else "LOCAL"
             if not pods: return f"✅ Success! No pods in '{ns}' ({scope})."

             status_counts = Counter([p.get('phase', 'Unknown') for p in pods])
             summary = ", ".join([f"{k}: {v}" for k, v in status_counts.items()])

             headers = ["Status", "Name", "Restarts", "Age", "Node"]
             rows = []
             for p in pods:
                 status = p.get('phase', 'Unknown')
                 emoji = "🟢" if status == "Running" else "🟡" if status == "Pending" else "🔴"
                 rows.append([
                     f"{emoji} {status}",
                     p['name'],
                     p.get('restarts', 0),
                     p.get('age', '?'),
                     p.get('node', '?')
                 ])
             return f"✅ **Kubernetes Pods in '{ns}' ({scope})**\n*Summary: {summary}*\n\n" + self._to_markdown_table(headers, rows)

        elif "describe_pod" in tool_name or "describe_deployment" in tool_name:
            # High-intelligence formatting for complex strings
            data = result.get("data", str(result))
            if isinstance(data, str) and "Name:" in data:
                return f"📋 **Detailed Description**:\n```yaml\n{data}\n```"
            return f"✅ **Resource Details**:\n{data}"

        return f"✅ K8s Tool '{tool_name}' executed successfully."
