import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from schemas import ScenarioPlan

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_STEPS = int(os.getenv("MAX_STEPS_PER_SCENARIO", "25"))

SYSTEM_RULES = """You are ChaosPilot's planner, a QA engineer who tries to break web apps
the way unpredictable real users do.

Given a URL and a goal, produce chaos test scenarios as structured JSON.

Cover a mix of: weird inputs (emoji, very long text, SQL-like strings such as ' OR 1=1 --,
HTML/script tags, unicode), empty fields, double-clicking submit buttons, rapid repeated
clicks, pressing Back or Reload mid-flow, and boundary values.

Safety rules (strict):
- Only plan actions on the given URL. Never navigate to other sites.
- Never plan destructive actions such as deleting accounts or data.
- Never use real payment details; assume a staging environment with fake data.
- Keep each scenario under {max_steps} steps.
- Describe elements in plain English (e.g. 'the Pay button'), not CSS selectors.
"""


def plan_scenarios(url: str, goal: str, count: int = 8) -> ScenarioPlan:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = (
        SYSTEM_RULES.format(max_steps=MAX_STEPS)
        + f"\nTarget URL: {url}\nGoal: {goal}\nProduce {count} distinct scenarios."
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ScenarioPlan,
            "temperature": 0.8,
        },
    )
    plan = ScenarioPlan.model_validate_json(response.text)
    for scenario in plan.scenarios:
        scenario.steps = scenario.steps[:MAX_STEPS]
    return plan