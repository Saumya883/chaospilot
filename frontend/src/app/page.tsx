"use client";

import { useEffect, useState } from "react";
import BlurText from "@/components/BlurText";
import ShinyText from "@/components/ShinyText";
import SpotlightCard from "@/components/SpotlightCard";
import CountUp from "@/components/CountUp";
import {
  API_URL,
  PROFILE_LABELS,
  cleanStep,
  getHealth,
  impactFor,
  postJson,
  verdictFor,
  type Finding,
  type RunReport,
  type Severity,
} from "@/lib/api";

const FONT = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

const STEPS = [
  { t: "1. Plan", d: "Imagines how a rushed, confused or unusual user would behave" },
  { t: "2. Safety check", d: "Only runs on sites you've allowed" },
  { t: "3. Try & re-try", d: "Runs each scenario, then repeats any failure" },
  { t: "4. Report", d: "Plain-English bugs with steps to reproduce" },
];

const sevStyle: Record<Severity, string> = {
  critical: "bg-red-500/20 text-red-300 border-red-500/40",
  high: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  medium: "bg-yellow-500/20 text-yellow-200 border-yellow-500/40",
  low: "bg-sky-500/20 text-sky-300 border-sky-500/40",
};

const inputCls =
  "w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2.5 text-white placeholder-white/30 outline-none focus:border-violet-400/60";

function Badge({ cls, children }: { cls: string; children: React.ReactNode }) {
  return <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

export default function Home() {
  const [runner, setRunner] = useState("Checking runner…");
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [url, setUrl] = useState("http://localhost:8080");
  const [goal, setGoal] = useState("Try to break checkout");
  const [profile, setProfile] = useState("");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<RunReport | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);

  useEffect(() => {
    getHealth()
      .then((h) => {
        setBackendUp(true);
        setRunner(h.runner === "mock" ? "Runner: SIMULATED (no real browser yet)" : `Runner: ${h.runner}`);
      })
      .catch(() => {
        setBackendUp(false);
        setRunner("Backend not reachable");
      });
  }, []);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setReport(null);
    setFindings([]);
    const body = { url: url.trim(), goal: goal.trim(), count, profile: profile || null };
    try {
      const [runRes, scanRes] = await Promise.allSettled([
        postJson<RunReport>("/run", body),
        postJson<Finding[]>("/scan", { url: body.url }),
      ]);
      if (runRes.status === "rejected") throw runRes.reason;
      setReport(runRes.value);
      if (scanRes.status === "fulfilled") setFindings(scanRes.value);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  const passed = report?.results.filter((r) => r.status === "passed") ?? [];
  const blocked = report?.results.filter((r) => r.status === "blocked") ?? [];
  const errored = report?.results.filter((r) => r.status === "error") ?? [];
  const simulated = report?.results.some((r) => r.source === "mock") ?? false;
  const verdict = report ? verdictFor(report) : null;

  return (
    <div
      className="min-h-screen text-white"
      style={{
        fontFamily: FONT,
        background:
          "radial-gradient(900px 500px at 50% -10%, rgba(124,58,237,0.45), transparent 60%), radial-gradient(700px 400px at 90% 20%, rgba(236,72,153,0.18), transparent 60%), #08060f",
      }}
    >
      <div className="mx-auto max-w-3xl px-5 pb-24 pt-14">
        <header className="mb-10 text-center">
          <h1 className="text-5xl font-bold tracking-tight md:text-6xl">
            <BlurText text="ChaosPilot" delay={150} animateBy="letters" direction="top" className="justify-center" />
          </h1>
          <p className="mt-3 text-lg font-semibold text-white/90">
            Test like a human. Think like a user. Report like an engineer.
          </p>
          <p className="mt-1 text-white/55">
            Give it a website and it tries to use it the way real, imperfect people do.
          </p>
        </header>

        <ul className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.t}>
              <SpotlightCard className="!p-4 h-full" spotlightColor="rgba(167, 139, 250, 0.2)">
                <p className="text-sm font-semibold">{s.t}</p>
                <p className="mt-1 text-xs leading-snug text-white/55">{s.d}</p>
              </SpotlightCard>
            </li>
          ))}
        </ul>

        <SpotlightCard className="!p-6" spotlightColor="rgba(167, 139, 250, 0.18)">
          <span
            className={`mb-4 inline-block rounded-full border px-3 py-1 text-xs ${
              backendUp === false
                ? "border-red-500/40 bg-red-500/10 text-red-300"
                : "border-amber-400/40 bg-amber-400/10 text-amber-200"
            }`}
          >
            {runner}
          </span>
          {backendUp === false && (
            <p className="mb-4 text-sm text-red-300/90">
              Can&apos;t reach {API_URL}. Start the backend: <code>uvicorn main:app --reload</code> in{" "}
              <code>backend/</code>.
            </p>
          )}

          <form onSubmit={run} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold">
                Website to test <span className="font-normal text-white/50">(a test site you&apos;re allowed to test)</span>
              </span>
              <input className={inputCls} value={url} onChange={(e) => setUrl(e.target.value)} required />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold">
                What should we try to break? <span className="font-normal text-white/50">(in plain English)</span>
              </span>
              <input className={inputCls} value={goal} onChange={(e) => setGoal(e.target.value)} required />
            </label>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-sm font-semibold">Type of user</span>
                <select className={inputCls} value={profile} onChange={(e) => setProfile(e.target.value)}>
                  <option value="">Mix of all</option>
                  <option value="impatient">Impatient: double-clicks, hits Back, reloads</option>
                  <option value="confused">Confused first-timer: blanks, wrong formats</option>
                  <option value="edge_case">Edge-case: emoji, very long text, odd characters</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-semibold">How many scenarios</span>
                <input
                  className={inputCls}
                  type="number"
                  min={1}
                  max={15}
                  value={count}
                  onChange={(e) => setCount(Math.min(15, Math.max(1, Number(e.target.value) || 1)))}
                />
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-violet-600 px-4 py-3.5 text-base font-semibold transition hover:bg-violet-500 disabled:cursor-wait disabled:opacity-60"
            >
              {loading ? "Working…" : <ShinyText text="Run chaos test" speed={3} />}
            </button>
          </form>

          {loading && (
            <p className="mt-4 animate-pulse text-sm text-white/60">
              Planning scenarios, running them and re-testing failures. This can take up to 30 seconds.
            </p>
          )}
          {error && <p className="mt-4 text-sm text-red-300">Something went wrong: {error}</p>}
        </SpotlightCard>

        {report && (
          <section className="mt-10 space-y-8">
            <div>
              <h2 className="text-2xl font-bold">ChaosPilot test report</h2>
              <p className="mt-1 text-sm text-white/60">
                <b className="text-white/80">Site tested:</b> {report.url} · <b className="text-white/80">Goal:</b>{" "}
                {report.goal}
              </p>
            </div>

            {simulated && (
              <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-4 text-sm text-amber-100">
                <b>SIMULATED RUN.</b> These results came from ChaosPilot&apos;s mock runner. No real browser was opened, so
                nothing below is a real finding.
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              {[
                { l: "Passed", v: passed.length },
                { l: "Confirmed bugs", v: report.bugs.length },
                { l: "Flaky", v: report.flaky_scenarios.length },
                { l: "Blocked", v: blocked.length },
                { l: "Errors", v: errored.length },
              ].map((s) => (
                <SpotlightCard key={s.l} className="!p-4" spotlightColor="rgba(167, 139, 250, 0.2)">
                  <p className="text-3xl font-bold">
                    <CountUp from={0} to={s.v} duration={1} />
                  </p>
                  <p className="text-xs text-white/55">{s.l}</p>
                </SpotlightCard>
              ))}
            </div>

            {verdict && (
              <p className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                <b>Verdict:</b> {verdict}
              </p>
            )}

            <div>
              <h3 className="mb-3 text-lg font-semibold">Confirmed bugs</h3>
              {report.bugs.length === 0 && <p className="text-sm text-white/55">None.</p>}
              <div className="space-y-4">
                {report.bugs.map((bug, i) => {
                  const imp = impactFor(bug);
                  return (
                    <SpotlightCard key={i} className="!p-5" spotlightColor="rgba(244, 63, 94, 0.18)">
                      <div className="mb-2 flex items-start justify-between gap-3">
                        <h4 className="font-semibold">
                          {i + 1}. {bug.title}
                        </h4>
                        <Badge cls={sevStyle[bug.severity]}>{bug.severity}</Badge>
                      </div>
                      <p className="mb-3 text-xs text-white/55">
                        Human impact: {imp.label} ({imp.score}/6) · Found by: {PROFILE_LABELS[bug.profile] ?? bug.profile}
                      </p>
                      <blockquote className="mb-4 rounded border-l-4 border-amber-400 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                        {bug.human_story}
                      </blockquote>

                      <p className="text-sm font-semibold">What went wrong</p>
                      <ul className="mb-3 mt-1 list-disc space-y-1 pl-5 text-sm text-white/70">
                        {(bug.observations.length ? bug.observations : ["(no observation recorded)"]).map((o, j) => (
                          <li key={j} className="break-words">
                            {o}
                          </li>
                        ))}
                      </ul>

                      <p className="text-sm">
                        <b>What should happen:</b> <span className="text-white/70">{bug.expected_behavior}</span>
                      </p>
                      <p className="mt-1 text-sm">
                        <b>Why it matters:</b> <span className="text-white/70">{imp.sentence}</span>
                      </p>

                      <p className="mt-3 text-sm font-semibold">How to reproduce</p>
                      <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm text-white/70">
                        {bug.reproduction_steps.map((s, j) => (
                          <li key={j} className="break-words">
                            {cleanStep(s)}
                          </li>
                        ))}
                      </ol>

                      <p className="mt-3 text-xs text-white/50">
                        Confidence: it failed in {bug.fail_count} of {bug.run_count} runs.
                        {bug.screenshot_path && <> Evidence: screenshot {bug.screenshot_path}</>}
                      </p>
                    </SpotlightCard>
                  );
                })}
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-lg font-semibold">Security observations</h3>
              {findings.length === 0 ? (
                <p className="text-sm text-white/55">Nothing of concern was observed.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {findings.map((f, i) => (
                    <li key={i} className="rounded-lg border border-white/10 bg-white/5 p-3">
                      <b>{f.title}</b> <span className="text-white/50">({f.severity})</span>
                      <p className="mt-1 break-words text-white/65">Evidence: {f.evidence}</p>
                      <p className="text-white/65">Why it matters: {f.why_it_matters}</p>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-xs italic text-white/40">
                ChaosPilot only reports what it observed in the browser. It cannot see how a site stores data on its
                servers.
              </p>
            </div>

            {errored.length > 0 && (
              <div>
                <h3 className="mb-2 text-lg font-semibold">Scenarios that could not run</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-white/70">
                  {errored.map((r, i) => (
                    <li key={i}>
                      <b>{r.scenario_name}:</b> {r.observations.join("; ")}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {report.flaky_scenarios.length > 0 && (
              <div>
                <h3 className="mb-2 text-lg font-semibold">Not reported (could not be confirmed)</h3>
                <p className="mb-1 text-sm text-white/55">
                  These failed once but passed when re-run, so they are not counted as bugs:
                </p>
                <ul className="list-disc space-y-1 pl-5 text-sm text-white/70">
                  {report.flaky_scenarios.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </div>
            )}

            {blocked.length > 0 && (
              <div>
                <h3 className="mb-2 text-lg font-semibold">Blocked by safety rules</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-white/70">
                  {blocked.map((r, i) => (
                    <li key={i} className="break-words">
                      {r.scenario_name}: {r.observations.join("; ")}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {passed.length > 0 && (
              <div>
                <h3 className="mb-2 text-lg font-semibold">What held up</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-white/70">
                  {passed.map((r, i) => (
                    <li key={i}>{r.scenario_name}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
