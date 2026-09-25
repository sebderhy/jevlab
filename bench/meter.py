"""Measure Jev's token meter: billed input tokens vs state length and question count.
Writes bench/meter.json. Cost of a full run is well under one cent."""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app

KEY = app.load_jev()
PARA = ("The quarterly review covered three regions. Sales in the north rose four percent while the south stayed flat. "
        "The logistics team reported two late shipments, both resolved within a day. Marketing asked for a larger "
        "budget for the autumn campaign and finance agreed to a ten percent increase. ")  # ~58 words

def state_of(words):
    txt = ""
    while len(txt.split()) < words:
        txt += PARA
    return " ".join(txt.split()[:words])

def q_of(n):
    return {f"q{i}": {"type": "noul", "instructions": f"Statement {i}: the text mentions sales."} for i in range(n)}

def call(state, qs):
    body = {"model": "jev-latest", "state": state, "questions": qs}
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t = time.time(); r = json.load(urllib.request.urlopen(req, timeout=120)); ms = (time.time() - t) * 1000
    return r["usage"], ms

rows = []
for words in [1, 75, 375, 750, 1500, 3000]:
    st = state_of(words)
    for nq in [1, 5, 10, 20]:
        u, ms = call(st, q_of(nq))
        rows.append({"words": words, "chars": len(st), "n_questions": nq, "input_tokens": u["input_tokens"],
                     "output_tokens": u.get("output_tokens") or 0, "ms": round(ms)})
        print(rows[-1], flush=True)
# same question text length sensitivity: 1 question of 5 / 50 / 200 words on a 1-word state
for qw in [5, 50, 200]:
    qs = {"q0": {"type": "noul", "instructions": " ".join(["word"] * qw)}}
    u, ms = call("x", qs)
    rows.append({"words": 1, "chars": 1, "n_questions": 1, "q_words": qw, "input_tokens": u["input_tokens"],
                 "output_tokens": u.get("output_tokens") or 0, "ms": round(ms)})
    print(rows[-1], flush=True)
json.dump(rows, open(os.path.join(os.path.dirname(__file__), "meter.json"), "w"), indent=1)
