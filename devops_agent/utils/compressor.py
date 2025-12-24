
import re
from typing import Dict, Any, List

class ContextCompressor:
    """
    [PHASE 3] Deep Intelligence: Context Compression.
    Reduces the size of large K8s/Docker outputs while preserving high-fidelity information.
    """
    
    @staticmethod
    def compress_k8s_describe(text: str, mode: str = "COMPRESSED") -> str:
        """
        Compresses K8s describe output by removing repetitive metadata.
        Set mode="RAW" to bypass compression.
        """
        if mode == "RAW":
            return text
            
        lines = text.split("\n")
        # ... existing logic ...
        compressed = []
        skip_sections = ["Managed Fields:", "Owner References:", "Resource Version:"]
        
        in_events = False
        event_count = 0
        
        for line in lines:
            line_strip = line.strip()
            
            # Skip noise
            if any(line_strip.startswith(s) for s in skip_sections):
                continue
                
            # Compress Events (Keep only latest 5)
            if "Events:" in line:
                in_events = True
                compressed.append(line)
                continue
            
            if in_events:
                if line_strip and event_count < 5:
                    compressed.append(line)
                    event_count += 1
                elif not line_strip:
                    in_events = False
                continue
            
            # Keep everything else
            compressed.append(line)
            
        return "\n".join(compressed)

    @staticmethod
    def compress_json_result(data: Dict[str, Any], max_items: int = 5, mode: str = "COMPRESSED") -> Dict[str, Any]:
        """
        Compresses large JSON lists. Set mode="RAW" to bypass.
        """
        if mode == "RAW" or not isinstance(data, dict):
            return data
            
        new_data = data.copy()
        for key, value in new_data.items():
            if isinstance(value, list) and len(value) > max_items:
                new_data[key] = value[:max_items]
                new_data[f"{key}_summary"] = f"Showing {max_items} of {len(value)} items. Use specific filters for more."
                
        return new_data
