import unittest
from typing import List

from mcp_manager.data.tool_models import BackendServer
from mcp_manager.mcp_manager import get_mcp_servers


"""
IMPORTANT FOR SUCCESSFUL EXECUTION:
    These tests require you to add the "YouTube Transcripts" MCP server to your servers in:
        Docker Desktop > MCP Toolkit (BETA) > Catalog
        
    After adding it and it showing up in your "My servers" tab, this test can be executed successfully.
"""


class TestMCPManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # create authenticating principal
        self.principal = {"user_id": "Admin", "role": "Super-Admin"}

    async def test_mcp_server_retrieval(self) -> None:
        """
        Assumes that the database in 'mcp_server_loader.py' is used for server access config.
        """
        # establish connection to the principal-accessible MCP servers
        backends: List[BackendServer] = await get_mcp_servers(self.principal)

        # save available servers/tools
        available_servers = [backend.server_id for backend in backends]
        available_tools = [tool for backend in backends for tool in backend.get_tools()]

        # verify
        self.assertEqual(len(available_servers), 4)
        self.assertIn("deepwiki", available_servers)
        self.assertIn("document_retrieval", available_servers)
        self.assertIn("wikipedia_mcp", available_servers)
        self.assertIn("youtube_transcript", available_servers)
        self.assertEqual(len(available_tools), 19)  # 11x wikipedia_mcp / 2x document_retrieval / 3x deepwiki / 3x youtube_transcripts


if __name__ == "__main__":
    # allows `python tests/mcp_manager/test_mcp_manager.py` as well as `python -m unittest`
    unittest.main()