
import time
import asyncio
import statistics
from typing import List, Dict
from devops_agent.agent import process_query_async

# Test cases: Path, Query, Expected Tool
BENCHMARK_SUITE = [
    {"name": "Regex Path", "query": "list pods", "expected": "local_k8s_list_pods"},
    {"name": "Semantic Path", "query": "show me all running containers", "expected": "docker_list_containers"},
    {"name": "RAG Path", "query": "which node is the most busy?", "expected": "remote_k8s_top_nodes"},
    {"name": "Complex Reasoning", "query": "restart the nginx pod and then tell me its status", "expected_count": 2},
]

async def run_benchmark():
    print("🏎️ Starting Baseline Benchmark...")
    results = []
    
    for test in BENCHMARK_SUITE:
        print(f"   Testing: {test['name']} - '{test['query']}'")
        
        start_time = time.perf_counter()
        # Mock session ID for caching consistency
        session_id = "bench_session_1"
        
        # We await the result directly as it's not a generator
        result = await process_query_async(test['query'], session_id=session_id)
        output = result.get("output", "")
        tool_calls = result.get("tool_calls", [])
                
        end_time = time.perf_counter()
        latency = (end_time - start_time) * 1000 # ms
        
        results.append({
            "name": test["name"],
            "latency": latency,
            "success": len(tool_calls) > 0 or "chat" in output.lower()
        })
        print(f"      ✅ Latency: {latency:.2f}ms | Tools identified: {[t['name'] for t in tool_calls]}")

    # Summary
    latencies = [r['latency'] for r in results]
    print("\n📊 Benchmark Results Summary:")
    print(f"   P50 Latency: {statistics.median(latencies):.2f}ms")
    print(f"   Avg Latency: {statistics.mean(latencies):.2f}ms")
    print(f"   Max Latency: {max(latencies):.2f}ms")
    print("-" * 30)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
