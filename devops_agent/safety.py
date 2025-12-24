
# devops_agent/safety.py
"""
Safety Layer Module

This module analyzes tool calls for potential risks.
It is non-blocking and enables "Human-in-the-Loop" flows for both CLI and Web UI.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

# Define which tools or prefixes are considered "dangerous"
DANGEROUS_PREFIXES = {
    "docker_stop", "docker_rm", "docker_prune",
    "k8s_delete", "local_k8s_delete", "remote_k8s_delete",
    "remote_k8s_promote", "remote_k8s_exec"
}

# Specific exact names for tools that don't follow prefix patterns but are risky
DANGEROUS_TOOLS_EXACT = {
    "docker_run_container",
}

def is_dangerous(tool_name: str) -> bool:
    """Check if a tool is dangerous using fast prefix matching."""
    if tool_name in DANGEROUS_TOOLS_EXACT:
        return True
    return any(tool_name.startswith(p) for p in DANGEROUS_PREFIXES)

@dataclass
class RiskAssessment:
    is_dangerous: bool
    risk_level: str = "LOW" # LOW, MEDIUM, HIGH
    reason: str = ""
    impact_analysis: List[str] = None
    
    def to_dict(self):
        return asdict(self)

def analyze_risk(tool_name: str, arguments: Dict[str, Any]) -> RiskAssessment:
    """
    Analyze risk for a given tool call (Optimized prefix matching).
    """
    if not is_dangerous(tool_name):
        return RiskAssessment(is_dangerous=False, risk_level="LOW", impact_analysis=[])
        
    # Default High Risk for known dangerous tools
    assessment = RiskAssessment(
        is_dangerous=True,
        risk_level="HIGH",
        reason=f"Tool '{tool_name}' performs destructive or resource-intensive actions.",
        impact_analysis=[]
    )
    
    # Specific Impact Analysis
    if tool_name == "docker_stop_container":
        cid = arguments.get('container_id', 'unknown')
        assessment.impact_analysis = [
            f"Stops container '{cid}' immediately.",
            "Service interruption for applications in this container.",
            "Potential data loss in ephemeral volumes."
        ]
        
    elif tool_name == "docker_run_container":
        img = arguments.get('image', 'unknown')
        assessment.impact_analysis = [
            f"Starts new container from '{img}'.",
            "Consumes system resources (CPU/RAM).",
            "Binds network ports."
        ]
        
    elif "delete" in tool_name:
        assessment.impact_analysis = [
            "PERMANENTLY removes the target resource.",
            "Cannot be undone.",
            "Service interruption."
        ]
        
    elif "exec" in tool_name:
        cmd = "unknown command"
        if "command" in arguments: cmd = arguments["command"]
        elif "cmd" in arguments: cmd = arguments["cmd"]
        
        assessment.impact_analysis = [
            f"Executes arbitrary command: '{cmd}'",
            "Full shell access risks.",
            "Potential system modification."
        ]
        
    elif "promote" in tool_name:
        name = arguments.get('name', 'unknown')
        res_type = arguments.get('resource_type', 'resource')
        assessment.impact_analysis = [
            f"Copies {res_type} '{name}' to the Remote Cluster.",
            "Modifies remote cluster state.",
            "Potential for configuration drift if versions mismatch."
        ]

    return assessment

# Legacy/Helper for manual overrides
def add_dangerous_tool(tool_name: str):
    DANGEROUS_TOOLS.add(tool_name)

def remove_dangerous_tool(tool_name: str):
    DANGEROUS_TOOLS.discard(tool_name)