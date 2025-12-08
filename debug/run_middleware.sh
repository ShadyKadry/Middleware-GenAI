#!/bin/bash

# Redirect stderr to a logfile so exceptions can be seen
LOGFILE="/Users/arno/Desktop/WiSe2526_AMT/git/Middleware-GenAI/debug/mcp_pg.log"

# Run the MCP middleware server exactly as Dive would, but with stderr captured
/Users/arno/Desktop/WiSe2526_AMT/git/Middleware-GenAI/.venv/bin/python \
    /Users/arno/Desktop/WiSe2526_AMT/git/Middleware-GenAI/src/middleware_application.py \
    --stdio 2>$LOGFILE
