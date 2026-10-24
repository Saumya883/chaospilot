import asyncio
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # must run before the local imports below
from detector import confirm_and_triage
from leak_checks import Finding, passive_scan
from planner import plan_scenarios
from report import render_html, render_markdown
from runner import get_runner, run_all
from safety import host_allowed
from schemas import Profile, RunReport, ScenarioPlan

app = FastAPI(title="ChaosPilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    url: str
    goal: str
    count: int = Field(default=5, ge=1, le=15)
    profile: Optional[Profile] = None


class ScanRequest(BaseModel):
    url: str


def check_url(url: str) -> None:
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")


async def execute_run(req: PlanRequest) -> RunReport:
    """Plan scenarios, run them, confirm failures, and return the structured report."""
    check_url(req.url)
    try:
        scenario_plan = await asyncio.to_thread(
            plan_scenarios, req.url, req.goal, req.count, req.profile
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")

    try:
        runner = get_runner()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    results = await run_all(scenario_plan.scenarios, req.url, runner)
    bugs, flaky = await confirm_and_triage(scenario_plan.scenarios, results, req.url, runner)
    return RunReport(
        url=req.url, goal=req.goal, results=results, bugs=bugs, flaky_scenarios=flaky
    )

@app.get("/health")
def health():
    return {"status": "ok", "runner": os.getenv("RUNNER", "mock")}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).parent / "ui.html")


@app.post("/plan", response_model=ScenarioPlan)
def plan(req: PlanRequest):
    check_url(req.url)
    try:
        return plan_scenarios(req.url, req.goal, req.count, req.profile)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")


@app.post("/run", response_model=RunReport)
async def run(req: PlanRequest):
    return await execute_run(req)


@app.post("/report")
async def report(req: PlanRequest, fmt: str = Query("html", alias="format")):
    """Same as /run, but returns a human-readable report (HTML by default, or format=markdown)."""
    run_report = await execute_run(req)
    extra: list[Finding] = []
    if host_allowed(req.url):
        try:
            extra = await asyncio.to_thread(passive_scan, req.url)
        except Exception:
            extra = []
    md_text = render_markdown(run_report, extra)
    if fmt == "markdown":
        return PlainTextResponse(md_text)
    return HTMLResponse(render_html(md_text))


@app.post("/scan", response_model=list[Finding])
def scan(req: ScanRequest):
    check_url(req.url)
    if not host_allowed(req.url):
        raise HTTPException(status_code=403, detail="Host not in ALLOWED_HOSTS")
    try:
        return passive_scan(req.url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scan failed: {e}")