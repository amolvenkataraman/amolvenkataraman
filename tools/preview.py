"""Build build/preview.html: how each new README header renders on GitHub, in light and dark.

Uses GitHub's own Markdown renderer (gh api markdown), inlines the generated SVGs and shields badges
as data URIs (forcing light or dark), and keeps only the top of each README.
    .venv/bin/python tools/preview.py
"""
import base64, binascii, json, os, re, subprocess, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
_badges = {}


def render(md, context):
    return subprocess.run(["gh", "api", "markdown", "-f", f"text={md}", "-f", "mode=gfm", "-f", f"context={context}"],
                          check=True, capture_output=True, text=True).stdout


def svg_uri(path, theme):
    svg = open(path).read()
    m = re.search(r"<style>(.*?)@media \(prefers-color-scheme:dark\)\{(.*)\}</style>", svg, re.S)
    if m:
        svg = svg[:m.start()] + f"<style>{m.group(2) if theme == 'dark' else m.group(1)}</style>" + svg[m.end():]
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def camo(url):
    if url not in _badges:
        real = binascii.unhexlify(url.rsplit("/", 1)[1]).decode()
        data = urllib.request.urlopen(urllib.request.Request(real, headers={"User-Agent": "readme-preview"}), timeout=20).read()
        mime = "image/svg+xml" if data.lstrip()[:4] in (b"<svg", b"<?xm") else "image/png"
        _badges[url] = f"data:{mime};base64," + base64.b64encode(data).decode()
    return _badges[url]


def top_of(md):
    """Header plus the intro, cut before the second level-2 heading."""
    heads = [m.start() for m in re.finditer(r"^## ", md, re.M)]
    return md[:heads[1]] if len(heads) > 1 else md


def pane(md, base, context, theme):
    h = render(md, context)
    h = re.sub(r'src="([^"]+\.svg)"', lambda m: f'src="{svg_uri(os.path.join(base, m.group(1)), theme)}"'
               if os.path.exists(os.path.join(base, m.group(1))) else m.group(0), h)
    h = re.sub(r"https://camo\.githubusercontent\.com/[0-9a-f]+/[0-9a-f]+", lambda m: camo(m.group(0)), h)
    h = re.sub(r'<img [^>]*src="(?!data:)[^"]*"[^>]*>', '<span class="ph">[screenshot]</span>', h)
    h = re.sub(r'<a target="_blank" rel="noopener noreferrer" href="[^"]*\.svg">(<img[^>]*>)</a>', r"\1", h)
    return f'<div class="gh {theme}"><div class="gh-hd">github.com/{context} · {theme}</div><article class="md">{h}</article></div>'


def main():
    specs = json.load(open(os.path.join(ROOT, "tools", "repos.json")))
    items = [(ROOT, "amolvenkataraman/amolvenkataraman", "Profile README"),
             (".github-org/profile", "upstream-wontfix/.github", "upstream-wontfix (org profile)")]
    items += [(s["repo"].split("/")[1], s["repo"], s["repo"]) for s in specs]
    sections = []
    for i, (d, ctx, title) in enumerate(items):
        base = os.path.join(BUILD, d)
        md = open(os.path.join(base, "README.md")).read()
        md = md if d.startswith(".github") or d == ROOT else top_of(md)
        sections.append(
            f'<section><h2>{title}</h2><div class="tabs" data-g="g{i}"><button aria-pressed="true" data-t="light">Light</button>'
            f'<button aria-pressed="false" data-t="dark">Dark</button></div>'
            f'<div class="frame" data-g="g{i}" data-t="light">{pane(md, base, ctx, "light")}</div>'
            f'<div class="frame" data-g="g{i}" data-t="dark" hidden>{pane(md, base, ctx, "dark")}</div></section>')
    tpl = open(os.path.join(ROOT, "tools", "preview_tpl.html")).read()
    open(os.path.join(BUILD, "preview.html"), "w").write(tpl.replace("{{sections}}", "\n".join(sections)))
    print(os.path.join(BUILD, "preview.html"))


if __name__ == "__main__":
    main()
