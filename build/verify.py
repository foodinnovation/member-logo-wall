#!/usr/bin/env python3
"""Checks the built logo wall the way a visitor sees it. usage: python3 verify.py WORKDIR
Serves WORKDIR/site on a local web server, opens it directly and through the CMS block
(with the Pages address swapped for the local one), and checks tiles, logos, count, search,
filters, frame resizing and that nothing loads from outside."""
import functools, http.server, json, pathlib, re, sys, threading
from playwright.sync_api import sync_playwright

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

W = pathlib.Path(sys.argv[1]); site = W / "site"
block = sorted((W / "out").glob("*_Website_Member-Logo-Wall-CMS-Block_v*.html"))[-1].read_text(encoding="utf-8")
counts = json.load(open(W / "last_counts.json"))

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
local = f"http://127.0.0.1:{srv.server_port}/"
pages_url = re.search(r'src="(https://[^"]+)"', block).group(1)
pages_origin = "/".join(pages_url.split("/")[:3])
host = W / "check_host.html"
host.write_text("<html><body style='margin:40px'><h1>Host page</h1>" +
                block.replace(pages_url, local).replace(pages_origin, local.rstrip("/")) + "<p>after</p></body></html>", encoding="utf-8")

fails = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 1000})
    errs, outside = [], []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("request", lambda r: outside.append(r.url[:70]) if r.url.startswith("http") and not r.url.startswith(local) else None)
    pg.goto(local)
    pg.evaluate("document.querySelectorAll('img').forEach(i=>i.loading='eager')"); pg.wait_for_timeout(3000)
    r = pg.evaluate("""({tiles:document.querySelectorAll('#grid li').length, imgs:document.images.length,
        ok:[...document.images].filter(i=>i.naturalWidth).length, count:document.getElementById('n').textContent,
        font:document.fonts.check('700 20px "Funnel Sans"')})""")
    if r["tiles"] != counts["tiles"]: fails.append(f"tiles on screen {r['tiles']} != {counts['tiles']}")
    if r["ok"] != r["imgs"]: fails.append(f"{r['imgs']-r['ok']} logos did not load: " + str(pg.evaluate("[...document.images].filter(i=>!i.naturalWidth).map(i=>i.alt).slice(0,8)")))
    if r["count"] != f"{counts['members']} members": fails.append(f"header shows '{r['count']}'")
    if not r["font"]: fails.append("Funnel Sans did not load from fonts/")
    pg.screenshot(path=str(W / "check_top.png"))

    pg.goto(host.resolve().as_uri()); pg.wait_for_timeout(3000)
    frame = lambda: pg.evaluate("document.getElementById('sfr-logo-wall').offsetHeight")
    f = pg.frames[1]; full = frame(); content = f.evaluate("Math.ceil(document.querySelector('.wall').getBoundingClientRect().height)")
    if abs(full - content) > 40: fails.append(f"frame height {full} does not follow the wall ({content})")
    f.fill("#q", "zhaw"); pg.wait_for_timeout(500)
    if f.locator("#grid li:not([hidden])").count() < 1: fails.append("search for 'zhaw' finds nothing")
    if frame() >= full: fails.append("frame does not shrink after filtering")
    f.fill("#q", ""); f.locator("#sec .chip").nth(1).click(); pg.wait_for_timeout(300)
    if not 0 < f.locator("#grid li:not([hidden])").count() < counts["tiles"]: fails.append("sector filter does not filter")
    b.close()
srv.shutdown()
if errs: fails.append(f"script errors: {errs}")
if outside: fails.append(f"requests outside the site: {sorted(set(outside))[:5]}")
print(r, "| frame", full)
print("VERIFY OK" if not fails else "VERIFY FAILED:\n- " + "\n- ".join(fails))
sys.exit(1 if fails else 0)
