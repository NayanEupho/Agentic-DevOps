import asyncio
import sys
import os

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from devops_agent.agent import process_query_async

async def verify():
    print("Testing Safety Check...")
    
    # "stop container" matches Regex and maps to docker_stop_container
    # docker_stop_container is in DANGEROUS_TOOLS
    
    try:
        result = await process_query_async("stop container 123abc456", log_callback=lambda x,y: print(f"LOG: {x}: {y}"))
    except Exception as e:
        print(f"❌ Execution Error: {e}")
        sys.exit(1)
    
    if "confirmation_request" in result:
        req = result["confirmation_request"]
        print("✅ SUCCESS: Caught Confirmation Request")
        print(f"   Tool: {req['tool']}")
        if "risk" in req:
            print(f"   Risk Level: {req['risk']['risk_level']}")
            print(f"   Reason: {req['risk']['reason']}")
        else:
            print("❌ Risk details missing from payload")
            sys.exit(1)
            
        if req['tool'] == "docker_stop_container":
             print("✅ Correct Tool Identified")
        else:
             print(f"❌ Wrong Tool: {req['tool']}")
             sys.exit(1)
    else:
        print("❌ FAILED: No Confirmation Request raised!")
        # It might have executed? 
        print(f"Output: {result.get('output')}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify())
