"""Merge engines from a results_*_local.json (runs made from .venv-local: decider, kev) into the main results file.
Run: .venv/bin/python bench/merge_local.py results_calib_private  (merges results_calib_private_local.json into results_calib_private.json)"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for base in sys.argv[1:]:
    main_p, loc_p = os.path.join(HERE, f"{base}.json"), os.path.join(HERE, f"{base}_local.json")
    main, loc = json.load(open(main_p)), json.load(open(loc_p))
    for k, v in loc["engines"].items():
        main["engines"][k] = v
    json.dump(main, open(main_p, "w"), indent=1)
    print(base, "engines:", list(main["engines"]))
