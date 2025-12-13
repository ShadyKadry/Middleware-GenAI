
from __future__ import annotations

import importlib
import json
import os
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Callable

import mcp_manager.local_servers as local_servers_pkg
from mcp_manager.data.tool_models import MockBackendServer, MCPConnectionConfig, RemoteBackendServer, BackendServer

BackendFactory = Callable[[], MockBackendServer]


class BackendRegistry:
    """
    Encapsulates:
    - backend factory functions (hr, jira, ...)
    - loading/parsing backends.json
    - building the list of backends for a given principal
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or Path(
            os.getenv("MW_BACKENDS_CONFIG", Path(__file__).parent / "local_servers" / "backends.json")  # let user define their own, otherwise use 'backends.json'
        )
        self._config: Dict[str, Any] = {"backends": []}
        self._factories: Dict[str, BackendFactory] = {}

        # auto-discover local mock factories once
        self._auto_register_local_factories()

    # ---------- auto-discovery of local servers ----------

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
        These keys must match the 'factory' field in backends.json.
        """
        self._factories[key] = factory

    # ---------- config loading ----------

    def load_config_from_disk(self) -> None:
        """
        Load/refresh the backend configuration from disk into memory.
        """
        if not self._config_path.exists():
            # no file -> keep empty config
            self._config = {"backends": []}
            return

        with self._config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if "backends" not in data or not isinstance(data["backends"], list):
            raise ValueError("Invalid backend config: missing 'backends' list")

        self._config = data

    @property
    def config(self) -> Dict[str, Any]:
        """
        Read-only access to current config.
        Useful if admin tools want to inspect it.
        """
        return self._config

    # ---------- main API ----------

    async def get_backends_for_principal(
        self,
        principal: Dict[str, Any],
    ) -> List[BackendServer]:
        """
        Returns a list of BackendServer instances the principal is allowed to access,
        based on current in-memory config.
        """
        user_id: str = principal.get("user_id", "guest")
        roles: List[str] = principal.get("roles", [])

        result: List[BackendServer] = []

        for backend_def in self._config.get("backends", []):
            if not backend_def.get("enabled", True):
                continue
            kind = backend_def.get("kind", "")

            factory_name: str = backend_def.get("factory", "")
            factory = self._factories.get(factory_name)
            if factory is None and kind != "remote_mcp":
                continue

            required_roles: List[str] = backend_def.get("required_roles", [])
            allowed_users: List[str] = backend_def.get("allowed_users", [])

            has_role = not required_roles or any(r in roles for r in required_roles)
            user_allowed = not allowed_users or user_id in allowed_users

            if not (has_role and user_allowed):
                continue

            if kind == "local_mcp_mock":
                factory_name: str = backend_def.get("factory", "")
                factory = self._factories.get(factory_name)
                if factory is None:
                    continue
                backend = factory()
                result.append(backend)

            elif kind == "remote_mcp":
                cfg = MCPConnectionConfig(
                    name=backend_def["name"],
                    transport=backend_def.get("transport", "stdio"),
                    command=backend_def.get("command"),
                    args=backend_def.get("args", []),
                    env=backend_def.get("env", {}),
                    server_url=backend_def.get("server_url"),
                    headers=backend_def.get("headers", {}),
                )
                backend = RemoteBackendServer(server_id=cfg.name, config=cfg)
                await backend.connect()  # this calls docker + MCP handshake + listTools
                result.append(backend)

        return result


# ---------- module-level singleton ----------
backend_registry = BackendRegistry()

