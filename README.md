# SFR member logo wall and member galaxy

Two views of the Swiss Food Research members, both built from the monday board Mitglieder and embedded on swissfoodresearch.ch through fixed iframe blocks in the Django admin:

- **Logo wall**: https://foodinnovation.github.io/member-logo-wall/ (code in `build/`)
- **Member galaxy** ("Our members"): https://foodinnovation.github.io/member-logo-wall/galaxy/ (code and design in `galaxy/`)

This repository holds only the build code. Both pages are built from monday on every run and published straight to GitHub Pages, so no member logo or member list is ever stored here, and a cancelled member disappears from the website at the next run.

## How it runs

Every Monday at about 05:17 Zurich time, the workflow `Rebuild logo wall` (in `.github/workflows/rebuild.yml`):

1. pulls the active members of the monday board **Mitglieder** (1597941591) with the files in their **Logo** column (`build/fetch_board.py`);
2. builds the page: one tile per organisation, departments of one institution merged, white logos on dark tiles, natural persons and ZZ/test records left out (`build/logo_wall.py`);
3. opens it in a headless browser and checks tiles, logos, header count, search, filters and frame resizing (`build/verify.py`);
4. builds the galaxy from the same pull plus the one-line descriptions on the Companies board (5098460127), and checks it the same way (`galaxy/build_galaxy.py`, `galaxy/verify_galaxy.py`). Its design, fonts and SFR logo are frozen in `galaxy/galaxy-template.html` and the `.b64` files: change them only on explicit request;
5. compares the member count with the live site and stops if it moved by more than 15% (`build/compare_live.py`);
6. publishes both to GitHub Pages.

If any step fails, nothing is published and the last good version stays online. GitHub sends a failure email to the account that owns the workflow.

A single logo file that cannot be used (download fails, not an image, browsers cannot display it) does not stop the run: that member is shown as a name tile and the file is listed in the run's summary on GitHub (and in `logo-problems.md` among the run's artifacts), to be replaced on monday. Only when many downloads fail at once, which means monday is down or the links expired, does the run stop.

## Run it by hand

Actions tab > Rebuild logo wall > Run workflow. Tick **force** only when a large change in member numbers is real.

Each run keeps the tile list (`*.csv`: organisation, monday entries, logo file, website, tile colour) and a screenshot for 30 days under the run's artifacts.

## Settings it depends on

- Repository secret `MONDAY_API_TOKEN`: a monday personal API token with read access to the Mitglieder board.
- Settings > Pages > Source: **GitHub Actions**.

## Common fixes

All in the constants at the top of `build/logo_wall.py`:

- A logo invisible on white: add the tile name to `FORCE_DARK`. A logo wrongly on a dark tile: add it to `FORCE_WHITE`.
- A department on its own tile: give it the institution's identical logo file on monday, or add a name pattern to `FORCE_MERGE`.
- A new Innovation Group label: add its website name to `IG_NAMES`.
- A wrong logo: replace the file in the Logo column on monday; the next run picks it up.

## The blocks in Django

Pasted once into the HTML element of each page; they do not change between runs.

Logo wall:

```html
<iframe id="sfr-logo-wall" src="https://foodinnovation.github.io/member-logo-wall/" title="Members of Swiss Food Research" loading="lazy" style="width:100%;height:1400px;border:0;display:block"></iframe>
<script>window.addEventListener("message",function(e){if(e.origin==="https://foodinnovation.github.io"&&e.data&&e.data.sfrLogoWall){document.getElementById("sfr-logo-wall").style.height=e.data.sfrLogoWall+"px"}});</script>
```

Member galaxy:

```html
<iframe src="https://foodinnovation.github.io/member-logo-wall/galaxy/" title="Our members" loading="lazy" style="width:100%;height:min(760px,85vh);border:0;display:block"></iframe>
```

Logos belong to the members and are shown only to document SFR membership.
