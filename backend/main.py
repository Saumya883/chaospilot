from fastapi import FastAPI

app = FastAPI(title="ChaosPilot API")


@app.get("/health")
def health():
    return {"status": "ok"}