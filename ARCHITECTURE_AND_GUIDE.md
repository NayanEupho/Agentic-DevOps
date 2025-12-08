graph TD
    User[User Input] -->|1. Natural Language| CLI[CLI (Typer)]
    CLI -->|2. Pass Query| Agent[Agent Orchestrator]
    Agent -->|3. Get Tool Decision| LLM[Ollama (phi3:mini)]
    LLM -->|4. Return Tool Name & Args| Agent
    Agent -->|5. Check Tool Prefix| Router[Routing Logic]
    Router -->|docker_| ClientDocker[Docker Client]
    Router -->|k8s_| ClientLocal[Local K8s Client]
    Router -->|remote_k8s_| ClientRemote[Remote K8s Client]
    ClientDocker -->|JSON-RPC Port 8080| ServerDocker[Docker MCP Server]
    ClientLocal -->|JSON-RPC Port 8081| ServerLocal[Local K8s MCP Server]
    ClientRemote -->|JSON-RPC Port 8082| ServerRemote[Remote K8s MCP Server]
    ServerDocker -->|Docker SDK| DockerEngine[Docker Engine]
    ServerLocal -->|kubectl| LocalCluster[Local K8s Cluster]
    ServerRemote -->|kubectl| RemoteCluster[Remote K8s Cluster]
    DockerEngine -->|Result| ServerDocker
    ServerDocker -->|Result| Agent
    Agent -->|6. Format & Display| User
```

---

## 4. The Lifecycle of a Command

Let's trace exactly what happens when you run a command.

### Scenario: "List my local pods"

#### Step 1: Initialization (`start-all`)
Before you run a query, you execute `agentic-docker start-all`.
- **Triggers:** `cli.py` spawns 3 separate subprocesses.
- **Process 1:** Starts `server.py` on `localhost:8080` (Docker).
- **Process 2:** Starts `k8s_server.py` on `localhost:8081` (Local K8s).
- **Process 3:** Starts `remote_k8s_server.py` on `localhost:8082` (Remote K8s).
- **Status:** All servers are now listening for JSON-RPC connections.

#### Step 2: User Input
You type:
```bash
agentic-docker run "Show me the pods in the default namespace"
```

#### Step 3: CLI Processing
- **Trigger:** `cli.py` receives the command via the `run` function.
- **Action:** The CLI calls `process_query()` with the user's query.
- **Output:** The query is passed to the Agent for processing.

#### Step 4: Agent Processing
- **Trigger:** `agent.py` receives the query.
- **Action 1:** The Agent calls `get_tool_calls()` to ask the LLM which tool to use.
- **Action 2:** The LLM analyzes the query and returns: `{"name": "k8s_list_pods", "arguments": {"namespace": "default"}}`.
- **Action 3:** The Agent checks if the tool is dangerous using `confirm_action_auto()`. For listing pods, it's safe, so no confirmation is needed.
- **Action 4:** The Agent calls `call_k8s_tool()` with the tool name and arguments.

#### Step 5: MCP Client Communication
- **Trigger:** `mcp/client.py` receives the request to call `k8s_list_pods`.
- **Action:** The client sends a JSON-RPC 2.0 request to `http://127.0.0.1:8081` (Local K8s MCP Server).
- **Request Body:**
```json
{
  "jsonrpc": "2.0",
  "method": "k8s_list_pods",
  "params": {
    "namespace": "default"
  },
  "id": 1
}
```

#### Step 6: MCP Server Execution
- **Trigger:** `mcp/k8s_server.py` receives the JSON-RPC request.
- **Action 1:** The server's dispatcher looks up the `k8s_list_pods` method.
- **Action 2:** It finds the `K8sListPodsTool` instance and calls its `run()` method.
- **Action 3:** The tool uses the Kubernetes Python client to execute `kubectl get pods -n default`.
- **Action 4:** The tool formats the result into a structured dictionary.

#### Step 7: Result Formatting
- **Trigger:** The tool execution completes successfully.
- **Action:** The tool returns:
```json
{
  "success": true,
  "pods": [
    {"name": "nginx-7cdbd8cdc9-g7brt", "phase": "Running", "ready": "1/1", "pod_ip": "10.1.0.4"},
    {"name": "redis-master-5ff498c5c6-7qj4b", "phase": "Running", "ready": "1/1", "pod_ip": "10.1.0.5"}
  ],
  "count": 2,
  "namespace": "default"
}
```
- **Action:** The server wraps this in a JSON-RPC response and sends it back to the client.

#### Step 8: Agent Result Processing
- **Trigger:** The Agent receives the JSON-RPC response.
- **Action:** The `format_tool_result()` function formats the result into a human-readable string:
```
✅ Success! Found 2 pod(s) in namespace 'default':

🟢 nginx-7cdbd8cdc9-g7brt (10.1.0.4) - Running [Ready: 1/1]
🟢 redis-master-5ff498c5c6-7qj4b (10.1.0.5) - Running [Ready: 1/1]
```

#### Step 9: User Output
- **Trigger:** The CLI receives the formatted result.
- **Action:** The CLI prints the result to the terminal.
- **Output:** You see the list of pods in the default namespace.

---

## 5. Component Deep Dive

### 5.1 The CLI (`cli.py`)
The CLI is the user-facing interface. It uses the **Typer** library to create a professional command-line interface.

**Key Functions:**
- `run_command()`: The main entry point for user queries.
- `start_server()`: Starts an individual MCP server.
- `list_tools()`: Lists all available tools for debugging.

**Example Usage:**
```bash
# Run a command
agentic-docker run "Start nginx on port 8080"

# Start the Docker server
agentic-docker server

# List available tools
agentic-docker list-tools
```

### 5.2 The Agent (`agent.py`)
The Agent is the central orchestrator. It coordinates communication between the CLI, LLM, and MCP servers.

**Key Functions:**
- `process_query()`: The main workflow function that processes a user query.
- `get_tool_calls()`: Calls the LLM to determine which tool to use.
- `format_tool_result()`: Formats the tool execution result for display.

**Workflow:**
1. **Tool Selection:** Ask the LLM which tool to use based on the query.
2. **Safety Check:** Apply safety rules and ask for user confirmation if needed.
3. **Execution:** Call the appropriate MCP server to execute the tool.
4. **Formatting:** Format the result in a human-readable way.

### 5.3 LLM Client (`llm/ollama_client.py`)
The LLM client handles communication with the local Ollama model.

**Key Functions:**
- `get_tool_calls()`: Sends a prompt to the LLM asking it to choose a tool.
- `ensure_model_exists()`: Checks if the required model is available and downloads it if not.
- `test_llm_connection()`: Verifies that Ollama is accessible.

**Prompt Structure:**
The LLM receives a structured prompt that includes:
- A list of all available tools in JSON Schema format.
- The user's natural language query.
- Instructions on how to respond (JSON format).

**Example Prompt:**
```
You are a Docker assistant. The user wants to perform one or more Docker/Kubernetes operations.
Your job is to choose the most appropriate tool(s) from the available tools below.

Available tools (in JSON Schema format):
[
  {
    "name": "docker_list_containers",
    "description": "List running or all Docker containers",
    "parameters": {
      "type": "object",
      "properties": {
        "all": {
          "type": "boolean",
          "description": "If true, list all containers (including stopped ones)"
        }
      },
      "required": []
    }
  }
]

User request: "List all containers"
```

**LLM Response:**
```json
[
  {
    "name": "docker_list_containers",
    "arguments": {
      "all": true
    }
  }
]
```

### 5.4 MCP Client (`mcp/client.py`)
The MCP client sends JSON-RPC 2.0 requests to the MCP servers.

**Key Functions:**
- `call_tool()`: Calls a Docker tool via the Docker MCP server.
- `call_k8s_tool()`: Calls a Kubernetes tool via the Local K8s MCP server.
- `call_remote_k8s_tool()`: Calls a Remote Kubernetes tool via the Remote K8s MCP server.
- `test_connection()`: Tests if a server is accessible.

**JSON-RPC Request Format:**
```json
{
  "jsonrpc": "2.0",
  "method": "docker_list_containers",
  "params": {
    "all": true
  },
  "id": 1
}
```

**JSON-RPC Response Format:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "containers": [
      {
        "id": "abc123",
        "name": "nginx",
        "image": "nginx:latest",
        "status": "running"
      }
    ],
    "count": 1
  },
  "id": 1
}
```

### 5.5 MCP Servers
The project uses three separate MCP servers, each running on a different port:

#### Docker MCP Server (`mcp/server.py`)
- **Port:** 8080
- **Purpose:** Exposes Docker tools as JSON-RPC methods.
- **Tools:** `docker_list_containers`, `docker_run_container`, `docker_stop_container`

#### Local Kubernetes MCP Server (`mcp/k8s_server.py`)
- **Port:** 8081
- **Purpose:** Exposes Local Kubernetes tools as JSON-RPC methods.
- **Tools:** `k8s_list_pods`, `k8s_list_nodes`

#### Remote Kubernetes MCP Server (`mcp/remote_k8s_server.py`)
- **Port:** 8082
- **Purpose:** Exposes Remote Kubernetes tools as JSON-RPC methods.
- **Tools:** `remote_k8s_list_pods`, `remote_k8s_list_nodes`, `remote_k8s_list_namespaces`, `remote_k8s_find_pod_namespace`

**Server Architecture:**
Each server follows the same pattern:
1. **Import Tools:** Import the relevant tool classes.
2. **Create Handlers:** Use `create_tool_handler()` to wrap each tool.
3. **Register Methods:** Add each handler to the JSON-RPC dispatcher.
4. **Start Server:** Run the Werkzeug WSGI server.

**Example Server Code:**
```python
from jsonrpc import JSONRPCResponseManager, dispatcher
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from ..k8s_tools import ALL_K8S_TOOLS

# Register all tools
for tool in ALL_K8S_TOOLS:
    handler = create_tool_handler(tool.name)
    dispatcher.add_method(handler, tool.name)

# Start server
run_simple('127.0.0.1', 8081, application)
```

### 5.6 Tools (`tools/` and `k8s_tools/`)
Tools are the actual implementations of Docker and Kubernetes operations. They follow a consistent interface defined by the `Tool` base class.

#### Tool Interface
```python
class Tool:
    name = "tool_name"
    description = "Human-readable description"
    
    def get_parameters_schema(self) -> dict:
        """Return JSON Schema for tool parameters"""
        pass
    
    def run(self, **kwargs) -> dict:
        """Execute the tool and return a structured result"""
        pass
```

#### Example: Docker List Containers Tool
```python
class DockerListContainersTool(Tool):
    name = "docker_list_containers"
    description = "List running or all Docker containers"

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": "If true, list all containers (including stopped ones)"
                }
            },
            "required": []
        }

    def run(self, **kwargs) -> dict:
        try:
            client = docker.from_env()
            all_containers = kwargs.get('all', False)
            containers = client.containers.list(all=all_containers)
            
            formatted_containers = []
            for container in containers:
                formatted_containers.append({
                    "id": container.short_id,
                    "name": container.name,
                    "image": container.image.tags[0] if container.image.tags else "unknown",
                    "status": container.status
                })
            
            return {
                "success": True,
                "containers": formatted_containers,
                "count": len(formatted_containers)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
```

### 5.7 Safety Layer (`safety.py`)
The safety layer prevents accidental destructive operations by requiring user confirmation.

**Key Functions:**
- `confirm_action()`: Prompts the user for confirmation before executing dangerous operations.
- `confirm_action_auto()`: Automatically selects the appropriate confirmation method.

**Dangerous Tools:**
- `docker_stop_container`: Stops running containers.
- `docker_run_container`: Creates new containers (uses resources).

**Confirmation Flow:**
1. **Check:** Is the tool in the dangerous list?
2. **Prompt:** If yes, show a confirmation prompt with details.
3. **Wait:** Wait for user input (yes/no).
4. **Proceed/Cancel:** Execute or cancel based on user response.

**Example Prompt:**
```
⚠️  POTENTIALLY DANGEROUS ACTION DETECTED
   Tool: docker_stop_container
   Arguments: {'container_id': 'abc123'}

   ⚠️  This will STOP container 'abc123' and any processes inside it.
   ⚠️  Data in non-persistent volumes may be lost.

   🤔 Do you want to proceed with this action?
   Type 'yes' to confirm or 'no' to cancel: 
```

---

## 6. Multi-Server Architecture Benefits

The Multi-MCP architecture provides several key benefits:

### 6.1 Isolation
- **Separate Processes:** Each server runs in its own process, preventing one server's issues from affecting others.
- **Resource Management:** Each server can be monitored and managed independently.

### 6.2 Scalability
- **Independent Scaling:** You can run servers on different machines if needed.
- **Load Distribution:** Different domains (Docker, K8s) don't compete for the same server resources.

### 6.3 Maintainability
- **Clear Boundaries:** Each server has a specific responsibility, making code easier to understand and maintain.
- **Independent Development:** Teams can work on different servers without conflicts.

### 6.4 Reliability
- **Fault Tolerance:** If one server crashes, the others continue to work.
- **Graceful Degradation:** The system can still function with some servers down.

---

## 7. Command Chaining

The system supports **command chaining**, allowing multiple operations in a single query. This is achieved by having the LLM return a list of tool calls instead of a single call.

### Example: "Start nginx and list pods"
**User Query:** "Start nginx and list pods"

**LLM Response:**
```json
[
  {
    "name": "docker_run_container",
    "arguments": {
      "image": "nginx"
    }
  },
  {
    "name": "k8s_list_pods",
    "arguments": {
      "namespace": "default"
    }
  }
]
```

**Execution Flow:**
1. The Agent receives the list of tool calls.
2. For each tool call:
   - Apply safety checks.
   - Execute the tool via the appropriate MCP server.
   - Format the result.
3. Combine all results into a single response.

**Result:**
```
✅ Success! Container nginx started successfully.

🟢 nginx-abc123 (10.1.0.4) - Running [Ready: 1/1]
🟢 redis-master-xyz789 (10.1.0.5) - Running [Ready: 1/1]
```

---

## 8. Error Handling

The system includes comprehensive error handling at multiple levels:

### 8.1 LLM Errors
- **Connection Issues:** If Ollama is not running, the system provides a clear error message.
- **Model Issues:** If the model is not available, the system attempts to download it.
- **Parsing Errors:** If the LLM returns invalid JSON, the system handles it gracefully.

### 8.2 MCP Server Errors
- **Connection Issues:** If a server is not running, the system provides a helpful error message.
- **Timeout Errors:** If a server takes too long to respond, the system times out gracefully.
- **Tool Errors:** If a tool execution fails, the error is captured and returned to the user.

### 8.3 Tool Execution Errors
- **Validation Errors:** If tool arguments are invalid, Pydantic validation catches them.
- **Runtime Errors:** If a tool fails during execution, the error is captured and returned.
- **Permission Errors:** If Docker/Kubernetes permissions are insufficient, the error is clearly reported.

---

## 9. Configuration and Customization

The system can be configured through environment variables and configuration files.

### 9.1 Environment Variables
- `AGENTIC_DOCKER_HOST`: Host for MCP servers (default: 127.0.0.1)
- `AGENTIC_DOCKER_PORT`: Port for Docker MCP server (default: 8080)
- `AGENTIC_K8S_PORT`: Port for Local K8s MCP server (default: 8081)
- `AGENTIC_REMOTE_K8S_PORT`: Port for Remote K8s MCP server (default: 8082)
- `AGENTIC_LLM_MODEL`: LLM model to use (default: phi3:mini)
- `AGENTIC_SAFETY_CONFIRM`: Enable/disable safety confirmation (default: true)

### 9.2 Adding New Tools
To add a new tool:

1. **Create the Tool Class:**
```python
class DockerLogsTool(Tool):
    name = "docker_get_logs"
    description = "Get logs from a running container"
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "ID or name of the container"
                }
            },
            "required": ["container_id"]
        }
    
    def run(self, **kwargs) -> dict:
        # Implementation
        pass
```

2. **Register the Tool:**
```python
# In tools/__init__.py
from .docker_logs import DockerLogsTool

ALL_TOOLS: List[Tool] = [
    DockerListContainersTool(),
    DockerRunContainerTool(),
    DockerStopContainerTool(),
    DockerLogsTool(),  # Add the new tool
]
```

3. **Restart the Server:** The new tool will be automatically registered with the MCP server.

---

## 10. Testing

The project includes a comprehensive test suite to ensure reliability.

### 10.1 Unit Tests
- **Tool Tests:** Test individual tool functionality.
- **LLM Tests:** Test LLM integration and tool selection.
- **Safety Tests:** Test safety confirmation logic.

### 10.2 Integration Tests
- **End-to-End Tests:** Test complete workflows from query to result.
- **Multi-Server Tests:** Test the interaction between different servers.
- **Error Handling Tests:** Test error scenarios and recovery.

### 10.3 Performance Tests
- **Tool Execution Time:** Measure how long tools take to execute.
- **LLM Response Time:** Measure LLM response times.
- **MCP Server Latency:** Measure server response times.

---

## 11. Future Enhancements

The project is designed to be extensible. Here are some potential future enhancements:

### 11.1 Additional Tool Categories
- **Image Management:** Pull, push, build, tag images.
- **Network Management:** Create, inspect, remove networks.
- **Volume Management:** Create, inspect, remove volumes.
- **Compose Support:** Manage Docker Compose applications.

### 11.2 Advanced LLM Features
- **Context Awareness:** Remember previous interactions for better responses.
- **Multi-Modal Input:** Support for images and other input types.
- **Custom Prompts:** Allow users to customize LLM prompts.

### 11.3 Enhanced Safety
- **Risk Assessment:** Automatically assess the risk level of operations.
- **Approval Workflows:** Require multiple approvals for high-risk operations.
- **Audit Logging:** Log all operations for compliance and debugging.

### 11.4 Performance Improvements
- **Caching:** Cache frequently used tool results.
- **Parallel Execution:** Execute independent tools in parallel.
- **Resource Monitoring:** Monitor system resources and adjust behavior accordingly.

---

## 12. Conclusion

The Agentic Docker project demonstrates a sophisticated approach to AI-powered DevOps tooling. By combining local LLMs, the Model Context Protocol, and a multi-server architecture, it provides a powerful and flexible platform for managing Docker and Kubernetes clusters using natural language.

The architecture is designed to be:
- **Reliable:** Through comprehensive error handling and testing.
- **Extensible:** Through a modular tool system and clear interfaces.
- **Safe:** Through safety checks and confirmation prompts.
- **Scalable:** Through a multi-server architecture that can grow with needs.

Whether you're a developer looking to simplify your workflow or an organization looking to build AI-powered DevOps tools, the Agentic Docker project provides a solid foundation for building intelligent, user-friendly systems.