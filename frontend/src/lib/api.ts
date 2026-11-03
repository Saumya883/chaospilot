// Types mirror backend/schemas.py. Talks to the FastAPI backend in backend/main.py.

export type Severity = "low" | "medium" | "high" | "critical";
export type Profile = "impatient" | "confused" | "edge_case";

export type ScenarioResult = {
  scenario_name: string;
  category: string;
  status: "passed" | "failed" | "error" | "blocked";
  steps_executed: number;
  observations: string[];
  screenshot_path: string | null;
  duration_s: number;
  source: "mock" | "tinyfish";
};

export type Bug = {
  title: string;
  category: string;
  profile: Profile;
  human_story: string;
  severity: Severity;
  confirmed: boolean;
  fail_count: number;
  run_count: number;
  reproduction_steps: string[];
  expected_behavior: string;
  observations: string[];
  screenshot_path: string | null;
  source: "mock" | "tinyfish";
};

export type RunReport = {
  url: string;
  goal: string;
  results: ScenarioResult[];
  bugs: Bug[];
  flaky_scenarios: string[];
};

// From leak_checks.Finding (fields used by report.py)
export type Finding = {
  title: string;
  severity: string;
  evidence: string;
  why_it_matters: string;
};

export type Health = { status: string; runner: string };

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const PROFILE_LABELS: Record<Profile, string> = {
  impatient: "Impatient user",
  confused: "Confused first-timer",
  edge_case: "Edge-case user",
};

async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    /* ignore */
  }
  return `Server error ${res.status}`;
}

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

// Same rule-based impact estimate as backend/report.py (severity points + category points, max 6).
const SEVERITY_POINTS: Record<Severity, number> = { low: 1, medium: 2, high: 3, critical: 4 };
const CATEGORY_POINTS: Record<string, number> = {
  double_submit: 2,
  navigation: 1,
  input_fuzzing: 1,
  empty_input: 0,
  boundary_values: 1,
  rapid_interaction: 1,
};
const IMPACT_SENTENCES: Record<string, string> = {
  double_submit: "A customer could be charged or ordered twice for one action.",
  navigation: "A customer could lose their progress or land on a broken page.",
  input_fuzzing: "Unusual text could break the page or expose internal details.",
  empty_input: "A customer could submit incomplete information and the app accepts it.",
  boundary_values: "Extreme values could produce wrong totals or errors.",
  rapid_interaction: "Fast repeated actions could leave the app in an inconsistent state.",
};

export function impactFor(bug: Bug): { score: number; label: string; sentence: string } {
  const score = SEVERITY_POINTS[bug.severity] + (CATEGORY_POINTS[bug.category] ?? 0);
  const label = score >= 5 ? "Severe" : score >= 4 ? "High" : score >= 3 ? "Moderate" : "Minor";
  const sentence = IMPACT_SENTENCES[bug.category] ?? "A customer's experience could be disrupted.";
  return { score, label, sentence };
}

export const cleanStep = (s: string) => s.replace(/^\d+\.\s*/, "");

// Plain-English verdict, same logic as backend/report.py (only for real, non-simulated runs).
export function verdictFor(report: RunReport): string | null {
  const results = report.results;
  if (results.some((r) => r.source === "mock")) return null;
  const blocked = results.filter((r) => r.status === "blocked").length;
  const errored = results.filter((r) => r.status === "error").length;
  if (results.length && blocked === results.length)
    return `Nothing was tested. All ${blocked} scenario(s) were blocked by safety rules, so this report says nothing about the site.`;
  if (results.length && blocked + errored === results.length)
    return "Nothing was completed. Every scenario was either blocked by safety rules or hit an error, so this report says nothing about the site yet.";
  if (results.length && errored === results.length)
    return "None of the scenarios could be completed, so this report says nothing about the site yet.";
  if (report.bugs.length)
    return `${report.bugs.length} confirmed bug(s) need attention. Worst severity: ${report.bugs[0].severity}.`;
  const skipped = blocked + errored;
  return (
    "No confirmed bugs in the scenarios that ran." +
    (skipped ? ` ${skipped} scenario(s) did not run (blocked or errored), so coverage is incomplete.` : "")
  );
}
