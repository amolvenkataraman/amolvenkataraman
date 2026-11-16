"""Put the shared header (banner, badges, nav, HAI Scale banner) on top of each repo's README.

    .venv/bin/python tools/headers.py fetch            # download current READMEs into build/
    .venv/bin/python tools/headers.py build            # render art + new READMEs into build/<repo>/
    .venv/bin/python tools/headers.py push [repo ...]  # commit build/<repo>/ files to GitHub (asks nothing; run only when approved)

The header lives between <!-- header:start --> and <!-- header:end -->, so rebuilding replaces it in place.
Specs: tools/repos.json (one entry per repo) and tools/org.json (the upstream-wontfix org profile).
"""
import base64, json, os, re, subprocess, sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import readme_art as art  # noqa: E402

BUILD = os.path.join(ROOT, "build")
START, END = "<!-- header:start -->", "<!-- header:end -->"
TEAL = "labelColor=15181c&color=0f6f68"


def gh(*args, input=None):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, input=input).stdout


def badge(label, value, link):
    if value.startswith("dynamic:"):
        url = value[len("dynamic:"):]
    else:
        esc = lambda s: quote(s.replace("-", "--").replace("_", "__"), safe="")
        url = f"https://img.shields.io/badge/{esc(label)}-{esc(value)}-0f6f68?{TEAL}"
    img = f"![{label}: {value.split(':')[0] if value.startswith('dynamic:') else value}]({url})"
    if value.startswith("dynamic:"):
        img = f"![{label}]({url})"
    return f"[{img}]({link})" if link else img


def header(spec, assets=".github/assets"):
    b, h = spec["banner"], spec["hai"]
    if spec.get("absolute"):  # render on PyPI too, not just GitHub
        raw = f'https://raw.githubusercontent.com/{spec["repo"]}/{spec["branch"]}'
        blob = f'https://github.com/{spec["repo"]}/blob/{spec["branch"]}'
        assets = raw + "/.github/assets"
        spec = dict(spec, badges=[[l, v, (blob + "/" + k) if k and not k.startswith("http") else k] for l, v, k in spec.get("badges", [])])
        if spec.get("fine_print"):
            spec["fine_print"] = spec["fine_print"].replace("(DISCLAIMER.md)", f"({blob}/DISCLAIMER.md)")
    if h.get("parts"):
        tier_name = ", ".join(f'{l} {c} ({art.HAI[c][0]})' for l, c in h["parts"])
        h = dict(h, hai=None)
    else:
        tier_name = art.HAI[h["hai"]][0]
    lines = [START, '<div align="center">', "",
             f'<img alt="{b["name"]}: {b["pitch"]}" src="{assets}/banner.svg" width="100%">', ""]
    lines += [badge(*x) for x in spec.get("badges", [])]
    if spec.get("nav"):
        lines += ["", " · ".join(f"[{t}](#{a})" for t, a in spec["nav"])]
    lines += ["", "</div>", ""]
    alt = f'HAI Scale {(h["hai"] + ", ") if h["hai"] else ""}{tier_name}. {h["statement"]} {h.get("note", "")}'.replace('"', "&quot;")
    link = f'https://haiscale.amolven.com/{h["hai"]}/' if h["hai"] else "https://haiscale.amolven.com/"
    lines.append(f'<a href="{link}"><img alt="{alt.strip()}" src="{assets}/hai.svg" width="100%"></a>')
    if spec.get("fine_print"):
        lines += ["", f"<sub>{spec['fine_print']}</sub>"]
    elif spec.get("disclaimer"):
        target = f'https://github.com/{spec["repo"]}/blob/{spec["branch"]}/DISCLAIMER.md' if spec.get("absolute") else "DISCLAIMER.md"
        lines += ["", f"<sub>Full terms: [DISCLAIMER.md]({target})</sub>"]
    lines.append(END)
    return "\n".join(lines)


def strip_old(md, rules):
    """Remove what the new header replaces: the H1, the old warning, a duplicate pitch line."""
    if START in md:
        body = md[md.index(END) + len(END):].lstrip("\n")
        if re.match(r"#\s", body):  # a title right under empty markers duplicates the banner
            body = body.split("\n", 1)[1].lstrip("\n") if "\n" in body else ""
        return body, None
    demo = None
    if rules.get("center_div"):
        m = re.match(r'\s*<div align="center">.*?</div>\s*', md, re.S)
        if m:
            img = re.search(r"<img [^>]*>", m.group(0))
            demo = img.group(0) if img else None
            md = md[m.end():]
    out, skipping_alert, h1_done = [], False, False
    for ln in md.split("\n"):
        if not h1_done and re.match(r"#\s", ln):
            h1_done = True
            continue
        if ln.startswith("> [!WARNING]"):
            skipping_alert = True
            continue
        if skipping_alert:
            if ln.startswith(">"):
                continue
            skipping_alert = False
        if ln.startswith("**WARNING**:"):
            continue
        if any(ln.startswith(p) for p in rules.get("drop_prefix", [])):
            continue
        out.append(ln)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).lstrip("\n")
    return body, demo


def name_of(spec):
    return spec["repo"].split("/")[1]


def fetch(specs):
    for s in specs:
        d = os.path.join(BUILD, name_of(s))
        os.makedirs(d, exist_ok=True)
        md = base64.b64decode(json.loads(gh("api", f"repos/{s['repo']}/readme"))["content"]).decode()
        open(os.path.join(d, "README.orig.md"), "w").write(md)
        print("fetched", s["repo"])


def build(specs):
    for s in specs:
        d = os.path.join(BUILD, name_of(s))
        a = os.path.join(d, ".github", "assets")
        os.makedirs(a, exist_ok=True)
        open(os.path.join(a, "banner.svg"), "w").write(art.banner(s["banner"]))
        open(os.path.join(a, "hai.svg"), "w").write(art.hai_banner(s["hai"]))
        body, demo = strip_old(open(os.path.join(d, "README.orig.md")).read(), s.get("strip", {}))
        parts = [header(s)]
        if s.get("lead") and s["lead"] not in body:
            parts.append(s["lead"])
        if demo:
            parts.append(f'<p align="center">{demo}</p>')
        parts.append(body)
        open(os.path.join(d, "README.md"), "w").write("\n\n".join(parts).rstrip() + "\n")
        print("built", s["repo"])


def build_org(org):
    d = os.path.join(BUILD, ".github-org")
    a = os.path.join(d, "profile", "assets")
    os.makedirs(a, exist_ok=True)
    open(os.path.join(a, "banner.svg"), "w").write(art.banner(org["banner"]))
    open(os.path.join(a, "hai.svg"), "w").write(art.hai_banner(org["hai"]))
    cards = []
    for c in org["cards"]:
        slug = c["name"].lower()
        open(os.path.join(a, f"card-{slug}.svg"), "w").write(art.card2(c))
        alt = re.search(r'aria-label="([^"]*)"', art.card2(c)).group(1)
        cards.append(f'<a href="https://github.com/upstream-wontfix/{c["name"]}"><img src="assets/card-{slug}.svg" alt="{alt}" width="49%"></a>')
    open(os.path.join(a, "sec-tools.svg"), "w").write(art.section({"label": "Tools"}))
    h = org["hai"]
    hai_alt = f'HAI Scale {h["hai"]}, {art.HAI[h["hai"]][0]}. {h["statement"]} {h.get("note","")}'.replace('"', "&quot;")
    md = "\n".join([
        '<div align="center">', "",
        f'<img alt="{org["banner"]["name"]}: {org["banner"]["pitch"]}" src="assets/banner.svg" width="100%">', "", "</div>", "",
        open(os.path.join(ROOT, "tools", "org_intro.md")).read().strip(), "",
        '<img src="assets/sec-tools.svg" alt="Tools" width="100%">', "",
        '<p align="center">', *cards, "</p>", "",
        f'<a href="https://haiscale.amolven.com/{h["hai"]}/"><img alt="{hai_alt.strip()}" src="assets/hai.svg" width="100%"></a>', "",
        open(os.path.join(ROOT, "tools", "org_body.md")).read().strip(), ""])
    open(os.path.join(d, "profile", "README.md"), "w").write(md)
    print("built upstream-wontfix/.github")


def push_files(repo, branch, files, message):
    """Commit several files in one commit through the Git Data API (no local clone needed)."""
    ref = json.loads(gh("api", f"repos/{repo}/git/ref/heads/{branch}"))["object"]["sha"]
    base_tree = json.loads(gh("api", f"repos/{repo}/git/commits/{ref}"))["tree"]["sha"]
    tree = [{"path": path, "mode": "100644", "type": "blob", "content": open(local).read()} for path, local in files]
    new_tree = json.loads(gh("api", f"repos/{repo}/git/trees", "--input", "-", input=json.dumps({"base_tree": base_tree, "tree": tree})))["sha"]
    commit = json.loads(gh("api", f"repos/{repo}/git/commits", "--input", "-",
                           input=json.dumps({"message": message, "tree": new_tree, "parents": [ref]})))["sha"]
    gh("api", "-X", "PATCH", f"repos/{repo}/git/refs/heads/{branch}", "-f", f"sha={commit}")
    return commit


def push(specs, org, only):
    for s in specs:
        n = name_of(s)
        if only and n not in only:
            continue
        d = os.path.join(BUILD, n)
        files = [("README.md", os.path.join(d, "README.md")),
                 (".github/assets/banner.svg", os.path.join(d, ".github/assets/banner.svg")),
                 (".github/assets/hai.svg", os.path.join(d, ".github/assets/hai.svg"))]
        print(s["repo"], push_files(s["repo"], s["branch"], files, "README: add banner and HAI Scale disclosure"))
    if not only or ".github" in only:
        d = os.path.join(BUILD, ".github-org", "profile")
        files = [("profile/README.md", os.path.join(d, "README.md"))] + \
                [(f"profile/assets/{f}", os.path.join(d, "assets", f)) for f in sorted(os.listdir(os.path.join(d, "assets")))]
        print("upstream-wontfix/.github", push_files("upstream-wontfix/.github", org["branch"], files, "Org profile: banner, tool cards and HAI Scale note"))


if __name__ == "__main__":
    specs = json.load(open(os.path.join(ROOT, "tools", "repos.json")))
    org = json.load(open(os.path.join(ROOT, "tools", "org.json")))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "fetch":
        fetch(specs)
    elif cmd == "build":
        build(specs)
        build_org(org)
    elif cmd == "push":
        push(specs, org, set(sys.argv[2:]))
