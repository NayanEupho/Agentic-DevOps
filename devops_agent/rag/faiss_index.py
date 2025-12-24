# devops_agent/rag/faiss_index.py
"""
FAISS-based Tool Index for Lightning-Fast Retrieval

Features:
- GPU-accelerated similarity search (faiss-gpu)
- Automatic fallback to CPU if GPU unavailable
- Persistent index with atomic save operations
- Thread-safe operations with file locking
- Integration with Dynamic Tool Auto-Indexer
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from filelock import FileLock
import logging

logger = logging.getLogger(__name__)

# FAISS import with GPU fallback
try:
    import faiss
    # Try to use GPU
    try:
        GPU_AVAILABLE = faiss.get_num_gpus() > 0
        if GPU_AVAILABLE:
            logger.info("🚀 FAISS GPU support detected")
    except:
        GPU_AVAILABLE = False
except ImportError:
    faiss = None
    GPU_AVAILABLE = False
    logger.warning("⚠️ FAISS not installed. Install with: pip install faiss-gpu")

# Constants
EMBEDDING_DIM = 768  # nomic-embed-text dimension
INDEX_FILE = "faiss_index.bin"
METADATA_FILE = "faiss_metadata.json"


class FaissToolIndex:
    """
    FAISS-based vector index for tool retrieval.
    
    Uses IndexFlatIP (Inner Product) for normalized embeddings,
    which is equivalent to cosine similarity.
    """
    
    def __init__(self, data_dir: str = None):
        """Initialize the FAISS index."""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.data_dir / INDEX_FILE
        self.metadata_path = self.data_dir / METADATA_FILE
        self.lock_path = self.data_dir / "faiss.lock"
        
        # In-memory state
        self.index: Optional[faiss.Index] = None
        self.metadata: Dict[str, Any] = {
            "tools": {},      # tool_name -> {"idx": int, "description": str}
            "idx_to_tool": {} # str(idx) -> tool_name
        }
        
        self._load_or_create()
    
    def _load_or_create(self):
        """Load existing index or create new one."""
        if faiss is None:
            logger.error("FAISS not available")
            return
            
        with FileLock(str(self.lock_path)):
            if self.index_path.exists() and self.metadata_path.exists():
                try:
                    self._load_index()
                    logger.info(f"✅ Loaded FAISS index with {self.count()} tools")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load index: {e}. Creating new.")
                    self._create_empty_index()
            else:
                self._create_empty_index()
    
    def _create_empty_index(self):
        """Create empty FAISS index."""
        # Use IndexFlatIP for Inner Product (cosine sim with normalized vectors)
        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        
        # Move to GPU if available
        if GPU_AVAILABLE:
            try:
                res = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
                logger.info("🚀 FAISS index moved to GPU")
            except Exception as e:
                logger.warning(f"⚠️ GPU transfer failed: {e}")
        
        self.metadata = {"tools": {}, "idx_to_tool": {}}
    
    def _load_index(self):
        """Load index from disk."""
        # Load metadata
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        
        # Load FAISS index
        self.index = faiss.read_index(str(self.index_path))
        
        # Move to GPU if available
        if GPU_AVAILABLE:
            try:
                res = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
            except:
                pass
    
    def _save(self):
        """Save index to disk atomically."""
        with FileLock(str(self.lock_path)):
            # Save metadata
            temp_meta = self.metadata_path.with_suffix(".tmp")
            with open(temp_meta, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2)
            temp_meta.replace(self.metadata_path)
            
            # Save FAISS index (convert from GPU if needed)
            index_to_save = self.index
            if GPU_AVAILABLE and hasattr(self.index, 'index'):
                index_to_save = faiss.index_gpu_to_cpu(self.index)
            
            temp_idx = self.index_path.with_suffix(".tmp")
            faiss.write_index(index_to_save, str(temp_idx))
            temp_idx.replace(self.index_path)
    
    def add(self, tool_name: str, embedding: List[float], description: str = "") -> bool:
        """Add or update a tool embedding."""
        if faiss is None or self.index is None:
            return False
            
        # Normalize embedding for cosine similarity
        emb = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(emb)
        
        # Check if tool already exists
        if tool_name in self.metadata["tools"]:
            # Remove old entry (FAISS doesn't support in-place update)
            self.remove(tool_name)
        
        # Add to index
        idx = self.index.ntotal  # Next index
        self.index.add(emb)
        
        # Update metadata
        self.metadata["tools"][tool_name] = {
            "idx": idx,
            "description": description[:200]  # Truncate for storage
        }
        self.metadata["idx_to_tool"][str(idx)] = tool_name
        
        self._save()
        return True
    
    def remove(self, tool_name: str) -> bool:
        """Remove a tool from the index."""
        if tool_name not in self.metadata["tools"]:
            return False
        
        # FAISS IndexFlat doesn't support removal
        # We need to rebuild without this tool
        tools_to_keep = {k: v for k, v in self.metadata["tools"].items() if k != tool_name}
        
        if not tools_to_keep:
            self.clear()
            return True
        
        # Rebuild is expensive but necessary for removal
        # For small index (<200), this is acceptable
        self._rebuild_without(tool_name)
        return True
    
    def _rebuild_without(self, exclude_tool: str):
        """Rebuild index excluding specific tool."""
        # This is called rarely (only on explicit removal)
        old_metadata = self.metadata.copy()
        self._create_empty_index()
        
        # We don't have the embeddings stored, so we need to regenerate
        # For now, just remove from metadata (embeddings lost)
        # In practice, user should use 'rebuild' command after removals
        
        for tool_name, info in old_metadata["tools"].items():
            if tool_name != exclude_tool:
                # Mark as needing re-embedding
                pass
        
        logger.warning(f"⚠️ Tool '{exclude_tool}' removed. Run 'devops-agent rag rebuild' to regenerate index.")
    
    def search(self, query_embedding: List[float], top_k: int = 8) -> List[Tuple[str, float]]:
        """Search for similar tools. Returns [(tool_name, score), ...]"""
        if faiss is None or self.index is None or self.index.ntotal == 0:
            return []
        
        # Normalize query
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        
        # Search
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query, k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for missing
                continue
            tool_name = self.metadata["idx_to_tool"].get(str(idx))
            if tool_name:
                results.append((tool_name, float(score)))
        
        return results
    
    def list_all(self) -> List[Dict[str, Any]]:
        """List all indexed tools with metadata."""
        return [
            {"name": name, "idx": info["idx"], "description": info.get("description", "")}
            for name, info in self.metadata["tools"].items()
        ]
    
    def get_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific tool."""
        if tool_name not in self.metadata["tools"]:
            return None
        info = self.metadata["tools"][tool_name]
        return {
            "name": tool_name,
            "idx": info["idx"],
            "description": info.get("description", ""),
            "indexed": True
        }
    
    def count(self) -> int:
        """Return number of indexed tools."""
        return len(self.metadata["tools"])
    
    def clear(self):
        """Clear all tools from index."""
        self._create_empty_index()
        self._save()
        logger.info("🗑️ FAISS index cleared")
    
    def verify(self) -> Dict[str, Any]:
        """Verify index consistency."""
        issues = []
        
        # Check index size matches metadata
        if self.index is not None:
            if self.index.ntotal != len(self.metadata["tools"]):
                issues.append(f"Index size mismatch: {self.index.ntotal} vs {len(self.metadata['tools'])}")
        
        # Check bidirectional mapping
        for name, info in self.metadata["tools"].items():
            idx = info["idx"]
            if self.metadata["idx_to_tool"].get(str(idx)) != name:
                issues.append(f"Mapping mismatch for {name}")
        
        return {
            "valid": len(issues) == 0,
            "tool_count": self.count(),
            "index_size": self.index.ntotal if self.index else 0,
            "issues": issues
        }


# Singleton instance
_faiss_index_instance = None

def get_faiss_index() -> FaissToolIndex:
    """Get singleton FAISS index instance."""
    global _faiss_index_instance
    if _faiss_index_instance is None:
        _faiss_index_instance = FaissToolIndex()
    return _faiss_index_instance
