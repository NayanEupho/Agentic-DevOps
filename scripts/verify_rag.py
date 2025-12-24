
import asyncio
from devops_agent.rag.tool_retriever import get_retriever

def verify_rag_sync():
    print("🔍 Initializing ToolRetriever for Sync Check...")
    retriever = get_retriever()
    
    # ToolRetriever.__init__ calls _init_index -> _sync_tools_to_faiss
    # which identifies tools in get_tools_schema() + get_k8s_tools_schema() 
    # and adds them to FAISS if missing.
    
    print(f"✅ RAG Index Count: {retriever.faiss_index.count() if retriever.faiss_index else 'JSON Fallback'}")
    
    # Verify specific tools
    if retriever.faiss_index:
        all_tools = [t['name'] for t in retriever.faiss_index.list_all()]
        check_tools = [
            "remote_k8s_promote_resource",
            "remote_k8s_find_resource_namespace",
            "remote_k8s_trace_dependencies",
            "remote_k8s_diff_resources",
            "remote_k8s_analyze_utilization"
        ]
        for tool in check_tools:
            if tool in all_tools:
                print(f"✨ Found '{tool}' in FAISS index!")
            else:
                print(f"❌ '{tool}' NOT FOUND in FAISS index.")
    else:
        check_tools = [
            "remote_k8s_promote_resource",
            "remote_k8s_find_resource_namespace",
            "remote_k8s_trace_dependencies",
            "remote_k8s_diff_resources",
            "remote_k8s_analyze_utilization"
        ]
        for tool in check_tools:
            if tool in retriever.tool_embeddings:
                print(f"✨ Found '{tool}' in JSON embeddings!")
            else:
                print(f"❌ '{tool}' NOT FOUND in JSON embeddings.")

if __name__ == "__main__":
    verify_rag_sync()
