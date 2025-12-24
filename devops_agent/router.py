
import re
import json
import os
import math
from typing import Optional, List, Dict, Any, Tuple
from .llm.ollama_client import get_embeddings
from .data_loader import get_data_file
from functools import lru_cache

# Configure logging
import logging
logger = logging.getLogger(__name__)

class ToolCallRequest:
    """Simple wrapper for a tool call decision."""
    def __init__(self, name: str, arguments: Dict[str, Any], score: float = 1.0, source: str = "unknown"):
        self.name = name
        self.arguments = arguments
        self.score = score
        self.source = source

    def to_dict(self):
        return {"name": self.name, "arguments": self.arguments}

class SemanticIntent:
    def __init__(self, text: str, tool: str, args: Dict[str, Any], embedding: List[float] = None):
        self.text = text
        self.tool = tool
        self.args = args
        self.embedding = embedding

class IntentRouter:
    """
    Layered Router for Lightning Fast Intent Matching.
    
    Order of Operations:
    1. Input Cache (Exact Match) - 0ms
    2. Regex Template Match (Pattern Match) - 1ms
    3. Semantic Similarity (Vector Match) - 50ms
    4. Fallback (None) - Trigger RAG/LLM
    """
    
    def __init__(self, intents_path: str = "devops_agent/data/intents.json", cache_path: str = "devops_agent/data/embeddings_cache.json"):
        self.intents_path = intents_path
        self.cache_path = cache_path
        self._templates = []
        self._semantic_intents = []
        self._input_cache = {} # Simple in-memory LRU-like 
        
        self.load_intents()
        
    def load_intents(self):
        """Load templates and semantic examples from JSON."""
        if not os.path.exists(self.intents_path):
            print(f"⚠️ Intents file not found: {self.intents_path}")
            return
            
        try:
            with open(self.intents_path, "r") as f:
                data = json.load(f)
                
            # Load Manual Templates (these take priority)
            self._templates = data.get("templates", [])
            manual_count = len(self._templates)
            
            # Load Auto-Generated Templates (appended after manual ones)
            try:
                from .tool_indexer import get_auto_templates
                auto_templates = get_auto_templates()
                # Filter out duplicates (if manual template exists for same tool)
                manual_tool_names = {t.get('tool') for t in self._templates}
                for at in auto_templates:
                    if at.get('tool') not in manual_tool_names:
                        self._templates.append(at)
            except Exception as e:
                logger.debug(f"Could not load auto-templates: {e}")
            
            # Pre-compile all regex patterns
            for t in self._templates:
                try:
                    t['compiled_pattern'] = re.compile(t['pattern'], re.IGNORECASE)
                except Exception as e:
                    print(f"❌ Invalid regex {t['pattern']}: {e}")
            
            # Load Semantic Intents
            raw_semantic = data.get("semantic", [])
            
            # Load Embedding Cache
            emb_cache = {}
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, "r") as f:
                        emb_cache = json.load(f)
                except Exception:
                    pass
            
            # Initialize Semantic Objects (Computing embeddings if missing)
            dirty = False
            for s in raw_semantic:
                text = s['text']
                embedding = emb_cache.get(text)
                
                if not embedding and text:
                    print(f"🧠 Generating embedding for intent: '{text}'...")
                    embedding = get_embeddings(text)
                    if embedding:
                        emb_cache[text] = embedding
                        dirty = True
                
                if embedding:
                    self._semantic_intents.append(SemanticIntent(
                        text=text,
                        tool=s['tool'],
                        args=s.get('args', {}),
                        embedding=embedding
                    ))
            
            # Save cache if updated
            if dirty:
                try:
                    with open(self.cache_path, "w") as f:
                        json.dump(emb_cache, f)
                    print(f"💾 Saved {len(emb_cache)} embeddings to cache.")
                except Exception:
                    pass
                    
            print(f"✅ Router Loaded: {len(self._templates)} templates, {len(self._semantic_intents)} semantic examples.")
            
        except Exception as e:
            print(f"❌ Failed to load intents: {e}")

    @lru_cache(maxsize=100)
    def route(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """
        Main routing function. 
        Returns List[ToolCall] or None.
        """
        query = query.strip()
        if not query: return None
        
        # 0. High-Performance Smart Match (Zero Latency)
        try:
            from .regex_router import RegexRouter
            smart_match = RegexRouter.route(query)
            if smart_match:
                return smart_match
        except Exception as e:
            logger.debug(f"RegexRouter failed: {e}")

        # 1. Exact Input Cache (Handled by @lru_cache)
        
        # 2. Regex Templates
        for t in self._templates:
            match = t['compiled_pattern'].fullmatch(query) or t['compiled_pattern'].search(query) 
            # search vs fullmatch? Templates usually implied full command structure. 
            # But let's use search to be lenient, or strict? 
            # 'logs for pod' -> fullmatch likely better to avoid accidental triggers inside logic?
            # Actually, User: "please get logs for pod web" -> fullmatch fails.
            # search is better but riskier. Let's use fullmatch for now, or ensure pattern covers ^$.
            # Update: pattern in JSON usually doesn't have ^$, so partial match is possible.
            # Let's try match.
            
            if match:
                # Extract args
                tool_name = t['tool']
                raw_args = t['args']
                
                # Interpolate args
                final_args = {}
                try:
                    # Named groups
                    groups = match.groupdict()
                    for k, v in raw_args.items():
                        if isinstance(v, str) and "{" in v:
                            # Simple replacement format "{pod}"
                            # We can use format_map but need to be careful
                            final_args[k] = v.format(**groups)
                        else:
                            final_args[k] = v
                    
                    print(f"⚡ [Router] Regex Match: '{t['name']}' -> {tool_name}")
                    return [{"name": tool_name, "arguments": final_args}]
                except Exception as e:
                    print(f"⚠️ Template interpolation failed: {e}")
        
        # 3. Semantic Similarity
        # Only if no regex match
        if self._semantic_intents:
            query_emb = get_embeddings(query)
            if query_emb:
                best_score = -1.0
                best_intent = None
                
                for intent in self._semantic_intents:
                    score = self._cosine_similarity(query_emb, intent.embedding)
                    if score > best_score:
                        best_score = score
                        best_intent = intent
                
                # Threshold (0.85 is a safe bet for "Almost Identical intent")
                if best_score > 0.82:
                    print(f"⚡ [Router] Semantic Match ({best_score:.2f}): '{best_intent.text}' -> {best_intent.tool}")
                    return [{"name": best_intent.tool, "arguments": best_intent.args}]
        
        # 4. Fallback
        return None

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not v1 or not v2: return 0.0
        
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        
        if norm_a == 0 or norm_b == 0: return 0.0
        
        return dot_product / (norm_a * norm_b)

# Global Router Instance
router = None

def get_router():
    global router
    if not router:
        router = IntentRouter()
    return router
