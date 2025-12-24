# devops_agent/formatters/docker.py
from typing import Dict, Any
from .base import BaseFormatter

class DockerFormatter(BaseFormatter):
    def can_format(self, tool_name: str) -> bool:
        return tool_name.startswith("docker_")

    def format(self, tool_name: str, result: Dict[str, Any]) -> str:
        if tool_name == "docker_list_containers":
            containers = result.get("containers", [])
            count = result.get("count", 0)
            if not containers: return "✅ Success! No containers found."
            
            headers = ["Status", "Name", "ID", "Image", "State"]
            rows = []
            for c in containers:
                status_emoji = "🟢" if "Up" in c.get('status', '') else "🔴"
                rows.append([
                    status_emoji, 
                    c['name'], 
                    c.get('id', 'unknown')[:12], 
                    c['image'], 
                    c['status']
                ])
            return f"✅ **Found {count} container(s):**\n\n" + self._to_markdown_table(headers, rows)
            
        elif tool_name == "docker_run_container":
             msg = result.get("message", "Container started.")
             return f"✅ **{msg}**\n\n| ID | Name |\n|---|---|\n| `{result.get('container_id')}` | **{result.get('name')}** |"

        elif tool_name == "docker_stop_container":
             msg = result.get("message", "Container stopped.")
             return f"✅ **{msg}**\n\n| ID | Name |\n|---|---|\n| `{result.get('container_id')}` | **{result.get('name')}** |"

        return f"✅ Tool '{tool_name}' executed successfully."
