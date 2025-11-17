
# Middleware for GenAI

---

## Prerequisites

Before starting you need to ensure you have the following on your machine:
* **Dive AI**: Open-source MCP Host Desktop Application that seamlessly integrates with any LLMs supporting function calling capabilities.
  *  Download the official release from: [here](https://github.com/OpenAgentPlatform/Dive?tab=readme-ov-file#download-and-install-%EF%B8%8F)
* **Google AI API Key**: The free API key lets you integrate gemini models into Dive AI.
  * Tutorial on how to get it: [here](https://www.youtube.com/watch?v=prrb0hsfI60&t=9s)
  * Note: You could also use any other model like ChatGPT or Claude, if you have an API key for them.
  * Note#2: Local models like Ollama also work, but were way too slow in test runs (on my machine).
* **GitHub repository**: Clone the repository to your machine.
* **Python**: Self-explanatory I guess.

---

## Set-Up

1. Go to the root of the repository and create a new virtual environment (name it `.venv`), using the `requirements.txt` file and `python3.12`.
2. Open the `Dive AI` desktop application. If asked to choose between `Local MCP servers` and `OAP Cloud Services`, choose the local variant.
3. You should see a **chat interface**, with a button next to it where you can select your model. Select `Gemini Flash 2.5` (as suggested
by Bach) and use your **Google AI API key** in the respective field to get access.
4. You should now be able to input prompts and get responses. (You're simply using `Gemini Flash 2.5` at this point.)
5. On the bottom right of the chat window you should see a button with a small tool icon. Click on it and navigate to the `MCP tool registry`.
6. You should see a single MCP server available which is named `echo`. Click on the green button above which lets you add new servers/configurations.
7. Now register the middleware application (implemented as MCP server) by copying the following into the JSON field on the right:
```
{
  "mcpServers": {
    "middleware-genai": {
      "transport": "stdio",
      "enabled": true,
      "command": "/Users/path/to/repository/Middleware-GenAI/.venv/bin/python",
      "args": [
        "/Users/path/to/repository/Middleware-GenAI/middleware_application.py"
      ],
      "exclude_tools": [],
      "initialTimeout": 20
    }
  }
}
```
* NOTE: Its important that you use the absolute path (i.e. starting from /Users on Mac)
8. The middleware application and all its 3 tools should now be available as a single MCP server and can be toggled on/off in the chat interface.
9. The MCP Client/LLM chatbot (i.e. `Gemini Flash 2.5`) is now able to interact with the middleware server through MCP.

---

## Running the current system

The current middleware implementation has 3 different MCP servers available which each having only one (hardcoded) tool:
- hr
- jira
- purpose

The way the LLM chatbot will integrate them is by parsing the prompt and looking through the **tool list** of the middleware 
server. If the description of a tool matches the prompt semantically (it does not have to match the description perfectly), 
it will be called to provide a response. 

### Examples
Make sure that the middleware-genai MCP server is used for responses (deactivate `echo` server just in case) and all 
three tools are accessible.

```
Prompt: hello
Response: Some generic answer without any tool calling as none of the tool descriptions will be matched to the prompt.
```
The MCP servers available within the middleware server do not contain actual logic, but rather mock real server behaviour 
through generic, hardcoded responses:
```
Prompt: can you provide all jira issues regarding project management?
Response: [calling jira.search_issues]

Here are the Jira issues regarding project management:

PROJ-1: Stubbed issue 1
PROJ-2: Stubbed issue 2
```
There's no actual jira tickets, let alone ones for project management. It's all pre-written.

```
Prompt: can you give me the vacation policy for germany?
Response: [calling hr.get_policy]

Here is the vacation policy for Germany:

Country: DE
Policy: Stubbed vacation policy for DE.
```
No actual logic to get real policies. Returns a simple pre-written string as `hr` MCP servers response.

The LLM chatbot however also lets you use tools even though the words don't match exactly (e.g. purpose and reason)
```
Prompt: whats the reason to learn more about MCP and GenAI?
Response: [calling purpose.find_purpose]
The purpose of learning more about MCP and GenAI is to finish the Fraunhofer AMT project.
```

You can also provide a prompt which triggers multiple tools for the same response or ask the LLM chatbot to do something with the response directly.