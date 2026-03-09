# Walkthrough

Assumes that all steps of the "Quick Setup (Local)" have been successfully executed, and you're now logged in as the systems root user:
- user name: ``Admin``
- user role: ``Super-Admin``

Through the pre-installed root user, you have access to a selection of pre-installed MCP servers. However, no documents are available yet.

## Chat
You will start on the `Chat` tab and might have to wait until all MCP servers and documents have been loaded. <br>

As you can see, the Chat tab consists of 3 logical sections: 
- **Auto-Search**: The systems RAG component.
    - On first start-up there will be no collections to search yet (i.e. `No collections available.`). We'll change that in a moment.
    - Can be toggled on/off for each request/prompt depending on needs.
    - Lets you restrict the amount of results that should be considered in the answer via the `Top K` spinbox.
- **Available Tools**:
    - On first start-up there will be following MCP servers available by default: `Wikipedia`, `YouTube Transcript` and `deepwiki`.
    - Each MCP server exposes at least one tool. Each tool provides a short description on its functionality in natural language.
    - You can select dynamically each prompt which tools you want to provide the LLM with when generating the answer. (The more tools you choose the more utilized the context window of the LLM becomes, so it makes sense to be selective)
- **Chat Interface**: 
    - Lets you communicate with the `Google Gemini 2.5 Flash` LLM model.
    - Each prompt/request can be extended by the desired MCP tools and document collections you would like to include in the answer generation.
    - Please be aware that ongoing conversations are currently stateless i.e. the LLM is not aware of previous prompts/answers in the same chat window.

For a normal user of the system, this sums up the system functionality which combines a LLM chat with RAG and dynamic MCP-based tool calling beyond text generation.

## Admin Functionality
As `Admin` (or `Super-Admin`) you have additional functionally available, which consist of user management, data upload and new MCP server registration.
Please be aware that the management of the current system through admins is restricted to **adding** users, documents and MCP servers. Deleting them selectively is not yet considered. (you can however reset to default by deleting all stored data via `docker compose down -v`)

An important component of the system is the user-/role-based-access control.
#### Currently considered user roles:
- Super-Admin ( not possible to create new user with this role → only the root user )
- Admin ( user with admin functionalities )
- User  ( normal user )
- Student ( normal user )
- Guest ( normal user ) <br>
Currently `User`, `Student` and `Guest` do not fill distinct roles by default, but rather serve as hypothetical roles to showcase user-/role-based access.

Its currently not possible to add/remove user roles dynamically through the web UI.
### 1. MCP Server Registration
New MCP servers can be added via the `Add MCP servers` tab on the left sidebar.

If you find an MCP server that you find useful, you should look for its JSON specification. It contains the information you need to register a new MCP server.<br>
To give an example for the `DuckDuckGo` MCP server:
```
{
  "mcpServers": {
    "duckduckgo": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "mcp/duckduckgo"
      ]
    }
  }
}
```
Now you need to fill out the form based on its information to register the server in the system:
- `Name` → specify the name the server should be known and displayed under
- `Transport` → the way the server is accessible i.e. via stdio, SSE or HTTP. (the example server runs as local docker container i.e. stdio)
- Depending on transport type, you should fill out the respective information. (`stdio` → `Command`&`Args`; `SSE/HTML` → `Server URL`)
- `Allowed users` → (optional) specify individual users that should have access to the MCP server
- `Required roles` → (optional) specify the roles that should have access to this MCP server (`Admin` users always have access to it)

In order to use the newly registered MCP servers, you should reload the web page. 

### 2. Document Upload
New documents can be uploaded via the `Upload documents` tab on the left sidebar.

Our document store is based on collections (groups of documents associated with the same context) which could be e.g. all documents (lectures slides/exercises/solutions) of a university course.
You can either:
- upload to an existing collection
- create a new collection (subsequently other docs can be uploaded to it as well)<br>

The latter is triggered automatically if the specified corpus doesn't exist.<br>
Some details on the upload form:
- `File` → select the file you want to upload (currently only one-at-a-time)
- `Corpus ID` → the collection you want to create/upload to
- `Allowed users` → (optional) specify individual users that should have access to this collection
- `Allowed roles` → (optional) specify the roles that should have access to this collection (`Admin` users  always have access to it)
- `Database` → choose the vector DB you want to upload to (currently `Qdrant` and `Pgvector` are supported)
- `Embedding Model` → choose the model you want to use for the embedding (use `Gemini embedding-001`. `Stub` is a deterministic but semantically useless dummy to highlight the choice of embedding pipeline)
- `Chunk Size` → the amount of tokens each document partition consists of (at most)
- `Chunk Overlap` → the token overlap between 2 sequential partitions

Note: `Corpus ID` will serve as the displayed name in the `Chat` tab, so try to keep it as accurate as possible to the collections content.<br>
Uploaded documents are chunked, embedded using the selected embedding model, and stored in the chosen vector database to enable semantic retrieval during chat queries.

On successful upload, you should reload the web page to be able to use the new document.

### 3. User Creation
Initially the only registered user is the system root user you're logged in as. To fill the system with other admins and users you can create them via the `Create user` tab on the left sidebar. 
For each new user you can choose which document collections and MCP servers it should have access to.
Again, some details on the upload form:
- `Username` and `Password` should be self-explanatory.
- `Role` → the role the new user should have (as mentioned above, you cannot create `Super-Admin` user)
- `Select MCP Servers` → Check/uncheck the servers the user should have access to
- `Select Document Collections` → Check/uncheck the collections the user should have access to (if you haven't uploaded any documents yet this will show: `No collections available.`)

It'll happen that new MCP servers/documents are uploaded after the user was created, the user subscribes via its user role and therefore automatically receives new servers/collection (on page reload)

## Access (User-/Role-based)
Access is granted based on a conjunction of allowed users and allowed roles i.e. an allowed user can access a server or document even though his role would not allow and vice versa.
The main intention of access control is however RBAC, with fine-granular selection of a small group or individuals that should also have access.