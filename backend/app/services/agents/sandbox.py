import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PythonSandbox:
    def __init__(self, timeout_seconds: int = 10, max_memory_mb: int = 512):
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb

    def _set_limits(self) -> None:
        """Applies OS resource restrictions before executing the child process (Linux/Unix)."""
        try:
            import resource

            # Memory limit (RLIMIT_AS) in bytes
            mem_bytes = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            # CPU time limit in seconds
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (self.timeout_seconds, self.timeout_seconds + 2),
            )
        except (ImportError, ValueError, OSError) as e:
            logger.warning(f"Could not apply OS resource limits: {e}")

    def execute(self, code: str) -> dict[str, Any]:
        """Runs arbitrary python code in an isolated temporary working directory."""
        temp_dir = tempfile.mkdtemp(prefix="aiwa_sandbox_")
        script_path = Path(temp_dir) / "script.py"

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Restrict permissions
            os.chmod(script_path, 0o600)

            # Run in isolated environment without inheriting parent env
            clean_env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "PYTHONHASHSEED": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            process = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=temp_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                preexec_fn=self._set_limits if os.name == "posix" else None,
            )

            return {
                "status": "success" if process.returncode == 0 else "error",
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "returncode": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds.",
            }
        except Exception as e:
            return {
                "status": "error",
                "returncode": -1,
                "stdout": "",
                "stderr": f"Sandbox execution failed: {e}",
            }
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


python_sandbox = PythonSandbox()
