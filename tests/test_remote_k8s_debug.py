
import unittest
from unittest.mock import patch, MagicMock
from devops_agent.k8s_tools.remote_k8s_debug_tools import RemoteK8sGetLogsTool, RemoteK8sListEventsTool

class TestRemoteK8sDebugTools(unittest.TestCase):

    @patch('devops_agent.k8s_tools.remote_k8s_debug_tools.requests.get')
    def test_get_logs_success(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Line 1\nLine 2\nError: Something bad happened\n"
        mock_get.return_value = mock_response

        tool = RemoteK8sGetLogsTool()
        result = tool.run(pod_name="test-pod", namespace="default", lines=50)

        self.assertTrue(result['success'])
        self.assertIn("Line 1", result['logs'])
        self.assertEqual(result['pod_name'], "test-pod")

    @patch('devops_agent.k8s_tools.remote_k8s_debug_tools.requests.get')
    def test_get_logs_multi_container_error(self, mock_get):
        # Setup mock for 400 error (ambiguous container)
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "a container name must be specified for pod test-pod, choose one of: [main-app, sidecar]"
        mock_get.return_value = mock_response

        tool = RemoteK8sGetLogsTool()
        result = tool.run(pod_name="test-pod")

        self.assertFalse(result['success'])
        self.assertIn("Pod has multiple containers", result['error'])

    @patch('devops_agent.k8s_tools.remote_k8s_debug_tools.requests.get')
    def test_list_events_success(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "reason": "FailedScheduling",
                    "message": "0/1 nodes are available",
                    "type": "Warning",
                    "involvedObject": {"kind": "Pod", "name": "test-pod"},
                    "count": 5,
                    "last_timestamp": "2023-10-27T10:00:00Z"
                },
                {
                    "reason": "Started",
                    "message": "Started container",
                    "type": "Normal",
                    "involvedObject": {"kind": "Pod", "name": "test-pod"},
                    "count": 1,
                    "last_timestamp": "2023-10-27T09:00:00Z"
                }
            ]
        }
        mock_get.return_value = mock_response

        tool = RemoteK8sListEventsTool()
        result = tool.run(resource_name="test-pod")

        self.assertTrue(result['success'])
        self.assertEqual(len(result['events']), 2)
        # Verify sorting (newest first)
        self.assertEqual(result['events'][0]['reason'], "FailedScheduling")

if __name__ == '__main__':
    unittest.main()
