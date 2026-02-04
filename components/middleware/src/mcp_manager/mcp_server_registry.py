
from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict, List, Callable

import mcp_manager.local_servers as local_servers_pkg
from mcp_manager.data.tool_models import MockBackendServer, MCPConnectionConfig, RemoteBackendServer, BackendServer
from mcp_manager.mcp_server_loader import load_allowed_servers_for_user

BackendFactory = Callable[[], MockBackendServer]


class BackendRegistry:
    """
    Encapsulates:
    - backend factory functions (document_retrieval, jira, ...) to execute local implementations
    - loading MCP servers configurations from database
    - building the list of backends for a given principal
    """

    def __init__(self) -> None:
        self._factories: Dict[str, BackendFactory] = {}

        # auto-discover local mock factories once
        self._auto_register_local_factories()

    # ---------- auto-discovery of local server factories ----------

    def _auto_register_local_factories(self) -> None:
        """
        Scan mcp_manager.local_servers for modules that define
        SERVER_KEY + build_backend() and register them automatically.
        """
        for module_info in pkgutil.iter_modules(local_servers_pkg.__path__):
            module_name = module_info.name
            full_name = f"{local_servers_pkg.__name__}.{module_name}"
            module = importlib.import_module(full_name)

            key = getattr(module, "SERVER_KEY", None)
            factory = getattr(module, "build_backend", None)

            if key and callable(factory):
                self.register_factory(key, factory)

    # ---------- factories ----------

    def register_factory(self, key: str, factory: BackendFactory) -> None:
        """
        Register a backend factory under a short name, e.g. "jira" -> build_jira_server.
        These keys must match the 'factory' field in the DB entries.
        """
        self._factories[key] = factory

    # ---------- main API ----------

    async def get_backends_for_principal(
        self,
        principal: Dict[str, Any],
    ) -> List[BackendServer]:
        """
        Returns a list of BackendServer instances the principal is allowed to access,
        based on current database access table.
        """
        user_id: str = principal.get("user_id", "guest")
        allowed_servers = await load_allowed_servers_for_user(username=user_id)
        result: List[BackendServer] = []

        # build connection to all allowed servers
        for server in allowed_servers:
            if not server.get("enabled", True):
                continue
            kind = server.get("kind", "")

            if kind == "local_mcp_mock":
                cfg = server.get("config", {})

                # load factory method for local server scripts
                factory_name: str = cfg.get("factory", "")
                factory = self._factories.get(factory_name)

                # ignore silently
                if factory is None:
                    continue

                factory = self._factories.get(factory_name)
                if factory is None:
                    continue
                backend = factory()
                result.append(backend)

            elif kind == "remote_mcp":
                cfg = server.get("config", {})
                connection_cfg = MCPConnectionConfig(
                    name=server["name"],
                    transport=server.get("transport", "stdio"),
                    command=cfg.get("command"),
                    args=cfg.get("args", []),
                    env=cfg.get("env", {}), # TODO redundant?
                    server_url=cfg.get("server_url"),
                    headers=cfg.get("headers", {}),
                )
                backend = RemoteBackendServer(server_id=connection_cfg.name, config=connection_cfg)
                await backend.connect()  # this calls docker + MCP handshake + listTools
                result.append(backend)

        return result


# ---------- module-level singleton ----------
backend_registry = BackendRegistry()

