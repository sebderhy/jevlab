"""Benchmark open typed-decision models (and an LLM logprob reference) on bench/questions.json.
Run: cd ~/jevlab && .venv/bin/python bench/bench.py [--engines laya,kotoba,gliner,gliner_b,llm,jev]
Writes bench/results.json. Reuses the engine adapters from app.py so the demo and the benchmark share one code path.
"""
import argparse, json, os, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(HERE), "hf"))
import app  # noqa: E402  (engine adapters)
from engines_local import load_decider, run_decider, load_kev, run_kev  # noqa: E402  (bench/engines_local.py: needs .venv-local, transformers>=5.17)

LLM_MODEL = app.LLM_MODEL


# ---------- extra engines that only exist for the benchmark ----------
def run_gliner_b(m, state, questions):
    """Alternative GLiNER mapping for noul: labels carry the statement instead of the task name.
    choice/score identical to the demo mapping."""
    schema = m.create_schema()
    keys = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            key = f"{qid}"
            schema = schema.classification(key, {"true": q["instructions"], "false": "the opposite: " + q["instructions"]})
        else:
            key = f"{qid}: {q['instructions']}"
            schema = schema.classification(key, app._options(q) if not isinstance(q.get("options"), dict) else q["options"])
        keys[qid] = key
    r = m.extract(app._state_text(state), schema, include_confidence=True, format_results=False)
    out = {}
    for qid, q in questions.items():
        probs = app._gliner_probs(r.get(keys[qid]))
        if q["type"] == "noul":
            out[qid] = app._norm_noul(probs["true"] if "true" in probs else 1 - probs.get("false", 1.0))
        else:
            out[qid] = app._norm_dist(probs)
    return out


ENGINES = {
    "laya": (app.load_laya, app.run_laya),
    "kotoba": (app.load_kotoba, app.run_kotoba),
    "gliner": (app.load_gliner, app.run_gliner),
    "gliner_b": (app.load_gliner, run_gliner_b),
    "llm": (app.load_llm, app.run_llm),
    "jev": (app.load_jev, app.run_jev),
    "llm_json": (app.load_llm, app.run_llm_json),
    "llm_think": (app.load_llm, app.run_llm_think),
    "decider": (load_decider, run_decider),
    "kev": (load_kev, run_kev),
}


# ---------- benchmark ----------
load_bench = app.load_bench


def by_state(items):
    g = defaultdict(list)
    for it in items:
        g[it["state"]].append(it)
    return g


question_of = app.bench_question


def score_item(it, a):
    gold = it["gold"]
    if it["type"] == "noul":
        p_true = a["answer"]
        pred = p_true >= 0.5
        return {"pred": pred, "correct": pred == gold, "p_gold": p_true if gold else 1 - p_true,
                "brier": (p_true - (1.0 if gold else 0.0)) ** 2, "conf": max(p_true, 1 - p_true)}
    probs = a["probabilities"]
    opts = it["options"] if it["type"] == "choice" else it["levels"]
    labels = list(opts.keys()) if isinstance(opts, dict) else list(opts)
    full = {l: probs.get(l, 0.0) for l in labels}
    if a.get("top_only") and len(labels) > 1:  # spread the remainder evenly over unreported labels
        rest = (1 - full[a["answer"]]) / (len(labels) - 1)
        full = {l: (full[l] if l == a["answer"] else rest) for l in labels}
    pred = a["answer"]
    return {"pred": pred, "correct": pred == gold, "p_gold": full.get(gold, 0.0),
            "brier": sum((full[l] - (1.0 if l == gold else 0.0)) ** 2 for l in labels), "conf": a["confidence"]}


def ece(rows, bins=10):
    tot = len(rows)
    e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [r for r in rows if lo < r["conf"] <= hi]
        if sel:
            e += len(sel) / tot * abs(sum(r["correct"] for r in sel) / len(sel) - sum(r["conf"] for r in sel) / len(sel))
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="laya,kotoba,gliner,gliner_b,llm,jev")
    ap.add_argument("--questions", default="questions.json", help="file in bench/ (questions.json or questions_long.json)")
    ap.add_argument("--out", default=None, help="results file in bench/ (default: results.json or results_long.json)")
    args = ap.parse_args()
    bench = load_bench(os.path.join(HERE, args.questions))
    groups = by_state(bench["items"])
    out_path = os.path.join(HERE, args.out or args.questions.replace("questions", "results"))
    results = {"llm_model": LLM_MODEL, "n_items": len(bench["items"]), "n_states": len(groups), "engines": {}}
    if os.path.exists(out_path):  # a partial --engines run keeps the other engines' results
        results["engines"] = json.load(open(out_path))["engines"]
    for name in args.engines.split(","):
        loader, runner = ENGINES[name]
        t = time.time()
        model = loader()
        print(f"[{name}] loaded in {time.time()-t:.1f}s", flush=True)
        runner(model, "warm-up", {"w": {"type": "noul", "instructions": "warm-up"}})
        per_item, call_ms, tokens, out_tokens = {}, [], 0, 0
        for st, items in groups.items():
            state = bench["states"][st]
            qs = {it["id"]: question_of(it) for it in items}
            t = time.time()
            answers = runner(model, state, qs)
            ms = (time.time() - t) * 1000
            usage = answers.pop("_usage", None)
            tokens += usage["input_tokens"] if usage else 0
            out_tokens += usage.get("output_tokens", 0) if usage else 0
            call_ms.append({"state": st, "n": len(qs), "ms": ms, **(usage or {})})
            for it in items:
                a = answers[it["id"]]
                per_item[it["id"]] = {**score_item(it, a), "answer": a}
        rows = list(per_item.values())
        cats = defaultdict(list)
        types = defaultdict(list)
        for it in bench["items"]:
            cats[it["category"]].append(per_item[it["id"]])
            types[it["type"]].append(per_item[it["id"]])
        summ = {
            "accuracy": sum(r["correct"] for r in rows) / len(rows),
            "brier": sum(r["brier"] for r in rows) / len(rows),
            "ece": ece(rows),
            "mean_conf": sum(r["conf"] for r in rows) / len(rows),
            "ms_per_call": sum(c["ms"] for c in call_ms) / len(call_ms),
            "ms_per_question": sum(c["ms"] for c in call_ms) / len(rows),
            "input_tokens": tokens,
            "output_tokens": out_tokens,
            "cost_usd": app.cost_usd(name, {"input_tokens": tokens, "output_tokens": out_tokens}) if name in app.PRICE_PER_MTOK else 0.0,
            "by_category": {c: {"n": len(v), "accuracy": sum(r["correct"] for r in v) / len(v)} for c, v in cats.items()},
            "by_type": {c: {"n": len(v), "accuracy": sum(r["correct"] for r in v) / len(v)} for c, v in types.items()},
        }
        results["engines"][name] = {"summary": summ, "items": per_item, "calls": call_ms}
        print(f"[{name}] acc={summ['accuracy']:.3f} brier={summ['brier']:.3f} ece={summ['ece']:.3f} "
              f"{summ['ms_per_call']:.0f} ms/call {summ['ms_per_question']:.0f} ms/question "
              f"{summ['input_tokens']} tokens ${summ['cost_usd']:.4f}", flush=True)
        for c, v in summ["by_category"].items():
            print(f"   {c:12s} {v['accuracy']:.2f} (n={v['n']})")
        json.dump(results, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main()
