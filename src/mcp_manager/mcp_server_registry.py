
from __future__ import annotations

from typing import Any, Dict, List, Callable
from pathlib import Path
import json
import os

from mcp_manager.data.tool_models import MockBackendServer
# manual import necessary for the moment
from mcp_manager.local_servers.hr import build_hr_server
from mcp_manager.local_servers.jira import build_jira_server

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

    def get_backends_for_principal(
        self,
        principal: Dict[str, Any],
    ) -> List[MockBackendServer]:
        """
        Returns MockBackendServer instances the principal is allowed to access,
        based on current in-memory config.
        """
        user_id: str = principal.get("user_id", "guest")
        roles: List[str] = principal.get("roles", [])

        result: List[MockBackendServer] = []

        for backend_def in self._config.get("backends", []):
            if not backend_def.get("enabled", True):
                continue

            factory_name: str = backend_def.get("factory", "")
            factory = self._factories.get(factory_name)
            if factory is None:
                # Unknown factory in config: skip (or log)
                continue

            required_roles: List[str] = backend_def.get("required_roles", [])
            allowed_users: List[str] = backend_def.get("allowed_users", [])

            has_role = not required_roles or any(r in roles for r in required_roles)
            user_allowed = not allowed_users or user_id in allowed_users

            if has_role and user_allowed:
                backend = factory()
                result.append(backend)

        return result


# ---------- module-level singleton ----------

backend_registry = BackendRegistry()

# register factories once here – no other code needs to know
backend_registry.register_factory("hr", build_hr_server)
backend_registry.register_factory("jira", build_jira_server)
