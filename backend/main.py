from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from planner import plan_scenarios
from schemas import ScenarioPlan
import asyncio
from runner import get_runner, run_all
@app.post("/run", response_model=RunReport)
async def run(req: PlanRequest):
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        plan = await asyncio.to_thread(plan_scenarios, req.url, req.goal, req.count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")
    results = await run_all(plan.scenarios, req.url, get_runner())
    return RunReport(url=req.url, goal=req.goal, results=results)

app = FastAPI(title="ChaosPilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    url: str
    goal: str
    count: int = Field(default=5, ge=1, le=15)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/plan", response_model=ScenarioPlan)
def plan(req: PlanRequest):
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        return plan_scenarios(req.url, req.goal, req.count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")