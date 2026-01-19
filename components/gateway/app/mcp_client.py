import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Optional

from google.genai import types
from google.genai.types import Tool, FunctionDeclaration
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

UNSUPPORTED_JSON_SCHEMA_KEYS = {
    "$schema",
    "$id",
    "id",
    "title",
    "description",
    "definitions",
    "$defs",
}

# todo split into 2 parts: e.g. MiddlewareSession & GeminiOrchestrator ?
class MCPClient:

    def __init__(self, user_id:str, role:str):
        self.model_name = "gemini-2.5-flash"  # change if more are supported at one point
        self.user_id = user_id
        self.role = role
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

        components_dir = Path(__file__).resolve().parent.parent.parent
        self.middleware_script = components_dir / "middleware" / "src" / "middleware_application.py"

        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            print("Missing GEMINI_API_KEY environment variable")
            #raise ValueError("Missing GEMINI_API_KEY environment variable")

        self.genai_client = None #genai.Client(api_key=gemini_api_key)
        self.function_declarations = []


    async def connect_to_server(self):
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[
                str(self.middleware_script),
                "--user_id", self.user_id,
                "--role", self.role,
            ],
            env=None,
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        read_stream, write_stream = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools

        self.function_declarations = convert_mcp_tools_to_gemini(tools)

    async def process_query(self, query: str):
        user_prompt_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)]
        )
        response = self.genai_client.models.generate_content(
            model=self.model_name,
            contents=[user_prompt_content],
            config=types.GenerateContentConfig(tools=self.function_declarations)
        )

        final_text = []
        assistant_message_content = []

        for candidate in response.candidates:
            if candidate.content.parts:
                for part in candidate.content.parts:
                    if isinstance(part, types.Part):
                        if part.function_call:
                            function_call_part = part
                            tool_name = function_call_part.function_call.name
                            tool_args = function_call_part.function_call.args

                            # Print debug info: Which tool is being called and with what arguments
                            print(f"\n[Gemini requested tool call: {tool_name} with args {tool_args}]")

                            # Execute the tool using the MCP server
                            try:
                                result = await self.session.call_tool(tool_name, tool_args)
                                function_response = {"result": result.content}
                            except Exception as e:
                                function_response = {"error": str(e)}

                            # Format the tool response for Gemini in a way it understands
                            function_response_part = types.Part.from_function_response(
                                name=tool_name,
                                response=function_response
                            )

                            # Structure the tool response as a Content object for Gemini
                            function_response_content = types.Content(
                                role="tool",
                                parts=[function_response_part]
                            )

                            response = self.genai_client.models.generate_content(
                                model=self.model_name,
                                contents=[
                                    user_prompt_content,
                                    function_call_part,
                                    function_response_content,
                                ],
                                config=types.GenerateContentConfig(
                                    tools=self.function_declarations,
                                ),
                            )

                            # Extract final response text from Gemini after processing the tool call
                            final_text.append(response.candidates[0].content.parts[0].text)
                        else:
                            # If no function call was requested, simply add Gemini's text response
                            final_text.append(part.text)

        # Return the combined response as a single formatted string
        return "\n".join(final_text)

    async def chat_loop(self):
        while True:
            query = input("\nQuery: ").strip()
            if query.lower() == 'quit':
                break

            # Process the user's query and display the response
            response = await self.process_query(query)
            print("\n" + response)

    async def cleanup(self):
        """Clean up resources before exiting."""
        await self.exit_stack.aclose()




def clean_schema(obj):
    # Recurse lists
    if isinstance(obj, list):
        return [clean_schema(x) for x in obj]

    # Recurse dicts
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if k in UNSUPPORTED_JSON_SCHEMA_KEYS:
                continue
            cleaned[k] = clean_schema(v)
        return cleaned

    # Primitives
    return obj



def convert_mcp_tools_to_gemini(tools) -> list:
    gemini_tools = []
    for tool in tools:
        parameters = clean_schema(tool.inputSchema)
        print(parameters)
        function_declaration = FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters=parameters,
        )
        gemini_tool = Tool(function_declarations=[function_declaration])
        gemini_tools.append(gemini_tool)

    return gemini_tools
