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
    description: str = Field(description="What this scenario tries to break and why")
    steps: list[Step]
    expected_behavior: str = Field(description="What a correct app should do")
    severity_guess: Literal["low", "medium", "high", "critical"]


class ScenarioPlan(BaseModel):
    scenarios: list[Scenario]