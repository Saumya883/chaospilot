from planner import plan_scenarios

plan = plan_scenarios("http://localhost:8080", "Try to break checkout", count=5)
print(plan.model_dump_json(indent=2))