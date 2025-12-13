import unittest

from mcp_manager.data.tool_models import ToolRegistry
from mcp_manager.mcp_manager import build_middleware_tool_registry


class MyTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_application(self):

        current_principal = {
            "user_id": "user",
            "roles": "admin",
            "token": 1234,  # not used at the moment
        }

        tool_registry: ToolRegistry = await build_middleware_tool_registry(current_principal)
        self.assertEqual(len(tool_registry._tools), 21)  # add assertion here


if __name__ == '__main__':
    unittest.main()
