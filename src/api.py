"""FastAPI entry point for the script agent."""

from dotenv import load_dotenv
from fastapi import FastAPI

from src.agent import run_agent
from src.models import ScriptRequest, ScriptResponse


load_dotenv()
app = FastAPI(title="Short Video Script Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/scripts/generate", response_model=ScriptResponse)
def generate_script(request: ScriptRequest) -> ScriptResponse:
    return run_agent(request)
