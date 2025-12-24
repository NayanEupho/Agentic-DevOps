
import unittest
from unittest.mock import patch, MagicMock
from devops_agent.k8s_tools.remote_k8s_metrics_tools import RemoteK8sTopNodesTool, RemoteK8sTopPodsTool
from devops_agent.k8s_tools.remote_k8s_exec_tools import RemoteK8sExecTool

class TestRemoteK8sAdvancedTools(unittest.TestCase):

    @patch('devops_agent.k8s_tools.remote_k8s_metrics_tools.requests.get')
    def test_top_nodes(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "metadata": {"name": "node-1"},
                    "usage": {"cpu": "100m", "memory": "2048Ki"}
                }
            ]
        }
        mock_get.return_value = mock_response

        tool = RemoteK8sTopNodesTool()
        result = tool.run()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['nodes'][0]['name'], "node-1")
        self.assertEqual(result['nodes'][0]['cpu_usage'], "100m")

    @patch('devops_agent.k8s_tools.remote_k8s_metrics_tools.requests.get')
    def test_top_pods(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "metadata": {"name": "pod-1", "namespace": "default"},
                    "containers": [{"usage": {"cpu": "10m", "memory": "100Ki"}}]
                }
            ]
        }
        mock_get.return_value = mock_response

        tool = RemoteK8sTopPodsTool()
        result = tool.run(namespace="default")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['pods'][0]['name'], "pod-1")

    @patch('devops_agent.k8s_tools.remote_k8s_exec_tools.subprocess.run')
    def test_exec_safe_command(self, mock_run):
        # Mock subprocess success
        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "bin\nboot\ndev\n"
        mock_run.return_value = mock_sub
        
        # Mock tempfile to avoid IO in test? 
        # Actually the tool has internal IO. We'll let it make the temp file (it cleans up).
        # We assume k8s_config has defaults.
        
        tool = RemoteK8sExecTool()
        # Mocking k8s_config internal token/url (it's a singleton import, so we patch safely if needed).
        # For this test we assume normal import works.
        
        result = tool.run(pod_name="test-pod", namespace="default", command=["ls", "/"])
        
        self.assertTrue(result['success'])
        self.assertIn("bin", result['output'])

    def test_exec_unsafe_command_rejected(self):
        tool = RemoteK8sExecTool()
        result = tool.run(pod_name="test-pod", namespace="default", command=["rm", "-rf", "/"])
        
        self.assertFalse(result['success'])
        self.assertIn("is NOT in the safe allow-list", result['error'])

if __name__ == '__main__':
    unittest.main()
