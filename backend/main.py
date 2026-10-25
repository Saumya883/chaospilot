"""ChaosPilot API.

POST /report  -> plan, run, confirm and return a human-readable report (used by the front page)
POST /run     -> same, but as structured JSON
POST /plan    -> only the planned scenarios
POST /scan    -> passive information-leak checks on one page
GET  /        -> the front page
"""
import asyncio
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

# Load .env BEFORE importing our own modules, so settings are available to all of them.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from detector import confirm_and_triage  # noqa: E402
from leak_checks import Finding, passive_scan  # noqa: E402
from planner import plan_scenarios  # noqa: E402
from report import render_html, render_markdown  # noqa: E402
from runner import get_runner, run_all  # noqa: E402
from safety import host_allowed  # noqa: E402
from schemas import Profile, RunReport, ScenarioPlan, ScenarioResult  # noqa: E402

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


def blocked_report(req: PlanRequest) -> RunReport:
    """Report for a site that is not on the allow-list. Nothing is contacted or planned."""
    source = "tinyfish" if os.getenv("RUNNER", "mock") == "tinyfish" else "mock"
    return RunReport(
        url=req.url,
        goal=req.goal,
        results=[ScenarioResult(
            scenario_name="No scenarios were planned",
            category="none",
            status="blocked",
            observations=[
                f"Host not in ALLOWED_HOSTS: {req.url}. ChaosPilot did not contact the site, "
                "did not call the planner and did not run anything."
            ],
            source=source,
        )],
    )


async def execute_run(req: PlanRequest) -> RunReport:
    """Safety check first, then plan scenarios, run them, confirm failures, and return the report."""
    check_url(req.url)
    if not host_allowed(req.url):
        return blocked_report(req)

    t0 = time.time()
    try:
        scenario_plan = await asyncio.to_thread(
            plan_scenarios, req.url, req.goal, req.count, req.profile
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")
    print(f"[timing] planned in {time.time() - t0:.1f}s")

    try:
        runner = get_runner()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    results = await run_all(scenario_plan.scenarios, req.url, runner)
    print(f"[timing] ran in {time.time() - t0:.1f}s")
    bugs, flaky = await confirm_and_triage(scenario_plan.scenarios, results, req.url, runner)
    print(f"[timing] confirmed in {time.time() - t0:.1f}s")
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
    if not host_allowed(req.url):
        raise HTTPException(status_code=403, detail="Host not in ALLOWED_HOSTS")
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
    allowed = req.url.startswith(("http://", "https://")) and host_allowed(req.url)
    scan_task = asyncio.create_task(asyncio.to_thread(passive_scan, req.url)) if allowed else None
    run_report = await execute_run(req)
    extra: list[Finding] = []
    if scan_task is not None:
        try:
            extra = await scan_task
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