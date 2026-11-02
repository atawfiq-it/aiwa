from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.core.config import settings
from app.core.security import cleanup_session_token, generate_session_token, verify_local_token
from app.database.engine import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run migrations & issue ephemeral local session token
    run_migrations()
    token = generate_session_token()
    print(
        f"\n[AIWA] Local daemon ready. Session Token: {token[:8]}... "
        f"(written to {settings.TOKEN_FILE_PATH})\n"
    )
    yield
    # Shutdown: Cleanup token
    cleanup_session_token()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.get("/api/v1/health")
async def health_check():
    """Public health check - does not require auth."""
    return {"status": "ok", "version": settings.VERSION}


@app.get("/api/v1/auth/verify", dependencies=[Depends(verify_local_token)])
async def verify_auth():
    """Sample protected endpoint to verify token validation."""
    return {"status": "authenticated"}
