"""Turns a RunReport into a report a non-programmer can follow (Markdown or HTML)."""
import re
from datetime import datetime
from typing import Optional

import markdown

from leak_checks import Finding, check_url_for_sensitive_params, scan_text_for_leaks
from schemas import Bug, RunReport

PROFILE_LABELS = {
    "impatient": "Impatient user",
    "confused": "Confused first-timer",
    "edge_case": "Edge-case user",
}

IMPACT_SENTENCES = {
    "double_submit": "A customer could be charged or ordered twice for one action.",
    "navigation": "A customer could lose their progress or land on a broken page.",
    "input_fuzzing": "Unusual text could break the page or expose internal details.",
    "empty_input": "A customer could submit incomplete information and the app accepts it.",
    "boundary_values": "Extreme values could produce wrong totals or errors.",
    "rapid_interaction": "Fast repeated actions could leave the app in an inconsistent state.",
}

# Transparent rule-based impact: severity points + category points (max 6).
SEVERITY_POINTS = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CATEGORY_POINTS = {
    "double_submit": 2, "navigation": 1, "input_fuzzing": 1,
    "empty_input": 0, "boundary_values": 1, "rapid_interaction": 1,
}


def impact_for(bug: Bug) -> tuple[int, str, str]:
    score = SEVERITY_POINTS[bug.severity] + CATEGORY_POINTS.get(bug.category, 0)
    if score >= 5:
        label = "Severe"
    elif score >= 4:
        label = "High"
    elif score >= 3:
        label = "Moderate"
    else:
        label = "Minor"
    sentence = IMPACT_SENTENCES.get(bug.category, "A customer's experience could be disrupted.")
    return score, label, sentence


def clean_step(step: str) -> str:
    return re.sub(r"^\d+\.\s*", "", step)


def render_markdown(report: RunReport, extra_findings: Optional[list[Finding]] = None) -> str:
    results = report.results
    passed = [r for r in results if r.status == "passed"]
    blocked = [r for r in results if r.status == "blocked"]
    errored = [r for r in results if r.status == "error"]
    simulated = any(r.source == "mock" for r in results)

    lines: list[str] = []
    add = lines.append

    add("# ChaosPilot test report")
    add("")
    add(f"**Site tested:** {report.url}  ")
    add(f"**Goal:** {report.goal}  ")
    add(f"**Generated:** {datetime.now().strftime('%d %b %Y, %H:%M')}")
    add("")

    if simulated:
        add("> **SIMULATED RUN.** These results came from ChaosPilot's mock runner. "
            "No real browser was opened, so nothing below is a real finding.")
        add("")

    # ---- Summary ----
    add("## Summary")
    add("")
    add(f"ChaosPilot tried **{len(results)}** scenarios, acting like imperfect real users.")
    add("")
    add(f"- Passed: **{len(passed)}**")
    add(f"- Confirmed bugs: **{len(report.bugs)}** (failed, then failed again when re-run)")
    add(f"- Not confirmed (flaky): **{len(report.flaky_scenarios)}**")
    add(f"- Blocked by safety rules: **{len(blocked)}**")
    add(f"- Errors while running: **{len(errored)}**")
    add("")
    if not simulated:
        if results and len(blocked) == len(results):
            add(f"**Verdict:** nothing was tested. All {len(blocked)} scenario(s) were blocked by "
                "safety rules, so this report says nothing about the site. "
                "See “Blocked by safety rules” below.")
        elif results and len(blocked) + len(errored) == len(results):
            add("**Verdict:** nothing was completed. Every scenario was either blocked by safety "
                "rules or hit an error, so this report says nothing about the site yet.")
        elif results and len(errored) == len(results):
            add("**Verdict:** none of the scenarios could be completed, so this report says "
                "nothing about the site yet. See “Scenarios that could not run” below.")
        elif report.bugs:
            add(f"**Verdict:** {len(report.bugs)} confirmed bug(s) need attention. "
                f"Worst severity: {report.bugs[0].severity}.")
        else:
            skipped = len(blocked) + len(errored)
            note = (f" {skipped} scenario(s) did not run (blocked or errored), "
                    "so coverage is incomplete.") if skipped else ""
            add("**Verdict:** no confirmed bugs in the scenarios that ran." + note)
        add("")

    # ---- Bugs ----
    add("## Confirmed bugs")
    add("")
    if not report.bugs:
        add("None.")
        add("")
    for i, bug in enumerate(report.bugs, start=1):
        score, label, sentence = impact_for(bug)
        add(f"### {i}. {bug.title}")
        add("")
        add(f"**Severity:** {bug.severity.title()} · **Human impact:** {label} ({score}/6) · "
            f"**Found by:** {PROFILE_LABELS.get(bug.profile, bug.profile)}")
        add("")
        add(f"> {bug.human_story}")
        add("")
        add("**What went wrong**")
        add("")
        for obs in bug.observations or ["(no observation recorded)"]:
            add(f"- {obs}")
        add("")
        add(f"**What should happen:** {bug.expected_behavior}")
        add("")
        add(f"**Why it matters:** {sentence}")
        add("")
        add("**How to reproduce**")
        add("")
        for n, step in enumerate(bug.reproduction_steps, start=1):
            add(f"{n}. {clean_step(step)}")
        add("")
        add(f"**Confidence:** it failed in {bug.fail_count} of {bug.run_count} runs.")
        if bug.screenshot_path:
            add(f"  \n**Evidence:** screenshot `{bug.screenshot_path}`")
        add("")

    # ---- Security observations ----
    findings: list[tuple[str, Finding]] = []
    for r in results:
        for text in r.observations:
            for f in scan_text_for_leaks(text):
                findings.append((f"seen in scenario “{r.scenario_name}”", f))
            if text.startswith("Final URL: "):
                for f in check_url_for_sensitive_params(text[len("Final URL: "):]):
                    findings.append((f"seen in scenario “{r.scenario_name}”", f))
    add("## Security observations")
    add("")
    if not findings:
        add("Nothing of concern was observed.")
    for where, f in findings:
        add(f"- **{f.title}** ({f.severity}, {where}). Evidence: {f.evidence} "
            f"Why it matters: {f.why_it_matters}")
    add("")
    add("_ChaosPilot only reports what it observed in the browser. It cannot see how a site "
        "stores data on its servers._")
    add("")
    if errored:
        add("## Scenarios that could not run")
        add("")
        for r in errored:
            add(f"- **{r.scenario_name}:** {'; '.join(r.observations)}")
        add("")
    # ---- Other outcomes ----
    if report.flaky_scenarios:
        add("## Not reported (could not be confirmed)")
        add("")
        add("These failed once but passed when re-run, so they are not counted as bugs:")
        add("")
        for name in report.flaky_scenarios:
            add(f"- {name}")
        add("")
    if blocked:
        add("## Blocked by safety rules")
        add("")
        for r in blocked:
            add(f"- {r.scenario_name}: {'; '.join(r.observations)}")
        add("")
    if passed:
        add("## What held up")
        add("")
        for r in passed:
            add(f"- {r.scenario_name}")
        add("")

    # ---- How to read ----
    add("---")
    add("")
    add("**How to read this report.** *Confirmed* means the scenario failed and then failed again "
        "when re-run. *Human impact* is a simple rule-based estimate (severity plus the kind of "
        "problem), not a measurement. *Found by* is the type of user behaviour that triggered it.")
    return "\n".join(lines)


HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChaosPilot report</title>
<style>
body { font-family: system-ui, sans-serif; background: #f5f5f7; color: #1d1d1f; margin: 0; }
main { max-width: 760px; margin: 32px auto; background: #fff; padding: 32px; border-radius: 12px; line-height: 1.55; }
h1 { margin-top: 0; }
h3 { margin-top: 28px; border-top: 1px solid #eee; padding-top: 20px; }
blockquote { margin: 12px 0; padding: 10px 16px; background: #fff7e6; border-left: 4px solid #f5a623; border-radius: 4px; }
code { background: #f0f0f2; padding: 2px 5px; border-radius: 4px; }
</style></head><body><main>__BODY__</main></body></html>"""


def render_html(md_text: str) -> str:
    body = markdown.markdown(md_text, extensions=["extra"])
    return HTML_TEMPLATE.replace("__BODY__", body)