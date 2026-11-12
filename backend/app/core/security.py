import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException, Query, status

from app.core.config import settings

ACTIVE_SESSION_TOKEN: str | None = None


def generate_session_token() -> str:
    """Generate ephemeral token and persist it for Tauri IPC handshake."""
    global ACTIVE_SESSION_TOKEN
    token = secrets.token_hex(32)
    ACTIVE_SESSION_TOKEN = token

    token_path = settings.TOKEN_FILE_PATH
    # Write token file with restricted read/write permissions (owner only: 0600)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode = 0o600
    fd = os.open(token_path, flags, mode)
    with os.fdopen(fd, "w") as f:
        f.write(token)

    return token


def get_active_session_token() -> str | None:
    """Returns the current in-memory token or reads from runtime token file."""
    global ACTIVE_SESSION_TOKEN
    if ACTIVE_SESSION_TOKEN:
        return ACTIVE_SESSION_TOKEN

    token_path = settings.TOKEN_FILE_PATH
    if token_path.exists():
        try:
            return token_path.read_text().strip()
        except OSError:
            pass
    return None


def cleanup_session_token() -> None:
    """Remove session token on application shutdown."""
    global ACTIVE_SESSION_TOKEN
    ACTIVE_SESSION_TOKEN = None
    if settings.TOKEN_FILE_PATH.exists():
        try:
            settings.TOKEN_FILE_PATH.unlink()
        except OSError:
            pass


async def verify_local_token(
    x_aiwa_token: str | None = Header(default=None, alias="X-AIWA-Token"),
    token: str | None = Query(default=None),
) -> None:
    """FastAPI dependency allowing authorization via X-AIWA-Token header OR ?token= query parameter."""
    if not settings.AUTH_ENABLED:
        return

    provided = x_aiwa_token or token
    active_token = get_active_session_token()

    if not provided or not active_token or not secrets.compare_digest(provided, active_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing local authorization token",
        )


def validate_safe_path(target_path: Path, allowed_parent: Path) -> Path:
    """Guarantees target path is strictly within the allowed parent directory."""
    resolved_target = target_path.resolve()
    resolved_parent = allowed_parent.resolve()
    try:
        resolved_target.relative_to(resolved_parent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Path traversal detected outside allowed directory.",
        ) from e
    return resolved_target
