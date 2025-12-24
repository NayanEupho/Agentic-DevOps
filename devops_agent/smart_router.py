
from typing import List, Set
import re

class SmartMCPRouter:
    """
    Phase 8: Smart MCP Routing (Layer 0)
    
    Determines which MCP servers are relevant for a given query BEFORE
    we ask the LLM to select specific tools. This reduces context noise.
    """
    
    MCP_DOCKER = "docker"
    MCP_K8S_LOCAL = "k8s_local"
    MCP_K8S_REMOTE = "k8s_remote"
    MCP_CHAT = "chat"
    
    def __init__(self):
        # Define keywords for each MCP
        self.keywords = {
            self.MCP_DOCKER: {
                "docker", "container", "image", "volume", "network", "compose"
            },
            self.MCP_K8S_LOCAL: {
                "local", "minikube", "kind", "desktop", "localhost"
            },
            self.MCP_K8S_REMOTE: {
                "remote", "cluster", "aws", "gcp", "azure", "cloud", "production", "staging"
            },
            self.MCP_CHAT: {
                "hi", "hello", "hey", "help", "who are you", "what is this", "thanks", "thank you", "bye", "test", "explain", "why"
            }
        }
        
        # Shared K8s terms that could be either
        self.k8s_common = {
            "pod", "node", "deployment", "service", "namespace", "replicaset", "configmap", "secret", "ingress", "pvc", "pv", "log", "logs", "describe", "ip", "port",
            "status", "phase", "labeled", "label", "selector", "filtering", "filter", "promote", "trace", "diff", "utilization", "compare"
        }
        
        # Follow-up indicators (Context-Dependent)
        self.context_indicators = {
            "it", "that", "this", "them", "those", "here", "there", "details", "more", "describe", "the"
        }

    def route(self, query: str, session_id: str = None) -> List[str]:
        """
        Analyze query and return list of relevant MCP IDs.
        If unsure, returns ALL relevant MCPs to be safe.
        """
        q_lower = query.lower()
        selected_mcps = set()
        
        # [PHASE 10] Context Check
        # If query is very short or contains references, check sticky context
        from .context_cache import context_cache
        
        is_follow_up = any(w in q_lower.split() for w in self.context_indicators)
        if session_id and is_follow_up:
            last_mcp = context_cache.get_last_mcp(session_id)
            if last_mcp:
                # If "describe it" and last was remote k8s, include it!
                selected_mcps.add(last_mcp)
        
        # 1. Check Specific Keywords
        for mcp, keywords in self.keywords.items():
            for k in keywords:
                if k in q_lower:
                    selected_mcps.add(mcp)
                    
        # 2. Check Common K8s Terms
        is_k8s = any(k in q_lower for k in self.k8s_common)
        
        if is_k8s:
            # If we already have a specific scope (local/remote), trust it.
            # If NOT, we must decide default behavior.
            has_local = self.MCP_K8S_LOCAL in selected_mcps
            has_remote = self.MCP_K8S_REMOTE in selected_mcps
            
            if not has_local and not has_remote:
                # Ambiguous K8s query (e.g., "list pods")
                # Phase 8 Requirement: "list all pods in my remote and local k8s" -> Both
                # Default policy: Include BOTH if ambiguous and generic, 
                # OR follow the user's remote-first preference?
                # The user asked for "smart logic".
                
                # If the user says "remote and local", keywords above would catch both.
                # If they say "list pods", neither is caught. 
                # We should return BOTH so the Agent can choose (or default to remote).
                selected_mcps.add(self.MCP_K8S_REMOTE)
                selected_mcps.add(self.MCP_K8S_LOCAL)
            
            elif has_local and not has_remote:
                # explicitly local
                pass 
                
            elif has_remote and not has_local:
                # explicitly remote
                pass
                
        # 3. Fallback: If nothing matched, maybe it's a generic "status" or "help"?
        if not selected_mcps:
            # ... (existing fallback logic) ...
            if "status" in q_lower or "check" in q_lower:
                selected_mcps = {self.MCP_DOCKER, self.MCP_K8S_LOCAL, self.MCP_K8S_REMOTE}
            else:
                if len(q_lower.split()) > 5:
                    selected_mcps = {self.MCP_DOCKER, self.MCP_K8S_LOCAL, self.MCP_K8S_REMOTE, self.MCP_CHAT}
                else:
                    selected_mcps = {self.MCP_CHAT}
        
        # [OPTIMIZATION] Filter out disconnected MCPs (except for explicit requests)
        # If the user says "why is remote down", we SHOULD still load it to let the agent explain.
        # But if they say "list pods", and pulse says remote is down, we skip it.
        try:
            from .pulse import get_pulse
            pulse = get_pulse()
            is_explicit_remote = "remote" in q_lower
            if self.MCP_K8S_REMOTE in selected_mcps and not is_explicit_remote:
                remote_status = pulse.get_status(self.MCP_K8S_REMOTE).get("status")
                if remote_status == "disconnected":
                    # print(f"💓 [SmartRouter] Skipping disconnected Remote MCP")
                    selected_mcps.discard(self.MCP_K8S_REMOTE)
        except Exception:
            pass
            
        return list(selected_mcps)

# Global instance
smart_router = SmartMCPRouter()
