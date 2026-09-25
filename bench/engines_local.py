"""Bench-only local engines: two open Jev clones on Qwen3.5 backbones, run on CPU.
  decider  Mapika/decider-2b (v10): full fine-tune of Qwen3.5-2B-Base, letter logits at one answer slot per question.
  kev      jaredpalmer/kev-4b: Qwen3.5-4B-Base + rank-16 LoRA (merged) + pointer head over each option's hidden state.
Same adapter signature as app.run_laya: run_x(model, state, questions) -> {qid: normalised answer}.
Both need transformers>=5.17 (qwen3_5 architecture); decider-ai and kev are installed with --no-deps (see bench notes).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(HERE), "hf"))
from app import _options, _norm_noul, _norm_dist  # noqa: E402

DECIDER_MODEL = os.environ.get("BENCH_DECIDER_MODEL", "Mapika/decider-2b")
KEV_MODEL = os.environ.get("BENCH_KEV_MODEL", "jaredpalmer/kev-4b")
DECIDER_LAYOUT = os.environ.get("DECIDER_LAYOUT", "independent")  # independent (bench default: one row per question) or packed (all questions behind one state copy, ~5x faster on CPU, used by the live demos)
DTYPE = os.environ.get("BENCH_LOCAL_DTYPE", "fp32")  # fp32: 3-5x faster than bf16 on this EPYC Milan (no native bf16), same answers within 1e-3; also kev's "exact" path


def _dtype():
    import torch
    return {"bf16": torch.bfloat16, "fp32": torch.float32}[DTYPE]


def _jev_questions(questions):
    """Bench questions -> TypeSafe /v1/systemone wire format (both clones speak it): criteria dict for choice, level list for score."""
    qs = {}
    for qid, q in questions.items():
        spec = {"type": q["type"], "instructions": q["instructions"]}
        if q["type"] == "choice":
            opts = q["options"]
            spec["criteria"] = opts if isinstance(opts, dict) else {o: None for o in opts}
        elif q["type"] == "score":
            spec["criteria"] = _options(q)
        elif q.get("criteria"):  # noul with {"true": ..., "false": ...} descriptions (both clones render them as the yes/no options)
            spec["criteria"] = q["criteria"]
        qs[qid] = spec
    return qs


def _normalise(questions, answers):
    """Jev-shaped answers {qid: {"noul": p} | {"choice", "confidence", "probabilities"} | {"score", "probabilities": {"0": p, ...}}}
    -> the bench's normalised form. Confidence is the top probability (as for the LLM and Jev rows), not the clone's own statistic."""
    out = {}
    for qid, q in questions.items():
        a = answers[qid]
        if q["type"] == "noul":
            out[qid] = _norm_noul(float(a["noul"]))
        elif q["type"] == "choice":
            out[qid] = _norm_dist({k: float(v) for k, v in a["probabilities"].items()})
        else:
            levels = _options(q)
            out[qid] = _norm_dist({levels[int(k)]: float(v) for k, v in a["probabilities"].items()})
            out[qid]["expected_level"] = round(float(a["score"]), 3)
        if "confidence" in a:  # the clone's own statistic (kev: (max-1/K)/(1-1/K) for choice, modal-distance for score), kept for reference
            out[qid]["engine_confidence"] = round(float(a["confidence"]), 4)
    return out


# ---------------- decider ----------------
def load_decider():
    from decider.infer import Decider
    return Decider(DECIDER_MODEL, device="cpu", dtype=_dtype())  # eager CPU path (use_graphs=False when device is not cuda)


def run_decider(d, state, questions):
    """One system_one call: the state is rendered by decider itself (JSON with array indices), every question is its own row
    behind the same state (independent=True), Score levels judged in isolation (v10 default); rows are batched in one forward."""
    r = d.system_one(state, _jev_questions(questions), independent=DECIDER_LAYOUT != "packed")
    return _normalise(questions, r["answers"])


# ---------------- kev ----------------
def load_kev():
    from kev.checkpoint import Checkpoint, LoadOptions
    tok, m = Checkpoint(KEV_MODEL).load("cpu", LoadOptions(dtype=_dtype()))  # base in fp32, LoRA merged exactly, then cast
    return tok, m


def run_kev(tm, state, questions):
    """kev.serve's path without the cross-request prefix cache (a driving state never repeats): encode the record, one batched pass over the per-question causal rows
    (hybrid Qwen3.5 backbones run the row form), pointer head + the checkpoint's fitted temperature, TypeSafe-shaped answers."""
    from kev.api import SystemOneRequest, to_record, to_answers
    from kev.model import SERVE_MAX_STATE, SERVE_MAX_BRANCH
    tok, m = tm
    rec, meta = to_record(SystemOneRequest(state=state, questions=_jev_questions(questions)))
    enc = m.encode(tok, rec, max_state=SERVE_MAX_STATE, max_branch=SERVE_MAX_BRANCH)
    ps = [p.tolist() for p in m.probs_and_prefix(enc)[0]]  # state encoded once, question rows continue its cache: exact (kev.model), about 3x fewer tokens
    return _normalise(questions, to_answers(ps, meta))
