import unittest
from devops_agent.agent_module import parse_dspy_tool_calls

class TestParserChaining(unittest.TestCase):
    def test_parse_multiple_tools(self):
        # Simulate LLM output with multiple tools
        llm_output = """
        [
            {"name": "remote_k8s_list_pods", "arguments": {"namespace": "default"}},
            {"name": "local_k8s_list_nodes", "arguments": {}}
        ]
        """
        
        result = parse_dspy_tool_calls(llm_output)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], "remote_k8s_list_pods")
        self.assertEqual(result[1]['name'], "local_k8s_list_nodes")
        
    def test_parse_multiple_tools_prose(self):
        # Simulate Prose with JSON
        llm_output = """
        Based on your request, I will listing pods and nodes.
        ```json
        [
            {"name": "tool_A", "arguments": {"x": 1}},
            {"name": "tool_B", "arguments": {"y": 2}}
        ]
        ```
        """
        result = parse_dspy_tool_calls(llm_output)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], "tool_A")
        self.assertEqual(result[1]['name'], "tool_B")

if __name__ == '__main__':
    unittest.main()
