import os

from runner import BaseRunner
from schemas import Bug, Scenario, ScenarioResult, Step

RERUNS = int(os.getenv("CONFIRM_RERUNS", "2"))
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def describe_step(number: int, step: Step) -> str:
    parts = [step.action.replace("_", " ")]
    if step.target:
        parts.append(step.target)
    if step.value:
        parts.append(f'"{step.value}"')
    return f"{number}. " + " ".join(parts)


async def confirm_and_triage(
    scenarios: list[Scenario],
    results: list[ScenarioResult],
    base_url: str,
    runner: BaseRunner,
) -> tuple[list[Bug], list[str]]:
    """Re-run each failed scenario. A failure counts as a bug only if most runs fail."""
    by_name = {s.name: s for s in scenarios}
    bugs: list[Bug] = []
    flaky: list[str] = []

    for res in results:
        if res.status != "failed":
            continue
        scenario = by_name[res.scenario_name]
        fails, total = 1, 1
        for _ in range(RERUNS):
            total += 1
            try:
                rerun = await runner.run_scenario(scenario, base_url)
            except Exception:
                continue
            if rerun.status == "failed":
                fails += 1

        if fails * 2 <= total:  # not failing most of the time -> flaky, don't report
            flaky.append(scenario.name)
            continue

        bugs.append(
            Bug(
                title=scenario.name,
                category=scenario.category,
                severity=scenario.severity_guess,
                confirmed=True,
                fail_count=fails,
                run_count=total,
                reproduction_steps=[describe_step(i + 1, st) for i, st in enumerate(scenario.steps)],
                expected_behavior=scenario.expected_behavior,
                observations=res.observations,
                screenshot_path=res.screenshot_path,
                source=res.source,
            )
        )

    bugs.sort(key=lambda b: SEVERITY_ORDER[b.severity])
    return bugs, flaky