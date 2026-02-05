CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  is_superadmin BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- predefined: enum like -- currently roles cannot be created dynamically so all will be predefined in 02-seed.sql
CREATE TABLE roles (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE mcp_servers (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL,
  transport TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  config JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE corpora (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  database_model TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  meta JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- joint table for users & roles -- allows multiple roles for user
CREATE TABLE user_roles (
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  role_id INT REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

-- joint table for users & servers --
CREATE TABLE mcp_servers_user_access (
  server_id INT NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (server_id, user_id)
);

-- joint table for roles & servers --
CREATE TABLE mcp_servers_role_access (
  server_id INT NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
  role_id INT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY (server_id, role_id)
);

-- joint table for corpus & user --
CREATE TABLE corpus_user_access (
  corpus_id TEXT NOT NULL REFERENCES corpora(id) ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (corpus_id, user_id)
);

-- join table for corpus & role --
CREATE TABLE corpus_role_access (
  corpus_id TEXT NOT NULL REFERENCES corpora(id) ON DELETE CASCADE,
  role_id INT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY (corpus_id, role_id)
);

-- INDEXES --

-- user_roles: fast lookup of all users that have a given role
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id
  ON user_roles(role_id);

-- mcp server access: fast lookup by user or role
CREATE INDEX IF NOT EXISTS idx_mcp_servers_user_access_user_id
  ON mcp_servers_user_access(user_id);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_role_access_role_id
  ON mcp_servers_role_access(role_id);

-- corpus access: fast lookup by user or role
CREATE INDEX IF NOT EXISTS idx_corpus_user_access_user_id
  ON corpus_user_access(user_id);

CREATE INDEX IF NOT EXISTS idx_corpus_role_access_role_id
  ON corpus_role_access(role_id);


-- VIEWS --

-- this view is for the 'mcp_server_loader.py' in the middleware component and retrieves all servers accessible
-- to a user based on its userID as well as its assigned roles (multiple possible).
-- selection via union(user grants, role grants).
CREATE OR REPLACE VIEW vw_mcp_servers_effective_by_username AS
WITH user_ctx AS (
  SELECT u.id AS user_id, u.username
  FROM users u
),
role_grants AS (
  SELECT uc.username, s.*
  FROM user_ctx uc
  JOIN user_roles ur ON ur.user_id = uc.user_id
  JOIN mcp_servers_role_access sra ON sra.role_id = ur.role_id
  JOIN mcp_servers s ON s.id = sra.server_id
  WHERE s.enabled = TRUE
),
user_grants AS (
  SELECT uc.username, s.*
  FROM user_ctx uc
  JOIN mcp_servers_user_access sua ON sua.user_id = uc.user_id
  JOIN mcp_servers s ON s.id = sua.server_id
  WHERE s.enabled = TRUE
)
SELECT DISTINCT ON (username, id)
  username,
  id,
  name,
  kind,
  transport,
  enabled,
  config,
  created_at
FROM (
  SELECT * FROM role_grants
  UNION ALL
  SELECT * FROM user_grants
) x
ORDER BY username, id;
