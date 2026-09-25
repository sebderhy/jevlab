"""Open-source Jev-style models running locally on CPU. Run: cd ~/jevlab && .venv/bin/python demo.py
Everything (venv, models, this file) lives under ~/jevlab. Revert with: rm -rf ~/jevlab"""
import json, os, time
os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(os.path.abspath(__file__)), "hf"))

STATE = {"email": "Hi, can we move Tuesday's call to 4pm instead? Also I never got the invite for Thursday. Thanks, Dana"}

def run_laya():
    import laya
    agent = laya.load("convaiinnovations/laya")
    qs = {
        "intent": {"type": "choice", "instructions": "What is the sender's main intent?",
                   "criteria": {"reschedule": "wants to change a meeting time", "cancel": "wants to cancel a meeting",
                                "confirm": "confirms a meeting", "other": "none of the above"}},
        "needs_human": {"type": "noul", "instructions": "A human should review this before the assistant replies."},
        "urgent": {"type": "noul", "instructions": "This needs action within the next few hours."},
        "missing_invite": {"type": "noul", "instructions": "The sender reports not receiving a calendar invite."},
    }
    agent.predict(STATE, qs)  # warm-up
    t = time.time(); r = agent.predict(STATE, qs); ms = (time.time() - t) * 1000
    print(f"\n== Laya (ModernBERT-large 421M, RLCD-trained)  {ms:.0f} ms for 4 questions")
    for k, a in r["answers"].items():
        print(f"  {k:15s} {a.get('choice', a.get('noul'))!s:12} conf={a['confidence']:.2f} {a.get('probabilities', '')}")

def run_kotoba():
    from typed_decisions.open_jev import OpenJev
    m = OpenJev.from_pretrained("com-kotobalabs/open-jev-deberta-v3-large", device="cpu")
    state = "Email: " + STATE["email"]
    qs = [
        {"type": "choice", "instructions": "What is the sender's main intent?", "options": ["reschedule", "cancel", "confirm", "other"]},
        {"type": "noul", "instructions": "A human should review this before the assistant replies."},
        {"type": "noul", "instructions": "This needs action within the next few hours."},
        {"type": "noul", "instructions": "The sender reports not receiving a calendar invite."},
    ]
    m.decide(state, qs)  # warm-up
    t = time.time(); r = m.decide(state, qs); ms = (time.time() - t) * 1000
    print(f"\n== kotoba open-jev (DeBERTa-v3-large 435M)  {ms:.0f} ms for 4 questions")
    for q, a in zip(["intent", "needs_human", "urgent", "missing_invite"], r):
        print(f"  {q:15s} {json.dumps(a, default=str)[:160]}")

if __name__ == "__main__":
    run_laya()
    run_kotoba()
