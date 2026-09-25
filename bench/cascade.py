"""System 1 answers, System 2 takes the cases it is least sure of. On the private hard set (benchmark 3):
first stage = Jev, DeepSeek logprobs or DeepSeek JSON mode; the least-confident share is re-answered by DeepSeek V4.1 Flash
with reasoning on. Writes bench/cascade.json and ~/reports/assets/jev-deck/cascade.png.
Run: .venv/bin/python bench/cascade.py"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from charts import C, INK, MUTED, RULE, save  # noqa: E402

R = json.load(open(os.path.join(HERE, "results_calib_private.json")))["engines"]
IDS = [it["id"] for it in json.load(open(os.path.join(HERE, "questions_calib_private.json")))["items"]]
N = len(IDS)
S2 = R["llm_think"]
FIRST = [("jev", "Jev first"), ("llm", "DeepSeek logprobs first"), ("llm_json", "DeepSeek JSON-mode confidence first")]
LABEL_AT = {"jev": (1, 4.2), "llm": (11, -3.4), "llm_json": (33, -3.4)}  # (x %, y offset in points of accuracy) for direct labels


def curve(key):
    it = R[key]["items"]; order = sorted(IDS, key=lambda i: it[i]["conf"])  # least confident first
    s1_cost, s2_cost = R[key]["summary"]["cost_usd"] / N, S2["summary"]["cost_usd"] / N
    s1_ms, s2_ms = R[key]["summary"]["ms_per_question"], S2["summary"]["ms_per_question"]
    pts = []
    for k in range(N + 1):
        esc = set(order[:k])
        acc = sum(S2["items"][i]["correct"] if i in esc else it[i]["correct"] for i in IDS) / N
        pts.append({"escalated": k / N, "accuracy": acc, "usd_per_1k": 1000 * (s1_cost + k / N * s2_cost), "ms_mean": s1_ms + k / N * s2_ms})
    return pts


out = {"n": N, "system2_alone": {"accuracy": S2["summary"]["accuracy"], "usd_per_1k": 1000 * S2["summary"]["cost_usd"] / N, "ms_per_question": S2["summary"]["ms_per_question"]},
       "curves": {k: curve(k) for k, _ in FIRST}}
for k, _ in FIRST:
    c = out["curves"][k]
    out.setdefault("to_95", {})[k] = next((p for p in c if p["accuracy"] >= 0.95), None)
json.dump(out, open(os.path.join(HERE, "cascade.json"), "w"), indent=1)

fig, ax = plt.subplots(figsize=(16.2, 7.6))
fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.2)
XMAX = 0.5
s2 = out["system2_alone"]["accuracy"]
ax.axhline(100 * s2, color=MUTED, lw=1.5, ls="--")
ax.text(1, 100 * s2 + 0.5, f"DeepSeek with reasoning on every question: {100*s2:.0f}%, 2.3 s per question", color=MUTED, fontsize=13)
ax.axhline(95, color=RULE, lw=1)
END_Y = {"jev": 97.2, "llm": 93.2, "llm_json": 88.4}          # label anchors, spaced so they never overlap
CALL = {"jev": (-150, 14), "llm": (12, -30), "llm_json": None}  # 95% callouts on opposite sides
for k, label in FIRST:
    c = [p for p in out["curves"][k] if p["escalated"] <= XMAX + 1e-9]
    xs = [100 * p["escalated"] for p in c]; ys = [100 * p["accuracy"] for p in c]
    ax.plot(xs, ys, color=C[k], lw=2.4)
    lx, dy = LABEL_AT[k]; ly = ys[min(range(len(xs)), key=lambda i: abs(xs[i] - lx))]
    ax.text(lx, ly + dy, f"{label} ({ys[0]:.0f}% alone)", fontsize=13, color=INK, fontweight="bold" if k == "jev" else "normal")
    t = out["to_95"][k]
    if t and t["escalated"] <= XMAX and CALL[k]:
        ax.plot([100 * t["escalated"]], [100 * t["accuracy"]], "o", color=C[k], ms=10, mec="white", mew=2, zorder=5)
        ax.annotate(f"95% with {100*t['escalated']:.0f}% escalated", (100 * t["escalated"], 100 * t["accuracy"]), xytext=CALL[k], textcoords="offset points", fontsize=12, color=INK)
ax.set_xlim(0, 100 * XMAX); ax.set_ylim(68, 100.5)
ax.set_xlabel("share of questions handed to DeepSeek with reasoning (least confident first), %"); ax.set_ylabel("accuracy, 300 private hard questions, %")
ax.grid(color=RULE); ax.set_axisbelow(True)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
ax.set_title("System 1 answers what it is sure of, System 2 takes the rest. The confidence decides what to escalate.", fontsize=16, pad=14)
fig.text(0.01, 0.03, "Private benchmark 3, single run. Escalation re-answers the least-confident questions with DeepSeek V4.1 Flash, logprob recipe, reasoning on (low effort).\nDashed: that model on every question. Thin line: 95%. JSON mode reaches 95% only after escalating 74%: its written confidence barely ranks right above wrong.", color=MUTED, fontsize=12)
save(fig, "cascade")
for k, _ in FIRST:
    t = out["to_95"][k]
    print(k, "alone", round(100 * out["curves"][k][0]["accuracy"], 1), "| 95% at", t and round(100 * t["escalated"]), "% escalated, $", t and round(t["usd_per_1k"], 3), "per 1k, mean", t and round(t["ms_mean"]), "ms/q")
print("S2 alone", out["system2_alone"])
