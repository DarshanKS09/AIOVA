import logging
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import invoke_agent
from .database import init_db

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environment configuration
ENV = os.getenv("ENV", "development")
DEBUG = ENV == "development"

# CORS configuration based on environment
if ENV == "production":
    ALLOWED_ORIGINS = [
        os.getenv("FRONTEND_URL", "https://yourdomain.vercel.app"),
    ]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]


class AgentInvokeRequest(BaseModel):
    action: str
    user_input: Optional[str] = None
    form_data: Optional[dict[str, Any]] = None
    current_state: Optional[dict[str, Any]] = None
    matched_entry_id: Optional[str | int] = None


app = FastAPI(
    title="AIOVA CRM Agent API",
    version="1.0.0",
    description="AI-powered CRM interaction logging system",
    debug=DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
def startup_event() -> None:
    try:
        init_db()
        logger.info("✅ MongoDB initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MongoDB: {e}")
        raise


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/invoke")
def agent_invoke(request: AgentInvokeRequest) -> dict[str, Any]:
    try:
        return invoke_agent(request.model_dump())
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Agent invocation failed: {exc}") from exc
