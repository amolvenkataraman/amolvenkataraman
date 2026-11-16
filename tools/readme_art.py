"""README art in the uwnotes / amolven.com style: banners, profile cards and HAI Scale disclosure banners.

One SVG per asset. Text is converted to outlines (Source Serif 4, Instrument Sans) so it renders the
same everywhere, and an internal prefers-color-scheme rule switches light/dark (GitHub mangles
<picture> inside links, so this is the robust option).

Usage: python mkart2.py spec.json outdir
"""
import functools, json, os, sys
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FACES = {"serif": "SourceSerif4.ttf", "sans": "InstrumentSans.ttf"}
LIGHT = dict(bg="#ffffff", line="#d6dbe0", ink="#15181c", ink2="#3c434b", muted="#6b737b", acc="#0f6f68")
DARK = dict(bg="#111416", line="#2a3137", ink="#eceff1", ink2="#c9cfd4", muted="#8b939b", acc="#5fd3bd")
HAI = {  # from AIBadge/src/tiers.json
    "H": ("Fully human", "#1F5C4F", "#FFFFFF"), "HC": ("Human, checked", "#3D7A62", "#FFFFFF"),
    "M1": ("Mixed, human-leaning", "#6B8F5B", "#FFFFFF"), "M2": ("Mixed, even split", "#A68A3E", "#1E1E1E"),
    "A1": ("Mostly automated", "#C07D3E", "#1E1E1E"), "A2": ("Almost fully automated", "#BD5B3B", "#FFFFFF"),
    "AF": ("Fully automated", "#9C3B3B", "#FFFFFF"),
}
NUM = lambda v: ("%.1f" % v).rstrip("0").rstrip(".")


@functools.lru_cache(None)
def face(kind, wght):
    path = os.path.join(FONTS, FACES[kind])
    axes = {"wght": wght, **({"opsz": 36} if kind == "serif" else {"wdth": 100})}
    static = instancer.instantiateVariableFont(TTFont(path), axes)
    hbf = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    hbf.set_variations(axes)
    return static, hbf


def shape(s, kind, size, wght, track=0.0):
    static, hbf = face(kind, wght)
    buf = hb.Buffer()
    buf.add_str(s)
    buf.guess_segment_properties()
    hb.shape(hbf, buf, {"kern": True, "liga": True})
    scale = size / static["head"].unitsPerEm
    glyphs, cx = [], 0.0
    order = static.getGlyphOrder()
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append((order[info.codepoint], cx + pos.x_offset * scale, pos.y_offset * scale))
        cx += pos.x_advance * scale + track
    return glyphs, cx - (track if glyphs else 0), static, scale


def width(s, kind, size, wght, track=0.0):
    return shape(s, kind, size, wght, track)[1]


def text(s, kind, size, wght, x, y, cls, track=0.0, anchor="start"):
    glyphs, w, static, scale = shape(s, kind, size, wght, track)
    if anchor == "end":
        x -= w
    elif anchor == "middle":
        x -= w / 2
    gs = static.getGlyphSet()
    pen = SVGPathPen(gs, ntos=NUM)
    for name, gx, gy in glyphs:
        gs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x + gx, y - gy)))
    d = pen.getCommands()
    return f'<path class="{cls}" d="{d}"/>' if d else ""


def wrap(s, kind, size, wght, maxw, maxlines=3):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if not cur or width(t, kind, size, wght) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > maxlines:
        lines = lines[:maxlines]
        while width(lines[-1] + "…", kind, size, wght) > maxw:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "…"
    return lines


def style(extra_light="", extra_dark=""):
    def block(c):
        return (f".bg{{fill:{c['bg']};stroke:{c['line']}}}.ln{{stroke:{c['line']}}}.ink{{fill:{c['ink']}}}"
                f".ink2{{fill:{c['ink2']}}}.mut{{fill:{c['muted']}}}.acc{{fill:{c['acc']}}}")
    return f"<style>{block(LIGHT)}{extra_light}@media (prefers-color-scheme:dark){{{block(DARK)}{extra_dark}}}</style>"


def svg_open(W, H, label, css):
    label = label.replace('"', "&quot;").replace("&", "&amp;")
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">',
            f"<title>{label}</title>", css]


def hai_mark(code, cx, cy, r):
    _, color, fg = HAI[code]
    size = r * (0.78 if len(code) == 1 else 0.66)
    glyphs, w, static, scale = shape(code, "sans", size, 700)
    gs = static.getGlyphSet()
    pen = SVGPathPen(gs, ntos=NUM)
    x, y = cx - w / 2, cy + size * 0.36
    for name, gx, gy in glyphs:
        gs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x + gx, y - gy)))
    return f'<circle cx="{NUM(cx)}" cy="{NUM(cy)}" r="{NUM(r)}" fill="{color}"/><path fill="{fg}" d="{pen.getCommands()}"/>'


def dots(items):
    return "  ·  ".join(items)


# ---------------------------------------------------------------- repo / profile banner
REPO_FIELDS = [("TYPE", "type"), ("BUILT WITH", "stack"), ("STARTED", "started"), ("STATUS", "status")]
BANNER_COLS = [60, 340, 660, 880]


def banner(it):
    """Owner / repo label, name, pitch, then the same labelled fields in the same columns on every banner."""
    W, X0, X1 = 1200, 60, 1140
    pitch = wrap(it["pitch"], "sans", 25, 400, 1000, 2)
    y_name = 168
    y_pitch = y_name + 46
    y_rule = y_pitch + 34 * (len(pitch) - 1) + 38
    H = y_rule + 96
    fields = it.get("fields") or [(label, it[key]) for label, key in REPO_FIELDS]
    p = svg_open(W, H, f'{it["name"]}: {it["pitch"]} ' + " ".join(f"{l[:1].upper()}{l[1:].lower()}: {v}." for l, v in fields), style())
    p.append(f'<rect class="bg" x="1" y="1" width="{W-2}" height="{H-2}" rx="16" stroke-width="2"/>')
    p.append(text(it["eyebrow"].upper(), "sans", 15, 500, X0, 72, "mut", track=2.6))
    p.append(text(it["name"], "serif", it.get("name_size", 74), 600, X0 - 3, y_name, "ink"))
    for i, ln in enumerate(pitch):
        p.append(text(ln, "sans", 25, 400, X0, y_pitch + i * 34, "ink2"))
    p.append(f'<line class="ln" x1="{X0}" y1="{y_rule}" x2="{X1}" y2="{y_rule}" stroke-width="1.5"/>')
    for (label, value), x in zip(fields, BANNER_COLS):
        p.append(text(label.upper(), "sans", 13, 500, x, y_rule + 38, "mut", track=2.2))
        p.append(text(value, "sans", 20, 500, x, y_rule + 68, "ink"))
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------- HAI disclosure banner
def hai_banner(it):
    """Compact callout in the style of the notes' "100% Human-made" box, tinted with the tier colour."""
    if it.get("parts"):
        return hai_split_banner(it)
    code = it["hai"]
    name, color, _ = HAI[code]
    W, X0, X1 = 1200, 104, 1156
    SZ, LH, NSZ, NLH = 20.5, 28, 16, 22
    lead = f"{name}."
    lw = width(lead + " ", "sans", SZ, 650)
    # first line shares space with the bold lead; later lines use the full width
    words, lines, cur, maxw = it["statement"].split(), [], "", X1 - X0 - lw
    for w in words:
        t = (cur + " " + w).strip()
        if not cur or width(t, "sans", SZ, 400) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur, maxw = w, X1 - X0
    lines.append(cur)
    note = wrap(it["note"], "sans", NSZ, 400, X1 - X0, 2) if it.get("note") else []
    y_eye, y_body = 34, 62
    y_note = y_body + LH * (len(lines) - 1) + 24
    H = (y_note + NLH * (len(note) - 1) if note else y_body + LH * (len(lines) - 1)) + 22
    extra_l = f".cb{{fill:{color};fill-opacity:.09;stroke:{color};stroke-opacity:.55}}"
    extra_d = f".cb{{fill:{color};fill-opacity:.16;stroke:{color};stroke-opacity:.7}}"
    p = svg_open(W, H, f'HAI Scale {code}, {name}. {it["statement"]} {it.get("note", "")}', style(extra_l, extra_d))
    p.append(f'<rect class="cb" x="1" y="1" width="{W-2}" height="{H-2}" rx="12" stroke-width="2"/>')
    p.append(hai_mark(code, 54, H / 2, 26))
    p.append(text(f"HAI SCALE  ·  {code}", "sans", 12, 600, X0, y_eye, "mut", track=2.2))
    p.append(text("haiscale.amolven.com", "sans", 12.5, 500, X1, y_eye, "mut", anchor="end"))
    p.append(text(lead, "sans", SZ, 650, X0, y_body, "ink"))
    for i, ln in enumerate(lines):
        p.append(text(ln, "sans", SZ, 400, X0 + (lw if i == 0 else 0), y_body + i * LH, "ink2"))
    for i, ln in enumerate(note):
        p.append(text(ln, "sans", NSZ, 400, X0, y_note + i * NLH, "mut"))
    p.append("</svg>")
    return "\n".join(p)


def hai_split_banner(it):
    """Same callout, for work labelled in parts, e.g. code H and docs A1: one mark per part, neutral tint."""
    parts = it["parts"]  # [[label, code], ...]
    W, X1 = 1200, 1156
    SZ, LH, NSZ, NLH = 20.5, 28, 16, 22
    X0 = 40 + 64 * len(parts) + 12
    lead = " · ".join(f"{label}: {HAI[c][0].lower()}" for label, c in parts) + "."
    lead = lead[0].upper() + lead[1:]
    lw = width(lead, "sans", SZ, 650)
    body = wrap(it["statement"], "sans", SZ, 400, X1 - X0, 3)
    note = wrap(it["note"], "sans", NSZ, 400, X1 - X0, 2) if it.get("note") else []
    y_eye, y_lead = 34, 62
    y_body = y_lead + LH
    y_note = y_body + LH * (len(body) - 1) + 24
    H = (y_note + NLH * (len(note) - 1) if note else y_body + LH * (len(body) - 1)) + 22
    extra_l = ".cb{fill:#6b737b;fill-opacity:.07;stroke:#6b737b;stroke-opacity:.45}"
    extra_d = ".cb{fill:#8b939b;fill-opacity:.12;stroke:#8b939b;stroke-opacity:.6}"
    label = "HAI Scale " + ", ".join(f"{l} {c} ({HAI[c][0]})" for l, c in parts)
    p = svg_open(W, H, f'{label}. {it["statement"]} {it.get("note", "")}', style(extra_l, extra_d))
    p.append(f'<rect class="cb" x="1" y="1" width="{W-2}" height="{H-2}" rx="12" stroke-width="2"/>')
    for i, (_, c) in enumerate(parts):
        p.append(hai_mark(c, 54 + i * 64, H / 2, 26))
    p.append(text("HAI SCALE  ·  " + "  ·  ".join(f"{l.upper()} {c}" for l, c in parts), "sans", 12, 600, X0, y_eye, "mut", track=2.2))
    p.append(text("haiscale.amolven.com", "sans", 12.5, 500, X1, y_eye, "mut", anchor="end"))
    p.append(text(lead, "sans", SZ, 650, X0, y_lead, "ink"))
    for i, ln in enumerate(body):
        p.append(text(ln, "sans", SZ, 400, X0, y_body + i * LH, "ink2"))
    for i, ln in enumerate(note):
        p.append(text(ln, "sans", NSZ, 400, X0, y_note + i * NLH, "mut"))
    p.append("</svg>")
    return "\n".join(p)


def hai_mini(it):
    """One-line HAI note for small or archived repos: one mark per part and a single sentence."""
    parts = it["parts"]
    W, H = 1200, 64
    X0 = 22 + 46 * len(parts) + 10
    p = svg_open(W, H, "HAI Scale " + ", ".join(f"{l} {c} ({HAI[c][0]})" for l, c in parts) + ". " + it["text"], style(
        ".cb{fill:#6b737b;fill-opacity:.06;stroke:#6b737b;stroke-opacity:.4}",
        ".cb{fill:#8b939b;fill-opacity:.1;stroke:#8b939b;stroke-opacity:.55}"))
    p.append(f'<rect class="cb" x="1" y="1" width="{W-2}" height="{H-2}" rx="10" stroke-width="2"/>')
    for i, (_, c) in enumerate(parts):
        p.append(hai_mark(c, 40 + i * 46, H / 2, 18))
    lead = " · ".join(f"{l} {c}" for l, c in parts)
    lw = width(lead + "   ", "sans", 19, 650)
    p.append(text(lead, "sans", 19, 650, X0, 39, "ink"))
    line = wrap(it["text"], "sans", 19, 400, W - X0 - lw - 30, 1)[0]
    p.append(text(line, "sans", 19, 400, X0 + lw, 39, "ink2"))
    p.append("</svg>")
    return "\n".join(p)


def hai_legend(it):
    """One-line key to the HAI Scale: the seven tier marks and a sentence."""
    W, H = 1200, 64
    codes = ["H", "HC", "M1", "M2", "A1", "A2", "AF"]
    p = svg_open(W, H, "HAI Scale tiers H, HC, M1, M2, A1, A2, AF. " + it["text"], style(
        ".cb{fill:#6b737b;fill-opacity:.06;stroke:#6b737b;stroke-opacity:.4}",
        ".cb{fill:#8b939b;fill-opacity:.1;stroke:#8b939b;stroke-opacity:.55}"))
    p.append(f'<rect class="cb" x="1" y="1" width="{W-2}" height="{H-2}" rx="10" stroke-width="2"/>')
    for i, c in enumerate(codes):
        p.append(hai_mark(c, 38 + i * 40, H / 2, 16))
    x0 = 38 + 7 * 40 + 6
    p.append(text(it["lead"], "sans", 19, 650, x0, 39, "ink"))
    lw = width(it["lead"] + "  ", "sans", 19, 650)
    p.append(text(wrap(it["text"], "sans", 19, 400, W - x0 - lw - 30, 1)[0], "sans", 19, 400, x0 + lw, 39, "ink2"))
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------- structured profile card
FIELDS = [("STARTED", "started"), ("BUILT WITH", "stack"), ("STATUS", "status")]
COLX = [28, 150, 440]


def card2(it):
    """Same fields in the same place on every card: name + HAI tier, pitch, then STARTED / BUILT WITH / STATUS."""
    W, H, X0 = 600, 232, 28
    p = svg_open(W, H, f'{it["name"]}: {it["pitch"]} Started {it["started"]}. Built with {it["stack"]}. Status: {it["status"]}. HAI Scale {it["hai"]}.', style())
    p.append(f'<rect class="bg" x="1" y="1" width="{W-2}" height="{H-2}" rx="12" stroke-width="2"/>')
    p.append(text(it["name"], "serif", 32, 600, X0 - 1, 56, "ink"))
    p.append(hai_mark(it["hai"], W - 44, 45, 16))
    for i, ln in enumerate(wrap(it["pitch"], "sans", 17.5, 400, W - 2 * X0, 2)):
        p.append(text(ln, "sans", 17.5, 400, X0, 92 + i * 24, "ink2"))
    p.append(f'<line class="ln" x1="{X0}" y1="{H-76}" x2="{W-X0}" y2="{H-76}" stroke-width="1.5"/>')
    for (label, key), x in zip(FIELDS, COLX):
        p.append(text(label, "sans", 11.5, 500, x, H - 47, "mut", track=2.0))
        p.append(text(it[key], "sans", 16, 500, x, H - 22, "ink"))
    p.append("</svg>")
    return "\n".join(p)


def section(it):
    W, H = 1200, 44
    p = svg_open(W, H, it["label"], style())
    p.append(text(it["label"].upper(), "sans", 15, 600, 2, 22, "mut", track=2.6))
    p.append(f'<line class="ln" x1="0" y1="40" x2="{W}" y2="40" stroke-width="1.5"/>')
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    for it in spec:
        p = os.path.join(out, it["file"] + ".svg")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write({"banner": banner, "card2": card2, "hai_mini": hai_mini, "hai_legend": hai_legend, "section": section, "hai": hai_banner}[it["kind"]](it))
        print(p, os.path.getsize(p))
