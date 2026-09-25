# jevlab

Everything behind the deck **"Jev, the first 'System 1' model: hype vs reality"** and its benchmark report:

- Deck: https://seb.shellteam.sh/reports/jev-deck.html (PDF: https://seb.shellteam.sh/reports/jev-deck.pdf)
- Report with every question, label and answer: https://seb.shellteam.sh/reports/typed-decision-models-benchmark.html

Jev is TypeSafe's hosted "System 1" model: you send a state and typed questions, it answers every question in one forward pass with calibrated probabilities and writes no text. This repo compares it with DeepSeek V4.1 Flash (three recipes) and five open models on three benchmarks, a calibration study, a cascade experiment, a token-meter measurement and two real-time demos (a self-driving car and a drone).

## What is here

| Path | What it is |
|---|---|
| `app.py` | One Jev-shaped `/decide` API in front of the real Jev, DeepSeek (logprob, JSON and reasoning recipes) and the CPU models Laya, kotoba open-jev and GLiNER2.5. Also serves the side-by-side demo page in `static/`. |
| `local_server.py`, `bench/engines_local.py` | The same `/decide` contract for the two Qwen3.5-based clones, Decider-2B and Kev-4B (they need `transformers>=5.17`, hence a second virtualenv). |
| `bench/bench.py` | Benchmarks 1 and 2: `questions.json` (100 short cases, with a harder tier) and `questions_long.json` (10 long documents, 100 questions). Writes `results.json` / `results_long.json`. |
| `bench/calib.py` | Benchmark 3, calibration: reliability diagrams, Brier, ECE, AUROC, coverage at a target error rate. `CALIB_SET=private` uses our 300-item private set (`questions_calib_private.json`, written for this study and unpublished until the deck); the default uses the public ANLI r3 + CommonsenseQA replica (`questions_calib.json`). |
| `bench/cascade.py` | System 1 first, then a reasoning model for the least-confident share. |
| `bench/meter.py` | Jev's billed input tokens against state length and question count (the fixed 260-token meter). |
| `bench/charts.py`, `bench/build_report.py` | The deck's charts and the HTML report. |
| `bench/results*.json` | Every answer of every engine, with probabilities, latency and reported usage. `*_local.json` are the Decider/Kev runs, merged with `bench/merge_local.py`. |
| `demos/live-jev/` | The self-driving car demo (vinilana's live-jev). Upstream has no licence file, so its sources are **not** redistributed here: `changes.patch` applies to upstream commit `cd13ab0` and adds the DeepSeek and local brains, the headless runner with `LATENCY_SCALE` / `LATENCY_FLOOR`, frame capture, the vision variant, the judgment probe and the run logs. See `demos/live-jev/FORK.md`. |
| `demos/jev-autopilot/` | The drone demo (Ariel Weinberger's jev-autopilot, MIT), with a DeepSeek pilot, a Laya/Decider pilot, a flight log and a headless runner (`runs/fly.mjs`). |

Not included: the model cache (`hf/`, 19 GB), the virtualenvs, the raw browser recordings and the API keys. The composed videos live next to the deck.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install fastapi uvicorn httpx matplotlib numpy torch transformers==4.57.6 gliner2 laya sentencepiece
git clone https://github.com/kotoba-lang/typed-decisions src-typed-decisions && .venv/bin/pip install -e src-typed-decisions   # kotoba open-jev
cp .env.example .env           # JEV_API_KEY=...
export FIREWORKS_API_KEY=...   # the DeepSeek reference

.venv/bin/python bench/bench.py --engines jev,llm,llm_json,llm_think,laya,kotoba,gliner_b          # benchmark 1 -> bench/results.json
.venv/bin/python bench/bench.py --questions questions_long.json --engines jev,llm,llm_json,llm_think  # benchmark 2 -> bench/results_long.json
CALIB_SET=private .venv/bin/python bench/calib.py     # benchmark 3 on the private set
.venv/bin/python bench/cascade.py                     # System 1 + System 2 cascade
.venv/bin/python bench/meter.py                       # token meter
.venv/bin/python bench/charts.py && .venv/bin/python bench/build_report.py report.html
```

Decider-2B and Kev-4B run from a second environment (`python3 -m venv .venv-local`, `transformers==5.17.0`, `peft`, `accelerate`; `decider-ai` and `kev` installed with `--no-deps`). They need 12 and 25 GB of RAM at full precision on a CPU. Serve them with `LOCAL_ENGINES=decider,kev .venv-local/bin/uvicorn local_server:app --port 3211` and benchmark them with `bench/bench.py --engines decider,kev`, then `bench/merge_local.py`.

Latencies in the results were measured from one server in Europe (12-core CPU, no GPU); list prices of September 2026. A local model's seconds are a property of that machine, not of the model.

## Results in one table

| | Jev | DeepSeek V4.1 Flash, logprobs | DeepSeek, reasoning on | Decider-2B | Kev-4B |
|---|---|---|---|---|---|
| Benchmark 1, 100 short cases | 98 | 98 | 99 | 92 | 89 |
| Benchmark 2, 10 long documents | 99 | 94 | 100 | 80 | 78 |
| Benchmark 3, 300 hard private | 81 | 71 | 98 | 49 | 58 |
| ECE on benchmark 3 | 0.08 | 0.20 | 0.02 | 0.16 | 0.15 |

The deck's reading: not a smarter model; a cheaper, faster, calibrated one. The speed is the one-pass architecture, which the open clones already share; the calibration and the hosted product are what they do not have yet.

## Who did the work

Most of the questions, labels, adapters, analysis code and charts were written by Claude Code (Claude Fable 5.1, then Claude Opus 5.5) on a ShellTeam cloud computer, directed and audited by the author, who set the questions, checked every disputed label against the text and verified the outside figures. One author reviewed the labels of benchmarks 1 and 2; with 100 items per set, differences under 3 points are noise.

## Licence

MIT (see `LICENSE`) for everything written here. `demos/jev-autopilot` keeps its upstream MIT licence; `demos/live-jev` upstream sources are not redistributed (see above). The public benchmark 3 replica reuses ANLI and CommonsenseQA items under their own licences.
