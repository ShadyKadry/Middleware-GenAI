import unittest
from typing import List

from mcp_manager.data.tool_models import BackendServer, RemoteBackendServer
from mcp_manager.mcp_manager import get_mcp_servers
from mcp_manager.mcp_server_registry import backend_registry


"""
IMPORTANT FOR SUCCESSFUL EXECUTION:
    These tests require you to add the "YouTube Transcripts" MCP server to your servers in:
        Docker Desktop > MCP Toolkit (BETA) > Catalog
        
    After adding it and it showing up in your "My servers" tab, this test can be executed successfully.
"""


class TestMCPManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # create authenticating principal
        self.principal = {
        "user_id": "user", #"test_user_1",
        "role": "admin",
        "token": "1234",
        }

        # load MCP server registry
        backend_registry.load_config_from_disk()

    async def test_mcp_server_retrieval(self) -> None:
        """
        Assumes that the backends.json is used for server access config.
        """
        # establish connection to the principal-accessible MCP servers
        backends: List[BackendServer] = await get_mcp_servers(self.principal)

        # save available servers/tools
        available_servers = [backend.server_id for backend in backends]
        available_tools = [tool for backend in backends for tool in backend.get_tools()]

        # close connections to the servers
        for backend in backends:
            if isinstance(backend, RemoteBackendServer):
                await backend.close()

        # verify
        self.assertEqual(len(available_servers), 3)
        self.assertIn("hr", available_servers)
        self.assertIn("jira", available_servers)
        self.assertIn("deepwiki", available_servers)
        self.assertEqual(len(available_tools), 5)  # 1x HR / 1x Jira / 3x deepwiki


if __name__ == "__main__":
    # allows `python tests/mcp_manager/test_mcp_manager.py` as well as `python -m unittest`
    unittest.main()