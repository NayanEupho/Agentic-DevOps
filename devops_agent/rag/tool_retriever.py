
import json
import os
import math
from functools import lru_cache
from typing import List, Dict, Any, Tuple, Optional
from ..llm.ollama_client import get_embeddings
from ..tools import get_tools_schema
from ..k8s_tools import get_k8s_tools_schema

# Simple async cache for query embeddings
_ASYNC_QUERY_CACHE: Dict[str, List[float]] = {}

async def _get_async_query_embedding(query: str) -> List[float]:
    """Cache query embeddings asynchronously."""
    if query in _ASYNC_QUERY_CACHE:
        return _ASYNC_QUERY_CACHE[query]
    
    from ..llm.ollama_client import async_get_embeddings
    emb = await async_get_embeddings(query)
    if emb:
        # Keep cache size small
        if len(_ASYNC_QUERY_CACHE) > 256:
            _ASYNC_QUERY_CACHE.clear()
        _ASYNC_QUERY_CACHE[query] = emb
    return emb or []


class ToolRetriever:
    """
    Retrieves the most relevant tools for a given query using vector embeddings.
    
    Uses FAISS for fast similarity search (O(log n) vs O(n)).
    Falls back to JSON-based linear search if FAISS unavailable.
    """
    
    def __init__(self, cache_path: str = "devops_agent/data/tool_embeddings.json"):
        self.cache_path = cache_path
        self.tools = []
        self.tool_embeddings = {}  # Fallback JSON cache
        self.faiss_index = None
        
        # Load tools
        self.tools = get_tools_schema() + get_k8s_tools_schema()
        # Note: _init_index is called synchronously in __init__ but 
        # _sync_tools_to_faiss will now be a background task or handled on first retrieve
        self._init_index()

    def _init_index(self):
        """Initialize FAISS index or fallback to JSON."""
        try:
            from .faiss_index import get_faiss_index
            self.faiss_index = get_faiss_index()
            # Background sync is better for "Lightning Fast" startup
        except Exception as e:
            print(f"⚠️ FAISS unavailable ({e}), using JSON fallback")
            self.faiss_index = None
            self._load_json_index()

    async def _async_ensure_synced(self):
        """Ensure tools are synced before retrieval if not already done."""
        if self.faiss_index:
            await self._sync_tools_to_faiss()
    
    async def _sync_tools_to_faiss(self):
        """Ensure all tools are in FAISS index (Asynchronous)."""
        if not self.faiss_index:
            return
            
        indexed_tools = {t["name"] for t in self.faiss_index.list_all()}
        
        from ..llm.ollama_client import async_get_embeddings
        tasks = []
        for tool in self.tools:
            name = tool['name']
            if name not in indexed_tools:
                text = f"{name}: {tool.get('description', '')}"
                tasks.append(self._add_tool_to_faiss(name, text, tool.get('description', '')))
        
        if tasks:
            import asyncio
            await asyncio.gather(*tasks)

    async def _add_tool_to_faiss(self, name: str, text: str, desc: str):
        from ..llm.ollama_client import async_get_embeddings
        emb = await async_get_embeddings(text)
        if emb:
            self.faiss_index.add(name, emb, desc)
            print(f"   Added {name} to FAISS index")
    
    def _load_json_index(self):
        """Fallback: Load JSON-based index."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r") as f:
                    self.tool_embeddings = json.load(f)
            except Exception:
                pass
                
        # Index missing tools
        dirty = False
        for tool in self.tools:
            name = tool['name']
            text = f"{name}: {tool.get('description', '')}"
            
            if name not in self.tool_embeddings:
                print(f"🔍 Indexing tool: {name}...")
                emb = get_embeddings(text)
                if emb:
                    self.tool_embeddings[name] = emb
                    dirty = True
        
        if dirty:
            try:
                with open(self.cache_path, "w") as f:
                    json.dump(self.tool_embeddings, f)
            except Exception:
                pass
    
    async def retrieve(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """
        Return top_k tools relevant to the query (Asynchronous).
        """
        # Ensure index is ready (background sync check)
        await self._async_ensure_synced()
        
        query_emb = await _get_async_query_embedding(query)
        if not query_emb:
            return self.tools
        
        # Try FAISS first
        if self.faiss_index and self.faiss_index.count() > 0:
            return self._retrieve_faiss(query_emb, top_k)
        else:
            return self._retrieve_json(query_emb, top_k)
    
    def _retrieve_faiss(self, query_emb: List[float], top_k: int) -> List[Dict[str, Any]]:
        """FAISS-based retrieval (fast)."""
        results = self.faiss_index.search(query_emb, top_k)
        
        # Map tool names back to full schemas
        tool_map = {t['name']: t for t in self.tools}
        return [tool_map[name] for name, _ in results if name in tool_map]
    
    def _retrieve_json(self, query_emb: List[float], top_k: int) -> List[Dict[str, Any]]:
        """JSON-based retrieval (fallback)."""
        scores = []
        for tool in self.tools:
            name = tool['name']
            emb = self.tool_embeddings.get(name)
            if emb:
                score = self._cosine_similarity(query_emb, emb)
                scores.append((score, tool))
            else:
                scores.append((0.0, tool))
                
        scores.sort(key=lambda x: x[0], reverse=True)
        return [t for s, t in scores[:top_k]]

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculate cosine similarity."""
        if not v1 or not v2: return 0.0
        
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        
        if norm_a == 0 or norm_b == 0: return 0.0
        
        return dot_product / (norm_a * norm_b)


_retriever_instance = None

def get_retriever():
    global _retriever_instance
    if not _retriever_instance:
         _retriever_instance = ToolRetriever()
    return _retriever_instance
