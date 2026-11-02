from fastapi import FastAPI

app = FastAPI(
    title="Local Multimodal AI Workstation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}