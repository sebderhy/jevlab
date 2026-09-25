"""Inject the rows from car_slide.py into the deck's car slide table (between its header row and </table>)."""
import json, re
p = "/home/seb/reports/jev-deck.html"; s = open(p).read()
rows = json.load(open("/home/seb/tmp/car_slide_rows.json"))["rows"]
hdr = '<tr><th>120 s runs, 3 seeds</th><th>Crashes</th><th>Traffic course, metres</th><th>Obstacle course, metres</th><th>Answer time</th><th>Recorded run, seed 42</th></tr>'
i = s.index(hdr) + len(hdr); j = s.index("</table>", i)
s = s[:i] + "\n        " + rows + "\n      " + s[j:]
open(p, "w").write(s); print("rows injected")
