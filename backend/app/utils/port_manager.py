import logging
import socket
import subprocess
import sys
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# Signatures identifying processes owned by AIWA
AIWA_PROCESS_SIGNATURES = [
    "llama-server",
    "mlx_worker.py",
    "mlx_lm.server",
    "mlx_vlm.server",
    "aiwa-backend",
    "app.main",
    "services/comfyui",
    "comfyui",
]


class PortConflictError(Exception):
    def __init__(self, port: int, service_name: str, owner: dict[str, Any]):
        self.port = port
        self.service_name = service_name
        self.owner = owner
        super().__init__(
            f"Port {port} required by {service_name} is occupied by "
            f"'{owner.get('name')}' (PID {owner.get('pid')})."
        )


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_free_port(host: str, start_port: int = 8000, max_tries: int = 100) -> int:
    for p in range(start_port + 1, start_port + max_tries):
        if not is_port_in_use(host, p):
            return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def get_port_owner(port: int) -> dict[str, Any] | None:
    """Identifies the PID, name, and command line holding a listening TCP port."""
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    cmdline = " ".join(proc.cmdline())
                    name = proc.name()
                    is_orphan = any(
                        sig in cmdline.lower() or sig in name.lower()
                        for sig in AIWA_PROCESS_SIGNATURES
                    )
                    return {
                        "pid": conn.pid,
                        "name": name,
                        "cmdline": cmdline or name,
                        "is_aiwa_orphan": is_orphan,
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return {
                        "pid": conn.pid,
                        "name": "Protected Process",
                        "cmdline": "",
                        "is_aiwa_orphan": False,
                    }
    except psutil.AccessDenied:
        # Fallback on macOS without root: use lsof
        if sys.platform in ("darwin", "linux"):
            try:
                pid_out = (
                    subprocess.check_output(
                        ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
                        stderr=subprocess.DEVNULL,
                    )
                    .decode()
                    .strip()
                )
                if pid_out:
                    pid = int(pid_out.splitlines()[0])
                    cmd_out = (
                        subprocess.check_output(
                            ["ps", "-p", str(pid), "-o", "command="],
                            stderr=subprocess.DEVNULL,
                        )
                        .decode()
                        .strip()
                    )
                    name = cmd_out.split()[0].split("/")[-1] if cmd_out else "Unknown"
                    is_orphan = any(sig in cmd_out.lower() for sig in AIWA_PROCESS_SIGNATURES)
                    return {
                        "pid": pid,
                        "name": name,
                        "cmdline": cmd_out,
                        "is_aiwa_orphan": is_orphan,
                    }
            except Exception:
                pass
    return None


def terminate_process(pid: int) -> bool:
    """Gracefully terminates a process by PID, escalating to kill if necessary."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.error(f"Failed terminating PID {pid}: {e}")
        return False


def resolve_port_conflict(
    host: str,
    port: int,
    service_name: str,
    interactive_cli: bool = False,
) -> int:
    """
    Checks port availability:
    - If free -> returns port.
    - If held by an orphaned AIWA process -> auto-reclaims it and returns port.
    - If held by another process -> prompts user (CLI) or raises PortConflictError (for UI modal).
    """
    if not is_port_in_use(host, port):
        return port

    owner = get_port_owner(port)
    if not owner:
        # Port might be in TIME_WAIT or protected; wait briefly
        time.sleep(0.5)
        if not is_port_in_use(host, port):
            return port
        owner = {"pid": None, "name": "Unknown Process", "cmdline": "", "is_aiwa_orphan": False}

    # 1. Auto-reclaim orphaned AIWA processes
    if owner.get("is_aiwa_orphan") and owner.get("pid"):
        logger.warning(
            f"🧹 Port {port} held by orphaned AIWA process "
            f"(PID {owner['pid']}: {owner['name']}). Auto-reclaiming..."
        )
        if terminate_process(owner["pid"]):
            for _ in range(10):
                if not is_port_in_use(host, port):
                    logger.info(f"✅ Port {port} successfully reclaimed for {service_name}.")
                    return port
                time.sleep(0.3)

    # 2. External process conflict
    if interactive_cli and sys.stdin.isatty():
        print("\n" + "!" * 65)
        print(f"⚠️  PORT CONFLICT: {service_name} requires port {port}, which is in use by:")
        print(f"    PID:     {owner.get('pid')}")
        print(f"    Process: {owner.get('name')}")
        print(f"    Command: {owner.get('cmdline')[:80]}")
        print("-" * 65)
        print("How would you like to proceed?")
        print(f"  [1] Close '{owner.get('name')}' (PID {owner.get('pid')}) and reclaim port {port}")
        print("  [2] Switch automatically to a free port")
        print("  [3] Terminate startup")
        print("!" * 65)

        choice = input("Enter your choice (1/2/3): ").strip()

        if choice == "1" and owner.get("pid"):
            if terminate_process(owner["pid"]):
                time.sleep(0.5)
                if not is_port_in_use(host, port):
                    print(f"✅ Reclaimed port {port}.")
                    return port
            print(f"❌ Could not reclaim port {port}. Exiting.")
            sys.exit(1)
        elif choice == "2":
            free_p = find_free_port(host, port)
            print(f"🔀 Switching {service_name} to free port: {free_p}")
            return free_p
        else:
            print("🛑 Terminated by user.")
            sys.exit(0)

    # Non-interactive / UI runtime: raise structured conflict so frontend modal asks the user
    raise PortConflictError(port=port, service_name=service_name, owner=owner)
