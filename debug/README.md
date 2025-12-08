# Problem
Dive AI does not display middleware internal error messages, so if something fails, the shown error message will be 
rather generic not leaving any clues to what exactly is broken inside.

# Fix
Wrap the middleware with a bash script which writes all middleware-internal error messages in a log file.

# How to:
Make the debugging script executable:
```chmod +x run_middleware.sh```

Then create a new (debugging) MCP server in Dive AI (see the src/README.md for more info), by only 
specifying a name (can be anything) and setting this as command:
```/absolute/path/to/repo/Middleware-GenAI/debug/run_middleware.sh```

The internal logs of the middleware will be stored in 'mcp_pg.log' in this directory.
