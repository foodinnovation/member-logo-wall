#!/usr/bin/env python3
"""SFR member logo wall: builds a paste-ready CMS block from one monday pull.

usage: python3 logo_wall.py WORKDIR [--version NN] [--date YYMMDD]
WORKDIR must contain board.json (written by fetch_board.py, or the same GraphQL pull made through the monday connector).
Writes WORKDIR/site/ (index.html, logos/, fonts/: the whole GitHub Pages site, replaced on every run) and into WORKDIR/out/:
  YYMMDD_Website_Member-Logo-Wall-CMS-Block_vNN.html   iframe that points at the Pages site (pasted into Django once)
  YYMMDD_Website_Member-Logo-Wall-Tile-List_vNN.csv    one row per tile, for checking
and prints a report. Exits non-zero on anything that should stop delivery.
"""
import argparse, base64, os, shutil, unicodedata, collections, concurrent.futures as cf, csv, datetime, hashlib, html, io, json, pathlib, re, subprocess, sys

from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # some members upload print-size PNGs

# ---------------------------------------------------------------- fixed facts
LOGO_COL, IG_COL, SECTOR_COL, WEB_COL, SIZE_COL = "filejn1oxvcs", "drop_down_mkkb7b31", "dropdown_mm47hc35", "link_mm47xh4f", "companysize__1"
IG_NAMES = {"Aqua": "Aquaculture", "Chocolate": "Cocoa & Chocolate", "Digi": "Digitalization",
            "Fungi": "Fungi & Fungal Systems", "P4F": "Proteins4Future"}
# Display name for institutions whose departments are separate members sharing one logo (matched on the member name).
INSTITUTIONS = [(r"^ZHAW\b", "ZHAW Zürcher Hochschule für Angewandte Wissenschaften"),
                (r"^FIBL\b", "FiBL Forschungsinstitut für biologischen Landbau"),
                (r"^BFH\b", "BFH Berner Fachhochschule"),
                (r"ETH ?Z", "ETH Zürich"),
                (r"^Agroscope\b", "Agroscope"),
                (r"^HES-SO\b", "HES-SO Haute école spécialisée de Suisse occidentale"),
                (r"^(Fresh Food|Bischofszell)", "Fresh Food & Beverage Group")]
# Members merged although their logo files differ: name pattern -> institution name above.
FORCE_MERGE = {r"^Bischofszell Nahrungsmittel": "Fresh Food & Beverage Group"}
# Lightness test errs on these; keep the list short and explain each entry in SKILL.md.
FORCE_DARK = {"Vivent SA"}      # white wordmark next to a green mark
FORCE_WHITE = set()
LIGHT_SHARE, MIN_TRANSPARENT = 0.9, 0.05
SITE_URL = "https://foodinnovation.github.io/member-logo-wall/"   # GitHub Pages address of the repo foodinnovation/member-logo-wall

ap = argparse.ArgumentParser()
ap.add_argument("workdir"); ap.add_argument("--version", default="01"); ap.add_argument("--date", default=datetime.date.today().strftime("%y%m%d"))
args = ap.parse_args()
W = pathlib.Path(args.workdir); OUT = W / "out"; LOGOS = W / "logos"; SITE = W / "site"
OUT.mkdir(exist_ok=True); LOGOS.mkdir(exist_ok=True)
shutil.rmtree(SITE, ignore_errors=True); (SITE / "logos").mkdir(parents=True); (SITE / "fonts").mkdir()
stem = f"{args.date}_Website_Member-Logo-Wall-{{}}_v{int(args.version):02d}"

def die(msg): print("STOP:", msg); sys.exit(1)

# ---------------------------------------------------------------- read pull
raw = json.load(open(W / "board.json"))
raw = raw.get("data", raw)
page = raw["boards"][0]["items_page"]
if page.get("cursor"): die("board.json is a partial page (cursor set). Page through and merge before building.")
items = page["items"]
if len(items) < 200: die(f"only {len(items)} active members pulled; check the status filter (index 0 = active).")

def cv(it, col):
    for c in it["column_values"]:
        if c["id"] == col: return (c.get("text") or "").strip()
    return ""

# ---------------------------------------------------------------- download logos
jobs = {}
for it in items:
    a = [x for x in it.get("assets") or [] if x.get("public_url")]
    if a:
        x = a[-1]; ext = (x.get("file_extension") or ".png").lower()
        jobs[it["id"]] = (LOGOS / f"{it['id']}{ext}", x["public_url"], x["name"])

def fetch(j):
    path, url, _ = j
    r = subprocess.run(["curl", "-sS", "-L", "-m", "90", "-o", str(path), "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()
with cf.ThreadPoolExecutor(8) as ex:
    codes = dict(zip(jobs, ex.map(fetch, jobs.values())))
# One bad file only costs that member its logo (name tile instead). Many failures mean monday is down
# or the links expired, and then nothing is published.
problems = []      # (organisation, logo file on monday, what went wrong): reported, never fatal
names = {it["id"]: it["name"].strip() for it in items}
bad = {i: c for i, c in codes.items() if c != "200"}
if len(bad) > max(5, len(jobs) // 20):
    die(f"{len(bad)} of {len(jobs)} logo downloads failed {sorted(set(bad.values()))}. Links expire after an hour: re-run the pull, then build at once.")
for i, c in bad.items():
    problems.append((names[i], jobs[i][2], "download failed (" + (f"HTTP {c}" if c.strip("0") else "no answer") + ")")); del jobs[i]

def web_logo(path):
    """(bytes, extension) as published: SVG unchanged, raster shrunk to tile size as WebP."""
    if path.suffix == ".svg":
        return path.read_bytes(), "svg"
    im = Image.open(path)
    im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA", "PA") or "transparency" in im.info else im.convert("RGB")
    im.thumbnail((400, 260), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "WEBP", quality=86, method=6)
    return b.getvalue(), "webp"

def data_uri(path):  # used only to measure lightness in the browser
    data, ext = web_logo(path)
    return f"data:image/{'svg+xml' if ext == 'svg' else ext};base64," + base64.b64encode(data).decode()

def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "logo"

# ---------------------------------------------------------------- tiles
def institution(name):
    for pat, inst in FORCE_MERGE.items():
        if re.search(pat, name, re.I): return inst
    for pat, inst in INSTITUTIONS:
        if re.search(pat, name, re.I): return inst
    return None

skipped, tiles = [], {}
for it in items:
    name = it["name"].strip()
    if cv(it, SIZE_COL) == "Natural Person" or re.match(r"(?i)zz\b", name) or re.search(r"(?i)\btest\b", name):
        skipped.append(name); continue
    j = jobs.get(it["id"])
    digest = hashlib.sha256(j[0].read_bytes()).hexdigest() if j else None
    inst = institution(name)
    if any(re.search(p, name, re.I) for p in FORCE_MERGE) or (inst in FORCE_MERGE.values()): key = "inst:" + inst
    elif digest: key = "logo:" + digest          # departments of one institution share the identical file
    else: key = "id:" + it["id"]
    t = tiles.setdefault(key, {"n": name, "f": "", "u": "", "ig": [], "s": [], "members": [], "src": "", "inst": inst})
    t["members"].append(name)
    if len(t["members"]) > 1 and t["inst"]: t["n"] = t["inst"]
    if j and not t["f"]:
        try: t["f"], t["src"], t["path"] = data_uri(j[0]), j[2], j[0]
        except Exception as e: problems.append((name, j[2], f"file is not a usable image ({type(e).__name__})"))
    m = re.search(r"https?://\S+", cv(it, WEB_COL))
    t["u"] = t["u"] or (m.group(0) if m else "")
    for g in [g.strip() for g in cv(it, IG_COL).split(",") if g.strip()]:
        g = IG_NAMES.get(g, g)
        if g not in t["ig"]: t["ig"].append(g)
    s = cv(it, SECTOR_COL)  # single-select; a label may itself hold a comma
    if s and s not in t["s"]: t["s"].append(s)

data = sorted(tiles.values(), key=lambda t: t["n"].casefold())

# ---------------------------------------------------------------- white logos -> dark tile (measured in a browser)
from playwright.sync_api import sync_playwright
MEASURE = """async (srcs)=>{const out=[];for(const s of srcs){const im=new Image();im.src=s;
 try{await im.decode()}catch(e){out.push(null);continue}
 const w=200,h=Math.max(1,Math.round(200*(im.naturalHeight||100)/(im.naturalWidth||200)));const c=document.createElement('canvas');c.width=w;c.height=h;
 const x=c.getContext('2d');x.drawImage(im,0,0,w,h);const d=x.getImageData(0,0,w,h).data;let op=0,li=0,tr=0;
 for(let i=0;i<d.length;i+=4){const a=d[i+3]/255;if(a<0.15){tr++;continue}const L=0.2126*d[i]+0.7152*d[i+1]+0.0722*d[i+2];op+=a;if(L>205)li+=a}
 out.push({light:op?li/op:0,transp:tr/(w*h)})}return out}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto("about:blank")
    logo_tiles = [t for t in data if t["f"]]
    stats = pg.evaluate(MEASURE, [t["f"] for t in logo_tiles]); b.close()
for t, s in zip(logo_tiles, stats):
    if s is None:   # browsers cannot display this file: name tile instead
        problems.append((t["n"], t["src"], "browsers cannot display the file")); t["f"] = ""; t.pop("path", None); continue
    dark = (s["light"] >= LIGHT_SHARE and s["transp"] > MIN_TRANSPARENT) or t["n"] in FORCE_DARK
    if dark and t["n"] not in FORCE_WHITE: t["d"] = 1
    t["light"] = round(s["light"], 2)

# ---------------------------------------------------------------- fonts (Funnel Sans, embedded)
fonts = ""
FONT_DIR = pathlib.Path(__file__).parent / "fonts"   # Funnel Sans (SIL Open Font License), kept in the repo
for w in (400, 600, 700):
    shutil.copy(FONT_DIR / f"funnel-sans-{w}.woff2", SITE / "fonts" / f"funnel-sans-{w}.woff2")
    fonts += f'@font-face{{font-family:"Funnel Sans";font-style:normal;font-weight:{w};font-display:swap;src:url(fonts/funnel-sans-{w}.woff2) format("woff2")}}\n'

# ---------------------------------------------------------------- page
used = set()
for t in data:
    if t["f"]:
        blob, ext = web_logo(t["path"]); base = slug(t["n"]); n = base; k = 2
        while n in used: n = f"{base}-{k}"; k += 1
        used.add(n); (SITE / "logos" / f"{n}.{ext}").write_bytes(blob); t["f"] = f"logos/{n}.{ext}"
igs = sorted({g for t in data for g in t["ig"]}, key=str.casefold)
secs = sorted({s for t in data for s in t["s"]}, key=str.casefold)
payload = [{k: v for k, v in t.items() if k in ("n", "f", "u", "ig", "s", "d") and v} for t in data]
shown = len(items) - len(skipped)
page_html = pathlib.Path(__file__).with_name("template.html").read_text(encoding="utf-8")
page_html = (page_html.replace("/*__FONTS__*/", fonts)
             .replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
             .replace("__IGS__", json.dumps(igs, ensure_ascii=False)).replace("__SECTORS__", json.dumps(secs, ensure_ascii=False))
             .replace("__COUNT__", str(shown)))
if re.search(r"__[A-Z]+__", page_html): die("template placeholder left unfilled")
if re.search(r"https?://", page_html.split("<script>")[0]): die("external URL in page head")

(SITE / "index.html").write_text(page_html, encoding="utf-8")
(SITE / ".nojekyll").write_text("")
json.dump({"members": shown, "tiles": len(data), "built": args.date}, open(SITE / "counts.json", "w"))
(SITE / "about.txt").write_text("SFR member logo wall, built from the monday board Mitglieder (active members only) by "
                               "github.com/foodinnovation/member-logo-wall. Logos belong to the members and are shown only to document SFR membership.\n")
# The block never changes between refreshes: it only points at the Pages site and resizes the frame to the wall.
block = ('<!-- SFR member logo wall. Content is served from ' + SITE_URL + ' and refreshed there; this block stays unchanged. -->\n'
         '<iframe id="sfr-logo-wall" src="' + SITE_URL + '" title="Members of Swiss Food Research" loading="lazy" '
         'style="width:100%;height:1400px;border:0;display:block"></iframe>\n'
         '<script>window.addEventListener("message",function(e){if(e.origin==="' + SITE_URL.split("/")[0] + "//" + SITE_URL.split("/")[2] + '"&&e.data&&e.data.sfrLogoWall)'
         '{document.getElementById("sfr-logo-wall").style.height=e.data.sfrLogoWall+"px"}});</script>\n')
(OUT / (stem.format("CMS-Block") + ".html")).write_text(block, encoding="utf-8")
with open(OUT / (stem.format("Tile-List") + ".csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh, delimiter=";")
    w.writerow(["Organisation", "Member entries on monday", "Logo file on monday", "Website", "Tile", "Light share"])
    for t in data:
        w.writerow([t["n"], " | ".join(t["members"]), t["src"] or "no logo in the Logo column", t["u"],
                    "name tile" if not t["f"] else ("dark" if t.get("d") else "white"), t.get("light", "")])

json.dump({"members": shown, "tiles": len(data)}, open(W / "last_counts.json", "w"))
logo_tiles = [t for t in data if t["f"]]
# Report for whoever looks after the board: files to replace on monday, members still without a logo.
report = ["## Logo wall: logo files to check on monday", ""]
if problems:
    report += ["These members are shown as a name tile until the file in their Logo column is replaced:", "",
               "| Organisation | File on monday | Problem |", "|---|---|---|"]
    report += [f"| {n} | {f} | {why} |" for n, f, why in problems]
else:
    report += ["All logo files on monday could be used."]
flagged = {n for n, _, _ in problems}
report += ["", "Members without any file in the Logo column: " + (", ".join(t["n"] for t in data if not t["f"] and t["n"] not in flagged) or "none"), ""]
(OUT / "logo-problems.md").write_text("\n".join(report), encoding="utf-8")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh: fh.write("\n".join(report) + "\n")
print(f"active {len(items)} | shown {shown} | tiles {len(data)} | logos {len(logo_tiles)} | name tiles {len(data)-len(logo_tiles)} | no website {sum(1 for t in data if not t['u'])}")
print("excluded:", skipped)
print("name tiles:", [t["n"] for t in data if not t["f"]])
for n, f, why in problems: print(f"LOGO PROBLEM: {n} | {f} | {why}")
print("dark tiles:", [t["n"] for t in data if t.get("d")])
print("merged:", {t["n"]: len(t["members"]) for t in data if len(t["members"]) > 1})
unknown = [g for g in igs if g not in IG_NAMES.values() and g not in ("Bioconversion", "Coffee", "Future Proof Farming", "Grains & Baked Goods", "Insects", "Packaging", "Sustainable Nutrition")]
if unknown: print("NEW IG LABELS (add to IG_NAMES if they need a website name):", unknown)
print("site size MB:", round(sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file()) / 1e6, 2), "| files:", sum(1 for _ in SITE.rglob("*")))
