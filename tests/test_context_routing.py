
import unittest
from devops_agent.smart_router import SmartMCPRouter
from devops_agent.context_cache import context_cache

class TestContextRouting(unittest.TestCase):
    def test_sticky_routing(self):
        """
        Verify that a session remembers the last MCP and uses it for follow-ups.
        """
        router = SmartMCPRouter()
        session_id = "test_session_123"
        
        # 1. Clear state
        context_cache.clear(session_id)
        
        # 2. Simulate "list pods" -> Should route to [k8s_local, k8s_remote] (ambiguous) 
        # But let's say we executed it on LOCAL
        context_cache.set_last_mcp(session_id, SmartMCPRouter.MCP_K8S_LOCAL)
        
        # 3. Follow-up: "describe it"
        # Since it contains "it", router should check cache
        routes = router.route("describe it", session_id=session_id)
        
        print(f"Routes for 'describe it': {routes}")
        
        # Should contain LOCAL because it was last active
        self.assertIn(SmartMCPRouter.MCP_K8S_LOCAL, routes)
        
        # 4. Verify explicit override "describe remote node"
        # Should pick remote even if last was local
        routes_explicit = router.route("describe remote node", session_id=session_id)
        self.assertIn(SmartMCPRouter.MCP_K8S_REMOTE, routes_explicit)

if __name__ == '__main__':
    unittest.main()
