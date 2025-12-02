from typing import Any, Dict
from mcp_manager.mcp_manager import MockBackendServer

def build_jira_server() -> MockBackendServer:
    jira = MockBackendServer("jira")

    def jira_search(args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        # Stubbed list of tickets
        return {
            "query": query,
            "issues": [
                {"key": "PROJ-1", "summary": "Stubbed issue 1"},
                {"key": "PROJ-2", "summary": "Stubbed issue 2"},
            ],
        }

    jira.add_tool(
        name="search_issues",
        description="Search Jira issues by text query (stubbed).",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string.",
                }
            },
            "required": ["query"],
        },
        handler=jira_search,
    )

    return jira