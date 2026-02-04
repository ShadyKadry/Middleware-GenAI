-- create new read-only user for middleware
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'middleware_ro') THEN
    CREATE ROLE middleware_ro LOGIN PASSWORD 'middleware_ro_pwd';
  END IF;
END$$;

-- allow user to connect to middleware
GRANT CONNECT ON DATABASE middleware_genai TO middleware_ro;
GRANT USAGE ON SCHEMA public TO middleware_ro;

-- allow only what middleware needs (plus users + user_roles because the view joins them)
GRANT SELECT ON TABLE
  mcp_servers,
  mcp_servers_user_access,
  mcp_servers_role_access,
  users,
  user_roles
TO middleware_ro;

GRANT SELECT ON vw_mcp_servers_effective_by_username TO middleware_ro;
