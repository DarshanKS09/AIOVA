from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agent import invoke_agent
from backend.database import init_db


class AgentInvokeRequest(BaseModel):
    action: str
    user_input: Optional[str] = None
    form_data: Optional[dict[str, Any]] = None
    current_state: Optional[dict[str, Any]] = None
    matched_entry_id: Optional[int] = None


app = FastAPI(title="AIOVA CRM Agent API")
frontend_origin = "http://localhost:5173"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/invoke")
def agent_invoke(request: AgentInvokeRequest) -> dict[str, Any]:
    try:
        return invoke_agent(request.model_dump())
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Agent invocation failed: {exc}") from exc
