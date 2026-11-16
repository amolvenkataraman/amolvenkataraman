# readme_art

Generates the banner, section labels and project cards used in this profile README, plus the
per-repo banners and [HAI Scale](https://haiscale.amolven.com/) disclosure banners.

The style matches [amolven.com](https://amolven.com) and the uwnotes PDFs: Source Serif 4 for names,
Instrument Sans for everything else, with teal accents. Every SVG switches between light and dark on its
own through a `prefers-color-scheme` rule, and all text is converted to outlines, so it renders the same
on GitHub without web fonts.

## Use

```bash
uv venv && uv pip install -p .venv/bin/python fonttools uharfbuzz
.venv/bin/python tools/readme_art.py tools/profile.json .
```

Edit `profile.json`, rerun, commit the changed SVGs. Each entry has a `kind`:

| kind | fields |
|---|---|
| `banner` | `eyebrow`, `name`, `pitch`, then `type`, `stack`, `started`, `status` (or a custom `fields` list of 4 label/value pairs) |
| `card2` | `name`, `hai`, `pitch`, `started`, `stack`, `status` |
| `section` | `label` |
| `hai` | `hai` (tier code), `statement`, `note` |

Fonts are included under the SIL Open Font License (see `fonts/OFL-*.txt`).

## Repo headers and the org profile

`tools/repos.json` describes the header for each repo (banner, badges, nav links, HAI Scale tier and statement),
and `tools/org.json` plus `org_intro.md` / `org_body.md` describe the upstream-wontfix org profile.

```bash
.venv/bin/python tools/headers.py fetch     # current READMEs → build/<repo>/README.orig.md
.venv/bin/python tools/headers.py build     # art + new READMEs → build/
.venv/bin/python tools/preview.py           # build/preview.html, rendered by GitHub in light and dark
.venv/bin/python tools/headers.py push uwquest   # commit one repo's header (omit names to push all)
```

The header sits between `<!-- header:start -->` and `<!-- header:end -->`, so a rebuild replaces it in place.
