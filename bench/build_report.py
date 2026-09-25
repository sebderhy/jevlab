"""Render bench/results.json + bench/questions.json into a self-contained HTML report.
Run: cd ~/jevlab && .venv/bin/python bench/build_report.py ~/reports/typed-decision-models-benchmark.html
"""
import html, json, os, shutil, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "report.html")
R = json.load(open(os.path.join(HERE, "results.json")))
B = json.load(open(os.path.join(HERE, "questions.json")))
ITEMS = B["items"]
STATES = B["states"]
R2 = json.load(open(os.path.join(HERE, "results_long.json"))) if os.path.exists(os.path.join(HERE, "results_long.json")) else None
R3 = json.load(open(os.path.join(HERE, "results_calib.json"))) if os.path.exists(os.path.join(HERE, "results_calib.json")) else None
B2 = json.load(open(os.path.join(HERE, "questions_long.json"))) if R2 else None

ENGINES = [  # display order = categorical slot order (validated palette, adjacent pairs)
    ("jev",      "Jev (TypeSafe)", "jev-latest via api.typesafe.ai, the real System One model, one request per state", "#d6407f", "TypeSafe cloud, $0.042/MTok"),
    ("llm",      "DeepSeek V4.1 Flash, logprobs", "one request per question on Fireworks, one-letter answer, top logprobs read as probabilities", "#2a78d6", "Fireworks cloud, $0.30/MTok in, $1.20/MTok out"),
    ("llm_json", "DeepSeek V4.1 Flash, JSON mode", "one request per state on Fireworks, every question answered in one JSON object with a stated confidence", "#eda100", "Fireworks cloud, $0.30/MTok in, $1.20/MTok out"),
    ("llm_think", "DeepSeek V4.1 Flash, logprobs, reasoning on", "same one-letter request with the model's thinking enabled (low effort); the answer letter's logprobs are read after the thinking, which is kept as an explanation", "#17407a", "Fireworks cloud, $0.30/MTok in, $1.20/MTok out"),
    ("decider",  "Decider-2B",    "Qwen3.5-2B fully fine-tuned into a one-pass typed-decision model, v10 of Sep 22 (Mapika/decider, Apache 2.0); fp32 on CPU", "#4a3aa7", "this box, CPU"),
    ("kev",      "Kev-4B",        "Qwen3.5-4B-Base plus a rank-16 LoRA and a pointer head that scores each option, trained on public datasets (jaredpalmer/kev, Apache 2.0); fp32 on CPU", "#008300", "this box, CPU"),
    ("laya",     "Laya",          "ModernBERT-large, 421M, RLCD-trained Jev clone (convaiinnovations/laya, Apache 2.0)", "#e34948", "this box, CPU"),
    ("kotoba",   "kotoba open-jev", "DeBERTa-v3-large, 435M, typed-decisions head (com-kotobalabs/open-jev-deberta-v3-large)", "#1baf7a", "this box, CPU"),
    ("gliner_b", "GLiNER2.5 multi", "mDeBERTa-v3-base, 287M, Fastino extraction model used as a zero-shot classifier (fastino/gliner2.5-multi-v1, Apache 2.0)", "#eb6834", "this box, CPU"),
]
ENGINES = [e for e in ENGINES if e[0] in R["engines"]]
CATS = list(dict.fromkeys(it["category"] for it in ITEMS))
CAT_DESC = {
    "reading": "true/false statements about a short passage, with negation traps; harder tier adds distractor-heavy policies",
    "sentiment": "3-level ordered score: negative, neutral, positive; harder tier adds sarcasm and mixed reviews",
    "intent": "5-way customer-message intent with option descriptions",
    "moderation": "4-way forum post rule check",
    "entailment": "does the hypothesis follow from the premise",
    "routing": "4-way support ticket routing",
    "urgency": "does the ticket need a reply within the hour",
    "compliance": "did the response follow the instruction; harder tier adds word limits, JSON-only and exactly-one-option rules",
    "numbers": "comparisons of prices, times, counts; harder tier adds percentages, durations and ages",
    "language": "which of 4 languages is the text in",
    "multi-hop": "harder tier: chain two facts or a rule and a case before answering",
    "negation": "harder tier: double negatives and 'unless' clauses",
    "pragmatics": "harder tier: what is implied but not said (indirect refusals, soft commitments, intent behind a question)",
}


def pct(x):
    return f"{100*x:.0f}%"


def money(x):
    return "$0 (your CPU)" if x == 0 else f"${x:.4f}"


def esc(s):
    return html.escape(str(s))


def state_text(s):
    return s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)


def reliability(rows, bins=5):
    out = []
    for b in range(bins):
        lo, hi = 0.5 + b * 0.5 / bins, 0.5 + (b + 1) * 0.5 / bins
        sel = [r for r in rows if lo < r["conf"] <= hi or (b == 0 and r["conf"] == lo)]
        if sel:
            out.append((f"{lo:.1f} to {hi:.1f}", len(sel), sum(r["conf"] for r in sel) / len(sel), sum(r["correct"] for r in sel) / len(sel)))
    return out


# ---------- summary table ----------
summary_rows = ""
for key, label, detail, color, where in ENGINES:
    s = R["engines"][key]["summary"]
    summary_rows += f"""<tr><td><span class="sw" style="background:{color}"></span><b>{esc(label)}</b><div class="sub">{esc(detail)}</div></td>
      <td class="num">{pct(s['accuracy'])}</td><td class="num">{s['brier']:.3f}</td><td class="num">{s['ece']:.3f}</td>
      <td class="num">{s['ms_per_question']:.0f} ms</td><td class="num">{s['ms_per_call']:.0f} ms</td>
      <td class="num">{s.get('input_tokens', 0):,}</td><td class="num">{money(s.get('cost_usd', 0))}</td><td>{esc(where)}</td></tr>"""

# ---------- per-category data for the chart + table ----------
cat_table = "<tr><th>Category</th><th>n</th>" + "".join(f"<th>{esc(l)}</th>" for _, l, *_ in ENGINES) + "</tr>"
chart_series = []
for key, label, detail, color, _ in ENGINES:
    bc = R["engines"][key]["summary"]["by_category"]
    chart_series.append({"name": label, "color": color, "y": [round(100 * bc[c]["accuracy"]) for c in CATS]})
for c in CATS:
    n = R["engines"][ENGINES[0][0]]["summary"]["by_category"][c]["n"]
    cat_table += f"<tr><td><b>{esc(c)}</b><div class='sub'>{esc(CAT_DESC.get(c, ''))}</div></td><td class='num'>{n}</td>"
    for key, *_ in ENGINES:
        a = R["engines"][key]["summary"]["by_category"][c]["accuracy"]
        cls = "good" if a >= 0.9 else ("mid" if a >= 0.7 else "bad")
        cat_table += f"<td class='num {cls}'>{pct(a)}</td>"
    cat_table += "</tr>"

# ---------- reliability ----------
rel_html = ""
for key, label, *_ in ENGINES:
    rows = list(R["engines"][key]["items"].values())
    rel_html += f"<div class='rel'><h4>{esc(label)}</h4><table><tr><th>confidence</th><th>n</th><th>mean conf</th><th>accuracy</th></tr>"
    for rng, n, mc, acc in reliability(rows):
        rel_html += f"<tr><td>{rng}</td><td class='num'>{n}</td><td class='num'>{mc:.2f}</td><td class='num'>{acc:.2f}</td></tr>"
    rel_html += "</table></div>"

# ---------- per-item table ----------
item_rows = ""
for it in ITEMS:
    opts = it.get("options") or it.get("levels")
    opt_txt = ", ".join(opts.keys() if isinstance(opts, dict) else opts) if opts else "true / false"
    item_rows += f"<tr><td class='mono'>{it['id']}</td><td>{esc(state_text(STATES[it['state']]))}</td><td>{esc(it['instructions'])}<div class='sub'>{it['type']}: {esc(opt_txt)}</div></td><td><b>{esc(it['gold'])}</b></td>"
    for key, *_ in ENGINES:
        row = R["engines"][key]["items"][it["id"]]
        p = row["p_gold"]
        cls = "good" if row["correct"] else "bad"
        item_rows += f"<td class='{cls}'>{esc(row['pred'])}<div class='sub'>p(gold) {p:.2f}</div></td>"
    item_rows += "</tr>"

n_items, n_states = R["n_items"], R["n_states"]
best_open = max((e for e in ENGINES if e[0] not in ("llm", "llm_json", "llm_think", "jev")), key=lambda e: R["engines"][e[0]]["summary"]["accuracy"])
llm_acc = R["engines"]["llm"]["summary"]["accuracy"] if "llm" in R["engines"] else None

long_section = ""
if R2:
    E2 = [e for e in ENGINES if e[0] in R2["engines"]]
    rows2 = ""
    for key, label, detail, color, where in E2:
        t = R2["engines"][key]["summary"]
        rows2 += f"""<tr><td><span class="sw" style="background:{color}"></span><b>{esc(label)}</b><div class="sub">{esc(detail)}</div></td>
          <td class="num">{pct(t['accuracy'])}</td><td class="num">{t['brier']:.3f}</td><td class="num">{t['ece']:.3f}</td>
          <td class="num">{t['ms_per_question']:.0f} ms</td><td class="num">{t['ms_per_call']:.0f} ms</td>
          <td class="num">{t.get('input_tokens', 0):,}</td><td class="num">{money(t.get('cost_usd', 0))}</td></tr>"""
    items2 = ""
    for it in B2["items"]:
        opts = it.get("options") or it.get("levels")
        if isinstance(opts, str):
            opts = B2["option_sets"][opts]
        opt_txt = ", ".join(opts.keys() if isinstance(opts, dict) else opts) if opts else "true / false"
        items2 += f"<tr><td class='mono'>{it['id']}</td><td>{esc(it['state'])}</td><td>{esc(it['instructions'])}<div class='sub'>{it['type']}: {esc(opt_txt)}</div></td><td><b>{esc(it['gold'])}</b><div class='sub'>{esc(it.get('why', ''))}</div></td>"
        for key, *_ in E2:
            row = R2["engines"][key]["items"][it["id"]]
            items2 += f"<td class='{'good' if row['correct'] else 'bad'}'>{esc(row['pred'])}<div class='sub'>p(gold) {row['p_gold']:.2f}</div></td>"
        items2 += "</tr>"
    words = [len(v.split()) for v in B2["states"].values()]
    j, l, jn = R2["engines"]["jev"]["summary"], R2["engines"]["llm"]["summary"], R2["engines"]["llm_json"]["summary"]
    long_section = f"""
<h2>Benchmark 2: ten long documents, ten questions each</h2>
<p class="lede">The first benchmark uses short states with one or two questions each, which is the regime where Jev's fixed per-call meter hurts it most. This second set tests the regime Jev was built for: one document of {min(words)} to {max(words)} words (a support thread, an incident postmortem, a meeting transcript, a lease, a batch of reviews, a hiring packet, a vendor negotiation, a news report, a group chat, release notes) and ten typed questions about it, at least four of which need two or more passages. 100 hand-labelled questions; every disagreement between a model and a label was re-read against the text and all labels held.</p>
<div class="card"><table>
<tr><th>Model</th><th>Accuracy</th><th>Brier</th><th>ECE</th><th>ms / question</th><th>ms / document</th><th>Input tokens</th><th>Cost, whole run</th></tr>
{rows2}
</table>
<ul>
<li><b>Jev {pct(j['accuracy'])}, DeepSeek V4.1 Flash in JSON mode {pct(jn['accuracy'])}, DeepSeek through logprobs {pct(l['accuracy'])}, DeepSeek with reasoning on 100%.</b> Jev's one miss was an early-termination fee that had to be computed as two months' rent from a deposit stated as one and a half months' rent, answered at 0.72. The cheap DeepSeek recipes missed counting questions (attendees with action items, five-star reviews of the right product), an open action item due in July, and a $4.6 million difference called "more than $5 million" at 0.98. With reasoning on, DeepSeek got all 100 right, at $0.054 for the run against Jev's $0.001.</li>
<li><b>Cost: Jev {money(j['cost_usd'])} for the run, JSON mode {money(jn['cost_usd'])} ({jn['cost_usd']/j['cost_usd']:.0f}x), logprobs {money(l['cost_usd'])} ({l['cost_usd']/j['cost_usd']:.0f}x).</b> Jev reads each document once ({j['input_tokens']:,} tokens billed for 10 calls, about 260 of them a fixed per-call fee); the logprob recipe resends the document with every question ({l['input_tokens']:,} tokens); JSON mode reads it once but pays $1.20 per million output tokens for its answers ({jn['output_tokens']:,} tokens).</li>
<li><b>Latency: Jev {j['ms_per_call']:.0f} ms per document for all ten questions, DeepSeek about {l['ms_per_call']:.0f} ms</b> (ten parallel requests for logprobs, one longer generation for JSON mode).</li>
<li><b>Calibration:</b> Jev's ECE rose to {j['ece']:.3f} here (it was under-confident on counting questions it got right, 0.40 to 0.58), while its Brier score {j['brier']:.3f} is still the best of the three because its one miss was hedged. DeepSeek's misses again came at 0.78 to 1.00.</li>
<li><b>The local clones can read long documents, slowly.</b> Decider-2B scores 80 and Kev-4B 78 on the same 100 questions (ECE 0.06 and 0.07), but at 125 and 228 s per document on this CPU in fp32, against 0.6 s for Jev; on a GPU that would be seconds, still one forward pass per question. Added 23 Sept 2026.</li>
<li><b>TypeSafe's own docs warn that accuracy falls as the state grows with irrelevant detail.</b> At about 1,000 words with distractors written in on purpose, we did not see it. Longer states, up to the 32k-token limit, are untested here.</li>
</ul></div>
<div class="card"><details><summary>Show all 100 long-document rows</summary><table class="items">
<tr><th>id</th><th>Document</th><th>Question</th><th>Label and evidence</th>{''.join(f'<th>{esc(l)}</th>' for _, l, *_ in E2)}</tr>
{items2}</table></details>
<p class="sub">Documents are in the dataset file below (questions_long.json).</p></div>
"""

calib_section = ""
if R3:
    import calib  # noqa: E402  (bench/calib.py: AUROC, coverage, temperature scaling)
    E3 = [e for e in ENGINES if e[0] in R3["engines"]]
    def r3rows(key, subset=None):
        return [dict(v, _id=k) for k, v in R3["engines"][key]["items"].items() if subset is None or calib.CAT[k] == subset]
    from bench import ece as _ece
    rows3 = ""
    for subset, sname in ((None, "all 500"), ("anli-r3", "ANLI round 3, 300"), ("commonsenseqa", "CommonsenseQA, 200")):
        for key, label, *_ in E3:
            rr = r3rows(key, subset)
            acc = sum(r["correct"] for r in rr) / len(rr); brier = sum(r["brier"] for r in rr) / len(rr)
            rows3 += f"<tr><td>{esc(sname)}</td><td><b>{esc(label)}</b></td><td class='num'>{pct(acc)}</td><td class='num'>{brier:.3f}</td><td class='num'>{_ece(rr):.3f}</td><td class='num'>{calib.auroc(rr):.2f}</td><td class='num'>{pct(calib.coverage(rr))}</td><td class='num'>{pct(calib.coverage(rr, 0.02))}</td></tr>"
    cost3 = {key: R3["engines"][key]["summary"]["cost_usd"] for key, *_ in E3}
    calib_section = f"""
<h2>Benchmark 3: calibration stress test on 500 hard public questions</h2>
<p class="lede">The first two benchmarks are too easy to measure calibration: at 98% accuracy nearly every answer sits at 0.99 and is right. This set uses two public datasets with published labels where models are wrong 15 to 40% of the time: 300 ANLI round-3 items (adversarial entailment, 3-way) and 200 CommonsenseQA validation items (5-way), sampled with seed 7. The question is not who scores higher but whose probabilities you can act on.</p>
<div class="card"><table>
<tr><th>Subset</th><th>Model</th><th>Accuracy</th><th>Brier</th><th>ECE</th><th>AUROC</th><th>Auto-answerable at 5% error</th><th>at 2% error</th></tr>
{rows3}
</table>
<p class="sub">AUROC: how well the stated confidence ranks correct answers above wrong ones (0.5 = no information). Auto-answerable: sort by confidence, take answers from the top until the error rate among them would exceed the budget; the share you get to keep. Both are unchanged by temperature scaling, which preserves the order.</p>
<ul>
<li><b>Jev's probabilities are the ones you can route on as delivered</b> (see benchmark 3b below for how much of this gap survives on private items). Over the 500 items, trusting Jev's number lets you automate 37% of answers at a 5% error budget; DeepSeek V4.1 Flash through logprobs gives 4%, its own stated confidence in JSON mode 1%, and with reasoning on 1%. Expected calibration error: Jev 0.09, logprobs 0.24, JSON 0.17, reasoning on 0.23. Brier: 0.34, 0.51, 0.47, 0.46.</li>
<li><b>Jev is not perfectly calibrated either.</b> On ANLI it is over-confident (ECE 0.14, a fitted temperature of 2.5), as Will Kelly and scienthoon reported on other hard sets; on CommonsenseQA it is close to honest (ECE 0.05).</li>
<li><b>The practitioner's fix does not close the gap.</b> Temperature scaling (one scalar fitted on half the set, tested on the other half) brings every model's ECE to about 0.07 to 0.08 on ANLI. It cannot change which answers are trusted first, and there Jev leads overall (AUROC 0.79 vs 0.74 vs 0.56 vs 0.50) and ties logprobs on ANLI.</li>
<li><b>Accuracy:</b> Jev 76%, logprobs 72%, JSON mode 73%, reasoning on 77% over the 500; Jev leads the cheap recipes on ANLI (70 vs 62 and 64) and trails by one point on CommonsenseQA. Cost of the run: Jev {money(cost3['jev'])}, logprobs {money(cost3['llm'])}, JSON {money(cost3['llm_json'])}, reasoning on {money(cost3.get('llm_think', 0))}.</li>
<li><b>Let the LLM think and the picture flips.</b> The same one-letter question with DeepSeek's reasoning on (low effort, 50 to 200 thinking tokens, the letter read as the last generated token) is the most accurate engine on all three benchmarks (99, 100, 77%) and explains every answer, at 7 to 54x Jev's cost and 1 to 3 s per question. Its probability is then 1.00 on every answer, right or wrong (AUROC 0.50): after reasoning, the letter is a foregone conclusion. System 2 is more accurate; only System 1 can say how sure it is.</li>
</ul></div>
"""

calib_private_section = ""
R3P = json.load(open(os.path.join(HERE, "results_calib_private.json"))) if os.path.exists(os.path.join(HERE, "results_calib_private.json")) else None
if R3P:
    import calib  # noqa: E402
    from bench import ece as _ece
    Q3P = json.load(open(os.path.join(HERE, "questions_calib_private.json")))
    CATP = {it["id"]: it["category"] for it in Q3P["items"]}
    E3P = [e for e in ENGINES if e[0] in R3P["engines"]]
    def r3prows(key, subset=None):
        return [dict(v, _id=k) for k, v in R3P["engines"][key]["items"].items() if subset is None or CATP[k] == subset]
    rows3p, M = "", {}
    for subset, sname in ((None, "all 300"), ("private-nli", "private NLI, 150"), ("private-mcq", "private MCQ, 150")):
        for key, label, *_ in E3P:
            rr = r3prows(key, subset)
            acc = sum(r["correct"] for r in rr) / len(rr); brier = sum(r["brier"] for r in rr) / len(rr)
            M[(key, subset)] = dict(acc=acc, brier=brier, ece=_ece(rr), auroc=calib.auroc(rr), cov5=calib.coverage(rr), cov2=calib.coverage(rr, 0.02))
            rows3p += f"<tr><td>{esc(sname)}</td><td><b>{esc(label)}</b></td><td class='num'>{pct(acc)}</td><td class='num'>{brier:.3f}</td><td class='num'>{_ece(rr):.3f}</td><td class='num'>{calib.auroc(rr):.2f}</td><td class='num'>{pct(calib.coverage(rr))}</td><td class='num'>{pct(calib.coverage(rr, 0.02))}</td></tr>"
    def pub(key):  # the same engine on the public set, for the side-by-side sentence
        rr = [dict(v, _id=k) for k, v in R3["engines"][key]["items"].items()] if R3 and key in R3["engines"] else []
        return dict(acc=sum(r["correct"] for r in rr) / len(rr), ece=_ece(rr), cov5=calib.coverage(rr)) if rr else None
    def cmp_row(key, label):
        pb, pr = pub(key), M[(key, None)]
        pa, pe, pc = (pct(pb["acc"]), f"{pb['ece']:.2f}", pct(pb["cov5"])) if pb else ("n/a", "n/a", "n/a")
        return f"<tr><td><b>{esc(label)}</b></td><td class='num'>{pa}</td><td class='num'>{pct(pr['acc'])}</td><td class='num'>{pe}</td><td class='num'>{pr['ece']:.2f}</td><td class='num'>{pc}</td><td class='num'>{pct(pr['cov5'])}</td></tr>"
    cmp_rows = "".join(cmp_row(key, label) for key, label, *_ in E3P)
    CALIB_PRIVATE_BULLETS = """<ul>
<li><b>No sign of memorisation.</b> From the public set to the private replica, accuracy went Jev 76 to 81, DeepSeek logprobs 72 to 71, JSON mode 73 to 80, reasoning on 77 to 98, Decider-2B 54 to 49, Kev-4B 61 to 58. A model that had memorised ANLI or CommonsenseQA would fall on fresh items; none of the hosted ones did.</li>
<li><b>The calibration ranking holds.</b> Jev ECE 0.08 and Brier 0.26 against 0.20 / 0.44 for logprobs, 0.17 / 0.38 for JSON mode, 0.16 / 0.66 and 0.15 / 0.59 for the two local clones. Jev's mean confidence (0.74) sits under its accuracy (0.81); every DeepSeek recipe states 0.91 to 0.93 while scoring 71 to 80.</li>
<li><b>But the "auto-answerable" gap is narrower than the public set suggested.</b> At a 5% error budget Jev covers 62% of the private items, DeepSeek logprobs 55%, JSON mode 0%. On the public set it was 37 vs 4 vs 1. The difference is ANLI: on adversarial entailment DeepSeek's logprobs are wildly over-confident (ECE 0.34 public, 0.28 private) and its ranking breaks; on 5-way questions its ranking is as good as Jev's (AUROC 0.88 vs 0.90) and only the level is off. The fair statement is: Jev's number is usable as delivered; DeepSeek's logprob needs a fitted temperature and still fails on entailment; DeepSeek's stated JSON confidence carries no information (AUROC 0.53) on either set.</li>
<li><b>Reasoning solves this set.</b> DeepSeek with thinking on scores 98% (97 on the NLI half, 99 on the MCQ half) at 2.3 s per question and $0.06 for the run, 11x Jev's $0.0055. Our private items lean on arithmetic, date counting and multi-hop logic, which is precisely what a one-pass model cannot do: every System 1 engine tops out at 81. Its probability is 1.00 on every answer; the 100% coverage is an artefact of 98% accuracy, not of calibration (AUROC 0.50).</li>
<li><b>The local clones get about half the hard entailment items right</b> (47 and 54% on three options, Jev 78%) and at 51 to 61% on the 5-way half; their probabilities rank answers poorly (AUROC 0.66) and cover 0 to 1% at a 5% error budget.</li>
</ul>"""
    calib_private_section = f"""
<h2>Benchmark 3b: the same test on 300 private questions nobody has seen</h2>
<p class="lede">A fair objection to benchmark 3: ANLI and CommonsenseQA are public with published labels, so any of these models may have met them in training, and a memorised answer looks exactly like a confident correct one. So we wrote a private replica on 23 September: 150 original adversarial NLI items and 150 original 5-way questions (arithmetic in words, pragmatics, spatial and ordering puzzles, negated rules), authored by Claude Fable 5.1 under instructions, blind re-labelled by a second Claude instance (300 of 300 labels agreed; one flawed item fixed), and never published before this report. Same runner, same scoring.</p>
<div class="card"><table>
<tr><th>Subset</th><th>Model</th><th>Accuracy</th><th>Brier</th><th>ECE</th><th>AUROC</th><th>Auto-answerable at 5% error</th><th>at 2% error</th></tr>
{rows3p}
</table>
<h3 style="margin-top:22px">Public set (500) vs private replica (300), same models</h3>
<table>
<tr><th>Model</th><th>Accuracy, public</th><th>private</th><th>ECE, public</th><th>private</th><th>Auto-answerable at 5%, public</th><th>private</th></tr>
{cmp_rows}
</table>
<p class="sub">If a model had memorised the public sets, its accuracy would drop on the private replica and its calibration would look worse. The private set is not a harder or easier copy of the public one (different authors, different mix), so compare the ranking and the gaps, not the absolute numbers.</p>
{CALIB_PRIVATE_BULLETS}
</div>
"""

cascade_section = ""
CASC = os.path.join(HERE, "cascade.json")
if os.path.exists(CASC):
    cz = json.load(open(CASC)); s2c = cz["system2_alone"]
    CN = {"jev": "Jev", "llm": "DeepSeek V4.1 Flash, logprobs", "llm_json": "DeepSeek V4.1 Flash, JSON mode"}
    crow = "".join(f"<tr><td><b>{esc(CN[k])}</b> first</td><td class='num'>{pct(cz['curves'][k][0]['accuracy'])}</td><td class='num'>{pct(t['escalated'])}</td><td class='num'>{t['ms_mean']/1000:.1f} s</td><td class='num'>{t['usd_per_1k']*100:.0f}¢</td></tr>" for k, t in cz["to_95"].items())
    cascade_section = f"""
<h2>System 1 plus System 2: escalate what the first model is unsure of</h2>
<p class="lede">On the private hard set, every question is first answered by a one-pass model; the least-confident share is then re-answered by DeepSeek V4.1 Flash with reasoning on (low effort), which alone scores {pct(s2c['accuracy'])} at {s2c['ms_per_question']/1000:.1f} s per question. The question is how much you must escalate to reach 95%, which depends only on how well the first model's confidence ranks its own answers.</p>
<div class="card"><img src="assets/jev-deck/cascade.png" alt="Accuracy against the share escalated" style="max-width:100%">
<table><tr><th>To reach 95% on 300 questions</th><th>Alone</th><th>Escalated</th><th>Mean time per question</th><th>Cost per 1,000 questions</th></tr>{crow}
<tr><td><b>DeepSeek with reasoning on everything</b></td><td class='num'>{pct(s2c['accuracy'])}</td><td class='num'>100%</td><td class='num'>{s2c['ms_per_question']/1000:.1f} s</td><td class='num'>{s2c['usd_per_1k']*100:.0f}¢</td></tr></table>
<ul>
<li><b>Calibration is what makes the pair work.</b> Jev answers the 65% it is surest of at 0.3 s each and hands 35% over: 95% at about half the time and half the cost of reasoning on every question.</li>
<li><b>DeepSeek's own logprobs route almost as well</b> (39% escalated): their ranking is good, only their level is overconfident. The confidence written into a JSON answer barely ranks at all: three questions in four must be escalated.</li>
<li><b>Label check.</b> DeepSeek with reasoning, a model from another lab, agrees with 295 of the 300 labels of the private set.</li>
<li>All costs here are fractions of a cent per question; in a real-time loop the gain is the time. Escalation order: ascending stated confidence, single run, list prices.</li>
</ul></div>
"""

probe_section = ""
PROBE = os.path.expanduser("~/jevlab/demos/live-jev/runs/judgment-probe-summary.json")
if os.path.exists(PROBE):
    pz = json.load(open(PROBE))
    PN = [("jev", "Jev"), ("kev", "Kev-4B (CPU)"), ("llm", "DeepSeek V4.1 Flash, JSON mode"), ("laya", "Laya 421M (CPU)"), ("decider", "Decider-2B (CPU)")]
    prow = "".join(f"<tr><td><b>{esc(n)}</b></td><td class='num'>{pz[k]['agree']}%</td><td class='num'>{pz[k]['timid']} of {pz[k]['go']}</td><td class='num'>{pz[k]['reckless']} of {pz[k]['brake']}</td><td class='num'>{pz[k]['stall']} of {pz[k]['stall_cases']}</td><td class='num'>{pz[k]['ped_fa']}%</td><td class='num'>{esc(pz[k]['top'])} {pz[k]['top_share']}%</td><td class='num'>{pz[k]['ms']/1000:.1f} s</td></tr>" for k, n in PN if k in pz)
    with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "typed-decision-models-benchmark-judgment-probe.json"), "w") as fh:
        json.dump([json.loads(l) for l in open(os.path.expanduser("~/jevlab/demos/live-jev/runs/judgment-probe.jsonl")) if l.strip()], fh)
    probe_section = f"""
<h2>Car demo, no clock: the same 87 driving states for every brain</h2>
<p class="lede">Latency and traffic luck dominate the live runs, so we also asked every model about identical frozen moments. The author's rule brain drove seeds 42, 7 and 123 on both courses; every 8 s of simulated time its state was saved (87 states). Each model then answered the same four questions about each state, and its answers were compared with the rule brain's, which implements what each question literally says. That reference is the sim author's code, not ground truth.</p>
<div class="card"><table><tr><th>Brain</th><th>Speed answer matches the rule</th><th>Timid: holds or brakes on a clear lane</th><th>Reckless: speeds up when the rule brakes</th><th>Stuck at 0 km/h on a clear lane</th><th>False pedestrian alarms</th><th>Most frequent speed answer</th><th>Median time per decision</th></tr>{prow}</table>
<ul>
<li><b>Two local clones answer almost a constant.</b> Laya says speed_up on all 87 states (hence its crashes), Decider-2B says hold on 84 (hence it never leaves the start). Reversing the option order on a sample did not change either: they follow the label, not its position.</li>
<li><b>Kev-4B reads the driving state best of all five</b>, Jev included, but needs 25 to 45 s per decision on this 12-core CPU (25 to 30 s after switching to its exact single-state-pass path).</li>
<li><b>Jev never speeds up when it should brake;</b> its errors are holds on clear lanes. DeepSeek's are almost all caution: it holds on 53 of 58 clear-lane states, which is why it crawls.</li>
<li><b>Bug found and fixed on the way.</b> The adapter for the local models dropped the pedestrian question's yes/no criteria ("standing pedestrians on the sidewalk are fine") that Jev and DeepSeek receive. Fixing it cut Decider's false alarms from 7% to 1%; its speed answers did not change.</li>
</ul>
<p class="sub">Every state, question and answer: <a href="typed-decision-models-benchmark-judgment-probe.json">judgment-probe.json</a>. Script: demos/live-jev/scripts/judgment-probe.mjs.</p></div>
"""

final_section = ""
FINAL = os.path.expanduser("~/jevlab/demos/live-jev/runs/final.jsonl")
if os.path.exists(FINAL):
    fr = [json.loads(l) for l in open(FINAL) if l.strip()]
    with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "typed-decision-models-benchmark-car-24sept.json"), "w") as fh:
        json.dump(fr, fh, indent=1)
    FN = {"jev": "Jev", "llm": "DeepSeek V4.1 Flash, JSON mode", "kev": "Kev-4B (CPU)"}
    TN = {"real": "real time", "slowed": "latency removed, a decision every 0.2 s", "slowed-0.5": "latency removed, a decision every 0.5 s"}
    def fcell(runs, course):
        rr = [r for r in runs if r["course"] == course]
        if not rr:
            return "<td class='num'>n/a</td>"
        crashes = sum(1 for r in rr if r["crashed"])
        d = sorted(r["distance_m"] for r in rr)
        rng = f"{d[0]:,}" if len(d) == 1 else f"{d[0]:,} to {d[-1]:,}"
        return f"<td class='num'>{rng} m{f', {crashes} crash' + ('es' if crashes > 1 else '') if crashes else ''} ({len(rr)} run{'s' if len(rr) > 1 else ''})</td>"
    frows = ""
    for tempo in ("real", "slowed", "slowed-0.5"):
        for b in ("jev", "llm", "kev"):
            runs = [r for r in fr if r["brainKind"] == b and r["tempo"] == tempo]
            if not runs:
                continue
            ms = sum(int(r["brain"].split("avg ")[1].split("ms")[0]) for r in runs) / len(runs)
            frows += f"<tr><td>{esc(TN[tempo])}</td><td><b>{esc(FN[b])}</b></td>{fcell(runs, 'traffic')}{fcell(runs, 'gauntlet')}<td class='num'>{ms/1000:.2f} s</td></tr>"
    kk = [r for r in fr if r["brainKind"] == "kev" and r["tempo"] == "slowed"]
    kev_note = (f"Kev-4B at the native pace: {'crashed at %.0f s after %d m' % (kk[-1]['crashed']['time'], kk[-1]['distance_m']) if kk[-1]['crashed'] else '%d m, clean' % kk[-1]['distance_m']}, about {int(kk[-1]['brain'].split('avg ')[1].split('ms')[0])/1000:.0f} s per decision on a 12-core CPU server." if kk else "Kev-4B's native-pace run is pending.")
    final_section = f"""
<h2>Car demo, re-run on 24 Sept: real time vs slowed, three brains</h2>
<p class="lede">Two videos on the same road: one in real time, one with latency removed. Every run below is from the same day, seeds 42, 7 and 123 on both courses (traffic: random cars and pedestrians; obstacle course: cones, barriers, parked cars), the videos recorded on seed 42 traffic, declared before the runs. Real time is a test for hosted models only: a model that needs tens of seconds per decision on a CPU cannot take part, so Kev-4B (the local model that judged frozen driving states best, previous section) appears in the latency-removed runs, where the clock stops while a brain thinks and every brain decides every 0.2 simulated seconds, the simulator's native rate. An intermediate pace of one decision per 0.5 s was also run and is kept in the file.</p>
<div class="card"><table><tr><th>Pace</th><th>Brain</th><th>Traffic course</th><th>Obstacle course</th><th>Time per decision</th></tr>{frows}</table>
<p class="sub">Videos: <a href="assets/jev-deck/jev-vs-deepseek-car-realtime.mp4">real time (Jev, DeepSeek)</a> and <a href="assets/jev-deck/jev-vs-deepseek-vs-kev-car-slowed.mp4">slowed</a>. All runs: <a href="typed-decision-models-benchmark-car-24sept.json">car-24sept.json</a>. Reading: in real time Jev is clean on 6 of 6 and farthest on both courses; DeepSeek decides about ten times less often (2.3 s vs 0.23 s) and crawls or leaves braking to the emergency brake. With latency removed at the native 0.2 s pace, DeepSeek matches Jev in traffic (695 to 923 m vs 755 to 1,141 m) but covers 406 to 722 m on the obstacle course against Jev's 1,210 to 1,236 m. {kev_note} Kev's on-screen title in the frames was captured before the renderer named open models; the video composer repaints that title, nothing else.
"""

demo_section = ""
FLIGHTS = os.path.expanduser("~/jevlab/demos/jev-autopilot/runs/flights.jsonl")
if os.path.exists(FLIGHTS):
    flights = [json.loads(l) for l in open(FLIGHTS).read().splitlines() if l.strip()]
    real = [f for f in flights if f["simSpeed"] >= 0.9]        # physics at real time; slower runs are an artefact of CPU rendering
    slow = [f for f in flights if f["simSpeed"] < 0.9]
    with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "typed-decision-models-benchmark-flights.json"), "w") as fh:
        json.dump(flights, fh, indent=1)
    PNAME = {"jev": "Jev", "deepseek": "DeepSeek V4.1 Flash, logprobs", "deepseek-json": "DeepSeek V4.1 Flash, JSON mode", "laya": "Laya 421M (CPU)", "decider": "Decider-2B (CPU)"}
    def frow(f):
        mins, secs = divmod(int(round(f["wallSeconds"])), 60)
        return (f"<tr><td>{f['seed']}</td><td><b>{PNAME[f['pilot']]}</b></td><td>{esc(f['outcome'].replace('_', ' '))}</td>"
                f"<td class='num'>{mins}:{secs:02d}</td><td class='num'>{f['decisions']}</td><td class='num'>{f['avgLatencyMs']}</td>"
                f"<td class='num'>{f['stale']}</td><td class='num'>{f['inputTokens'] + f['outputTokens']:,}</td><td class='num'>{money(f['costUsd'])}</td><td class='num'>x{f['simSpeed']:.2f}</td></tr>")
    frows = "".join(frow(f) for f in sorted(real, key=lambda f: (f["seed"], f["pilot"])))
    srows = "".join(frow(f) for f in sorted(slow, key=lambda f: (f["seed"], f["pilot"])))
    demo_section = f"""
<h2>Demo replay: the drone autopilot with DeepSeek at the sticks</h2>
<p class="lede">Benchmarks score answers; a demo scores a loop. We took Ariel Weinberger's open-source <a href="https://github.com/arielweinberger/jev-autopilot">jev-autopilot</a> (three.js drone sim, MIT): code computes altitude, bearing and obstacles, writes a plain-language situation report, and every 180 ms asks the model six typed questions (a Choice per stick axis, plus "commit to landing?" and "cut motors?"); code turns the probability distributions into stick deflections and drops any answer older than 2 s. We added a second pilot that answers the same six questions with DeepSeek V4.1 Flash on Fireworks (the logprob recipe, six requests in parallel, and JSON mode), a ?pilot= switch, a flight log and a headless runner, then flew both on the same cities. Side-by-side video of seed 42: <a href="assets/jev-deck/jev-vs-deepseek-drone-seed42.mp4">jev-vs-deepseek-drone-seed42.mp4</a>.</p>
<div class="card"><table>
<tr><th>Seed</th><th>Pilot</th><th>Outcome</th><th>Flight</th><th>Decisions</th><th>ms per decision</th><th>Dropped as stale</th><th>Tokens</th><th>Cost</th><th>Physics speed</th></tr>
{frows}
</table>
<p class="sub">Physics speed is simulated seconds per wall second while the model flew; the sim is software-rendered on this box, so only runs at about x1.0 count. Tokens are input plus output; Jev's output tokens are free. Prices: Jev $0.042 per million input tokens; DeepSeek $0.30 in, $1.20 out.</p>
<ul>
<li><b>Both land; the tempo differs.</b> On seed 42 Jev landed in 57 s after 213 decisions at 244 ms each, for $0.015. DeepSeek through logprobs landed on the same pad after 8 min 43 s, 329 decisions at 1,107 ms each, 54 of them discarded as stale, for $0.27. The loop was tuned for a 200 ms pilot: a hard turn that arrives 1.1 s late overshoots, and the drone hunts around the pad.</li>
<li><b>Four cities, same picture.</b> Jev landed every time in 57 to 67 s for $0.014 to $0.017. DeepSeek through logprobs landed on seeds 2026 and 123 in 5 min 53 s and 8 min 47 s (touching down at 3.3 and 3.5 m/s, the crash threshold) and was still airborne after the 9-minute budget on seed 7; JSON mode (one call per tick, about 1.5 s) was still airborne after 9 minutes on seed 42. Runs that did not land within 9 minutes have no record in the table.</li>
<li><b>Laya, the open zero-shot model, cannot fly it at any tempo.</b> On this box's CPU it answers in about 3.5 s; at real time every answer failed the 2 s freshness check and the drone never armed (48 answers, 0 used). With the physics slowed ten times, so that it is judged as a 350 ms pilot would be, it received 168 fresh answers and still never left the pad: "descend" while on the ground, "commit to landing" at 0.71 and "cut motors" at 0.73 before take-off. The problem is judgment, not latency.</li>
<li><b>Decider-2B, the best local clone on our benchmarks, does not fly either.</b> Served from this box's CPU in its packed layout (all six questions behind one copy of the situation, about 6 s per answer): at real time 13 answers, all stale, never armed; at timescale 0.1, 91 fresh answers and the drone never left the ground. Added 24 Sept.</li>
<li><b>Latency relative to the world is what matters.</b> In runs where four browsers shared the CPU and the physics ran at about half speed (table below, excluded from the comparison), DeepSeek's effective latency halved and it landed in 62 to 110 simulated seconds. A slower model needs a slower loop or smaller gains; it is not less able to answer the six questions.</li>
</ul></div>
<div class="card"><details><summary>Runs at slowed physics (excluded)</summary><table>
<tr><th>Seed</th><th>Pilot</th><th>Outcome</th><th>Flight</th><th>Decisions</th><th>ms per decision</th><th>Dropped as stale</th><th>Tokens</th><th>Cost</th><th>Physics speed</th></tr>
{srows}
</table></details></div>
"""

av_section = ""
AV = os.path.expanduser("~/jevlab/demos/live-jev/runs/av.jsonl")
if os.path.exists(AV):
    import re as _re
    av = []
    for l in open(AV).read().splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        d["pilot"] = d["brain"].split()[0]                     # the summary string starts with the brain name
        m = _re.search(r"avg (\d+)ms.*?(\d+) errors.*?tokens (\d+)/(\d+), cost \$([\d.]+)", d["brain"])
        d["avgLatencyMs"], d["errors"], d["tokensIn"], d["tokensOut"], d["costUsd"] = int(m[1]), int(m[2]), int(m[3]), int(m[4]), float(m[5])
        av.append(d)
    with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "typed-decision-models-benchmark-av.json"), "w") as fh:
        json.dump(av, fh, indent=1)
    ANAME = {"jev": "Jev", "llm": "DeepSeek V4.1 Flash, JSON mode", "laya": "Laya 421M (CPU)"}
    CNAME = {"traffic": "random traffic and pedestrians", "gauntlet": "gauntlet (mixed static obstacles)"}
    def avrow(d):
        crash = f"<span style='color:#b3261e'>crashed into {esc(d['crashed']['type'])} at {d['crashed']['time']:.0f} s</span>" if d["crashed"] else "clean"
        return (f"<tr><td>{esc(CNAME.get(d['course'], d['course']))}</td><td>{d['seed']}</td><td><b>{esc(ANAME[d['pilot']])}</b></td><td>{crash}</td>"
                f"<td class='num'>{d['distance_m']:,}</td><td class='num'>{d['avg_kmh']}</td><td class='num'>{d['decisions']}</td><td class='num'>{d['avgLatencyMs']:,}</td>"
                f"<td class='num'>{d['reflexTicks']}</td><td class='num'>{'' if d['minTtc'] == 'Infinity' or d['minTtc'] is None else f'{d['minTtc']:.1f}'}</td><td class='num'>{money(d['costUsd'])}</td></tr>")
    order = {"jev": 0, "llm": 1, "laya": 2}
    avrows = "".join(avrow(d) for d in sorted(av, key=lambda d: (d["course"] != "traffic", d["seed"], order[d["pilot"]])))
    av_section = f"""
<h2>Demo replay 2: a self-driving car with three brains</h2>
<p class="lede">Second public demo, closer to Seb's field: vinilana's public <a href="https://github.com/vinilana/live-jev">live-jev</a>, a top-down car on a three-lane road with seeded traffic, trucks, pedestrians who cross, cones and barriers. Every 200 ms the car turns its sensors into a JSON state and asks four typed questions: lane action (keep, left, right), speed action (stop, slow, hold, speed up), a hazard score from 0 to 3, and "must I yield to a pedestrian?". Code applies the answers with confidence gating and keeps an emergency-brake reflex for imminent impacts. The author already built a Jev-vs-LLM compare mode with DeepSeek V4.1 Flash in JSON mode; we pointed it at Fireworks, added a third brain, Laya (the open zero-shot typed-decision model, on this box's CPU), and ran the author's headless runner, which advances the simulation by each answer's real latency, so a slow brain decides less often, exactly as it would on the road.</p>
<div class="card"><table>
<tr><th>Course</th><th>Seed</th><th>Brain</th><th>Outcome in 120 s</th><th>Distance (m)</th><th>Avg km/h</th><th>Decisions</th><th>ms per decision</th><th>Reflex ticks</th><th>Min TTC (s)</th><th>Cost</th></tr>
{avrows}
</table>
<p class="sub">A recorded three-track run of seed 42 in traffic (<a href="assets/jev-deck/jev-vs-deepseek-vs-laya-car-seed42.mp4">video</a>, in-browser, wall-clock decision loops) gave Jev 640 m and DeepSeek 924 m, both clean, Laya crashed at 22 s; one more sample, with the traffic luck going the other way. A second recording on the evening of 23 Sept with Decider-2B as the third brain (video withdrawn: its overlay mislabelled Decider as the rule brain; <a href="typed-decision-models-benchmark-av-decider-video.json">the three runs</a>): Jev 726 m at 0.66 s per decision that evening, DeepSeek 820 m at 2.6 s, both clean; Decider-2B in the slowed game 0 m. The 24 Sept re-run with Kev-4B below replaces it. Reflex ticks: physics frames (60 per second) in which the code's emergency brake overrode the brain. Min TTC: the smallest time-to-collision seen during the run. Prices: Jev $0.042 per million input tokens; DeepSeek $0.30 in, $1.20 out; Laya free, but 3 to 8 s per decision on a CPU.</p>
</div>
"""


axes_section = ""
AXES = os.path.expanduser("~/jevlab/demos/live-jev/runs/av-axes.jsonl")
if os.path.exists(AXES) and av:
    import re as _re
    axes = []
    for l in open(AXES).read().splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        m = _re.search(r"avg (\d+)ms.*?(\d+) errors.*?tokens (\d+)/(\d+), cost \$([\d.]+)", d["brain"])
        d["avgLatencyMs"], d["errors"], d["tokensIn"], d["tokensOut"], d["costUsd"] = int(m[1]), int(m[2]), int(m[3]), int(m[4]), float(m[5])
        axes.append(d)
    with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "typed-decision-models-benchmark-av-axes.json"), "w") as fh:
        json.dump(axes, fh, indent=1)
    AXV = os.path.expanduser("~/jevlab/demos/live-jev/runs/av-axes-video.jsonl")
    if os.path.exists(AXV):
        with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "typed-decision-models-benchmark-av-axes-video.json"), "w") as fh:
            json.dump([json.loads(l) for l in open(AXV).read().splitlines() if l.strip()], fh, indent=1)
    DXV = os.path.expanduser("~/jevlab/demos/live-jev/runs/av-decider-video.jsonl")
    if os.path.exists(DXV):
        with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "typed-decision-models-benchmark-av-decider-video.json"), "w") as fh:
            json.dump([json.loads(l) for l in open(DXV).read().splitlines() if l.strip()], fh, indent=1)
    # Baseline rows (real latency, JSON state) come from the first AV batch.
    base = [dict(d, brainKind=d["pilot"], latencyScale=1, latencyFloor=0.2) for d in av]
    CONFIGS = [  # (brainKind, latencyScale, latencyFloor) -> (brain label, input, tempo)
        (("jev", 1, 0.2), ("Jev", "JSON state", "real, ~370 ms")),
        (("jev", 1, 1.35), ("Jev", "JSON state", "handicapped to 1.35 s")),
        (("llm", 1, 0.2), ("DeepSeek V4.1 Flash", "JSON state", "real, ~1.3 s")),
        (("llm", 0, 0.2), ("DeepSeek V4.1 Flash", "JSON state", "slowed game, 0.2 s")),
        (("llm-vision-state", 1, 0.2), ("DeepSeek V4.1 Flash", "screenshot + JSON state", "real, ~2.5 s")),
        (("llm-vision-state", 0, 0.2), ("DeepSeek V4.1 Flash", "screenshot + JSON state", "slowed game, 0.2 s")),
        (("llm-vision", 1, 0.2), ("DeepSeek V4.1 Flash", "screenshot + ego odometry", "real, ~1.9 s")),
        (("llm-vision", 0, 0.2), ("DeepSeek V4.1 Flash", "screenshot + ego odometry", "slowed game, 0.2 s")),
        (("laya", 1, 0.2), ("Laya 421M (CPU)", "JSON state", "real, ~2.6 s")),
        (("laya", 0, 0.2), ("Laya 421M (CPU)", "JSON state", "slowed game, 0.2 s")),
        (("decider", 0, 0.2), ("Decider-2B (CPU)", "JSON state", "slowed game, 0.2 s")),
    ]
    def cell(runs):
        if not runs:
            return "<td colspan='6' class='num' style='color:#8a8580'>not run</td>"
        crashes = sum(1 for d in runs if d["crashed"])
        dist = sorted(d["distance_m"] for d in runs)
        rf = sorted(d["reflexTicks"] for d in runs)
        lat = sum(d["avgLatencyMs"] for d in runs) / len(runs)
        cost = sum(d["costUsd"] for d in runs) / len(runs)
        cr = f"<span style='color:#b3261e'><b>{crashes}</b> of {len(runs)}</span>" if crashes else f"0 of {len(runs)}"
        rng = lambda v: f"{v[0]:,}" if v[0] == v[-1] else f"{v[0]:,} to {v[-1]:,}"
        return (f"<td class='num'>{cr}</td><td class='num'>{rng(dist)}</td><td class='num'>{sum(d['avg_kmh'] for d in runs) / len(runs):.0f}</td>"
                f"<td class='num'>{rng(rf)}</td><td class='num'>{lat:,.0f}</td><td class='num'>{money(cost)}</td>")
    rows = []
    for key, (brain, inp, tempo) in CONFIGS:
        runs = [d for d in base + axes if (d["brainKind"], d["latencyScale"], d["latencyFloor"]) == key]
        if not runs:
            continue
        for course, cname in (("traffic", "traffic"), ("gauntlet", "gauntlet")):
            cr = [d for d in runs if d["course"] == course]
            rows.append(f"<tr><td><b>{esc(brain)}</b></td><td>{esc(inp)}</td><td>{esc(tempo)}</td><td>{cname}</td>{cell(cr)}</tr>")
    axes_section = f"""
<h2>Demo replay 2b: splitting latency from judgment from input</h2>
<p class="lede">Seb asked two questions after replay 2: would DeepSeek do better if it could <i>see the screen</i> instead of reading the JSON state, and would it match Jev if the game were slowed down as for the drone? The author's headless runner makes both cheap to test. Tempo is a single knob: each answer's real round trip is charged to simulated time (real), or ignored so every brain decides every 0.2 s (slowed game), or floored at 1.35 s so Jev is handicapped to DeepSeek's tempo. Input is a second knob: the runner renders the same frame the browser shows (with the sim's own renderer, no ray or answer overlays) and attaches it as a JPEG to the DeepSeek V4.1 Flash call, either next to the JSON state or instead of it (the model then gets only ego's own odometry: speed, lane, stopping distance, which lanes exist). Everything else is unchanged: same four questions, same confidence gate, same code reflex, same seeds and courses, 120 simulated seconds per run.</p>
<div class="card"><table>
<tr><th>Brain</th><th>Input</th><th>Decision tempo</th><th>Course</th><th>Crashes</th><th>Distance in 120 s (m)</th><th>Avg km/h</th><th>Reflex ticks</th><th>ms per call</th><th>Cost per run</th></tr>
{"".join(rows)}
</table>
<p class="sub">A four-track <a href="assets/jev-deck/jev-vs-deepseek-axes-car-seed42.mp4">video</a> replays seed 42 in the gauntlet at 2x: Jev, DeepSeek at real tempo, DeepSeek slowed, DeepSeek screenshot only (a separate set of four runs rendered by the same headless runner; their numbers are in av-axes-video.json). Baseline rows (real tempo, JSON state) are the replay 2 runs above. Slowed-game runs make about 558 calls per run instead of 50 to 90, hence the cost. In a handful of slowed runs one or two calls out of 558 failed to parse and fell back to the author's rule-based brain for that tick (the 'errors' field in av-axes.json). Screenshot: 600 x 840 px, 14 px per metre, about 47 m of road ahead of ego, versus the 60 m the JSON sensors report. Prices: Jev $0.042 per million input tokens; DeepSeek $0.30 in, $1.20 out, image tokens billed as input.</p>
</div>
<div class="card">
<h3>What the two knobs say</h3>
<ul>
<li><b>Tempo alone does not close the gap.</b> Jev handicapped to DeepSeek's 1.35 s tempo still drives clean in all six runs, 770 to 1,030 m in traffic and 1,165 to 1,185 m in the gauntlet. DeepSeek given Jev's 0.2 s tempo also stops crashing (0 of 6), but covers 440 to 945 m in traffic and 670 to 760 m in the gauntlet: with ten times more decisions it becomes hesitant ("hold" or "stop" in two thirds of its answers) and on one seed the code reflex fires 4,087 times. So Jev at DeepSeek's tempo beats DeepSeek at Jev's tempo. Latency explains the crashes; judgment explains the distance.</li>
<li><b>The screen makes DeepSeek worse, not better.</b> Screenshot only: 8 crashes in 12 runs, and the clean runs crawl at 4 to 14 km/h. At 5.7 s into the gauntlet, with a cone 7 m ahead at 35 km/h, its stated reasoning was "the small orange disc far ahead is not a hazard" (<a href="assets/jev-deck/av-vision-frame.jpg">the frame it saw</a>). The cone is a 10-pixel dot in a render made for human eyes, so part of this is the picture, but the model did notice the dot and still said "speed up", at both tempos.</li>
<li><b>Screenshot plus JSON is DeepSeek's best configuration, and it is noise-level.</b> At real tempo, 0 crashes and 414 to 966 m; slowed, 904 to 1,093 m on five seeds and a crash into a cone at 191 m on the sixth, the same spot where the text-only brain crashed at real tempo. The image adds about 700 input tokens and 0.6 s per call and does not change what the model gets wrong.</li>
<li><b>Laya is judgment-limited, full stop.</b> Slowed ten-fold it crashes at exactly the same places (136 m in traffic, 48 m in the gauntlet), with 107 and 40 decisions instead of 9 and 5.</li>
<li><b>Decider-2B never leaves the start line.</b> In the slowed game on seed 42 (both courses, 558 decisions each, about 6 to 7 s per decision on this CPU, packed layout) it answers "hold" at 0 km/h and says yes to "yield to a pedestrian" for a pedestrian on the sidewalk, which the gate turns into slow_down: 0 m in 120 s, twice. The best local clone on the static benchmarks reads this JSON state worse than Laya, which at least drives into things. Added 24 Sept.</li>
</ul>
<h3>The axes, then</h3>
<table>
<tr><th>Axis</th><th>What the runs show</th><th>Who wins</th></tr>
<tr><td><b>Latency</b> (decisions per second)</td><td>Jev 0.35 s, DeepSeek 1.3 s text / 2.2 s with an image, Laya 2.6 s on CPU. Removing it removes DeepSeek's crashes but not its hesitation.</td><td>Jev, 4x</td></tr>
<tr><td><b>Judgment</b> (quality of each answer)</td><td>At equal tempo DeepSeek reaches 55 to 85% of Jev's distance and crashes once in six; Laya crashes every time.</td><td>Jev, clearly; DeepSeek usable</td></tr>
<tr><td><b>Input</b> (JSON vs pixels)</td><td>Pixels alone: unusable. Pixels plus JSON: same as JSON. This demo is not a vision test; the JSON sensors are the right interface for both models.</td><td>Tie on JSON; Jev is text-only, which here costs nothing</td></tr>
<tr><td><b>Cost per 120 s</b></td><td>Jev $0.025 at real tempo. DeepSeek $0.07 at real tempo, $0.41 slowed, $0.50 slowed with images.</td><td>Jev, 3x to 20x</td></tr>
<tr><td><b>Consistency</b> across seeds</td><td>Jev's six real-tempo runs span 1,044 to 1,210 m; DeepSeek's best configuration spans 191 (crash) to 1,093 m.</td><td>Jev</td></tr>
<tr><td><b>Calibration</b></td><td>Not what these demos test. The code gate uses confidence thresholds, but the outcomes above are explained by tempo and by whether the top answer was right. Calibration was benchmark 3's contribution (routing and abstention), not the drone's or the car's.</td><td>Not measured here</td></tr>
</table>
</div>
"""

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jev versus DeepSeek and the open typed-decision models: three benchmarks</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Spline+Sans:wght@400;500;600&family=Spline+Sans+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  :root{{--paper:#f6f2ea;--ink:#1d1a16;--muted:#6f675c;--line:#d9d1c4;--card:#fffdf8;--accent:#b4531d}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 "Spline Sans",system-ui,sans-serif}}
  .wrap{{max-width:1100px;margin:0 auto;padding:40px 28px 80px}}
  h1{{font-family:Fraunces,serif;font-weight:600;font-size:38px;line-height:1.1;margin:0 0 10px;letter-spacing:-.01em}}
  h2{{font-family:Fraunces,serif;font-weight:600;font-size:24px;margin:44px 0 12px}}
  h4{{margin:0 0 6px;font-size:14px}}
  .lede{{font-size:17px;color:var(--muted);max-width:820px;margin:0 0 6px}}
  .meta{{font:13px "Spline Sans Mono";color:var(--muted)}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-top:14px}}
  table{{width:100%;border-collapse:collapse;font-size:14px}}
  th{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:500;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}}
  td{{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
  td.num{{font-family:"Spline Sans Mono";text-align:right;white-space:nowrap}}
  .sub{{color:var(--muted);font-size:12.5px;margin-top:2px}}
  .mono{{font-family:"Spline Sans Mono";font-size:13px}}
  .sw{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px;vertical-align:middle}}
  .good{{background:#e6f2e8}} .mid{{background:#fbf1d9}} .bad{{background:#f8e1dc}}
  .rels{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:22px}}
  .rel table{{font-size:13px}} .rel td,.rel th{{padding:5px 8px}}
  details summary{{cursor:pointer;color:var(--muted);font-size:14px;margin:8px 0}}
  ul{{padding-left:20px}} li{{margin:4px 0}}
  a{{color:var(--accent)}}
  .items td{{font-size:13px}}
  .kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:18px}}
  .kpi div{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
  .kpi b{{display:block;font:600 30px/1 Fraunces,serif;margin-bottom:6px}}
  .kpi span{{color:var(--muted);font-size:13px}}
</style></head><body><div class="wrap">
<h1>Jev, DeepSeek V4.1 Flash and the open typed-decision models, benchmarked on {n_items} short cases, 10 long documents and 500 hard public questions</h1>
<p class="lede">The real Jev (TypeSafe's hosted System One model), three open-weight "Jev-style" models that run on a CPU, and a frontier-class LLM read through logprobs, all answering the same batches of typed questions (true/false, multiple choice, ordered score) about the same pieces of text. Every question is generic and hand-labelled; the dataset is linked at the bottom.</p>
<p class="meta">{n_states} states, {n_items} questions, 10 categories. Single run, September 2026. CPU: 12-core VPS, no GPU. Full method and caveats below.</p>

<div class="kpi">
  <div><b>{pct(R['engines']['jev']['summary']['accuracy'])}</b><span>Jev accuracy (jev-latest, ECE {R['engines']['jev']['summary']['ece']:.2f}, {R['engines']['jev']['summary']['ms_per_question']:.0f} ms per question over the network)</span></div>
  <div><b>{pct(llm_acc) if llm_acc is not None else 'n/a'}</b><span>DeepSeek V4.1 Flash accuracy, logprob read (JSON mode: {pct(R["engines"]["llm_json"]["summary"]["accuracy"]) if "llm_json" in R["engines"] else "n/a"})</span></div>
  <div><b>{pct(R['engines'][best_open[0]]['summary']['accuracy'])}</b><span>best open CPU model ({esc(best_open[1])})</span></div>
  <div><b>{R['engines'][best_open[0]]['summary']['ms_per_question']:.0f} ms</b><span>per question for {esc(best_open[1])} on CPU, all questions of a state in one pass</span></div>
  <div><b>{R['engines'][best_open[0]]['summary']['ece']:.2f}</b><span>expected calibration error for {esc(best_open[1])} (lower is better, 0 is perfect)</span></div>
</div>

<h2>Headline numbers</h2>
<div class="card"><table>
<tr><th>Model</th><th>Accuracy</th><th>Brier</th><th>ECE</th><th>ms / question</th><th>ms / state</th><th>Input tokens</th><th>Cost, whole run</th><th>Runs on</th></tr>
{summary_rows}
</table>
<p class="sub">Accuracy: argmax answer equals the label (true/false threshold 0.5). Brier: mean squared error of the full probability vector, 0 is perfect. ECE: expected calibration error over 10 confidence bins. Latency: wall time per call divided by questions in that call; the local models answer every question about a state in one forward pass, the DeepSeek logprob recipe fires one request per question in parallel.</p></div>

<h2>Accuracy by category</h2>
<div class="card"><div id="chart" style="height:380px"></div>
<details><summary>Table view</summary><table>{cat_table}</table></details></div>

<h2>What the numbers say</h2>
<div class="card"><ul>
<li><b>Jev and DeepSeek V4.1 Flash tie on accuracy at 98%, and differ on how they are wrong.</b> Jev's two misses are both instruction-compliance checks that need counting (a 12-word reply against a 10-word limit; two recommendations against "exactly one"), and it hedged on both (0.79 and 0.61 confidence). DeepSeek's two misses (logprob recipe) are the arguable "reply within the hour" label and a birth-year subtraction it got wrong at 0.99 confidence. Same score, but Jev's Brier is 0.012 against 0.020 because its errors come with a warning and DeepSeek's do not. On the 26-question harder tier: Jev 24, DeepSeek 25, best open clone 16.</li>
<li><b>Jev's calibration held on data it never saw.</b> ECE 0.03 over {n_items} questions, and its lowest-confidence answers are the debatable or missed ones. Latency 540 to 710 ms per call from this box, all questions of a state in one request.</li>
<li><b>Cost: the whole run was a tenth of a cent for Jev and a quarter of a cent for DeepSeek, so the 7x list-price gap shrank to about 2x here.</b> Jev's usage counter charges about 280 tokens per call before any content (a regression over the 85 calls gives 276 fixed, 0.8 per state token, 1.2 per question token), so on these short states that fixed part was 82% of Jev's bill: the smallest call was 282 tokens, the median 327, for states of 20 to 60 words. The DeepSeek logprob recipe, format instructions included, averaged 73 tokens per question. Jev billed 28,710 input tokens against 7,302, four times more for the same content, and its usage field also reports about 33 "output" tokens per question that are not charged, which suggests a hidden per-question template on their side. The gap widens in Jev's favour as states get longer and carry more questions, because Jev reads the state once per call while the letter recipe resends it with every question: a 2,000-token state with ten questions is about $0.0001 on Jev and about $0.006 on DeepSeek through logprobs, a 60x difference on paper (measured on benchmark 2: 45x).</li>
<li><b>DeepSeek V4.1 Flash through logprobs is just as accurate and slightly overconfident.</b> Mean confidence 0.99 on a 98% hit rate looks fine in aggregate, but one of its two misses came at 0.99, which is the failure mode a calibrated model is supposed to avoid. Reading logprobs of a single letter gives you Jev's interface on top of any hosted LLM, at about 400 ms and a fraction of a cent per question.</li>
<li><b>The two Qwen-based clones released the week after launch, Decider-2B and Kev-4B, score 92 and 89</b> (95 and 92 on the everyday tier, 85 and 81 on the harder one), well above the encoder clones and six to nine points below Jev and DeepSeek. They run on this box's CPU at 0.9 and 1.4 s per question in fp32 (11 and 25 GB of RAM); their misses cluster on instruction compliance (about 50 to 60%) and urgency. Added 23 Sept 2026.</li>
<li><b>The two encoder clones land at 75 to 77%, and drop to about 60% on the harder tier.</b> They are strong where the answer is written in the text (reading, sentiment, routing) and weak where the question needs a comparison between two things (instruction versus response, premise versus hypothesis), a second hop, or arithmetic. Language identification is at chance.</li>
<li><b>The clones' calibration is honest but rough.</b> Mean confidence of about 0.69 against 75 to 77% accuracy: under-confident overall, and an ECE of 0.11 to 0.14 means a stated 0.9 is not a 0.9. Fine for ranking and triage, not for hard thresholds without fine-tuning.</li>
<li><b>GLiNER2.5 is an extraction model, not a judge.</b> Used as a zero-shot classifier it does well on sentiment and intent (label-shaped tasks) and collapses on anything that is a statement to verify. That is expected: it was trained on entity and label extraction, not on typed decisions.</li>
<li><b>Fine-tuning is the lever.</b> Both open clones publish 85% in-distribution versus 69% out-of-distribution on their own data. A few hundred labelled examples from your real question set is what turns 80% into 90%+, and that is exactly the step the hosted Jev API does not need you to take: it scored 98% here zero-shot.</li>
</ul></div>

<h2>Calibration: stated confidence versus actual accuracy</h2>
<div class="card"><div class="rels">{rel_html}</div>
<p class="sub">Confidence is the probability of the predicted option. A well-calibrated model has accuracy close to its mean confidence in every row.</p></div>

<h2>Method</h2>
<div class="card"><ul>
<li><b>Code and data.</b> Everything here (question sets, adapters, benchmark and analysis scripts, the demo forks and every run log) is public at <a href="https://github.com/sebderhy/jevlab">github.com/sebderhy/jevlab</a>, MIT.</li>
<li><b>Dataset.</b> {n_items} questions over {n_states} short states, written and labelled by hand for this benchmark. No product data. Categories: {', '.join(CATS)}. Question types: noul (true/false statement), choice (2 to 5 options, most with one-line descriptions), score (3 ordered levels).</li>
<li><b>Protocol.</b> All questions about one state are sent together in one call, the way the Jev API works. Same state text and same question wording for every model. One run, no retries, no prompt tuning per model beyond the mapping below.</li>
<li><b>Cost.</b> Token counts come from each API's usage field, summed over the run. Prices are list prices at the time of the run: TypeSafe $0.042 per million input tokens (output free); Fireworks serverless DeepSeek V4.1 Flash $0.30 per million input and $1.20 per million output tokens (the recipe emits one output token per question). The open models run on this box's CPU, so their marginal cost is zero and is shown as such.</li>
<li><b>Jev</b> is called at api.typesafe.ai with model jev-latest, one request per state with all its questions; choice options and score levels are passed as its "criteria" (option descriptions kept where the dataset has them). Probabilities and confidence are used as returned.</li>
<li><b>Laya and kotoba open-jev</b> take the questions natively (type, instructions, options or levels) and return a probability per option.</li>
<li><b>Decider-2B and Kev-4B</b> (added 23 Sept) take the questions natively through their own libraries (decider-ai 1.1.2, kev from GitHub) in a separate venv with transformers 5.17, fp32 on CPU (bf16 was 3 to 5x slower on this EPYC without bf16 instructions); each question is one row behind the shared state, rows batched into one forward pass. Their confidence column is the top probability, like the DeepSeek rows.</li>
<li><b>GLiNER2.5</b> has no decision head. Each question becomes a classification task in its schema: choice and score options become labels; a true/false statement becomes two labels, "true: statement" and "false: the opposite". Two mappings were tried; this is the better one (69% versus 65%). GLiNER only reports the winning label's score, so the remainder is spread evenly for the Brier score.</li>
<li><b>LLM reference</b> is DeepSeek V4.1 Flash on Fireworks with reasoning off, max_tokens 1, options listed as letters, answer probabilities read from the top-5 logprobs of the first token and renormalised. Same recipe works on any provider that exposes logprobs.</li>
<li><b>Hardware.</b> Open models on a 12-core CPU VPS, PyTorch CPU build, fp32, batch size 1. Jev and DeepSeek are network calls from the same box.</li>
<li><b>Who did the work.</b> Most of the benchmark data, labels, adapters, analysis code and charts were generated by Claude Code (Claude Fable 5.1) running on a ShellTeam box, directed by the author, who chose the questions to ask, audited every disputed label against the text and checked the outside figures.</li>
</ul>
<p><b>Caveats.</b> {n_items} questions is enough to see the shape, not to separate 75% from 77% or 98% from 98%. The first 74 questions are easy for a frontier-class judge (Jev 74 of 74); the 26-question harder tier was written after seeing that, and is still small. Adversarial and long-context sets are where Jev is known to drop and are not covered here. Labels were written by one person. Categories are unequal in size (4 to 12). The local latency numbers depend on this CPU. The GLiNER mapping is a best effort at a task the model was not built for.</p></div>

<h2>Every question and answer</h2>
<div class="card"><details><summary>Show all {n_items} rows</summary><table class="items">
<tr><th>id</th><th>State</th><th>Question</th><th>Label</th>{''.join(f'<th>{esc(l)}</th>' for _, l, *_ in ENGINES)}</tr>
{item_rows}</table></details>
<p class="sub">Each model cell shows the predicted option and the probability it gave to the correct one. Green means correct.</p></div>

{long_section}
{calib_section}
{calib_private_section}
{cascade_section}
{demo_section}
{av_section}
{probe_section}
{final_section}
{axes_section}
<h2>Files</h2>
<div class="card"><ul>
<li><a href="typed-decision-models-benchmark-questions.json">questions.json</a>: benchmark 1, the dataset (states, option sets, items with labels).</li>
<li><a href="typed-decision-models-benchmark-results.json">results.json</a>: benchmark 1, every model's probabilities, per-call latency and summary metrics.</li>
<li><a href="typed-decision-models-benchmark-questions-long.json">questions_long.json</a> and <a href="typed-decision-models-benchmark-results-long.json">results_long.json</a>: benchmark 2, the ten documents, 100 questions with labels and evidence, and every model's answers.</li>
<li><a href="typed-decision-models-benchmark-questions-calib.json">questions_calib.json</a> and <a href="typed-decision-models-benchmark-results-calib.json">results_calib.json</a>: benchmark 3, the 500 public items and every model's probabilities.</li>
<li><a href="typed-decision-models-benchmark-questions-calib-private.json">questions_calib_private.json</a> and <a href="typed-decision-models-benchmark-results-calib-private.json">results_calib_private.json</a>: benchmark 3b, the 300 private items (published here for the first time, so they stop being private the day this report goes out) and every model's probabilities.</li>
<li><a href="typed-decision-models-benchmark-meter.json">meter.json</a>: the 30 Jev calls behind the token-meter measurement.</li>
<li><a href="typed-decision-models-benchmark-flights.json">flights.json</a>: every drone flight (pilot, seed, outcome, decisions, latency, tokens, cost, physics speed).</li>
<li><a href="typed-decision-models-benchmark-av.json">av.json</a>: every self-driving run (brain, course, seed, outcome, distance, decisions, latency, reflex ticks, cost).</li>
<li><a href="typed-decision-models-benchmark-av-axes.json">av-axes.json</a>: the axis-splitting car runs (tempo handicap, slowed game, screenshot inputs).</li>
<li><a href="typed-decision-models-benchmark-av-axes-video.json">av-axes-video.json</a>: the four recorded runs behind the axis-split video.</li>
<li><a href="typed-decision-models-benchmark-cascade.json">cascade.json</a>: the System 1 plus System 2 escalation curves on the private set.</li>
<li><a href="typed-decision-models-benchmark-judgment-probe.json">judgment-probe.json</a>: the 87 frozen driving states and every brain's answers.</li>
<li><a href="typed-decision-models-benchmark-av-decider-video.json">av-decider-video.json</a>: the three recorded runs behind the Jev vs DeepSeek vs Decider-2B video.</li>
</ul></div>

<script>
const cats = {json.dumps(CATS)};
const series = {json.dumps(chart_series)};
Plotly.newPlot('chart', series.map(s => ({{type:'bar', name:s.name, x:cats, y:s.y, marker:{{color:s.color}}, hovertemplate:'%{{x}}: %{{y}}%<extra>'+s.name+'</extra>'}})), {{
  barmode:'group', bargap:0.25, bargroupgap:0.06, margin:{{l:44,r:10,t:10,b:60}}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  font:{{family:'Spline Sans, system-ui', color:'#1d1a16', size:13}}, legend:{{orientation:'h', y:1.12}},
  yaxis:{{range:[0,105], ticksuffix:'%', gridcolor:'#e8e0d2', zeroline:false}}, xaxis:{{tickangle:-20}}
}}, {{displayModeBar:false, responsive:true}});
</script>
</div></body></html>"""

open(OUT, "w").write(page)
outdir = os.path.dirname(os.path.abspath(OUT))
shutil.copy(os.path.join(HERE, "questions.json"), os.path.join(outdir, "typed-decision-models-benchmark-questions.json"))
shutil.copy(os.path.join(HERE, "results.json"), os.path.join(outdir, "typed-decision-models-benchmark-results.json"))
for src, dst in (("questions_long.json", "questions-long"), ("results_long.json", "results-long"), ("questions_calib.json", "questions-calib"), ("results_calib.json", "results-calib"), ("questions_calib_private.json", "questions-calib-private"), ("results_calib_private.json", "results-calib-private"), ("cascade.json", "cascade"), ("meter.json", "meter")):
    if os.path.exists(os.path.join(HERE, src)):
        shutil.copy(os.path.join(HERE, src), os.path.join(outdir, f"typed-decision-models-benchmark-{dst}.json"))
print("wrote", OUT)

# ---- deck: refresh the embedded benchmark data (charts on the "in charts" slide read it) ----
DECK = os.path.join(outdir, "jev-deck.html")
if os.path.exists(DECK):
    def rel_bins(key, bins=5):
        rows = list(R["engines"][key]["items"].values())
        out = []
        for b in range(bins):
            lo, hi = 0.5 + b * 0.5 / bins, 0.5 + (b + 1) * 0.5 / bins
            sel = [r for r in rows if lo < r["conf"] <= hi or (b == 0 and r["conf"] <= lo)]
            if sel:
                out.append({"conf": sum(r["conf"] for r in sel) / len(sel), "acc": sum(r["correct"] for r in sel) / len(sel), "n": len(sel)})
        return out
    deck_data = {
        "n_items": n_items, "n_states": n_states, "cats": CATS,
        "models": [{"key": k, "label": l, "color": c, "where": w,
                    "accuracy": R["engines"][k]["summary"]["accuracy"], "brier": R["engines"][k]["summary"]["brier"],
                    "ece": R["engines"][k]["summary"]["ece"], "ms_q": R["engines"][k]["summary"]["ms_per_question"],
                    "input_tokens": R["engines"][k]["summary"].get("input_tokens", 0), "cost_usd": R["engines"][k]["summary"].get("cost_usd", 0),
                    "by_cat": [R["engines"][k]["summary"]["by_category"][c]["accuracy"] for c in CATS],
                    "reliability": rel_bins(k)} for k, l, _, c, w in ENGINES],
    }
    d = open(DECK).read()
    start, end = "<!-- benchdata:start -->", "<!-- benchdata:end -->"
    i, j = d.find(start), d.find(end)
    if i < 0 or j <= i:  # the current deck (v3) embeds PNG charts from bench/charts.py instead of a data blob
        print("deck has no benchdata markers, skipping injection (run bench/charts.py instead)")
        raise SystemExit(0)
    d = d[:i] + start + "\n<script id=\"benchdata\" type=\"application/json\">" + json.dumps(deck_data) + "</script>\n" + d[j:]
    open(DECK, "w").write(d)
    print("refreshed deck data in", DECK)
