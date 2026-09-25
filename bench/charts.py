"""Charts for the Jev deck, generated from bench/results.json, bench/results_long.json and bench/meter.json.
Run: /home/seb/jevlab/.venv/bin/python bench/charts.py [names...]   -> ~/reports/assets/jev-deck/<name>.png"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.expanduser("~/reports/assets/jev-deck")
PAPER, INK, MUTED, RULE = "#f7f4ee", "#1c1a17", "#6f665a", "#d9d2c4"
C = {"jev": "#d6407f", "llm": "#2a78d6", "llm_json": "#eda100", "llm_think": "#17407a", "decider": "#4a3aa7", "kev": "#008300", "laya": "#e34948", "kotoba": "#1baf7a", "gliner_b": "#eb6834"}  # validated: dataviz validate_palette.js, bench1 order, light
LABEL = {"jev": "Jev (TypeSafe, hosted)", "llm": "DeepSeek V4.1 Flash, logprobs\n1 call per question",
         "llm_json": "DeepSeek V4.1 Flash, JSON mode\n1 call per state",
         "llm_think": "DeepSeek V4.1 Flash, logprobs\nwith reasoning on",
         "laya": "Laya, 421M, CPU", "kotoba": "kotoba open-jev, 435M, CPU", "gliner_b": "GLiNER2.5, 287M, CPU", "decider": "Decider-2B (Qwen3.5), CPU", "kev": "Kev-4B (Qwen3.5), CPU"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 15, "axes.edgecolor": INK, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "text.color": INK, "figure.facecolor": PAPER,
                     "axes.facecolor": PAPER, "savefig.facecolor": PAPER, "axes.spines.top": False, "axes.spines.right": False})
R1 = json.load(open(os.path.join(HERE, "results.json")))
R2 = json.load(open(os.path.join(HERE, "results_long.json"))) if os.path.exists(os.path.join(HERE, "results_long.json")) else None
Q1 = json.load(open(os.path.join(HERE, "questions.json")))
METER = json.load(open(os.path.join(HERE, "meter.json")))
HARD = {it["id"] for it in Q1["items"][74:]}


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=120)
    plt.close(fig)
    print("wrote", name)


def tier_acc(items, ids):
    rows = [items[i] for i in ids]
    return 100 * sum(r["correct"] for r in rows) / len(rows)


def bench1():
    eng = [e for e in ["jev", "llm", "llm_json", "decider", "kev", "laya", "kotoba", "gliner_b"] if e in R1["engines"]]
    easy = [i for i in R1["engines"]["jev"]["items"] if i not in HARD]
    hard = [i for i in R1["engines"]["jev"]["items"] if i in HARD]
    fig, ax = plt.subplots(figsize=(16.2, 8.4))
    fig.subplots_adjust(left=0.24, right=0.97, top=0.90, bottom=0.14)
    y = list(range(len(eng)))[::-1]
    for yi, e in zip(y, eng):
        it = R1["engines"][e]["items"]
        a, b = tier_acc(it, easy), tier_acc(it, hard)
        ax.barh(yi + 0.19, a, 0.36, color=C[e])
        ax.barh(yi - 0.19, b, 0.36, color=C[e], alpha=0.45, hatch="///", edgecolor=PAPER)
        ax.text(a + 1, yi + 0.19, f"{a:.0f}%", va="center", fontsize=15)
        ax.text(b + 1, yi - 0.19, f"{b:.0f}%", va="center", fontsize=15)
    ax.set_yticks(y, [LABEL[e] for e in eng], fontsize=15)
    ax.set_xlim(0, 112); ax.set_xlabel("accuracy, %"); ax.grid(axis="x", color=RULE); ax.set_axisbelow(True)
    ax.set_title("Benchmark 1: 100 short cases. Solid: 74 everyday questions. Hatched: 26 harder ones.", fontsize=17, pad=14)
    ax.legend(handles=[Patch(color=INK, label="74 everyday questions"), Patch(facecolor=INK, alpha=0.35, hatch="///", label="26 harder questions")],
              loc="lower right", frameon=False, fontsize=14)
    fig.text(0.01, 0.02, "Harder tier: multi-hop, negation, pragmatics, arithmetic, sarcasm, word-count and format rules. Single run, Sep 2026. Dataset and results published with the deck.", color=MUTED, fontsize=13)
    save(fig, "bench1")


def reliability():
    fig, ax = plt.subplots(figsize=(8.6, 8.4))
    fig.subplots_adjust(left=0.14, right=0.97, top=0.90, bottom=0.17)
    ax.plot([0, 1], [0, 1], color=RULE, lw=2, ls="--", zorder=1)
    for e, mk in [("jev", "o"), ("llm", "s"), ("llm_json", "D")]:
        rows = list(R1["engines"][e]["items"].values())
        xs, ys, ns = [], [], []
        for b in range(10):
            lo, hi = b / 10, (b + 1) / 10
            sel = [r for r in rows if lo < r["conf"] <= hi]
            if sel:
                xs.append(sum(r["conf"] for r in sel) / len(sel)); ys.append(sum(r["correct"] for r in sel) / len(sel)); ns.append(len(sel))
        ax.scatter(xs, ys, s=[40 + 6 * n for n in ns], color=C[e], marker=mk, alpha=0.85, zorder=3,
                   label=f"{ {'jev': 'Jev', 'llm': 'DeepSeek V4.1 Flash, logprobs', 'llm_json': 'DeepSeek V4.1 Flash, JSON + stated confidence'}[e] }: ECE {R1['engines'][e]['summary']['ece']:.3f}, Brier {R1['engines'][e]['summary']['brier']:.3f}")
    ax.set_xlim(0.45, 1.02); ax.set_ylim(0.45, 1.02)
    ax.set_xlabel("stated confidence"); ax.set_ylabel("share actually correct")
    ax.set_title("Reliability: when it says 0.6, is it right 60% of the time?", fontsize=16, pad=12)
    ax.grid(color=RULE); ax.set_axisbelow(True); ax.legend(loc="center left", bbox_to_anchor=(0.02, 0.62), frameon=False, fontsize=12)
    fig.text(0.02, 0.03, "Benchmark 1, 100 questions each. Marker size = number of answers in that confidence bin.\nOn the dashed line the model is perfectly honest about its own uncertainty.", color=MUTED, fontsize=12)
    save(fig, "reliability")


def meter():
    fig, ax = plt.subplots(figsize=(10.4, 8.4))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.9, bottom=0.22)
    pts = [m for m in METER if "q_words" not in m]
    for nq, ls in [(1, "-"), (20, "--")]:
        sel = sorted([m for m in pts if m["n_questions"] == nq], key=lambda m: m["words"])
        ax.plot([m["words"] for m in sel], [m["input_tokens"] for m in sel], ls=ls, marker="o", color=C["jev"], lw=2.5, label=f"Jev, {nq} question{'s' if nq>1 else ''} per call")
    ax.plot([0, 3000], [5, 3316], color=C["llm"], lw=2.5, marker="s", label="DeepSeek V4.1 Flash, same text, 1 question")
    ax.annotate("276 tokens billed for a\n1-word state and 1 question", xy=(1, 276), xytext=(650, 40), fontsize=14,
                arrowprops=dict(arrowstyle="->", color=INK, connectionstyle="arc3,rad=0.25"), color=INK)
    ax.set_xlabel("state length, words"); ax.set_ylabel("input tokens billed per call")
    ax.set_title("Jev's meter: a fixed 260-token entry fee, then about 1 token per word", fontsize=16, pad=12)
    ax.grid(color=RULE); ax.set_axisbelow(True); ax.legend(loc="upper left", frameon=False, fontsize=13, bbox_to_anchor=(0, 0.88))
    fig.text(0.02, 0.03, "Measured Sep 20 2026: a repeated business paragraph, one-line yes/no questions. Fit: 260 fixed\n+ about 16 per tiny question + the state. The state count matched DeepSeek's tokenizer to the token\n(3,311 for 3,000 words). Latency stayed between 550 and 750 ms across the whole grid.", color=MUTED, fontsize=12)
    save(fig, "meter")


def costscale():
    """Analytic: cost per document with 10 questions, from the measured meters and list prices."""
    import numpy as np
    S = np.linspace(20, 8000, 400)
    q_txt, nq = 30, 10  # tokens per question text
    jev = (260 + S + nq * (8 + q_txt)) * 0.042 / 1e6
    ds_lp = nq * (S + 25 + q_txt + 15) * 0.30 / 1e6 + nq * 1 * 1.20 / 1e6
    ds_js = (S + 60 + nq * (q_txt + 12)) * 0.30 / 1e6 + nq * 18 * 1.20 / 1e6
    fig, ax = plt.subplots(figsize=(10.4, 8.4))
    fig.subplots_adjust(left=0.13, right=0.97, top=0.9, bottom=0.22)
    ax.plot(S, 100 * ds_lp, color=C["llm"], lw=2.5, label="DeepSeek V4.1 Flash, logprobs: state resent 10 times")
    ax.plot(S, 100 * ds_js, color=C["llm_json"], lw=2.5, label="DeepSeek V4.1 Flash, JSON mode: state once, pays for output")
    ax.plot(S, 100 * jev, color=C["jev"], lw=2.5, label="Jev: state once, output free")
    ax.set_yscale("log"); ax.set_xlabel("document length, tokens"); ax.set_ylabel("cost per document with 10 questions, cents (log)")
    ax.set_title("Where the price gap opens: long documents, many questions", fontsize=16, pad=12)
    ax.grid(color=RULE, which="both"); ax.set_axisbelow(True); ax.legend(loc="lower right", frameon=False, fontsize=12)
    for x, lab in [(45, "benchmark 1:\n~45-token states"), (2000, "benchmark 2:\n~2,000-token documents")]:
        ax.axvline(x, color=MUTED, ls=":", lw=1.2); ax.text(x + 80, 100 * ds_lp[-1] * 0.75, lab, color=MUTED, fontsize=12, va="top")
    r = ds_lp / jev; r2 = ds_js / jev
    fig.text(0.02, 0.03, f"List prices: Jev \\$0.042 per M input tokens, output free; DeepSeek V4.1 Flash on Fireworks \\$0.30 in,\n\\$1.20 out. Questions of 30 tokens. Cost ratio to Jev at 45 / 2,000 / 8,000 tokens: logprobs {r[1]:.0f}x / {r[100]:.0f}x / {r[-1]:.0f}x,\nJSON mode {r2[1]:.0f}x / {r2[100]:.0f}x / {r2[-1]:.0f}x. Measured runs on the next slides land close to these lines.", color=MUTED, fontsize=12)
    save(fig, "costscale")


def ood():
    fig, ax = plt.subplots(figsize=(8.6, 7.2))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.84, bottom=0.22)
    x = [0, 1]
    v, j = [77, 48], [73, 91]
    ax.bar([i - 0.2 for i in x], v, 0.38, color="#3d6b4f", label="Verdict, 151M encoder fine-tuned on labelled decisions")
    ax.bar([i + 0.2 for i in x], j, 0.38, color=C["jev"], label="Jev, zero-shot")
    for xi, val in zip([-0.2, 0.8, 0.2, 1.2], v[:1] + v[1:] + j[:1] + j[1:]):
        ax.text(xi, val + 1.5, f"{val}%", ha="center", fontsize=16)
    ax.set_xticks(x, ["the workflow it was trained on\n(2,000 held-out cases)", "TypeSafe's own external cases\n(337, never seen)"], fontsize=14)
    ax.set_ylim(0, 108); ax.set_ylabel("accuracy, %"); ax.grid(axis="y", color=RULE); ax.set_axisbelow(True)
    ax.set_title("With labelled examples a tiny local model wins.\nOn questions it never saw, it collapses.", fontsize=16, pad=12)
    ax.legend(loc="upper center", frameon=False, fontsize=12, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.02, 0.03, "Community project (Heman10x, ModernBERT-large, 20 to 25 ms on a laptop). Left: Verdict 2.0\non the LocalLLaMA typed-decisions set. Right: Verdict v1 on TypeSafe's external eval. Two\nversions, so read the gap as a pattern, not a number. kotoba open-jev: 85% in, 69% out.", color=MUTED, fontsize=11.5)
    save(fig, "ood")


def bench2():
    eng = [e for e in ["jev", "llm", "llm_json", "decider", "kev"] if e in R2["engines"]]
    hosted = [e for e in eng if e in ("jev", "llm", "llm_json")]  # cost and latency: hosted APIs only; the CPU clones are a different hardware class
    fig, axs = plt.subplots(1, 3, figsize=(16.2, 7.2), gridspec_kw={"width_ratios": [1.45, 1, 1]})
    fig.subplots_adjust(left=0.05, right=0.98, top=0.82, bottom=0.22, wspace=0.3)
    S = {e: R2["engines"][e]["summary"] for e in eng}
    short = {"jev": "Jev", "llm": "DeepSeek\nlogprobs", "llm_json": "DeepSeek\nJSON", "decider": "Decider-2B\nCPU", "kev": "Kev-4B\nCPU"}
    for ax, key, title, fmt, es in [(axs[0], "accuracy", "accuracy, 100 questions", lambda v: f"{100*v:.0f}%", eng),
                                    (axs[1], "cost_usd", "cost of the run, USD", lambda v: f"${v:.4f}", hosted),
                                    (axs[2], "ms_per_question", "latency per question, ms", lambda v: f"{v:.0f}", hosted)]:
        vals = [S[e][key] * (100 if key == "accuracy" else 1) for e in es]
        ax.bar(range(len(es)), vals, 0.66, color=[C[e] for e in es], edgecolor=PAPER, linewidth=2)
        for i, v in enumerate(vals):
            ax.text(i, v * 1.02 + (1 if key == "accuracy" else 0), fmt(v / (100 if key == "accuracy" else 1)), ha="center", fontsize=14)
        ax.set_xticks(range(len(es)), [short[e] for e in es], fontsize=12); ax.set_title(title, fontsize=15, pad=10); ax.grid(axis="y", color=RULE); ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        if key == "accuracy":
            ax.set_ylim(0, 112)
    loc = "; ".join(f"{short[e].split(chr(10))[0]} {S[e]['ms_per_question']/1000:.0f} s per question" for e in eng if e not in hosted)
    fig.suptitle("Benchmark 2: 10 documents of 900 to 1,150 words, 10 questions each", fontsize=17, y=0.95)
    fig.text(0.02, 0.025, f"Jev and JSON mode: one call per document. Logprobs: one call per question, the document resent each time, questions in parallel. Latency measured from the box.\nLocal clones run free on this 12-core CPU and are left out of cost and latency: {loc}; a GPU would be sub-second. Single run, Sep 2026.", color=MUTED, fontsize=12)
    save(fig, "bench2")


def heatmap():
    import numpy as np
    eng = [e for e in ["jev", "llm", "llm_json", "decider", "kev", "laya", "kotoba", "gliner_b"] if e in R1["engines"]]
    cats = list(R1["engines"]["jev"]["summary"]["by_category"].keys())
    M = np.array([[100 * R1["engines"][e]["summary"]["by_category"][c]["accuracy"] for c in cats] for e in eng])
    fig, ax = plt.subplots(figsize=(17.5, 7.6))
    fig.subplots_adjust(left=0.24, right=0.99, top=0.9, bottom=0.2)
    ax.imshow(M, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    for i in range(len(eng)):
        for j in range(len(cats)):
            ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=15, color="white" if M[i, j] > 60 else INK)
    ax.set_xticks(range(len(cats)), cats, rotation=35, ha="right", fontsize=14)
    ax.set_yticks(range(len(eng)), [LABEL[e].replace("\n", ", ") for e in eng], fontsize=14)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("Benchmark 1: accuracy by category, % correct", fontsize=17, pad=12, loc="left")
    fig.text(0.02, 0.03, "100 questions, 13 categories, n = 4 to 14 per category. Single run, Sep 2026.", color=MUTED, fontsize=13)
    save(fig, "heatmap")


def costbars():
    """Measured cost per 1,000 questions, benchmark 1 (short cases) and benchmark 2 (long documents), linear scale."""
    eng = [e for e in ["jev", "llm", "llm_json", "llm_think"] if e in R1["engines"] and e in R2["engines"]]
    names = [{"jev": "Jev", "llm": "DeepSeek\nlogprobs", "llm_json": "DeepSeek\nJSON mode", "llm_think": "DeepSeek\nreasoning on"}[e] for e in eng]
    short = [R1["engines"][e]["summary"]["cost_usd"] * 1000 for e in eng]   # 100 questions -> per 1,000, in cents: *10*100
    long_ = [R2["engines"][e]["summary"]["cost_usd"] * 1000 for e in eng]
    fig, axs = plt.subplots(1, 2, figsize=(10.4, 8.4))
    fig.subplots_adjust(left=0.1, right=0.98, top=0.86, bottom=0.24, wspace=0.3)
    for ax, vals, title in [(axs[0], short, "Benchmark 1: short cases\n(2 to 4 sentences, 1 to 2 questions each)"), (axs[1], long_, "Benchmark 2: long documents\n(1,000 words, 10 questions each)")]:
        ax.bar(range(len(eng)), vals, 0.62, color=[C[e] for e in eng])
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals) * 0.02, f"{v:.1f}¢" + ("" if i == 0 else f"\n{v / vals[0]:.0f}x Jev"), ha="center", fontsize=13, va="bottom")
        ax.set_xticks(range(len(eng)), names, fontsize=11); ax.set_title(title, fontsize=14, pad=10)
        ax.set_ylim(0, max(vals) * 1.25); ax.grid(axis="y", color=RULE); ax.set_axisbelow(True)
        ax.set_ylabel("cents per 1,000 questions, measured", fontsize=13)
    fig.suptitle("What we actually paid per 1,000 questions: Jev vs DeepSeek V4.1 Flash", fontsize=16, y=0.96)
    fig.text(0.02, 0.03, "Usage as reported by each API, at list prices (Jev \\$0.042 per M input tokens, output free;\nDeepSeek V4.1 Flash on Fireworks \\$0.30 in, \\$1.20 out). Jev's 260-token entry fee is what keeps\nthe short-case gap at 2x; on long documents it reads the text once and pays nothing for output.", color=MUTED, fontsize=12)
    save(fig, "costbars")


if __name__ == "__main__":
    names = sys.argv[1:] or ["bench1", "reliability", "meter", "costbars", "ood", "heatmap"] + (["bench2"] if R2 else [])
    for n in names:
        globals()[n]()
