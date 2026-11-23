#!/usr/bin/env python3
"""Builds the "Our members" galaxy into WORKDIR/site/galaxy/index.html.

usage: python3 build_galaxy.py WORKDIR
WORKDIR must contain board.json and companies.json from build/fetch_board.py.
Run after build/logo_wall.py, which recreates WORKDIR/site.

The page design, fonts, SFR logo and group naming live in galaxy-template.html and the .b64
files next to this script (signed off by Lucas in August 2026); this script only fills in data.
Ported from the member-galaxy-refresh skill: same filters, same description matching.
"""
import datetime, json, os, re, sys, unicodedata, zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))

def norm(s):
    s = (s or "").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ")
    s = re.sub(r"\b(ag|gmbh|sa|sagl|sarl|ltd|llc|inc|kg|se|plc|co|genossenschaft|stiftung|verein|foundation|association)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)

def dom(s):
    if not s: return None
    m = re.search(r"([a-z0-9-]+(?:\.[a-z0-9-]+)+)", str(s), re.I)
    return m.group(1).lower().removeprefix("www.") if m else None

def clean(s):
    s = (s or "").strip()
    return s or None

# Whole word only: "Radicle (test)" and "ZZ TEST Website-Bridge" are test records,
# but "Swiss Quality Testing Services" is a real member.
TEST_NAME = re.compile(r"\btest\b|\bzz\b", re.I)

def fail(msg):
    print("GALAXY BUILD FAILED: " + msg); sys.exit(1)

wd = sys.argv[1] if len(sys.argv) == 2 else fail("usage: build_galaxy.py WORKDIR")
raw = json.load(open(os.path.join(wd, "board.json")))
items = raw.get("data", raw)["boards"][0]["items_page"]["items"]
companies = json.load(open(os.path.join(wd, "companies.json")))

desc = {}
for c in companies:
    k, d = norm(c["name"]), clean(c.get("description"))
    if k and d and k not in desc:
        desc[k] = d

orgs, np_skip, test_skip = [], [], []
from_companies = from_mitglieder = none = 0
for it in items:
    cv = {c["id"]: c.get("text") for c in it["column_values"]}
    name = (it.get("name") or "").strip()
    if len(re.sub(r"[^A-Za-z0-9]", "", name)) < 2:
        continue
    typ = clean(cv.get("companysize__1"))
    if typ == "Natural Person":             # people never appear on the public site
        np_skip.append(name); continue
    if TEST_NAME.search(name):              # internal test records stay internal
        test_skip.append(name); continue
    igs = [x.strip() for x in (clean(cv.get("drop_down_mkkb7b31")) or "").split(",") if x.strip()]
    web = dom(cv.get("enablemembers__1")) or dom(cv.get("link_mm47xh4f"))
    tagline = desc.get(norm(name))          # Companies board first, richer text
    if tagline: from_companies += 1
    else:
        tagline = clean(cv.get("short_textjdbqe5zb"))
        if tagline: from_mitglieder += 1
        else: none += 1; tagline = ""
    orgs.append({"name": name, "igs": igs, "type": typ, "sector": clean(cv.get("dropdown_mm47hc35")),
                 "tagline": tagline, "website": ("https://" + web) if web else None})

if len(orgs) < 150:
    fail(f"only {len(orgs)} members after filtering, far below normal (~290). Check the status filter.")

orgs.sort(key=lambda o: o["name"].lower())
data = json.dumps(orgs, ensure_ascii=False, separators=(",", ":"))
json.dump(orgs, open(os.path.join(wd, "galaxy_members.json"), "w"), ensure_ascii=False)

h = open(os.path.join(HERE, "galaxy-template.html")).read()
for ph, f in [("__NS400__", "noto-sans-latin-400-normal.b64"), ("__NS700__", "noto-sans-latin-700-normal.b64"),
              ("__LOGO__", "logo-official.b64")]:
    if ph not in h: fail(f"placeholder {ph} missing from template")
    h = h.replace(ph, open(os.path.join(HERE, f)).read().strip())
built = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Zurich")).isoformat(timespec="seconds")
if "/*__MEMBER_DATA__*/" not in h or "/*__BUILT_AT__*/" not in h:
    fail("data placeholders missing from template")
h = h.replace("/*__MEMBER_DATA__*/", data).replace("/*__BUILT_AT__*/", built)

out = os.path.join(wd, "site", "galaxy"); os.makedirs(out, exist_ok=True)
open(os.path.join(out, "index.html"), "w").write(h)

print(f"GALAXY BUILD OK: {len(orgs)} members (companies scanned: {len(companies)})")
print(f"descriptions: {from_companies} from Companies board, {from_mitglieder} Mitglieder fallback, {none} none")
print(f"natural persons excluded: {np_skip}")
print(f"test records excluded: {test_skip}")
print(f"without innovation group (Supporters): {sum(1 for o in orgs if not o['igs'])}")
print(f"page KB: {len(h) // 1024} | built at {built}")
