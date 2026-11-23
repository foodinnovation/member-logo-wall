# SFR member logo wall

The logo wall of Swiss Food Research members, published at https://foodinnovation.github.io/member-logo-wall/ and embedded on swissfoodresearch.ch through a fixed iframe block in the Django admin.

This repository holds only the build code. The wall itself (page, logos, fonts) is built from monday on every run and published straight to GitHub Pages, so no member logo is ever stored here, and a cancelled member disappears from the website at the next run.

## How it runs

Every Monday at about 05:17 Zurich time, the workflow `Rebuild logo wall` (in `.github/workflows/rebuild.yml`):

1. pulls the active members of the monday board **Mitglieder** (1597941591) with the files in their **Logo** column (`build/fetch_board.py`);
2. builds the page: one tile per organisation, departments of one institution merged, white logos on dark tiles, natural persons and ZZ/test records left out (`build/logo_wall.py`);
3. opens it in a headless browser and checks tiles, logos, header count, search, filters and frame resizing (`build/verify.py`);
4. compares the member count with the live site and stops if it moved by more than 15% (`build/compare_live.py`);
5. publishes to GitHub Pages.

If any step fails, nothing is published and the last good version stays online. GitHub sends a failure email to the account that owns the workflow.

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

## The block in Django

Pasted once into the HTML element of the page; it does not change between runs:

```html
<iframe id="sfr-logo-wall" src="https://foodinnovation.github.io/member-logo-wall/" title="Members of Swiss Food Research" loading="lazy" style="width:100%;height:1400px;border:0;display:block"></iframe>
<script>window.addEventListener("message",function(e){if(e.origin==="https://foodinnovation.github.io"&&e.data&&e.data.sfrLogoWall){document.getElementById("sfr-logo-wall").style.height=e.data.sfrLogoWall+"px"}});</script>
```

Logos belong to the members and are shown only to document SFR membership.
