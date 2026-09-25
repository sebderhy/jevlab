"""Local Jev-style typed decisions demo. Three open engines plus the real Jev behind one Jev-shaped API.
Run: cd ~/jevlab && .venv/bin/uvicorn app:app --port 3210
Everything lives under ~/jevlab. Revert with: rm -rf ~/jevlab
"""
import json, os, time, warnings
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("HF_HOME", os.path.join(HERE, "hf"))
warnings.filterwarnings("ignore")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="jevlab")
ENGINES: dict[str, object] = {}
ENGINE_INFO = {
    "laya":   {"label": "Laya",            "detail": "ModernBERT-large 421M, RLCD-trained, Jev API clone (convaiinnovations/laya)"},
    "kotoba": {"label": "kotoba open-jev", "detail": "DeBERTa-v3-large 435M, typed-decisions head (com-kotobalabs/open-jev-deberta-v3-large)"},
    "gliner": {"label": "GLiNER2.5 multi", "detail": "mDeBERTa-v3-base 287M, Fastino extraction/classification model (fastino/gliner2.5-multi-v1)"},
    "jev":    {"label": "Jev (TypeSafe)",  "detail": "the real thing: jev-latest via api.typesafe.ai, hosted, key in ~/jevlab/.env"},
    "llm":    {"label": "DeepSeek V4.1 Flash (logprobs)", "detail": "LLM reference: one request per question on Fireworks, one-letter answer, top logprobs read as probabilities"},
}
PRICE_PER_MTOK = {"jev": (0.042, 0.0), "llm": (0.30, 1.20), "llm_json": (0.30, 1.20), "llm_think": (0.30, 1.20)}  # USD per million (input, output) tokens: TypeSafe list price; Fireworks serverless list price for DeepSeek V4.1 Flash


def cost_usd(engine: str, usage: dict) -> float:
    pin, pout = PRICE_PER_MTOK[engine]
    return (usage["input_tokens"] * pin + usage.get("output_tokens", 0) * pout) / 1e6
LETTERS = "ABCDEFGHIJKLMNOP"
LLM_MODEL = os.environ.get("BENCH_LLM_MODEL", "accounts/fireworks/models/deepseek-v4p1-flash")


class DecideRequest(BaseModel):
    state: str | dict | list
    questions: dict[str, dict]
    engines: list[str] | None = None


def _options(q: dict) -> list[str]:
    """choice: options as list or {label: description}; score: levels list."""
    opts = q.get("options") if q["type"] == "choice" else q.get("levels")
    if not opts:
        raise HTTPException(400, f"question of type {q['type']} needs {'options' if q['type']=='choice' else 'levels'}")
    return list(opts)


def _state_text(state) -> str:
    return state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)


def _norm_noul(p_yes: float) -> dict:
    return {"answer": round(p_yes, 4), "probabilities": {"yes": round(p_yes, 4), "no": round(1 - p_yes, 4)},
            "confidence": round(max(p_yes, 1 - p_yes), 4)}


def _norm_dist(probs: dict, confidence: float | None = None) -> dict:
    best = max(probs, key=probs.get)
    return {"answer": best, "probabilities": {k: round(v, 4) for k, v in probs.items()},
            "confidence": round(confidence if confidence is not None else probs[best], 4)}


# ---------------- engines ----------------
def load_laya():
    import laya
    return laya.load("convaiinnovations/laya")


def run_laya(agent, state, questions):
    qs = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            c = q.get("criteria") or {}
            extra = " ".join(f"{'Yes' if k == 'true' else 'No'} if: {v}" for k, v in c.items() if v)  # Laya's noul has no criteria field
            qs[qid] = {"type": "noul", "instructions": f"{q['instructions']} {extra}".strip()}
        elif q["type"] == "choice":
            opts = q["options"]
            crit = opts if isinstance(opts, dict) else {o: o for o in opts}
            qs[qid] = {"type": "choice", "instructions": q["instructions"], "criteria": crit}
        else:
            qs[qid] = {"type": "score", "instructions": q["instructions"], "criteria": _options(q)}
    r = agent.predict(state, qs)
    out = {}
    for qid, a in r["answers"].items():
        if a["type"] == "noul":
            out[qid] = _norm_noul(a["noul"])
        elif a["type"] == "choice":
            out[qid] = _norm_dist(a["probabilities"], a["confidence"])
        else:
            legend = a["legend"]
            out[qid] = _norm_dist({legend[k]: v for k, v in a["probabilities"].items()}, a["confidence"])
            out[qid]["expected_level"] = round(a["score"], 3)
    return out


def load_kotoba():
    from typed_decisions.open_jev import OpenJev
    return OpenJev.from_pretrained("com-kotobalabs/open-jev-deberta-v3-large", device="cpu")


def run_kotoba(m, state, questions):
    qs = []
    for q in questions.values():
        if q["type"] == "noul":
            qs.append({"type": "noul", "instructions": q["instructions"]})
        else:
            qs.append({"type": q["type"], "instructions": q["instructions"], "options": _options(q)})
    r = m.decide(_state_text(state), qs)
    out = {}
    for (qid, q), a in zip(questions.items(), r):
        if q["type"] == "noul":
            out[qid] = _norm_noul(a["noul"])
        else:
            out[qid] = _norm_dist(a["probabilities"], a["confidence"])
            if q["type"] == "score":
                out[qid]["expected_level"] = round(a["score"], 3)
    return out


def load_gliner():
    from gliner2 import AutoExtractor
    return AutoExtractor.from_pretrained("fastino/gliner2.5-multi-v1")


def run_gliner(m, state, questions):
    """GLiNER has no typed-decision head: every question becomes a zero-shot classification task.
    noul -> yes/no labels, choice -> option labels, score -> level labels. Instructions become the task name."""
    schema = m.create_schema()
    for qid, q in questions.items():
        labels = ["yes", "no"] if q["type"] == "noul" else _options(q)
        schema = schema.classification(f"{qid}: {q['instructions']}", labels)
    r = m.extract(_state_text(state), schema, include_confidence=True, format_results=False)
    out = {}
    for qid, q in questions.items():
        key = f"{qid}: {q['instructions']}"
        raw = r.get(key) or r.get(qid)
        probs = _gliner_probs(raw)
        if q["type"] == "noul":
            out[qid] = _norm_noul(probs["yes"] if "yes" in probs else 1 - probs.get("no", 1.0))
        else:
            out[qid] = _norm_dist(probs)
            out[qid]["top_only"] = True  # GLiNER reports only the winning label's score, not a full distribution
    return out


def _gliner_probs(raw) -> dict:
    """Normalise the various shapes gliner2 returns for a classification task into {label: score}."""
    if isinstance(raw, tuple) and len(raw) == 2:  # format_results=False -> (label, confidence)
        return {str(raw[0]): float(raw[1])}
    if isinstance(raw, dict) and "label" in raw:
        return {raw["label"]: float(raw.get("confidence", 1.0))}
    if isinstance(raw, dict):
        return {k: float(v) for k, v in raw.items() if isinstance(v, (int, float))}
    if isinstance(raw, list):
        d = {}
        for item in raw:
            if isinstance(item, dict) and "label" in item:
                d[item["label"]] = float(item.get("confidence", 1.0))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                d[str(item[0])] = float(item[1])
        return d
    return {}


def load_jev():
    """Returns the API key read from ~/jevlab/.env (JEV_API_KEY=...). Raises if missing."""
    for line in open(os.path.join(HERE, ".env")):
        k, _, v = line.strip().partition("=")
        if k == "JEV_API_KEY" and v:
            return v
    raise RuntimeError("JEV_API_KEY missing in ~/jevlab/.env")


def run_jev(key, state, questions):
    import urllib.request
    qs = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            qs[qid] = {"type": "noul", "instructions": q["instructions"]}
        elif q["type"] == "choice":
            opts = q["options"]
            qs[qid] = {"type": "choice", "instructions": q["instructions"],
                       "criteria": opts if isinstance(opts, dict) else {o: o for o in opts}}
        else:
            qs[qid] = {"type": "score", "instructions": q["instructions"], "criteria": _options(q)}
    body = {"model": "jev-latest", "state": state, "questions": qs}
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=60))
    out = {}
    for qid, q in questions.items():
        a = r["answers"][qid]
        if q["type"] == "noul":
            out[qid] = _norm_noul(a["noul"])
        elif q["type"] == "choice":
            out[qid] = _norm_dist(a["probabilities"], a["confidence"])
        else:  # score: probabilities keyed by integer level, legend maps level -> description
            legend = {str(k): v for k, v in a["legend"].items()}
            out[qid] = _norm_dist({legend[str(k)]: v for k, v in a["probabilities"].items()}, a["confidence"])
    out["_usage"] = {"input_tokens": r["usage"]["input_tokens"], "output_tokens": r["usage"].get("output_tokens") or 0}
    return out


def load_llm():
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        raise RuntimeError("FIREWORKS_API_KEY missing from the environment")
    return key


def _llm_one(key, state, q):
    import math, urllib.request
    opts = ["yes", "no"] if q["type"] == "noul" else _options(q)
    desc = q.get("options") if isinstance(q.get("options"), dict) else {}
    lines = "\n".join(f"{LETTERS[i]}. {o}" + (f": {desc[o]}" if o in desc else "") for i, o in enumerate(opts))
    kind = {"noul": "Is the following statement about the state true?", "choice": "Question:", "score": "Question (ordered levels):"}[q["type"]]
    prompt = (f"State:\n{_state_text(state)}\n\n{kind} {q['instructions']}\n{lines}\n\n"
              f"Reply with exactly one letter from A-{LETTERS[len(opts)-1]} and nothing else.")
    body = {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1,
            "temperature": 0, "logprobs": True, "top_logprobs": 5, "reasoning_effort": "none"}
    req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=60))
    probs = {}
    for e in r["choices"][0]["logprobs"]["content"][0]["top_logprobs"]:
        tok = e["token"].strip().upper()
        if len(tok) == 1 and tok in LETTERS[:len(opts)]:  # len check: '' is a substring of any string
            probs[opts[LETTERS.index(tok)]] = probs.get(opts[LETTERS.index(tok)], 0) + math.exp(e["logprob"])
    z = sum(probs.values()) or 1.0
    probs = {o: probs.get(o, 0.0) / z for o in opts}
    out = _norm_noul(probs["yes"]) if q["type"] == "noul" else _norm_dist(probs)
    return out, r["usage"]


def run_llm(key, state, questions):
    """One request per question, in parallel. Adds answers["_usage"] = {"input_tokens": total} like run_jev."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(len(questions)) as ex:
        futs = {qid: ex.submit(_llm_one, key, state, q) for qid, q in questions.items()}
        out = {qid: f.result()[0] for qid, f in futs.items()}
        out["_usage"] = {"input_tokens": sum(f.result()[1]["prompt_tokens"] for f in futs.values()),
                         "output_tokens": sum(f.result()[1]["completion_tokens"] for f in futs.values())}
    return out


def _llm_think_one(key, state, q, effort="low"):
    """Recipe C: same one-letter question, but reasoning left ON. The model thinks first (billed as output tokens),
    then the answer letter is the last generated token; we read its logprobs. The thinking is kept as an explanation."""
    import math, urllib.request
    opts = ["yes", "no"] if q["type"] == "noul" else _options(q)
    desc = q.get("options") if isinstance(q.get("options"), dict) else {}
    lines = "\n".join(f"{LETTERS[i]}. {o}" + (f": {desc[o]}" if o in desc else "") for i, o in enumerate(opts))
    kind = {"noul": "Is the following statement about the state true?", "choice": "Question:", "score": "Question (ordered levels):"}[q["type"]]
    prompt = (f"State:\n{_state_text(state)}\n\n{kind} {q['instructions']}\n{lines}\n\n"
              f"Think briefly, then reply with exactly one letter from A-{LETTERS[len(opts)-1]} and nothing else.")
    body = {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 4000,
            "temperature": 0, "logprobs": True, "top_logprobs": 5, "reasoning_effort": effort}
    req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=180))
    entries = r["choices"][0]["logprobs"]["content"]
    ans = next((e for e in reversed(entries) if len(e["token"].strip()) == 1 and e["token"].strip().upper() in LETTERS[:len(opts)]), None)
    probs = {}
    if ans is not None:
        for e in ans["top_logprobs"]:
            tok = e["token"].strip().upper()
            if len(tok) == 1 and tok in LETTERS[:len(opts)]:
                probs[opts[LETTERS.index(tok)]] = probs.get(opts[LETTERS.index(tok)], 0) + math.exp(e["logprob"])
    z = sum(probs.values()) or 1.0
    probs = {o: probs.get(o, 0.0) / z for o in opts}
    out = _norm_noul(probs["yes"]) if q["type"] == "noul" else _norm_dist(probs)
    out["reasoning"] = (r["choices"][0]["message"].get("reasoning_content") or "")[:2000]
    out["answer_token_found"] = ans is not None
    out["reasoning_tokens"] = r["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0)
    return out, r["usage"]


def run_llm_think(key, state, questions):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(min(len(questions), 10)) as ex:
        futs = {qid: ex.submit(_llm_think_one, key, state, q) for qid, q in questions.items()}
        out = {qid: f.result()[0] for qid, f in futs.items()}
        out["_usage"] = {"input_tokens": sum(f.result()[1]["prompt_tokens"] for f in futs.values()),
                         "output_tokens": sum(f.result()[1]["completion_tokens"] for f in futs.values())}
    return out


def run_llm_json(key, state, questions):
    """Prior-art recipe: one request per state, every question at once, answer as JSON with a letter and a
    self-reported confidence per question (no logprobs). Adds answers["_usage"] like run_llm."""
    import urllib.request
    blocks, opt_lists = [], {}
    for qid, q in questions.items():
        opts = ["yes", "no"] if q["type"] == "noul" else _options(q)
        opt_lists[qid] = opts
        desc = q.get("options") if isinstance(q.get("options"), dict) else {}
        lines = "\n".join(f"  {LETTERS[i]}. {o}" + (f": {desc[o]}" if o in desc else "") for i, o in enumerate(opts))
        kind = {"noul": "Is this statement about the state true?", "choice": "Question:", "score": "Question (ordered levels):"}[q["type"]]
        blocks.append(f"[{qid}] {kind} {q['instructions']}\n{lines}")
    prompt = (f"State:\n{_state_text(state)}\n\nAnswer every question below from the state.\n\n" + "\n\n".join(blocks) +
              "\n\nReply with a single JSON object mapping each question id to {\"a\": <one letter>, \"p\": <your probability, 0 to 1, that the letter is correct>}. No other text.")
    body = {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0,
            "max_tokens": 40 * len(questions) + 50, "response_format": {"type": "json_object"}, "reasoning_effort": "none"}
    req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120))
    parsed = json.loads(r["choices"][0]["message"]["content"])
    out = {}
    for qid, q in questions.items():
        opts = opt_lists[qid]
        a = parsed.get(qid) or {}
        letter = str(a.get("a", "")).strip().upper()[:1]
        p = min(max(float(a.get("p", 1.0)), 0.0), 1.0)
        if letter not in LETTERS[:len(opts)]:  # malformed or missing: count as a wrong, fully unconfident answer
            letter, p = "A", 0.0
        pick = opts[LETTERS.index(letter)]
        rest = (1 - p) / (len(opts) - 1) if len(opts) > 1 else 0.0
        probs = {o: (p if o == pick else rest) for o in opts}
        out[qid] = _norm_noul(probs["yes"]) if q["type"] == "noul" else _norm_dist(probs)
    out["_usage"] = {"input_tokens": r["usage"]["prompt_tokens"], "output_tokens": r["usage"]["completion_tokens"]}
    return out


LOADERS = {"laya": (load_laya, run_laya), "kotoba": (load_kotoba, run_kotoba), "gliner": (load_gliner, run_gliner),
           "jev": (load_jev, run_jev), "llm": (load_llm, run_llm)}


@app.on_event("startup")
def _load():
    for name, (loader, runner) in LOADERS.items():
        t = time.time()
        try:
            model = loader()
            runner(model, "warm-up", {"w": {"type": "noul", "instructions": "warm-up"}})
        except Exception as e:  # a hosted engine with a bad key must not take the local ones down
            print(f"[jevlab] FAILED to load {name}: {type(e).__name__}: {e}", flush=True)
            continue
        ENGINES[name] = model
        print(f"[jevlab] loaded {name} in {time.time()-t:.1f}s", flush=True)


def load_bench(path: str | None = None):
    """bench/questions.json (or another file in the same format) with option-set names resolved to their lists/dicts."""
    bench = json.load(open(path or os.path.join(HERE, "bench", "questions.json")))
    for it in bench["items"]:
        key = "options" if it["type"] == "choice" else "levels" if it["type"] == "score" else None
        if key and isinstance(it[key], str):
            it[key] = bench["option_sets"][it[key]]
    return bench


def bench_question(it: dict) -> dict:
    q = {"type": it["type"], "instructions": it["instructions"]}
    if it["type"] == "choice":
        q["options"] = it["options"]
    elif it["type"] == "score":
        q["levels"] = it["levels"]
    return q


@app.get("/bench")
def bench_cases():
    """Both benchmarks grouped by state, for the demo's picker:
    [{id, set, category, state, questions:{qid: question}, gold:{qid: label}}]. set is "short" (benchmark 1) or "long" (benchmark 2)."""
    out = []
    for tag, fname in (("short", "questions.json"), ("long", "questions_long.json")):
        b = load_bench(os.path.join(HERE, "bench", fname))
        groups: dict[str, dict] = {}
        for it in b["items"]:
            g = groups.setdefault(it["state"], {"id": f"{tag}:{it['state']}", "set": tag, "categories": [], "state": b["states"][it["state"]], "questions": {}, "gold": {}})
            if it["category"] not in g["categories"]:
                g["categories"].append(it["category"])
            g["questions"][it["id"]] = bench_question(it)
            g["gold"][it["id"]] = it["gold"]
        out += list(groups.values())
    return out


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.get("/engines")
def engines():
    return {k: {**v, "loaded": k in ENGINES} for k, v in ENGINE_INFO.items()}


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
        usage = answers.pop("_usage", None)
        results[name] = {"ms": round((time.time() - t) * 1000), "answers": answers}
        if usage:
            results[name]["input_tokens"] = usage["input_tokens"]
            results[name]["cost_usd"] = cost_usd(name, usage)
    return {"results": results, "state_chars": len(_state_text(req.state))}
