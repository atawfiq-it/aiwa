from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import verify_local_token
from app.utils.port_manager import find_free_port, terminate_process

router = APIRouter(prefix="/system", tags=["System"], dependencies=[Depends(verify_local_token)])


class PortResolveRequest(BaseModel):
    port: int
    pid: int | None = None
    service_type: str = "llm"  # "llm" or "comfyui"
    action: str  # "kill", "switch", or "abort"


@router.post("/port-resolve")
def resolve_port_action(req: PortResolveRequest):
    """Executes the user's chosen resolution for an external port conflict."""
    if req.action == "abort":
        return {"status": "aborted", "message": "Operation cancelled by user."}

    if req.action == "kill":
        if not req.pid:
            raise HTTPException(status_code=400, detail="No PID available to terminate.")
        success = terminate_process(req.pid)
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Permission denied or failed closing PID {req.pid}.",
            )
        return {"status": "reclaimed", "port": req.port}

    if req.action == "switch":
        new_port = find_free_port(settings.API_HOST, req.port)
        if req.service_type == "llm":
            settings.LLAMA_SERVER_PORT = new_port
        elif req.service_type == "comfyui":
            settings.COMFYUI_PORT = new_port
            settings.COMFYUI_BASE_URL = f"http://{settings.API_HOST}:{new_port}"
        return {"status": "switched", "new_port": new_port}

    raise HTTPException(status_code=400, detail="Invalid action. Must be kill, switch, or abort.")
