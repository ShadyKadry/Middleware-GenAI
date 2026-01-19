import os
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

@dataclass
class McpProcess:
    proc: asyncio.subprocess.Process

    @classmethod
    async def start(cls, username: str, role: str) -> "McpProcess":
        # initializes the middleware server with the correct user/role
        components_dir = Path(__file__).resolve().parent.parent.parent
        middleware_script = components_dir / "middleware" / "src" / "middleware_application.py"
        if not middleware_script.exists():
            raise RuntimeError(f"Middleware entry not found at: {middleware_script}")

        env = os.environ.copy()

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(middleware_script),
            "--user", username,
            "--role", role,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        return cls(proc=proc)

    async def stop(self) -> None:
        if self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                self.proc.kill()
