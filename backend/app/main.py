import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

import app.services.tasks.workflow_handlers  # noqa: F401
from app.api.v1.agents import router as agents_router
from app.api.v1.characters import router as characters_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.files import router as files_router
from app.api.v1.knowledge_bases import router as kb_router
from app.api.v1.media import router as media_router
from app.api.v1.models import router as models_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.workflows import router as workflows_router
from app.core.config import settings
from app.core.security import cleanup_session_token, generate_session_token, verify_local_token
from app.database.engine import engine, run_migrations
from app.database.models import ModelConfig
from app.database.seed_characters import seed_characters_if_empty
from app.services.tasks.queue import task_queue
from app.supervisors import comfyui_supervisor
from app.supervisors.model_supervisor import ModelState, model_supervisor


async def auto_load_default_model():
    """Automatically loads default registered model on startup if present."""
    await asyncio.sleep(0.5)  # Let migrations complete
    with Session(engine) as db:
        default_model = db.exec(
            select(ModelConfig).where(ModelConfig.is_default == True)  # noqa: E712
        ).first()
        if default_model and model_supervisor.state == ModelState.UNLOADED:
            print(f"[AIWA] Auto-loading default model '{default_model.display_name}'...")
            try:
                await model_supervisor.load_model(default_model)
                print(f"[AIWA] ✅ Default model '{default_model.display_name}' is Ready.")
            except Exception as e:
                print(f"[AIWA] ⚠️ Failed auto-loading default model: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    seed_characters_if_empty()  # Add this line
    token = generate_session_token()
    task_queue.start_worker()

    # Trigger background auto-load of default model
    asyncio.create_task(auto_load_default_model())

    print(
        f"\n[AIWA] Local daemon ready. Session Token: {token[:8]}... "
        f"(written to {settings.TOKEN_FILE_PATH})\n"
    )

    # lifespan shutdown
    yield
    await task_queue.stop_worker()
    await model_supervisor.unload_model()
    await comfyui_supervisor.stop()

    cleanup_session_token()


docs_url = None if settings.is_production else "/docs"
redoc_url = None if settings.is_production else "/redoc"
openapi_url = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
    lifespan=lifespan,
)

# Enable CORS for desktop web clients and Tauri native windows
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount Routers
app.include_router(models_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(files_router, prefix=settings.API_V1_PREFIX)
app.include_router(conversations_router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks_router, prefix=settings.API_V1_PREFIX)
app.include_router(media_router, prefix=settings.API_V1_PREFIX)
app.include_router(kb_router, prefix=settings.API_V1_PREFIX)
app.include_router(agents_router, prefix=settings.API_V1_PREFIX)
app.include_router(workflows_router, prefix=settings.API_V1_PREFIX)
app.include_router(characters_router, prefix=settings.API_V1_PREFIX)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/api/v1/auth/verify", dependencies=[Depends(verify_local_token)])
async def verify_auth():
    return {"status": "authenticated"}
