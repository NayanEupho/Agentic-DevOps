
from devops_agent.regex_router import RegexRouter

def test_router():
    queries = [
        "list containers",
        "docker ps",
        "docker stop my-container",
        "docker logs web-app",
        "docker inspect database",
        "list pods",
        "list remote pods in kube-system",
        "stop all containers",
        "promote deployment web-app from local to remote",
        "describe all the pods that are paused in my remote k8s",
        "find namespace for auth-db",
        "trace pod web-app in prod",
        "compare deployment nginx",
        "analyze utilization in namespace monitoring"
    ]
    
    print("--- [RegexRouter] Local Match Test ---")
    for q in queries:
        match = RegexRouter.route(q)
        if match:
            print(f"✅ Query: '{q}'")
            print(f"   Tool: {match[0]['name']}")
            print(f"   Args: {match[0]['arguments']}")
        else:
            print(f"❌ Query: '{q}' (No Match)")
        print("-" * 30)

if __name__ == "__main__":
    test_router()
