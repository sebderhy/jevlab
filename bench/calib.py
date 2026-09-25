"""Calibration analysis of bench/results_calib.json: reliability, Brier, ECE, AUROC, coverage at a target error rate.
Run: .venv/bin/python bench/calib.py  -> prints a table and writes ~/reports/assets/jev-deck/calib.png"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from charts import C, PAPER, INK, MUTED, RULE, save  # noqa: E402

# CALIB_SET="" -> the public set (ANLI r3 + CommonsenseQA); CALIB_SET=private -> our unpublished replica (private-nli + private-mcq).
SET = os.environ.get("CALIB_SET", "")
SUFFIX = f"_{SET}" if SET else ""
R = json.load(open(os.path.join(HERE, f"results_calib{SUFFIX}.json")))
Q = json.load(open(os.path.join(HERE, f"questions_calib{SUFFIX}.json")))
SUBSETS = ([("private-nli", "Private NLI, 150 items (hard entailment)"), ("private-mcq", "Private MCQ, 150 items (5-way)")] if SET == "private"
           else [("anli-r3", "ANLI round 3, 300 items (hard entailment)"), ("commonsenseqa", "CommonsenseQA, 200 items (5-way)")])
N_ALL = len(Q["items"])
ORIGIN = "private items written 23 Sep 2026, unpublished" if SET == "private" else "public datasets, seed 7"
BNAME = "Benchmark 3" if SET == "private" else "Benchmark 3, public version"
CAT = {it["id"]: it["category"] for it in Q["items"]}
ENG = [e for e in [("jev", "Jev"), ("llm", "DeepSeek V4.1 Flash, logprobs"), ("llm_json", "DeepSeek V4.1 Flash, JSON mode"), ("llm_think", "DeepSeek V4.1 Flash, logprobs, reasoning on"), ("decider", "Decider-2B, CPU"), ("kev", "Kev-4B, CPU")] if e[0] in R["engines"]]


def auroc(rows):
    """Does confidence rank correct answers above wrong ones? 0.5 = no information, 1 = perfect."""
    pos = [r["conf"] for r in rows if r["correct"]]; neg = [r["conf"] for r in rows if not r["correct"]]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def coverage(rows, max_err=0.05):
    """Largest share of questions you can auto-answer (highest confidence first) while keeping the error rate at or under max_err."""
    srt = sorted(rows, key=lambda r: -r["conf"])
    best, wrong = 0.0, 0
    for i, r in enumerate(srt, 1):
        wrong += not r["correct"]
        if wrong / i <= max_err:
            best = i / len(rows)
    return best


def bins(rows, n=10, min_n=8):
    out = []
    for b in range(n):
        lo, hi = b / n, (b + 1) / n
        sel = [r for r in rows if lo < r["conf"] <= hi]
        if len(sel) >= min_n:
            out.append((sum(r["conf"] for r in sel) / len(sel), sum(r["correct"] for r in sel) / len(sel), len(sel)))
    return out


GOLD = {it["id"]: it["gold"] for it in Q["items"]}


def _probs(rows):
    """Full probability vectors and the index of the gold option, for temperature scaling."""
    out = []
    for r in rows:
        p = r["answer"]["probabilities"]; labels = list(p)
        out.append(([max(p[l], 1e-6) for l in labels], labels.index(GOLD[r["_id"]])))
    return out


def _scale(vec, T):
    import math
    z = [math.log(v) / T for v in vec]; m = max(z); e = [math.exp(x - m) for x in z]; s = sum(e)
    return [x / s for x in e]


def fit_T(data):
    import math
    best, bestnll = 1.0, float("inf")
    for i in range(1, 400):
        T = i / 20
        nll = -sum(math.log(max(_scale(v, T)[g], 1e-9)) for v, g in data) / len(data)
        if nll < bestnll:
            best, bestnll = T, nll
    return best


def scaled_rows(rows, T):
    """Rows re-scored after temperature scaling with T (conf = max prob, correct unchanged)."""
    out = []
    for r, (v, g) in zip(rows, _probs(rows)):
        s = _scale(v, T)
        out.append({"correct": r["correct"], "conf": max(s), "brier": sum((s[i] - (1 if i == g else 0)) ** 2 for i in range(len(s)))})
    return out


def temperature_report(subset):
    """2-fold: fit T on one half of the subset, evaluate on the other, average. The 'practitioner with 150 labels' baseline."""
    from bench import ece
    print(f"\n== temperature scaling, {subset}, 2-fold (fit on half, test on the other half) ==")
    print(f"{'engine':32s} {'T':>5s} {'ece raw':>8s} {'ece cal':>8s} {'brier raw':>9s} {'brier cal':>9s}")
    for key, label in ENG:
        rows = [dict(v, _id=k) for k, v in R["engines"][key]["items"].items() if CAT[k] == subset]
        h = len(rows) // 2; folds = [(rows[:h], rows[h:]), (rows[h:], rows[:h])]
        Ts, e_raw, e_cal, b_raw, b_cal = [], [], [], [], []
        for fit, test in folds:
            T = fit_T(_probs(fit)); Ts.append(T)
            e_raw.append(ece(test)); b_raw.append(sum(r["brier"] for r in test) / len(test))
            sr = scaled_rows(test, T); e_cal.append(ece(sr)); b_cal.append(sum(r["brier"] for r in sr) / len(sr))
        avg = lambda x: sum(x) / len(x)
        print(f"{label:32s} {avg(Ts):5.2f} {avg(e_raw):8.3f} {avg(e_cal):8.3f} {avg(b_raw):9.3f} {avg(b_cal):9.3f}")


def table(subset=None):
    print(f"\n== {subset or f'all {N_ALL}'} ==")
    print(f"{'engine':32s} {'n':>4s} {'acc':>6s} {'brier':>6s} {'ece':>6s} {'auroc':>6s} {'cov5%':>6s} {'cov2%':>6s} {'mean conf':>9s}")
    for key, label in ENG:
        rows = [dict(v, _id=k) for k, v in R["engines"][key]["items"].items() if subset is None or CAT[k] == subset]
        acc = sum(r["correct"] for r in rows) / len(rows)
        brier = sum(r["brier"] for r in rows) / len(rows)
        from bench import ece
        print(f"{label:32s} {len(rows):4d} {acc:6.3f} {brier:6.3f} {ece(rows):6.3f} {auroc(rows):6.3f} {coverage(rows):6.2f} {coverage(rows, 0.02):6.2f} {sum(r['conf'] for r in rows)/len(rows):9.3f}")


def chart():
    fig, axs = plt.subplots(1, 2, figsize=(16.2, 7.6))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.86, bottom=0.2, wspace=0.25)
    ENG_CH = [e for e in ENG if e[0] != "llm_think"]
    for ax, (subset, title) in zip(axs, SUBSETS):
        ax.plot([0, 1], [0, 1], color=RULE, lw=2, ls="--")
        for (key, label), mk in zip(ENG_CH, ["o", "s", "D", "^", "v", "P"]):
            rows = [dict(v, _id=k) for k, v in R["engines"][key]["items"].items() if CAT[k] == subset]
            b = bins(rows)
            ax.scatter([x for x, _, _ in b], [y for _, y, _ in b], s=[30 + 3 * n for _, _, n in b], color=C[key], marker=mk, zorder=3,
                       label=f"{label}: acc {100*sum(r['correct'] for r in rows)/len(rows):.0f}%, ECE {__import__('bench').ece(rows):.2f}")
        ax.set_xlim(0.2, 1.02); ax.set_ylim(0.2, 1.02); ax.set_xlabel("stated confidence"); ax.set_ylabel("share actually correct")
        ax.set_title(title, fontsize=15, pad=10); ax.grid(color=RULE); ax.set_axisbelow(True); ax.legend(loc="upper left", frameon=False, fontsize=11)
    fig.suptitle(f"{BNAME}: when the models are often wrong, whose probabilities can you trust?", fontsize=17, y=0.95)
    fig.text(0.02, 0.04, f"10 confidence bins, bins with fewer than 8 answers hidden, marker size = answers in the bin. Below the dashed line = over-confident. {ORIGIN.capitalize()}.\nLogprobs: probability of the chosen letter, renormalised over the options. JSON mode: the confidence the model wrote next to its answer.", color=MUTED, fontsize=12)
    save(fig, "calib" + SUFFIX.replace("_", "-"))


if __name__ == "__main__":
    table(); table(SUBSETS[0][0]); table(SUBSETS[1][0])
    temperature_report(SUBSETS[0][0]); temperature_report(SUBSETS[1][0])
    chart()


def trust_chart():
    """Coverage at a 5% error budget and AUROC, per dataset: the practical value of a probability."""
    fig, axs = plt.subplots(1, 2, figsize=(16.2, 7.0))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.27, wspace=0.25)
    subsets = [(SUBSETS[0][0], SUBSETS[0][1].split(",")[0]), (SUBSETS[1][0], SUBSETS[1][1].split(",")[0]), (None, f"all {N_ALL}")]
    for ax, metric, title, fmt in [(axs[0], coverage, "Share of questions you can auto-answer at a 5% error budget", lambda v: f"{100*v:.0f}%"),
                                   (axs[1], auroc, "Does confidence rank right answers above wrong ones? (AUROC)", lambda v: f"{v:.2f}")]:
        ENG_CH = [e for e in ENG if e[0] != "llm_think"]
        w = 0.8 / len(ENG_CH)
        for j, (key, label) in enumerate(ENG_CH):
            vals = [metric([dict(v, _id=k) for k, v in R["engines"][key]["items"].items() if s is None or CAT[k] == s]) for s, _ in subsets]
            xs = [i + (j - (len(ENG_CH) - 1) / 2) * w for i in range(len(subsets))]
            ax.bar(xs, vals, w, color=C[key], label=label, edgecolor=PAPER, linewidth=2)
            for x, v in zip(xs, vals):
                ax.text(x, max(v, 0.5 if metric is auroc else 0) + (0.01 if metric is coverage else 0.008), fmt(v), ha="center", fontsize=12)
        ax.set_xticks(range(len(subsets)), [t for _, t in subsets], fontsize=13)
        ax.set_title(title, fontsize=14, pad=10); ax.grid(axis="y", color=RULE); ax.set_axisbelow(True)
        if metric is coverage:
            ax.set_ylim(0, 1.12); ax.set_ylabel("share of questions")
        else:
            ax.set_ylim(0.5, 1.0); ax.set_ylabel("AUROC, 0.5 = no information"); ax.axhline(0.5, color=MUTED, lw=1)
    fig.legend(*axs[0].get_legend_handles_labels(), loc="lower center", ncol=5, frameon=False, fontsize=12, bbox_to_anchor=(0.5, 0.11))
    fig.suptitle(f"{BNAME}: what a probability is for. Automate the sure ones, hand the rest to a person.", fontsize=16, y=0.95)
    fig.text(0.02, 0.04, f"Coverage: sort by stated confidence, take answers from the top until the error rate among them would exceed 5%. Neither number changes under temperature scaling,\nbecause scaling keeps the order: this is the part of calibration you cannot fix with 150 labels afterwards. {N_ALL} items, {ORIGIN}, single run, Sep 2026.", color=MUTED, fontsize=12)
    save(fig, "trust" + SUFFIX.replace("_", "-"))


if __name__ == "__main__":
    trust_chart()
