-- enum of available roles in the system
WITH system_roles(name) AS (
  VALUES
    ('Super-Admin'),
    ('Admin'),
    ('User'),
    ('Guest'),
    ('Student')
)
INSERT INTO roles(name)
SELECT name FROM system_roles
ON CONFLICT DO NOTHING;

-- create super admin (base user without any access restrictions)
INSERT INTO users (username, password_hash, is_superadmin)
VALUES (
  'Admin',
  '$2b$12$3tUFwKNqyWLWHEsDJYf3vOnLu.txlzspW4QCHeK2wKBDlBuTlEonq', -- bcrypt hash of: adminpass
  TRUE
)
ON CONFLICT (username) DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.username = 'Admin'
  AND r.name = 'Super-Admin'
ON CONFLICT DO NOTHING;

-- create all base MCP server specs
INSERT INTO mcp_servers (name, kind, transport, enabled, config)
VALUES
(
  'youtube_transcript',
  'remote_mcp',
  'stdio',
  TRUE,
  '{
            "command": "docker",
            "args": ["run", "-i", "--rm", "mcp/youtube-transcript"]
          }'::jsonb
),
(
  'wikipedia_mcp',
  'remote_mcp',
  'stdio',
  TRUE,
  '{
            "command": "docker",
            "args": ["run", "-i", "--rm", "mcp/wikipedia-mcp"]
          }'::jsonb
),
(
 'deepwiki',
 'remote_mcp',
 'http',
 TRUE,
 '{
            "server_url": "https://mcp.deepwiki.com/mcp"
          }'::jsonb
),
(
 'document_retrieval',
 'local_mcp_mock',
 'in_app',
 TRUE,
 '{ "factory": "document_retrieval" }'::jsonb
)
ON CONFLICT (name) DO NOTHING;

-- grant super-admin access to all MCP servers
INSERT INTO mcp_servers_role_access (server_id, role_id)
SELECT s.id, r.id
FROM mcp_servers s
JOIN roles r ON r.name IN ('Super-Admin', 'Admin')
ON CONFLICT DO NOTHING;

-- TODO create collections on start