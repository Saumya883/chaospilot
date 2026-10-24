from typing import Literal, Optional
from pydantic import BaseModel, Field

ActionType = Literal[
    "navigate", "fill", "click", "double_click",
    "press_key", "go_back", "reload", "wait",
]

Category = Literal[
    "input_fuzzing", "double_submit", "navigation",
    "boundary_values", "rapid_interaction", "empty_input",
]

Profile = Literal["impatient", "confused", "edge_case"]


class Step(BaseModel):
    action: ActionType
    target: Optional[str] = Field(
        default=None, description="Plain-English description of the element, e.g. 'the Pay button'"
    )
    value: Optional[str] = Field(
        default=None, description="Text to type or key to press, if the action needs one"
    )


class Scenario(BaseModel):
    name: str
    category: Category
    profile: Profile
    human_story: str = Field(
        description="One plain-English sentence from the user's point of view: why a real person would do this"
    )
    description: str = Field(description="What this scenario tries to break and why")
    steps: list[Step]
    expected_behavior: str = Field(description="What a correct app should do")
    severity_guess: Literal["low", "medium", "high", "critical"]


class ScenarioPlan(BaseModel):
    scenarios: list[Scenario]


class ScenarioResult(BaseModel):
    scenario_name: str
    category: str
    status: Literal["passed", "failed", "error", "blocked"]
    steps_executed: int = 0
    observations: list[str] = []
    screenshot_path: Optional[str] = None
    duration_s: float = 0.0
    source: Literal["mock", "tinyfish"]


class Bug(BaseModel):
    title: str
    category: str
    profile: Profile
    human_story: str
    severity: Literal["low", "medium", "high", "critical"]
    confirmed: bool
    fail_count: int
    run_count: int
    reproduction_steps: list[str]
    expected_behavior: str
    observations: list[str] = []
    screenshot_path: Optional[str] = None
    source: Literal["mock", "tinyfish"]


class RunReport(BaseModel):
    url: str
    goal: str
    results: list[ScenarioResult]
    bugs: list[Bug] = []
    flaky_scenarios: list[str] = []