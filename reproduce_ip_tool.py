
import sys
import os
sys.path.append(os.getcwd())

from devops_agent.k8s_tools.remote_k8s_extended_tools import RemoteK8sGetResourcesIPsTool
from devops_agent.settings import settings

# Mock settings just in case (though it uses k8s_config which loads from settings)
# Ensure k8s_config is configured
from devops_agent.k8s_tools.k8s_config import k8s_config

print(f"Configuring for {settings.REMOTE_K8S_API_URL}")
k8s_config.configure_remote(
    api_url=settings.REMOTE_K8S_API_URL,
    token="mock_token", # We need a real token if we want to talk to real K8s, but wait...
    # The user's env has the real token in token.txt.
    # I should load it.
    verify_ssl=False
)

def load_token():
    try:
        with open(settings.REMOTE_K8S_TOKEN_PATH, "r") as f:
            return f.read().strip()
    except:
        return ""

k8s_config.configure_remote(
    api_url=settings.REMOTE_K8S_API_URL,
    token=load_token(),
    verify_ssl=settings.REMOTE_K8S_VERIFY_SSL
)

tool = RemoteK8sGetResourcesIPsTool()

print("--- Test 1: Node 'kc-m1' ---")
try:
    result = tool.run(resource_type="node", names=["kc-m1"])
    print(result)
except Exception as e:
    print(f"Error: {e}")

print("\n--- Test 2: Node 'kc-m1' (String input) ---")
try:
    result = tool.run(resource_type="node", names="kc-m1")
    print(result)
except Exception as e:
    print(f"Error: {e}")

