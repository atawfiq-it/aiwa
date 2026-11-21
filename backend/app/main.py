import asyncio
import json
from asyncio.log import logger
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

import app.services.tasks.workflow_handlers  # noqa: F401
from app.api.v1.agents import router as agents_router
from app.api.v1.characters import router as characters_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.files import router as files_router
from app.api.v1.huggingface import router as hf_router
from app.api.v1.knowledge_bases import router as kb_router
from app.api.v1.media import router as media_router
from app.api.v1.models import router as models_router
from app.api.v1.openai_compat.router import router as openai_compat_router
from app.api.v1.system import router as system_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.workflows import router as workflows_router
from app.core.config import settings
from app.core.security import (
    cleanup_session_token,
    generate_session_token,
    get_active_session_token,
    verify_local_token,
)
from app.database.engine import engine, run_migrations
from app.database.models import AppSetting, ModelConfig
from app.database.seed_agents import seed_scenario_agents_if_empty
from app.database.seed_characters import seed_characters_if_empty
from app.services.models.scanner import model_scanner
from app.services.tasks.queue import task_queue
from app.supervisors.comfyui_supervisor import comfyui_supervisor
from app.supervisors.model_supervisor import ModelState, model_supervisor


async def auto_discover_and_register_models():
    """Prunes missing models, scans configured directories/subdirectories, and registers valid LLMs."""
    search_paths = [str(p) for p in settings.get_llm_search_paths()]

    with Session(engine) as db:
        record = db.get(AppSetting, "model_search_directories")
        if record and record.value:
            try:
                custom_dirs = json.loads(record.value)
                for d in custom_dirs:
                    if d not in search_paths and Path(d).exists():
                        search_paths.append(d)
            except Exception:
                pass

        # 1. Prune stale/moved rows whose paths no longer exist on disk
        pruned_count = 0
        for existing_row in db.exec(select(ModelConfig)).all():
            if not Path(existing_row.file_path).exists():
                print(f"🗑️ [PRUNE] Removing missing model path: {existing_row.file_path}")
                db.delete(existing_row)
                pruned_count += 1
        if pruned_count > 0:
            db.commit()

        # 2. Run deep recursive scan across all search paths
        print(f"🔍 [SCANNER] Effective Search Paths: {search_paths}")
        scanned = model_scanner.scan_directories(search_paths)

        newly_registered = 0
        for item in scanned:
            if item.get("category") == "llm":
                file_p = item["file_path"]
                existing = db.exec(
                    select(ModelConfig).where(ModelConfig.file_path == file_p)
                ).first()

                if not existing:
                    new_model = ModelConfig(
                        display_name=item["display_name"],
                        file_path=file_p,
                        format=item.get("format", "gguf"),
                        mmproj_path=item.get("mmproj_path"),
                        vision_supported=item.get("vision_supported", False),
                        context_length=4096,
                        gpu_layers=-1,
                        is_default=False,
                    )
                    db.add(new_model)
                    newly_registered += 1
                    print(
                        f"➕ [REGISTER] Added {item.get('format').upper()}: {item['display_name']} -> {file_p}"
                    )
                else:
                    existing.format = item.get("format", "gguf")
                    existing.vision_supported = item.get("vision_supported", False)
                    existing.display_name = item["display_name"]
                    db.add(existing)

        db.commit()

        # 3. Guarantee a valid model is marked default
        default_model = db.exec(
            select(ModelConfig).where(ModelConfig.is_default == True)  # noqa: E712
        ).first()
        if not default_model:
            first_model = db.exec(select(ModelConfig)).first()
            if first_model:
                first_model.is_default = True
                db.add(first_model)
                db.commit()

        if newly_registered > 0:
            print(f"✅ [SCANNER] Registered {newly_registered} valid LLM/VLM model(s).")


async def auto_load_default_model():
    """Automatically selects and loads the default model specified in .env or database on startup."""
    await asyncio.sleep(0.5)
    with Session(engine) as db:
        target_model = None

        # 1. Try matching DEFAULT_LLM_MODEL from .env
        if settings.DEFAULT_LLM_MODEL:
            stmt = select(ModelConfig).where(
                ModelConfig.display_name.ilike(f"%{settings.DEFAULT_LLM_MODEL}%")
                | ModelConfig.file_path.ilike(f"%{settings.DEFAULT_LLM_MODEL}%")
            )
            target_model = db.exec(stmt).first()

        # 2. Fallback to existing is_default flag
        if not target_model:
            target_model = db.exec(
                select(ModelConfig).where(ModelConfig.is_default == True)  # noqa: E712
            ).first()

        # 3. Fallback to first registered model
        if not target_model:
            target_model = db.exec(select(ModelConfig)).first()

        if target_model and model_supervisor.state == ModelState.UNLOADED:
            # Mark as default in DB
            all_models = db.exec(select(ModelConfig)).all()
            for m in all_models:
                m.is_default = m.id == target_model.id
                db.add(m)
            db.commit()

            print(f"[AIWA] Auto-loading default LLM '{target_model.display_name}'...")
            try:
                await model_supervisor.load_model(target_model)
                print(f"[AIWA] ✅ Default model '{target_model.display_name}' is Ready.")
            except Exception as e:
                print(f"[AIWA] ⚠️ Failed auto-loading default model: {e}")


def check_and_record_app_version():
    """Records application schema version into SQLite app_settings to detect breaking updates."""
    with Session(engine) as db:
        record = db.get(AppSetting, "app_schema_version")
        if not record:
            record = AppSetting(
                key="app_schema_version",
                value=settings.VERSION,
            )
            db.add(record)
            logger.info(f"💾 Initialized database schema version: {settings.VERSION}")
        else:
            if record.value != settings.VERSION:
                logger.warning(
                    f"⚠️ Application version updated from {record.value} to {settings.VERSION}. "
                    "Verifying Alembic schema integrity..."
                )
                record.value = settings.VERSION
                record.updated_at = datetime.now(UTC)
                db.add(record)
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence - Runs on boot
    run_migrations()
    check_and_record_app_version()  # Track version in SQLite database
    seed_characters_if_empty()
    seed_scenario_agents_if_empty()
    # Run fast directory scan before accepting HTTP traffic
    await auto_discover_and_register_models()
    # Keep heavy model VRAM loading asynchronous in background
    asyncio.create_task(auto_load_default_model())
    token = generate_session_token()

    task_queue.start_worker()

    # Trigger background auto-load of default model
    asyncio.create_task(auto_load_default_model())

    print(
        f"\n[AIWA] Local daemon ready. Session Token: {token[:8]}... "
        f"(written to {settings.TOKEN_FILE_PATH})\n"
    )

    yield

    # Shutdown sequence
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
app.include_router(hf_router, prefix=settings.API_V1_PREFIX)
app.include_router(openai_compat_router)
app.include_router(system_router, prefix=settings.API_V1_PREFIX)


@app.get("/api/v1/health")
async def health_check():
    """Public health-check endpoint for daemon readiness probing."""
    return {"status": "ok", "version": settings.VERSION}


@app.get("/api/v1/auth/dev-token")
async def get_development_token():
    """Allows local loopback clients to acquire the session token in development mode."""
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev-token endpoint disabled in production mode.",
        )
    return {"token": get_active_session_token()}


@app.get("/api/v1/auth/verify", dependencies=[Depends(verify_local_token)])
async def verify_auth():
    """Verifies that the provided session token header is valid."""
    return {"status": "authenticated"}


if __name__ == "__main__":
    import uvicorn

    from app.utils.port_manager import resolve_port_conflict

    resolved_port = resolve_port_conflict(
        host=settings.API_HOST,
        port=settings.API_PORT,
        service_name="AIWA API Daemon",
        interactive_cli=True,
    )
    settings.API_PORT = resolved_port

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=resolved_port,
        reload=not settings.is_production,
    )
