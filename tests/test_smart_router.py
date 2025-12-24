
import unittest
from devops_agent.smart_router import smart_router, SmartMCPRouter

class TestSmartRouter(unittest.TestCase):
    def test_docker_routing(self):
        mcps = smart_router.route("list docker containers")
        self.assertIn(SmartMCPRouter.MCP_DOCKER, mcps)
        self.assertNotIn(SmartMCPRouter.MCP_K8S_LOCAL, mcps)
    
    def test_remote_k8s_routing(self):
        mcps = smart_router.route("show nodes in remote cluster")
        self.assertIn(SmartMCPRouter.MCP_K8S_REMOTE, mcps)
    
    def test_local_k8s_routing(self):
        mcps = smart_router.route("list local pods")
        self.assertIn(SmartMCPRouter.MCP_K8S_LOCAL, mcps)
        
    def test_ambiguous_k8s_routing(self):
        # "list pods" -> should return BOTH local and remote to be safe
        mcps = smart_router.route("list pods")
        self.assertIn(SmartMCPRouter.MCP_K8S_LOCAL, mcps)
        self.assertIn(SmartMCPRouter.MCP_K8S_REMOTE, mcps)
        
    def test_complex_routing(self):
        # "list remote and local pods" -> Should have both
        mcps = smart_router.route("list remote and local pods")
        self.assertIn(SmartMCPRouter.MCP_K8S_LOCAL, mcps)
        self.assertIn(SmartMCPRouter.MCP_K8S_REMOTE, mcps)

    def test_chat_routing(self):
        # "hi" -> Should return CHAT
        mcps = smart_router.route("hi")
        self.assertIn(SmartMCPRouter.MCP_CHAT, mcps)
        # Should NOT include heavy tools
        self.assertNotIn(SmartMCPRouter.MCP_DOCKER, mcps)
        self.assertNotIn(SmartMCPRouter.MCP_K8S_REMOTE, mcps)

    def test_generic_fallback(self):
        # "status" -> Fallback to all system tools 
        mcps = smart_router.route("check system status")
        self.assertIn(SmartMCPRouter.MCP_DOCKER, mcps)
        self.assertIn(SmartMCPRouter.MCP_K8S_REMOTE, mcps)

if __name__ == '__main__':
    unittest.main()
