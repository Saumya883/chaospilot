import asyncio
import json
import os
import re
import time

import httpx

from safety import blocked_reason
from schemas import Scenario, ScenarioResult

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "2"))
TINYFISH_RUN_URL = "https://agent.tinyfish.ai/v1/automation/run"

PROFILE_LABELS = {
    "impatient": "an impatient user in a hurry",
    "confused": "a confused first-time user",
    "edge_case": "a user who types unusual input",
}


class BaseRunner:
    source = "mock"

    async def run_scenario(self, scenario: Scenario, base_url: str) -> ScenarioResult:
        raise NotImplementedError


class MockRunner(BaseRunner):
    """Simulated runner for testing the pipeline. Results are NOT real findings."""

    source = "mock"
    FAILING = {"double_submit", "input_fuzzing", "navigation"}

    async def run_scenario(self, scenario: Scenario, base_url: str) -> ScenarioResult:
        start = time.time()
        await asyncio.sleep(0.5)
        failed = scenario.category in self.FAILING
        return ScenarioResult(
            scenario_name=scenario.name,
            category=scenario.category,
            status="failed" if failed else "passed",
            steps_executed=len(scenario.steps),
            observations=["[MOCK] simulated result, no browser was opened"],
            duration_s=round(time.time() - start, 2),
            source=self.source,
        )


def step_to_text(number: int, step) -> str:
    action = step.action.replace("_", " ")
    parts = [action]
    if step.action == "double_click":
        parts = ["double-click (two very fast clicks in a row)"]
    if step.target:
        parts.append(step.target)
    if step.value is not None and step.action != "navigate":
        parts.append(f'with the exact text "{step.value}"' if step.action == "fill" else f'"{step.value}"')
    if step.action == "navigate":
        parts.append("(the page you are already on)")
    return f"{number}. " + " ".join(parts)


def parse_result(raw) -> dict:
    """TinyFish returns the agent's answer; pull the JSON object out of it."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


class TinyFishRunner(BaseRunner):
    """Runs one scenario in a real cloud browser through TinyFish."""

    source = "tinyfish"

    def __init__(self):
        self.api_key = os.getenv("TINYFISH_API_KEY", "")
        if not self.api_key:
            raise ValueError("TINYFISH_API_KEY is not set in .env")
        self.max_steps = int(os.getenv("TINYFISH_MAX_STEPS", "40"))
        self.max_seconds = int(os.getenv("TINYFISH_MAX_SECONDS", "240"))

    def build_goal(self, scenario: Scenario) -> str:
        who = PROFILE_LABELS.get(scenario.profile, "a real user")
        steps = "\n".join(step_to_text(i + 1, s) for i, s in enumerate(scenario.steps))
        return (
            "You are testing a website whose owner has authorised testing. "
            "Stay on this site only and never visit any other site. "
            "Use only the fake data given below. Never enter real personal or payment details.\n\n"
            f"Behave like {who}. {scenario.human_story}\n\n"
            f"Do these steps in order, exactly as written:\n{steps}\n\n"
            "After the last step, stop and observe carefully. Do not try to fix or retry anything. "
            "Then reply with ONLY a JSON object with these keys:\n"
            '{"matches_expected": true or false,\n'
            ' "what_happened": "one or two sentences describing what you actually saw",\n'
            ' "error_messages": ["exact error text shown on the page, if any"],\n'
            ' "final_url": "the page URL now",\n'
            ' "page_text_after": "visible text of the page now, max 400 characters",\n'
            ' "counters_or_totals": "any counters or totals visible, for example order counts, else null"}\n\n'
            f"Correct behaviour would be: {scenario.expected_behavior}\n"
            "Set matches_expected to false if what you saw differs from that."
        )

    async def run_scenario(self, scenario: Scenario, base_url: str) -> ScenarioResult:
        start = time.time()
        payload = {
            "url": base_url,
            "goal": self.build_goal(scenario),
            "agent_config": {
            },
            "capture_config": {"screenshots": True},
        }

        def result(status, observations, steps=0):
            return ScenarioResult(
                scenario_name=scenario.name,
                category=scenario.category,
                status=status,
                steps_executed=steps,
                observations=observations,
                duration_s=round(time.time() - start, 2),
                source=self.source,
            )

        import asyncio

        resp = None
        async with httpx.AsyncClient(timeout=self.max_seconds + 60) as client:
            for attempt in range(3):
                try:
                    resp = await client.post(
                        TINYFISH_RUN_URL, json=payload, headers={"X-API-Key": self.api_key}
                    )
                except httpx.TimeoutException:
                    return result("error", ["TinyFish did not answer in time"])
                if resp.status_code < 500:
                    break
                await asyncio.sleep(3 * (attempt + 1))
        if resp.status_code >= 400:
            return result("error", [f"TinyFish returned HTTP {resp.status_code}: {resp.text[:300]}"])

        data = resp.json()
        if str(data.get("status", "")).upper() in {"FAILED", "CANCELLED"}:
            err = data.get("error") or {}
            if "usage policies" in str(err.get("message", "")).lower():
                print(f"[policy-block] {getattr(scenario, 'name', '?')}\n{payload['goal']}", flush=True)
            return result("error", [f"TinyFish run did not finish: {err.get('message', 'unknown reason')}"])

        parsed = parse_result(data.get("result", data))
        if not parsed or "matches_expected" not in parsed:
            return result("error", [f"Could not read TinyFish's answer: {str(data)[:300]}"])

        notes = [parsed.get("what_happened") or "(no description)"]
        for msg in parsed.get("error_messages") or []:
            notes.append(f"Error shown on page: {msg}")
        if parsed.get("counters_or_totals"):
            notes.append(f"Counters/totals shown: {parsed['counters_or_totals']}")
        if parsed.get("final_url"):
            notes.append(f"Final URL: {parsed['final_url']}")
        if parsed.get("page_text_after"):
            notes.append(f"Page text after: {str(parsed['page_text_after'])[:400]}")
        if data.get("run_id"):
            notes.append(f"TinyFish run id: {data['run_id']}")

        status = "passed" if parsed.get("matches_expected") is True else "failed"
        return result(status, notes, steps=len(scenario.steps))


def get_runner() -> BaseRunner:
    kind = os.getenv("RUNNER", "mock")
    if kind == "mock":
        return MockRunner()
    if kind == "tinyfish":
        return TinyFishRunner()
    raise ValueError(f"Unknown RUNNER '{kind}' (use 'mock' or 'tinyfish')")


async def run_all(scenarios: list[Scenario], base_url: str, runner: BaseRunner) -> list[ScenarioResult]:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def one(s: Scenario) -> ScenarioResult:
        reason = blocked_reason(s, base_url)
        if reason:
            return ScenarioResult(
                scenario_name=s.name, category=s.category, status="blocked",
                observations=[reason], source=runner.source,
            )
        async with sem:
            try:
                return await runner.run_scenario(s, base_url)
            except Exception as e:
                return ScenarioResult(
                    scenario_name=s.name, category=s.category, status="error",
                    observations=[f"Runner error: {e}"], source=runner.source,
                )

    return list(await asyncio.gather(*(one(s) for s in scenarios)))