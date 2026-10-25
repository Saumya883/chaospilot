import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from page_context import fetch_page_summary
from schemas import ScenarioPlan

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MAX_STEPS = int(os.getenv("MAX_STEPS_PER_SCENARIO", "25"))

PROFILE_GUIDE = {
    "impatient": (
        "The Impatient User is rushed: double-clicks buttons, clicks again when nothing seems to happen, "
        "reloads or presses Back before a page finishes. Look for duplicate actions, repeated "
        "submissions and confusing loading states."
    ),
    "confused": (
        "The Confused First-Timer misreads labels, leaves fields blank, enters data in the wrong format "
        "and tries to recover from mistakes. Look for unclear validation, misleading labels and dead ends."
    ),
    "edge_case": (
        "The Edge-Case User uses very long text, emoji, non-Latin characters, boundary values and "
        "SQL-like or HTML-like strings. Look for crashes, broken rendering and inconsistent validation."
    ),
}

SYSTEM_RULES = """You are ChaosPilot's planner, a QA engineer who tests web apps the way
imperfect real people use them, not with random clicks.

Given a URL and a goal, produce test scenarios as structured JSON. Each scenario has a
behaviour profile and a human_story: one plain-English sentence from the user's point of
view explaining why a real person would do this (no technical jargon).

Safety rules (strict):
- Only plan actions on the given URL. Never navigate to other sites.
- Never plan destructive actions such as deleting accounts or data.
- Never use real payment details; assume a staging environment with fake data.
- Keep each scenario under {max_steps} steps.
- Describe elements in plain English (e.g. 'the Pay button'), not CSS selectors.
"""


def plan_scenarios(
    url: str,
    goal: str,
    count: int = 8,
    profile: Optional[str] = None,
    retries: int = 4,
) -> ScenarioPlan:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    if profile:
        profile_text = (
            f"Behaviour profile: {profile}. {PROFILE_GUIDE[profile]}\n"
            f'Every scenario must have profile "{profile}".'
        )
    else:
        profile_text = (
            "Mix the following behaviour profiles across the scenarios:\n"
            + "\n".join(f"- {k}: {v}" for k, v in PROFILE_GUIDE.items())
            + "\nInclude at least one scenario each for emoji or non-Latin text, "
            "double-clicking the main submit button, and pressing Back after a successful submission."
        )

    page = fetch_page_summary(url)
    prompt = (
        SYSTEM_RULES.format(max_steps=MAX_STEPS)
        + f"\nTarget URL: {url}\nGoal: {goal}"
        + f"\n\n{profile_text}"
        + f"\n\nPage structure (only plan actions on elements that exist here):\n{page}"
        + f"\n\nProduce {count} distinct scenarios."
    )

    last_error = None
    for attempt in range(retries):
        try:
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
                if profile:
                    scenario.profile = profile
            return plan
        except errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                detail = getattr(e, "message", None) or str(e)
                raise RuntimeError(
                    "Gemini rejected the request because of a quota or rate limit (HTTP 429). "
                    f"Provider message: {detail[:300]} "
                    "Wait a bit and retry, or set GEMINI_MODEL in .env to a model with quota "
                    "(then restart uvicorn)."
                ) from e
            raise
        except errors.ServerError as e:  # 5xx: model busy, try again
            last_error = e
            wait = 2 ** attempt * 2
            print(f"Gemini busy (attempt {attempt + 1}/{retries}), retrying in {wait}s...")
            time.sleep(wait)
    raise last_error