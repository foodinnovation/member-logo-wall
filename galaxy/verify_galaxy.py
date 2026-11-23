#!/usr/bin/env python3
"""Checks the built galaxy the way a visitor sees it. usage: python3 verify_galaxy.py WORKDIR
Renders WORKDIR/site/galaxy/index.html in headless Chromium: member count on screen equals the
dataset, title is "Our members", the accessibility list is complete, search and group chips
work, no script errors, no external requests."""
import json, os, sys
from playwright.sync_api import sync_playwright

wd = sys.argv[1]
page_path = os.path.abspath(os.path.join(wd, "site", "galaxy", "index.html"))
members = json.load(open(os.path.join(wd, "galaxy_members.json")))
expected = len(members)
problems, external, errors = [], [], []
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1600, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("request", lambda r: external.append(r.url) if not r.url.startswith(("file:", "data:")) else None)
    pg.goto("file://" + page_path); pg.wait_for_timeout(3500)
    shown = int(pg.inner_text("#n-orgs"))
    if shown != expected: problems.append(f"member count on page is {shown}, dataset has {expected}")
    if pg.inner_text("h1").strip() != "Our members": problems.append("title is not 'Our members'")
    a11y = pg.evaluate("document.querySelectorAll('#a11y-list li').length")
    if a11y != expected: problems.append(f"accessibility list has {a11y} entries, expected {expected}")
    probe = members[0]["name"][:6]
    pg.fill("#f-search", probe); pg.wait_for_timeout(300)
    if int(pg.inner_text("#n-orgs")) < 1: problems.append(f"search for {probe!r} found nothing")
    pg.fill("#f-search", ""); pg.wait_for_timeout(200)
    pg.evaluate("document.querySelector('.ig-pill').click()"); pg.wait_for_timeout(300)
    chip = int(pg.inner_text("#n-orgs"))
    if not 0 < chip < expected: problems.append(f"group chip did not narrow the view ({chip})")
    pg.screenshot(path=os.path.join(wd, "check_galaxy.png"))
    b.close()
if external: problems.append(f"external requests: {external[:3]}")
if errors: problems.append(f"console errors: {errors[:3]}")
print("GALAXY VERIFY FAILED\n - " + "\n - ".join(problems) if problems else f"GALAXY VERIFY OK ({expected} members)")
sys.exit(1 if problems else 0)
