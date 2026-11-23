#!/usr/bin/env python3
"""Pulls the active members of the monday board Mitglieder (1597941591) with their logo files,
and the one-line descriptions from the Companies board (5098460127) used by the galaxy.
usage: MONDAY_API_TOKEN=... python3 fetch_board.py OUT/board.json
Also writes OUT/companies.json: [{"name":..., "description":...}, ...]
Writes the same shape the build expects: {"data":{"boards":[{"items_page":{"cursor":null,"items":[...]}}]}}.
The logo links (public_url) expire after one hour, so the build must run straight after."""
import json, os, pathlib, sys, time, urllib.request

BOARD, STATUS_ACTIVE = 1597941591, 0     # Status column status__1, label index 0 = active
FIELDS = """id name column_values(ids:["companysize__1","drop_down_mkkb7b31","dropdown_mm47hc35","link_mm47xh4f","enablemembers__1","short_textjdbqe5zb"]) { id text }
            assets(assets_source: columns, column_ids:["filejn1oxvcs"]) { name file_extension public_url }"""
FIRST = f"""query {{ boards(ids:[{BOARD}]) {{ items_page(limit:200, query_params:{{rules:[{{column_id:"status__1", compare_value:[{STATUS_ACTIVE}], operator:any_of}}]}}) {{ cursor items {{ {FIELDS} }} }} }} }}"""
NEXT = "query($c:String!) { next_items_page(limit:200, cursor:$c) { cursor items { " + FIELDS + " } } }"
COMPANIES, DESC_COL = 5098460127, "text_mm489x1q"
C_FIELDS = f'name column_values(ids:["{DESC_COL}"]) {{ text }}'
C_FIRST = f"query {{ boards(ids:[{COMPANIES}]) {{ items_page(limit:500) {{ cursor items {{ {C_FIELDS} }} }} }} }}"
C_NEXT = "query($c:String!) { next_items_page(limit:500, cursor:$c) { cursor items { " + C_FIELDS + " } } }"

token = os.environ.get("MONDAY_API_TOKEN") or sys.exit("STOP: MONDAY_API_TOKEN is not set (repository secret missing?)")

def call(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    for attempt in range(4):
        req = urllib.request.Request("https://api.monday.com/v2", data=body, method="POST",
                                     headers={"Authorization": token, "Content-Type": "application/json", "API-Version": "2025-04"})
        try:
            out = json.load(urllib.request.urlopen(req, timeout=120))
        except Exception as e:
            err = str(e)
        else:
            if "errors" not in out and "error_message" not in out:
                return out["data"]
            err = json.dumps(out.get("errors") or out.get("error_message"))[:500]
        time.sleep(10 * (attempt + 1))
    sys.exit(f"STOP: monday API call failed: {err}")

page = call(FIRST)["boards"][0]["items_page"]
items, cursor = page["items"], page["cursor"]
while cursor:
    page = call(NEXT, {"c": cursor})["next_items_page"]
    items += page["items"]; cursor = page["cursor"]

out = pathlib.Path(sys.argv[1]); out.parent.mkdir(parents=True, exist_ok=True)
json.dump({"data": {"boards": [{"items_page": {"cursor": None, "items": items}}]}}, open(out, "w"), ensure_ascii=False)
comp = []
page = call(C_FIRST)["boards"][0]["items_page"]
while True:
    comp += [{"name": i["name"], "description": (i["column_values"][0].get("text") or "").strip()} for i in page["items"]]
    if not page["cursor"]: break
    page = call(C_NEXT, {"c": page["cursor"]})["next_items_page"]
if len(comp) < 1000: sys.exit(f"STOP: only {len(comp)} companies pulled from the Companies board; expected about 3000")
json.dump(comp, open(out.parent / "companies.json", "w"), ensure_ascii=False)
print(f"pulled {len(comp)} companies, {sum(1 for c in comp if c['description'])} with a description")
print(f"pulled {len(items)} active members, {sum(1 for i in items if i.get('assets'))} with a logo file")
