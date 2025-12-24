
import dspy
from devops_agent.agent_module import DevOpsAgent
from devops_agent.dspy_client import init_dspy_lms
import json
import os

# 1. COMPREHENSIVE CURRICULUM
# This list explicitly targets every tool in our MCP to ensure the optimizer learns them all.
SCENARIOS = [
    # --- BASE DISCOVERY ---
    "List all pods in the remote cluster",
    # "Show me all nodes in the remote cluster",
    # "List all namespaces in the remote cluster",
    # "Show all services in the remote default namespace",
    
    # --- DEEP INSPECTION ---
    # "Describe the pod 'web-backend-1' in remote",
    # "Get details for the 'postgres-db' service in remote",
    "Describe the node 'k8s-worker-1'",
    
    # --- PHASE 1: LOGS & EVENTS (Debugging) ---
    "Get the logs for the 'auth-service' pod",
    # "Show me the last 50 lines of logs for 'payment-processor'",
    # "Why is the 'frontend' pod pending? Check events.",
    # "Show me warning events in the 'kube-system' namespace",
    
    # --- PHASE 2: OBSERVABILITY (Metrics) ---
    "Which node is using the most CPU?",
    # "Show me memory usage for all pods in the 'backend' namespace",
    # "Check if any node is running out of memory (top nodes)",
    # "What is the current CPU usage of the 'redis-cache' pod?",
    
    # --- PHASE 2: INTROSPECTION (Exec) ---
    # "Check the environment variables of the 'api-server' pod",
    # "List the files in /app inside the 'worker' pod",
    "Run 'ps aux' in the 'sidecar' container of pod 'main-app'",
    
    # --- COMPLEX COMBINATIONS (Chain of Thought) ---
    # "Find the pod with high memory usage and get its logs",
    "My web pod is crashing. Check its status, events, and logs to tell me why.",
    # "Check if the database service is reachable and what its endpoints are",
    # "Verify that the 'config-loader' pod has the correct file at /etc/config/settings.json",
    
    # --- AMBIGUITY HANDLING ---
    "List pods"  # Should prefer local or ask, but training it to handle ambiguity is good
    # "Remote list pods" # Explicit intent
]

from devops_agent.tools import get_tools_schema
from devops_agent.k8s_tools import get_k8s_tools_schema
from devops_agent.k8s_tools.remote_k8s_tools import get_remote_k8s_tools_schema

def get_all_tools_schema():
    return get_tools_schema() + get_k8s_tools_schema() + get_remote_k8s_tools_schema()

def generate_golden_examples():
    """
    The 'Teacher' Loop.
    Uses the Strongest Model (Smart LM) to generate 'Gold Standard' traces.
    """
    print("🧠 Initializing Teacher Model...")
    _, teacher_lm = init_dspy_lms() # Ensure we use the smart model
    
    # We use the raw agent (unoptimized) relying on the Teacher's zero-shot intelligence
    agent = DevOpsAgent() 
    all_tools = get_all_tools_schema()
    
    synthetic_data = []
    
    print(f"🚀 Generating {len(SCENARIOS)} synthetic training examples...")
    print("   This may take a few minutes as we run each scenario through the Teacher model...")
    
    for i, question in enumerate(SCENARIOS):
        print(f"   [{i+1}/{len(SCENARIOS)}] Teaching: '{question}'")
        
        # We ask the agent to solve it. 
        # Since we are using the 'Smart' model, it will likely get it right (slowly).
        # We CAPTURE this successful thought process.
        try:
            # Note: In a real script we might inject a 'hint' or 'demos' to ensure correctness
            # For now we trust the Teacher model's zero-shot capability.
            with dspy.context(lm=teacher_lm):
                prediction = agent(query=question, tools_schema=all_tools, history=[])
            
            # Create a DSPy Example object
            example = dspy.Example(
                query=question,
                tool_calls=prediction.tool_calls,
                rationale=prediction.reasoning # The "Thought" process
            ).with_inputs("query")
            
            synthetic_data.append(example)
            
        except Exception as e:
            print(f"XP Failed to generate trace for '{question}': {e}")

    # Save to disk
    output_path = "devops_agent/data/synthetic_examples.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Serialize (DSPy examples are pickle-able, but JSON is readable)
    # We save a simplified JSON for inspection/loading
    data_json = [
        {
            "query": ex.query, 
            "rationale": ex.rationale, 
            "tool_calls": ex.tool_calls
        } 
        for ex in synthetic_data
    ]
    
    with open(output_path, "w") as f:
        json.dump(data_json, f, indent=2)
        
    print(f"✅ Saved {len(synthetic_data)} synthetic examples to {output_path}")
    print("   -> Next Step: Run 'optimize.py' to compile the agent using this data.")

if __name__ == "__main__":
    generate_golden_examples()
