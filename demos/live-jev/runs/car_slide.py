"""Rebuild the deck's car-demo slide (Demo 2) rows from runs/final.jsonl (24 Sept, same-day runs).
Real time: hosted brains only (a CPU model at tens of seconds per decision is not a real-time test).
Latency removed: the clock stops while a brain thinks; every brain decides every 0.2 s of simulated time (the simulator's native rate).
Writes /home/seb/tmp/car_slide_rows.json and prints the rows."""
import json
F = "/home/seb/jevlab/demos/live-jev/runs/final.jsonl"
runs = [json.loads(l) for l in open(F) if l.strip()]
def sel(b, t):
    """The latest run per (seed, course): 6 runs = 3 seeds x 2 courses; a re-recorded video run replaces the earlier one for its seed."""
    latest = {}
    for r in runs:
        if r["brainKind"] == b and r["tempo"] == t:
            latest[(r["seed"], r["course"])] = r
    return list(latest.values())
def ms(rs): return sum(int(r["brain"].split("avg ")[1].split("ms")[0]) for r in rs) / len(rs)
def rng(rs, course):
    d = sorted(r["distance_m"] for r in rs if r["course"] == course)
    return "n/a" if not d else (f"{d[0]:,}" if len(d) == 1 else f"{d[0]:,} to {d[-1]:,}")
def crashes(rs): return sum(1 for r in rs if r["crashed"])
def vid(b, t, v=1):
    x = [r for r in runs if r["brainKind"] == b and r["tempo"] == t and r.get("video") == v]
    return x[-1] if x else None
def res(r): return "not recorded" if r is None else (f"crash at {r['crashed']['time']:.0f} s, {r['distance_m']:,} m" if r["crashed"] else f"{r['distance_m']:,} m, clean")
B = [("jev", "Jev", "#d6407f"), ("llm", "DeepSeek V4.1 Flash", "#2a78d6"), ("kev", "Kev-4B (CPU)", "#006b00")]
rows = ""
for t, tname, brains, v in (("real", "Real time: hosted models only", ("jev", "llm"), 2), ("slowed", "Latency removed: every brain decides 5 times per simulated second", ("jev", "llm", "kev"), 1)):
    rows += f'<tr><td colspan="6" style="padding-top:12px;font-size:15px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)">{tname}</td></tr>'
    for b, name, col in B:
        if b not in brains: continue
        rs = sel(b, t)
        if not rs: continue
        n = len(rs)
        batch = f"{crashes(rs)} of {n}" if n > 1 else ("1 run, crashed" if crashes(rs) else "1 run, clean")
        rows += (f'<tr><td style="white-space:nowrap;color:{col}"><b>{name}</b></td><td class="n">{batch}</td>'
                 f'<td class="n">{rng(rs, "traffic")}</td><td class="n">{rng(rs, "gauntlet")}</td><td class="n">{ms(rs)/1000:.2f} s</td><td class="n">{res(vid(b, t, v))}</td></tr>')
json.dump({"rows": rows}, open("/home/seb/tmp/car_slide_rows.json", "w"))
print(rows.replace("</tr>", "</tr>\n"))
