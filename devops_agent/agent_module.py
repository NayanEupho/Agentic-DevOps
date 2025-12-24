import dspy
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# =============================================
# Pydantic Models for Validation
# =============================================

class ToolCall(BaseModel):
    # ...
    name: str = Field(description="The EXACT name of the tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")

class InsightAgent(dspy.Module):
    """
    Opinionated Analyst Agent.
    Transforms raw tool results into expert insights.
    """
    def __init__(self):
        super().__init__()
        self.prog = dspy.Predict(InsightSignature)
    
    def forward(self, query: str, results_str: str) -> dspy.Prediction:
        return self.prog(user_query=query, tool_results=results_str)

# =============================================
# DSPy Signature
# =============================================

# =============================================
# DSPy Signatures
# =============================================

class FastDevOpsSignature(dspy.Signature):
    """
    You are a high-performance JSON API.
    Input: user_query, history_context, available_tools
    Output: JSON List of tool calls.

    Constraints:
    1. OUTPUT ONLY JSON. No thinking, no reasoning, no markdown, no specific comments.
    2. Format: [{"name": "tool_name", "arguments": {"arg": "val"}}]
    3. Do NOT use "tool_name" or "input" as keys. Use "name" and "arguments".
    """
    history_context: str = dspy.InputField(desc="JSON list of previous messages")
    available_tools: str = dspy.InputField(desc="JSON schema of tools")
    user_query: str = dspy.InputField(desc="User command")
    
    tool_calls: str = dspy.OutputField(desc="JSON list")

class DevOpsAgentSignature(dspy.Signature):
    """
    You are an intelligent DevOps Assistant.
    Your goal is to map the user's natural language query to tool calls.
    
    Instructions:
    1. ANALYZE the 'history_context' and 'user_query'.
    2. THINK step-by-step about which tool(s) match the user's intent.
    3. CHECK 'available_tools' to ensure the tool exists and arguments are correct.
    4. IF the user asks for multiple things (e.g. "list pods and nodes"), RETURN MULTIPLE TOOL CALLS in the list.
    5. IF the user is just saying "hi", generic chat, or asking a question that doesn't need a tool, USE the 'chat' tool.
    6. OUTPUT the "tool_calls" as a JSON list.

    RICH CONTEXT:
    - If `System Context` is provided in the query, use it to resolve names (e.g. "restart web" -> "restart web-container-123").

    OUTPUT FORMAT:
    - Reasoning: [Your thought process]
    - tool_calls: [{"name": "tool_1", "arguments": {...}}, {"name": "tool_2", "arguments": {...}}]
    """
    
    history_context: str = dspy.InputField(desc="Previous conversation history")
    available_tools: str = dspy.InputField(desc="JSON schema of available tools")
    user_query: str = dspy.InputField(desc="The user's natural language command")
    
    tool_calls: str = dspy.OutputField(desc="JSON list of tool calls. Example: [{\"name\": \"k8s_list_pods\", \"arguments\": {}}]")

class InsightSignature(dspy.Signature):
    """
    You are an expert Kubernetes and DevOps Analyst.
    Your goal is to provide a concise, high-intelligence opinion based on tool results.
    
    Instructions:
    1. ANALYZE the raw 'tool_results' in context of the 'user_query'.
    2. Provide a 2-3 sentence 'expert_opinion' that answers the user's specific question (e.g. comparing environments, identifying risks).
    3. Be DIRECT and TECHNICAL. Don't use fluff.
    """
    user_query: str = dspy.InputField(desc="The user's original question")
    tool_results: str = dspy.InputField(desc="The data fetched by the tools")
    
    expert_opinion: str = dspy.OutputField(desc="A 2-3 sentence insightful summary")

# =============================================
# DevOpsAgent Module with Retry
# =============================================

class FastDevOpsAgent(dspy.Module):
    """Zero-shot agent for high speed."""
    def __init__(self, lm=None):
        super().__init__()
        self.prog = dspy.Predict(FastDevOpsSignature)

        self.lm = lm
    
    def forward(self, query: str, tools_schema: List[Dict], history: List[Dict], log_callback=None) -> dspy.Prediction:
        history_str = json.dumps(history, indent=2) if history else "[]"
        tools_str = json.dumps(tools_schema, indent=2)
        
        # Use specific LM if provided
        if self.lm:
            with dspy.context(lm=self.lm):
                return self.prog(
                    history_context=history_str,
                    available_tools=tools_str,
                    user_query=query
                )
        else:
             return self.prog(
                history_context=history_str,
                available_tools=tools_str,
                user_query=query
            )

class DevOpsAgent(dspy.Module):
    """
    Hybrid Agent:
    1. Tries Fast Zero-Shot approach first (Latency optimized).
    2. Falls back to CoT (Reasoning) if Fast fails validation (Reliability optimized).
    """
    def __init__(self, max_retries: int = 2, fast_lm=None, smart_lm=None, load_compiled: bool = True):
        super().__init__()
        self.fast_agent = FastDevOpsAgent(lm=fast_lm)
        self.smart_prog = dspy.ChainOfThought(DevOpsAgentSignature)
        self.smart_lm = smart_lm
        self.max_retries = max_retries
        
        if load_compiled:
             self._try_load_compiled()

    def _try_load_compiled(self):
        import os
        path = "devops_agent/compiled_agent.json"
        # Use absolute path relative to this file for safety
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_dir, "compiled_agent.json")
        
        if os.path.exists(path):
            print(f"⚡ [Optimizer] Loading compiled agent from {path}...")
            try:
                self.load(path)
                print("✅ [Optimizer] Compiled agent loaded successfully!")
            except Exception as e:
                print(f"⚠️ [Optimizer] Failed to load compiled agent: {e}")
        else:
             # This is expected during first run or if optimization hasn't run
             pass
    
    def forward(self, query: str, tools_schema: List[Dict], history: List[Dict], log_callback=None) -> dspy.Prediction:
        history_str = json.dumps(history, indent=2) if history else "[]"
        tools_str = json.dumps(tools_schema, indent=2)
        
        # --- ATTEMPT 1: FAST MODE (Zero-Shot) ---
        msg = "⚡ [FastAgent] Attempting zero-shot execution..."
        print(msg)
        if log_callback: log_callback("thought", msg)

        try:
            # fast_agent already handles context switch
            prediction = self.fast_agent(query=query, tools_schema=tools_schema, history=history)
            raw_output = prediction.tool_calls
            validated = _validate_and_parse(raw_output)
            
            if validated:
                is_valid_sem, sem_error = _validate_semantics(validated, tools_schema)
                if is_valid_sem:
                    prediction._validated_calls = validated
                    if log_callback: log_callback("thought", "✅ FastAgent validation passed.")
                    return prediction
                else:
                    msg = f"⚠️ [FastAgent] Semantic Error: {sem_error}. Switching to CoT."
                    print(msg)
                    if log_callback: log_callback("thought", msg)
            else:
                msg = "⚠️ [FastAgent] Invalid JSON. Switching to CoT."
                print(msg)
                if log_callback: log_callback("thought", msg)
                
        except Exception as e:
            msg = f"⚠️ [FastAgent] Error: {e}. Switching to CoT."
            print(msg)
            if log_callback: log_callback("thought", msg)

        # --- ATTEMPT 2: SMART MODE (Chain-of-Thought with Retries) ---
        msg = "🧠 [SmartAgent] Switching to Chain-of-Thought reasoning..."
        print(msg)
        if log_callback: log_callback("thought", msg)
        
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # Add error feedback to query if retrying
                modified_query = query
                if last_error and attempt > 0:
                    modified_query = f"{query}\n\n[SYSTEM: Your previous response was invalid. Error: {last_error}. Please output ONLY a valid JSON list.]"
                
                # Use Smart LM Context
                if self.smart_lm:
                    with dspy.context(lm=self.smart_lm):
                         prediction = self.smart_prog(
                            history_context=history_str,
                            available_tools=tools_str,
                            user_query=modified_query
                        )
                else:
                     prediction = self.smart_prog(
                        history_context=history_str,
                        available_tools=tools_str,
                        user_query=modified_query
                    )
                
                # Validate the output
                raw_output = prediction.tool_calls
                validated = _validate_and_parse(raw_output)
                
                if validated:
                    # --- SEMANTIC VERIFICATION ---
                    is_valid_sem, sem_error = _validate_semantics(validated, tools_schema)
                    if is_valid_sem:
                        # Return successful prediction
                        prediction._validated_calls = validated
                        return prediction
                    else:
                        last_error = f"Semantic Error: {sem_error}"
                        # print(f"⚠️  Agent Self-Correction Triggered: {last_error}")
                else:
                    last_error = "Output was not a valid JSON list of tool calls"
                    
            except Exception as e:
                last_error = str(e)
        
        # Return last prediction even if invalid (let caller handle)
        return prediction

def _validate_and_parse(output: str) -> Optional[List[Dict]]:
    """Validate and parse the output. Returns None if invalid."""
    import json_repair
    import re
    
    if not output or not isinstance(output, str):
        return None
    
    cleaned = output.strip()
    
    # Remove markdown code blocks
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1])
    
    # Try to extract JSON from prose if needed
    if not cleaned.startswith("[") and not cleaned.startswith("{"):
        # Look for embedded JSON - use greedy match and rely on json_repair
        # Find the start of a JSON array or object
        array_start = cleaned.find('[')
        obj_start = cleaned.find('{')
        
        if array_start != -1:
            # Find matching closing bracket using bracket counting
            bracket_count = 0
            for i, c in enumerate(cleaned[array_start:], start=array_start):
                if c == '[': bracket_count += 1
                elif c == ']': bracket_count -= 1
                if bracket_count == 0:
                    cleaned = cleaned[array_start:i+1]
                    break
        elif obj_start != -1:
            # Find matching closing brace
            brace_count = 0
            for i, c in enumerate(cleaned[obj_start:], start=obj_start):
                if c == '{': brace_count += 1
                elif c == '}': brace_count -= 1
                if brace_count == 0:
                    cleaned = f"[{cleaned[obj_start:i+1]}]"
                    break
        else:
            return None
    
    try:
        data = json_repair.loads(cleaned)
        # print(f"[DEBUG] agent.py: Parsed tool_calls: {tool_calls}")
        
        if isinstance(data, list) and len(data) > 0:
            # Validate structure
            normalized_list = []
            for item in data:
                if isinstance(item, dict):
                    # Check for name variants
                    if "name" in item or "tool_name" in item or "tool" in item:
                        normalized_list.append(item)
            
            if normalized_list:
                return _normalize_tool_list(normalized_list)
            else:
                pass
                # print(f"[DEBUG] keys found in items: {[list(i.keys()) for i in data if isinstance(i, dict)]}")

        elif isinstance(data, dict):
             if "name" in data or "tool_name" in data or "tool" in data:
                return [_normalize_single(data)]
    except Exception as e:
        # print(f"[DEBUG] json_repair/validation exception: {e}")
        pass
    
    # print(f"[DEBUG] _validate_and_parse failed to find valid tools in: {cleaned[:100]}")
    return None

def _normalize_single(item: Dict) -> Dict:
    """Normalize a single tool call dict."""
    # Normalize Name
    name = item.get("name") or item.get("tool_name") or item.get("tool")
    
    # Normalize Arguments
    args = item.get("arguments") or item.get("parameters") or item.get("input") or {}
    
    return {"name": name, "arguments": args}

def _normalize_tool_list(data: List) -> List[Dict[str, Any]]:
    """Normalize tool call list to standard format."""
    normalized = []
    
    # Handle [name, args] format
    if len(data) == 2 and isinstance(data[0], str) and isinstance(data[1], dict):
        return [{"name": data[0], "arguments": data[1]}]
    
    # Handle [name] format
    if len(data) == 1 and isinstance(data[0], str):
        return [{"name": data[0], "arguments": {}}]
    
    for item in data:
        if isinstance(item, str):
            normalized.append({"name": item, "arguments": {}})
        elif isinstance(item, dict):
             if "name" in item or "tool_name" in item or "tool" in item:
                normalized.append(_normalize_single(item))
    
    return normalized

def _validate_semantics(tool_calls: List[Dict], tools_schema: List[Dict]) -> tuple[bool, str]:
    """
    Check if tool names exist and required arguments are present.
    Returns (True, "") if valid, or (False, "Error message") if invalid.
    """
    # Create a map for fast lookup
    schema_map = {t['name']: t for t in tools_schema}
    
    for call in tool_calls:
        name = call.get('name')
        args = call.get('arguments', {})
        
        if name not in schema_map:
            # Suggestions?
            # primitive fuzzy match?
            return False, f"Tool '{name}' does not exist. Please check 'available_tools' for the correct name."
        
        schema = schema_map[name]
        params_schema = schema.get('parameters', {})
        required_params = params_schema.get('required', [])
        
        # Check required args
        if required_params:
            for req in required_params:
                if req not in args:
                    return False, f"Tool '{name}' is missing required argument: '{req}'."
                    
    return True, ""

# =============================================
# Public Parser Function
# =============================================

def parse_dspy_tool_calls(output: Any) -> List[Dict[str, Any]]:
    """
    Parse DSPy output into a list of tool call dicts.
    Handles various formats and edge cases.
    """
    import json_repair
    import re
    
    # Check for pre-validated calls (from retry mechanism)
    if hasattr(output, '_validated_calls'):
        return output._validated_calls
    
    # Handle string output
    if isinstance(output, str):
        result = _validate_and_parse(output)
        if result:
            return result
        
        # Last resort: try to find ANY tool name in the output
        # This handles prose responses that mention tool names
        cleaned = output.strip()
        
        # Look for tool names matching pattern 'remote_k8s_*' or similar
        tool_pattern = r'(remote_k8s_\w+|k8s_\w+|docker_\w+)'
        matches = re.findall(tool_pattern, cleaned)
        if matches:
            print(f"⚠️  Extracted tool name from prose: {matches[0]}")
            return [{"name": matches[0], "arguments": {}}]
        
        print(f"❌ Parse Error. Raw: {cleaned[:150]}...")
        return []
    
    print(f"❌ Unexpected output type: {type(output)}")
    return []

# =============================================
# Error Analysis Signature
# =============================================

class ErrorAnalysisSignature(dspy.Signature):
    """
    You are a Kubernetes and DevOps expert. 
    Analyze the 'raw_error' and 'user_query' to explain WHY the operation failed and HOW to fix it.
    
    Instructions:
    1. Identify the core issue (e.g., RBAC denial, resource not found, network timeout).
    2. Explain it simply to a user.
    3. Suggest concrete fixes (e.g., "Run 'kubectl create namespace...'", "Check your kubeconfig").
    
    OUTPUT FORMAT:
    - explanation: A formatted string containing:
        1. **What Happened**: [Brief summary]
        2. **Why**: [Technical Reason]
        3. **Possible Fixes**: [Bulleted list of commands or actions]
    """
    
    user_query: str = dspy.InputField(desc="The command the user tried to run")
    error_summary: str = dspy.InputField(desc="The short error message")
    raw_error: str = dspy.InputField(desc="The raw JSON error payload from the tool")
    
    explanation: str = dspy.OutputField(desc="The natural language explanation")


class ErrorAnalyzer(dspy.Module):
    """Module for explaining technical errors."""
    def __init__(self):
        super().__init__()
        self.prog = dspy.ChainOfThought(ErrorAnalysisSignature)
    
    def forward(self, user_query: str, error_summary: str, raw_error: Dict) -> dspy.Prediction:
        import json
        raw_str = json.dumps(raw_error, indent=2) if raw_error else str(error_summary)
        return self.prog(
            user_query=user_query,
            error_summary=error_summary,
            raw_error=raw_str
        )