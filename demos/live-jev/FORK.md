# live-jev fork notes

Upstream: https://github.com/vinilana/live-jev, commit `cd13ab0a7b58ca9b6749a78aed2a729153fa6910` (18 Sept 2026). Upstream publishes no licence file, so its sources are not redistributed in this repo; `.gitignore` here lists them.

To rebuild our version:

```bash
git clone https://github.com/vinilana/live-jev && cd live-jev && git checkout cd13ab0
git apply ../changes.patch      # from this folder
cp -r ../scripts/{drive.mjs,judgment-probe.mjs,vision.js} scripts/ && cp -r ../runs runs
npm install && cp .env.example .env && PORT=3001 node server.js
```

What the patch adds:

- `server.js`: a second brain on any OpenAI-compatible endpoint (`LLM_*`, JSON-mode recipe with the same four typed questions), and any number of local brains (`LOCAL_BRAINS`, routed as `/api/<name>-decide`); the pedestrian question's yes/no criteria are passed to every brain.
- `scripts/headless.js`: the runner used for every number in the deck. `BRAIN=jev|llm|<local>`; `LATENCY_SCALE=1` charges each answer's real round trip to simulated time (real time), `LATENCY_SCALE=0` stops the clock while a brain thinks; `LATENCY_FLOOR` is the decision interval in simulated seconds (0.2 = the simulator's native rate); `FRAMES=dir` captures frames for the videos.
- `scripts/judgment-probe.mjs`: 87 frozen states from the simulator's own rule-based driver, every brain answers, compared with the rule's choice.
- `scripts/vision.js`: the screenshot variant of the questions.
- `public/js/*`: track labels, the third track on a local model, the emergency-brake gate as shipped.
- `runs/`: every run behind the deck (`final.jsonl` is the 24 Sept batch; `car_slide.py` rebuilds the deck's table from it), the recording and composition scripts, and the probe output.
