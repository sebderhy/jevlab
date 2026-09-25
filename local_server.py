"""Serve the local Qwen3.5 Jev clones (bench/engines_local.py) with the same /decide contract as app.py, from .venv-local.
Run: .venv-local/bin/uvicorn local_server:app --host 127.0.0.1 --port 3211   (user unit app-decider)
LOCAL_ENGINES=decider (default) or decider,kev; each engine loads at startup and stays in RAM (decider 12 GB, kev 25 GB in fp32)."""
import json, os, sys, time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "bench"))
import engines_local  # noqa: E402

LOADERS = {"decider": (engines_local.load_decider, engines_local.run_decider), "kev": (engines_local.load_kev, engines_local.run_kev)}
NAMES = [e for e in os.environ.get("LOCAL_ENGINES", "decider").split(",") if e]
ENGINES = {}
for name in NAMES:
    t = time.time()
    ENGINES[name] = LOADERS[name][0]()
    print(f"[{name}] loaded in {time.time() - t:.1f}s", flush=True)

app = FastAPI(title="jevlab local clones")


class DecideRequest(BaseModel):
    state: str | dict | list
    questions: dict[str, dict]
    engines: list[str] | None = None


@app.get("/engines")
def engines():
    return {k: {"loaded": True} for k in ENGINES}


@app.post("/decide")
def decide(req: DecideRequest):
    for qid, q in req.questions.items():
        if q.get("type") not in ("noul", "choice", "score"):
            raise HTTPException(400, f"question {qid}: type must be noul, choice or score")
        if not q.get("instructions"):
            raise HTTPException(400, f"question {qid}: instructions required")
    results = {}
    for name in (req.engines if req.engines is not None else list(ENGINES)):
        if name not in ENGINES:
            raise HTTPException(400, f"unknown engine {name}")
        t = time.time()
        answers = LOADERS[name][1](ENGINES[name], req.state, req.questions)
        results[name] = {"ms": round((time.time() - t) * 1000), "answers": answers}
    state = req.state if isinstance(req.state, str) else json.dumps(req.state, ensure_ascii=False)
    return {"results": results, "state_chars": len(state)}
