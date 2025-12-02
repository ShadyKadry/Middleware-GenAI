import unittest
from typing import List

from mcp_manager.data.tool_models import MockBackendServer
from mcp_manager.mcp_manager import get_mock_mcp_servers
from mcp_manager.mcp_server_registry import backend_registry


class TestMCPManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # create authenticating principal
        self.principal = {
        "user_id": "user",
        "roles": "admin",
        "token": "1234",
        }

        # load MCP server registry
        backend_registry.load_config_from_disk()

    async def test_mock_mcp_server_retrieval(self) -> None:
        """
        Assumes that the backends.json is used for server access config.
        """
        # establish connection to the principal-accessible MCP servers
        backends: List[MockBackendServer] = get_mock_mcp_servers(self.principal)
        available_servers = [backend.server_id for backend in backends]

        # verify
        self.assertEqual(len(available_servers), 2)
        self.assertIn("hr", available_servers)
        self.assertIn("jira", available_servers)

if __name__ == "__main__":
    # allows `python tests/mcp_manager/test_mcp_manager.py` as well as `python -m unittest`
    unittest.main()