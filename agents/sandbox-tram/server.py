"""HTTP wrapper so the sandbox agent can run on AgentBase.

Runtime contract (hard): listen on port 8080, expose GET /health -> 200.
We also add POST /invocations (the GreenNode SDK convention) and a friendly
GET /ask for quick manual testing.

Run locally:
  uvicorn server:app --host 0.0.0.0 --port 8080
Then:
  curl http://localhost:8080/health
  curl "http://localhost:8080/ask?q=MPU this week vs last week"
"""
import os

from fastapi import FastAPI
from pydantic import BaseModel

import ask
import metrics

DATA = os.path.join(os.path.dirname(__file__), "data", "disbursements.csv")

app = FastAPI(title="Sandbox Disbursement Agent")
_df = None


def get_df():
    global _df
    if _df is None:
        _df = metrics.load(DATA)
    return _df


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ask")
def ask_get(q: str = "total disbursement this week vs last week"):
    return {"question": q, "answer": ask.answer(get_df(), q)}


class Invocation(BaseModel):
    question: str = "total disbursement this week vs last week"


@app.post("/invocations")
def invocations(body: Invocation):
    return {"question": body.question, "answer": ask.answer(get_df(), body.question)}
