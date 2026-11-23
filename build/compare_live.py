#!/usr/bin/env python3
"""Stops publication when the member count moved suspiciously against the live site.
usage: python3 compare_live.py WORKDIR   (set FORCE=true to publish anyway)
A broken status filter looks exactly like a mass cancellation, so a swing of more than
MAX_SWING against the published counts.json needs a person to look before it goes live."""
import json, os, pathlib, sys, urllib.request

SITE_URL, MAX_SWING = "https://foodinnovation.github.io/member-logo-wall/", 0.15
new = json.load(open(pathlib.Path(sys.argv[1]) / "site" / "counts.json"))
try:
    live = json.load(urllib.request.urlopen(SITE_URL + "counts.json", timeout=30))
except Exception as e:
    print(f"no live counts to compare with ({e}); first publication, continuing"); sys.exit(0)
swing = abs(new["members"] - live["members"]) / max(live["members"], 1)
print(f"live: {live['members']} members ({live.get('built', '?')}) | new: {new['members']} members | change {swing:.0%}")
if swing > MAX_SWING and os.environ.get("FORCE", "").lower() != "true":
    sys.exit(f"STOP: member count moved by {swing:.0%}. Check the Status column on monday; "
             "if the change is real, run the workflow by hand with 'force' ticked.")
