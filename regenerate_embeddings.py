
import sys
import os
import time

# Add project root to path
sys.path.append(os.getcwd())

print("⏳ Initializing embedding regeneration...")

try:
    # 1. Regenerate Intent Embeddings (L3 Router)
    from devops_agent.router import get_router
    print("🔄 Loading Router (Intent Embeddings)...")
    router = get_router()
    # Access private attribute to ensure load
    count = len(router._semantic_intents)
    print(f"✅ Router Loaded: {count} semantic intents indexed.")
    
    # 2. Regenerate Tool Embeddings (L4 RAG)
    from devops_agent.rag.tool_retriever import get_retriever
    print("🔄 Loading Retriever (Tool Embeddings)...")
    retriever = get_retriever()
    # Force load/index
    retriever.load_index()
    count_tools = len(retriever.tool_embeddings)
    print(f"✅ Retriever Loaded: {count_tools} tools indexed.")
    
    print("\n🎉 SUCCESS: All embeddings regenerated!")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
