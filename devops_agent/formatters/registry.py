# devops_agent/formatters/registry.py
from typing import Dict, Any, List
from .base import BaseFormatter

class FormatterRegistry:
    _formatters: List[BaseFormatter] = []

    @classmethod
    def register(cls, formatter: BaseFormatter):
        cls._formatters.append(formatter)

    @classmethod
    def format(cls, tool_name: str, result: Dict[str, Any]) -> str:
        # 1. Handle Errors with AI diagnostics if available
        if not result.get("success"):
            from .diagnostics import DiagnosticFormatter
            return DiagnosticFormatter().format(tool_name, result)

        # 2. Handle specific formatters
        for formatter in cls._formatters:
            if formatter.can_format(tool_name):
                return formatter.format(tool_name, result)
        
        # Generic JSON fallback
        import json
        return f"✅ **Result for {tool_name}**:\n```json\n{json.dumps(result, indent=2)}\n```"

def get_registry():
    return FormatterRegistry
