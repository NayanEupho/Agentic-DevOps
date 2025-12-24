import dspy
import os
from .settings import settings
from .llm.ollama_client import get_client # Used for pulling

def _ensure_model(model_name: str):
    """Ensure model exists, pull if not."""
    try:
        from .llm.ollama_client import list_available_models
        models = list_available_models()
        # Simple substring check
        if not any(model_name in m for m in models):
            print(f"📦 Model '{model_name}' not found. Pulling... (This might take a while)")
            get_client().pull(model_name)
    except Exception as e:
        print(f"⚠️ Warning: Could not verify model '{model_name}': {e}")

# Global flag to track if DSPy has been configured
_DSPY_CONFIGURED = False
_LM_CACHE = {}

def init_dspy_lms():
    """
    Initialize DSPy with Smart and Fast variants using Singleton pattern.
    Returns: (fast_lm, smart_lm)
    """
    global _DSPY_CONFIGURED, _LM_CACHE
    
    smart_model = settings.LLM_MODEL
    # Fallback to smart model if prompt/fast model not set (Option B: Silent Genius)
    fast_model = settings.LLM_FAST_MODEL or smart_model
    
    host = settings.LLM_HOST
    fast_host = settings.LLM_FAST_HOST or host
    
    # Only print initialization message if not cached
    if not _LM_CACHE:
        print(f"🧠 Initializing DSPy LMs (Singleton):")
        print(f"   Smart: {smart_model} ({host})")
        print(f"   Fast:  {fast_model} ({fast_host})")
    
    # Helper to get/create LM
    def get_or_create_lm(model, api_base):
        key = (model, api_base)
        if key in _LM_CACHE:
            return _LM_CACHE[key]
        
        try:
            # Using dspy.LM is the modern way
            lm = dspy.LM(f"ollama/{model}", api_base=api_base, api_key="ollama")
            _LM_CACHE[key] = lm
            return lm
        except Exception as e:
            print(f"⚠️ Error initializing LM '{model}': {e}")
            return None

    # 1. Get/Create LMs
    smart_lm = get_or_create_lm(smart_model, host)
    
    if fast_model == smart_model and fast_host == host:
        fast_lm = smart_lm
    else:
        fast_lm = get_or_create_lm(fast_model, fast_host)
        if not fast_lm:
            fast_lm = smart_lm # Fallback
        
    # Configure global default to Smart (for CoT fallback stability)
    if smart_lm:
        # FIX: Only configure DSPy settings ONCE per process.
        if not _DSPY_CONFIGURED:
            dspy.settings.configure(lm=smart_lm)
            _DSPY_CONFIGURED = True
        
    return fast_lm, smart_lm
