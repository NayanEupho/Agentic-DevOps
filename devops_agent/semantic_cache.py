
import json
import os
import time
import math
from typing import List, Dict, Any, Optional
from .llm.ollama_client import get_embeddings, async_get_embeddings

class SemanticCache:
    """
    Layer 1.5 Cache: Vector-based semantic similarity cache.
    Stores query -> tool_calls and final output.
    Reduces LLM latency to ~50ms (embedding cost only) for repeat or near-duplicate queries.
    """
    
    def __init__(self, cache_path: str = "devops_agent/data/semantic_cache.json", threshold: float = 0.98):
        self.cache_path = cache_path
        self.threshold = threshold
        self.entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception:
                self.entries = []

    def _save(self):
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save semantic cache: {e}")

    async def lookup(self, query: str, active_mcp: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a semantically similar query in the cache (Asynchronous)."""
        if not self.entries:
            return None
            
        query_emb = await async_get_embeddings(query)
        if not query_emb:
            return None
            
        best_match = None
        highest_score = -1.0
        
        for entry in self.entries:
            # Contextual isolation: don't match across different MCP domains if specified
            if active_mcp and entry.get("active_mcp") != active_mcp:
                continue
                
            score = self._cosine_similarity(query_emb, entry["embedding"])
            if score > highest_score:
                highest_score = score
                best_match = entry
        
        if highest_score >= self.threshold:
            print(f"🎯 [SemanticCache] Hit! (Score: {highest_score:.4f})")
            return {
                "output": best_match["output"],
                "tool_calls": best_match["tool_calls"],
                "cached": True
            }
            
        return None

    async def add(self, query: str, output: str, tool_calls: List[Dict], active_mcp: Optional[str] = None):
        """Add a successful result to the cache (Asynchronous)."""
        # Don't cache error results
        if "failed" in output.lower() or "error" in output.lower():
            return
            
        # Don't cache confirmation requests (they are transient)
        if any("confirmation" in str(tc) for tc in tool_calls):
            return

        query_emb = await async_get_embeddings(query)
        if not query_emb:
            return
            
        # Avoid duplicates in cache
        for entry in self.entries:
            if entry["query"] == query:
                return

        new_entry = {
            "query": query,
            "embedding": query_emb,
            "output": output,
            "tool_calls": tool_calls,
            "active_mcp": active_mcp,
            "timestamp": time.time()
        }
        
        self.entries.append(new_entry)
        
        # Keep cache size manageable (Max 500 entries)
        if len(self.entries) > 500:
            self.entries.pop(0)
            
        # Async-safe disk I/O via executor
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._save)
        except RuntimeError:
            self._save()

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2: return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0 or norm_b == 0: return 0.0
        return dot_product / (norm_a * norm_b)

_cache_instance = None
def get_semantic_cache():
    global _cache_instance
    if not _cache_instance:
        _cache_instance = SemanticCache()
    return _cache_instance
