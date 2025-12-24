# devops_agent/formatters/diagnostics.py
from typing import Dict, Any
from .base import BaseFormatter
import json

class DiagnosticFormatter(BaseFormatter):
    def can_format(self, tool_name: str) -> bool:
        # This formatter handles failures with raw error context
        return False # We will call it explicitly or use a special check in Registry

    def format(self, tool_name: str, result: Dict[str, Any]) -> str:
        raw_error = result.get("raw_error")
        if not raw_error:
            return f"❌ Operation failed: {result.get('error', 'Unknown error')}"

        from ..agent_module import ErrorAnalyzer
        raw_json_str = json.dumps(raw_error, indent=2)
        
        analyzer = ErrorAnalyzer()
        # Note: analyzer is sync, we might want to make it async later if needed
        prediction = analyzer(
            user_query="Action: " + tool_name,
            error_summary=result.get("error", "Unknown error"),
            raw_error=raw_error
        )
        return (
            f"❌ **Operation Failed**: {result.get('error')}\n\n"
            f"🐛 **Raw API Error**:\n```json\n{raw_json_str}\n```\n\n"
            f"🤖 **AI Diagnostic**:\n{prediction.explanation}"
        )
