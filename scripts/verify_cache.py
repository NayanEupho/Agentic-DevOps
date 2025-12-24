import asyncio
import time
from devops_agent.agent import process_query_async

async def main():
    query = "list docker containers"
    print(f"--- Query: '{query}' ---")
    
    # First call (populate cache)
    print("Executing first call (should be slow)...")
    start = time.time()
    await process_query_async(query)
    end = time.time()
    print(f"First call took {(end-start):.2f}s")
    
    # Second call (should hit cache)
    print("\nExecuting second call (should be cached)...")
    start = time.time()
    result = await process_query_async(query)
    end = time.time()
    latency_ms = (end-start) * 1000
    print(f"Second call took {latency_ms:.2f}ms")
    
    if "cached" in str(result).lower():
        print("SUCCESS: Cache hit detected!")
    else:
        print("FAILURE: No cache hit detected.")

if __name__ == "__main__":
    asyncio.run(main())
