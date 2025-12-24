# devops_agent/formatters/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseFormatter(ABC):
    @abstractmethod
    def can_format(self, tool_name: str) -> bool:
        pass

    @abstractmethod
    def format(self, tool_name: str, result: Dict[str, Any]) -> str:
        pass

    def _to_markdown_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Helper to create a markdown table."""
        if not headers or not rows: return ""
        header_str = "| " + " | ".join(headers) + " |"
        sep_str = "| " + " | ".join(["---"] * len(headers)) + " |"
        row_strs = ["| " + " | ".join([str(cell) for cell in row]) + " |" for row in rows]
        return "\n".join([header_str, sep_str] + row_strs)
