import asyncio
import os
import time

from safety import blocked_reason
from schemas import Scenario, ScenarioResult

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "2"))


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


def get_runner() -> BaseRunner:
    kind = os.getenv("RUNNER", "mock")
    if kind == "mock":
        return MockRunner()
    raise ValueError(f"Unknown RUNNER '{kind}' (tinyfish runner coming later)")


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