from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.files import router as files_router
from app.api.v1.knowledge_bases import router as kb_router
from app.api.v1.media import router as media_router
from app.api.v1.models import router as models_router
from app.api.v1.tasks import router as tasks_router
from app.core.config import settings
from app.core.security import cleanup_session_token, generate_session_token, verify_local_token
from app.database.engine import run_migrations
from app.services.tasks.queue import task_queue
from app.supervisors.model_supervisor import model_supervisor


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    token = generate_session_token()
    task_queue.start_worker()
    print(
        f"\n[AIWA] Local daemon ready. Session Token: {token[:8]}... "
        f"(written to {settings.TOKEN_FILE_PATH})\n"
    )
    yield
    await task_queue.stop_worker()
    await model_supervisor.unload_model()
    cleanup_session_token()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Mount Routers
app.include_router(models_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(files_router, prefix=settings.API_V1_PREFIX)
app.include_router(conversations_router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks_router, prefix=settings.API_V1_PREFIX)
app.include_router(media_router, prefix=settings.API_V1_PREFIX)
app.include_router(kb_router, prefix=settings.API_V1_PREFIX)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/api/v1/auth/verify", dependencies=[Depends(verify_local_token)])
async def verify_auth():
    return {"status": "authenticated"}
