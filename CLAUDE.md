# ChaosPilot

AI-driven user chaos engineer for web apps. The user gives a URL and a plain-English goal (e.g. "Try to break checkout"). ChaosPilot plans chaos scenarios with an LLM, runs them in real browsers via the TinyFish agent, re-runs failures to confirm them, and reports bugs with screenshots and repro steps.

## Stack
- Backend: FastAPI (Python 3.12), Pydantic
- Frontend: Next.js + TypeScript (built last)
- LLM planner: Gemini / OpenAI
- Browser agent: TinyFish (integrated later)
- DB: Postgres / Supabase

## Layout
- `backend/` FastAPI app (`main.py` is the entry point)
- `demo-app/` intentionally buggy checkout site used as a test target
- `frontend/` Next.js UI (later)

## Run
cd backend && source .venv/bin/activate && uvicorn main:app --reload

## Rules
- Staging-only: never run scenarios against production or real payment flows.
- Every run has a step cap and an allowed-actions list.
- Re-run each failing scenario before reporting it as a bug.
- Never commit `.env` or any API keys.
- Small, focused commits with clear messages.