import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("Step 1: Import safety")
try:
    import devops_agent.safety as safety
    print(f"Safety items: {dir(safety)}")
except ImportError as e:
     print(f"Safety failed: {e}")

print("Step 2: Import agent")
try:
    import devops_agent.agent as agent
    print("Agent imported")
except ImportError as e:
    print(f"Agent failed: {e}")
    import traceback
    traceback.print_exc()

print("Step 3: Import CLI Helper")
try:
    import devops_agent.cli_helper as cli_helper
    print("CLI Helper imported")
except Exception as e:
    print(f"CLI Helper failed: {e}")
    import traceback
    traceback.print_exc()
