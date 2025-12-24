# devops_agent/tool_indexer.py
"""
Dynamic Tool Auto-Indexer

Automatically syncs tool embeddings and infers regex templates at startup.
This ensures new tools are indexed with ZERO query-time overhead.

Design:
- Runs ONCE at startup (before servers accept queries)
- Diff-based: Only processes tools not already in cache
- Preserves manual templates (they take priority)
"""

import os
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

# Data paths
DATA_DIR = Path(__file__).parent / "data"
TOOL_EMBEDDINGS_PATH = DATA_DIR / "tool_embeddings.json"
AUTO_TEMPLATES_PATH = DATA_DIR / "auto_templates.json"

# Template inference patterns
# Maps tool name patterns to regex template generators
TEMPLATE_PATTERNS = {
    # describe_* patterns
    r".*_describe_pod$": {
        "pattern": r"describe (?:the )?(?:pod )?(?P<pod>[\w-]+)",
        "args": {"pod_name": "{pod}", "namespace": "default"}
    },
    r".*_describe_node$": {
        "pattern": r"describe (?:the )?node (?P<node>[\w-]+)",
        "args": {"node_name": "{node}"}
    },
    r".*_describe_service$": {
        "pattern": r"describe (?:the )?service (?P<service>[\w-]+)",
        "args": {"service_name": "{service}"}
    },
    r".*_describe_deployment$": {
        "pattern": r"describe (?:the )?deployment (?P<deployment>[\w-]+)",
        "args": {"deployment_name": "{deployment}"}
    },
    r".*_describe_namespace$": {
        "pattern": r"describe (?:the )?namespace (?P<namespace>[\w-]+)",
        "args": {"namespace": "{namespace}"}
    },
    # get_logs patterns
    r".*_get_logs$": {
        "pattern": r"(?:get |show )?logs (?:for )?(?:pod )?(?P<pod>[\w-]+)",
        "args": {"pod_name": "{pod}"}
    },
    # list_* patterns (no args needed)
    r".*_list_pods$": {
        "pattern": r"(?:list|show) (?:all )?pods",
        "args": {}
    },
    r".*_list_nodes$": {
        "pattern": r"(?:list|show) (?:all )?nodes",
        "args": {}
    },
    r".*_list_services$": {
        "pattern": r"(?:list|show) (?:all )?services",
        "args": {}
    },
    r".*_list_deployments$": {
        "pattern": r"(?:list|show) (?:all )?deployments",
        "args": {}
    },
    r".*_list_namespaces$": {
        "pattern": r"(?:list|show) (?:all )?namespaces",
        "args": {}
    },
    # top_* patterns
    r".*_top_nodes$": {
        "pattern": r"(?:top|metrics for) nodes",
        "args": {}
    },
    r".*_top_pods$": {
        "pattern": r"(?:top|metrics for) pods",
        "args": {}
    },
}


def get_all_tools() -> List[Dict[str, Any]]:
    """Get all tools from all registries."""
    tools = []
    
    # Docker tools
    try:
        from .tools import get_tools_schema
        tools.extend(get_tools_schema())
    except Exception as e:
        print(f"⚠️  Could not load Docker tools: {e}")
    
    # K8s tools
    try:
        from .k8s_tools import get_k8s_tools_schema
        tools.extend(get_k8s_tools_schema())
    except Exception as e:
        print(f"⚠️  Could not load K8s tools: {e}")
    
    return tools


def load_existing_embeddings() -> Dict[str, List[float]]:
    """Load existing tool embeddings from cache."""
    if not TOOL_EMBEDDINGS_PATH.exists():
        return {}
    
    try:
        with open(TOOL_EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_embeddings(embeddings: Dict[str, List[float]]):
    """Save tool embeddings to cache."""
    try:
        with open(TOOL_EMBEDDINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(embeddings, f, indent=2)
    except Exception as e:
        print(f"⚠️  Could not save embeddings: {e}")


def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for text using the embedding model."""
    try:
        from .llm.ollama_client import get_embeddings
        return get_embeddings(text)
    except Exception as e:
        print(f"⚠️  Embedding generation failed: {e}")
        return None


def infer_template(tool_name: str, tool_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Infer a regex template from tool name and schema.
    Returns None if no confident pattern match.
    """
    for pattern, template_def in TEMPLATE_PATTERNS.items():
        if re.match(pattern, tool_name):
            # Determine scope prefix for pattern (local/remote)
            scope_prefix = ""
            if tool_name.startswith("remote_k8s_"):
                scope_prefix = "remote "
            elif tool_name.startswith("local_k8s_"):
                scope_prefix = "local "
            
            return {
                "name": f"auto_{tool_name}",
                "pattern": scope_prefix + template_def["pattern"],
                "tool": tool_name,
                "args": template_def["args"],
                "auto_generated": True
            }
    
    return None


def sync_tool_index(verbose: bool = True) -> Dict[str, Any]:
    """
    Main sync function. Called at startup.
    Syncs both JSON embeddings and FAISS index.
    
    Returns:
        Dict with stats: {"new_embeddings": int, "new_templates": int, "total_tools": int, "faiss_synced": int}
    """
    stats = {"new_embeddings": 0, "new_templates": 0, "total_tools": 0, "faiss_synced": 0}
    
    if verbose:
        print("🔄 Syncing tool index...")
    
    # 1. Get all registered tools
    all_tools = get_all_tools()
    stats["total_tools"] = len(all_tools)
    
    if verbose:
        print(f"   Found {len(all_tools)} tools")
    
    # 2. Load existing embeddings
    embeddings = load_existing_embeddings()
    existing_count = len(embeddings)
    
    # 3. Find tools missing embeddings
    # Use simple tool name as key (matches existing tool_embeddings.json format)
    missing_tools = []
    for tool in all_tools:
        key = tool['name']  # Must match existing format!
        if key not in embeddings:
            missing_tools.append((tool, key))
    
    # 4. Generate embeddings for missing tools
    new_embeddings_list = []  # For FAISS sync
    if missing_tools:
        if verbose:
            print(f"   Generating embeddings for {len(missing_tools)} new tools...")
        
        for tool, key in missing_tools:
            # Create embedding text from name and description
            embed_text = f"{tool['name']}: {tool['description']}"
            embedding = generate_embedding(embed_text)
            if embedding:
                embeddings[key] = embedding
                new_embeddings_list.append((tool, embedding))
                stats["new_embeddings"] += 1
    
    # 5. Save updated embeddings (JSON)
    if stats["new_embeddings"] > 0:
        save_embeddings(embeddings)
        if verbose:
            print(f"   💾 Saved {stats['new_embeddings']} new embeddings (JSON)")
    
    # 6. Sync to FAISS index
    try:
        from .rag.faiss_index import get_faiss_index
        faiss_idx = get_faiss_index()
        
        # Get already indexed tools
        indexed_tools = {t["name"] for t in faiss_idx.list_all()}
        
        # Add missing tools to FAISS
        for tool in all_tools:
            name = tool['name']
            if name not in indexed_tools and name in embeddings:
                faiss_idx.add(name, embeddings[name], tool.get('description', ''))
                stats["faiss_synced"] += 1
        
        if verbose and stats["faiss_synced"] > 0:
            print(f"   🚀 Synced {stats['faiss_synced']} tools to FAISS index")
    except Exception as e:
        if verbose:
            print(f"   ⚠️ FAISS sync skipped: {e}")
    
    # 7. Infer templates for tools
    auto_templates = []
    for tool in all_tools:
        template = infer_template(tool["name"], tool)
        if template:
            auto_templates.append(template)
    
    stats["new_templates"] = len(auto_templates)
    
    # 8. Save auto-generated templates (separate from manual ones)
    if auto_templates:
        try:
            with open(AUTO_TEMPLATES_PATH, "w", encoding="utf-8") as f:
                json.dump({"templates": auto_templates}, f, indent=2)
            if verbose:
                print(f"   📝 Generated {len(auto_templates)} auto-templates")
        except Exception as e:
            print(f"⚠️  Could not save auto-templates: {e}")
    
    if verbose:
        print(f"✅ Tool index sync complete ({stats['total_tools']} tools, {stats['new_embeddings']} new embeddings)")
    
    return stats


def get_auto_templates() -> List[Dict[str, Any]]:
    """Load auto-generated templates (for router to use)."""
    if not AUTO_TEMPLATES_PATH.exists():
        return []
    
    try:
        with open(AUTO_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("templates", [])
    except Exception:
        return []


# For CLI usage
if __name__ == "__main__":
    sync_tool_index(verbose=True)
