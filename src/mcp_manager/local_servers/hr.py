from typing import Any, Dict
from mcp_manager.mcp_manager import MockBackendServer

def build_hr_server() -> MockBackendServer:
    hr = MockBackendServer("hr")

    def hr_get_policy(args: Dict[str, Any]) -> Dict[str, Any]:
        country = args.get("country", "UNKNOWN")
        return {
            "country": country,
            "policy": f"Stubbed vacation policy for {country}.",
        }

    hr.add_tool(
        name="get_policy",
        description=(
            "Get HR vacation policy for a country code. "
            "Use this tool whenever the user asks about HR vacation policy "
            "for any country. Do NOT guess."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "description": "ISO country code, e.g. 'DE'.",
                }
            },
            "required": ["country"],
        },
        handler=hr_get_policy,
    )

    return hr