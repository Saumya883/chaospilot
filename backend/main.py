import asyncio
from leak_checks import Finding, passive_scan
from safety import host_allowed

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from detector import confirm_and_triage
from planner import plan_scenarios
from runner import get_runner, run_all
from schemas import RunReport, ScenarioPlan
from typing import Optional
from schemas import Profile, RunReport, ScenarioPlan

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
    profile: Optional[Profile] = None


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


@app.post("/run", response_model=RunReport)
async def run(req: PlanRequest):
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        scenario_plan = await asyncio.to_thread(plan_scenarios, req.url, req.goal, req.count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")

    runner = get_runner()
    results = await run_all(scenario_plan.scenarios, req.url, runner)
    bugs, flaky = await confirm_and_triage(scenario_plan.scenarios, results, req.url, runner)
    return RunReport(
        url=req.url, goal=req.goal, results=results, bugs=bugs, flaky_scenarios=flaky
    )