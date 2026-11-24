#!/usr/bin/env python3
"""Build an architecture-visualise page from a body file and check it.

    build.py <body.html> [-o page.html] [--repo <git checkout>]

Checks the diagrams by geometry (no browser): labels that leave their box or
collide, boxes that overlap, arrows that float or cut through a box or a
label, units that sit at different coordinates in two figures, "?" icons
that cover a label or cannot work, units without a source. With --repo it also checks every source link against git.
Writes the page only when nothing fails. Exit 0 clean, 1 failed, 2 bad input.
"""
import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HEAD = Path(__file__).resolve().parent.parent / "assets" / "head.html"
# class -> (font size px, average glyph width in em). Mono is exact; sans is
# set a little wide so a label that passes here fits in any fallback font.
FONT = {"t": (13, .6), "tp": (13, .56), "s": (11.5, .54), "m": (11, .6),
        "ms": (10.5, .6), "cap": (11.5, .52), "lane": (10.5, .68)}
PAD = 8

fails, warns = [], []


def num(el, key, default=0.0):
    try:
        return float(el.get(key, default))
    except ValueError:
        return default


class Box:
    def __init__(self, el):
        self.cls = el.get("class", "").split()
        self.x, self.y = num(el, "x"), num(el, "y")
        self.w, self.h = num(el, "width"), num(el, "height")
        self.unit = el.get("data-unit")
        self.name = self.unit or ("a group" if "grp" in self.cls else "an inner box" if "in" in self.cls else "a box")

    def holds(self, x, y, pad=0.0):
        return self.x + pad <= x <= self.x + self.w - pad and self.y + pad <= y <= self.y + self.h - pad

    def on_edge(self, x, y, tol=2.0):
        return self.holds(x, y, -tol) and not self.holds(x, y, tol)


class Label:
    def __init__(self, el):
        cls = [c for c in el.get("class", "").split() if c in FONT]
        self.cls = cls[0] if cls else None
        size, em = FONT.get(self.cls, (12, .6))
        self.text = " ".join("".join(el.itertext()).split())
        w = len(self.text) * size * em
        x, y = num(el, "x"), num(el, "y")
        anchor = el.get("text-anchor", "start")
        self.x0 = x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
        self.x1, self.y0, self.y1 = self.x0 + w, y - size * .8, y + size * .25
        self.ax, self.ay = x, y - size * .3

    def hits(self, o, tol=1.0):
        return self.x0 < o.x1 - tol and o.x0 < self.x1 - tol and self.y0 < o.y1 - tol and o.y0 < self.y1 - tol


def arrow_points(el, where):
    if el.tag == "line":
        return [(num(el, "x1"), num(el, "y1")), (num(el, "x2"), num(el, "y2"))]
    d = el.get("d", "")
    if re.search(r"[^MLHV0-9.,\s-]", d):
        fails.append(f"{where}: arrow path '{d}' may use only absolute M L H V")
        return []
    pts, cmd, x, y = [], None, 0.0, 0.0
    toks = re.findall(r"[MLHV]|-?\d+(?:\.\d+)?", d)
    i = 0
    while i < len(toks):
        if toks[i] in "MLHV":
            cmd = toks[i]
            i += 1
            continue
        if cmd == "H":
            x = float(toks[i]); i += 1
        elif cmd == "V":
            y = float(toks[i]); i += 1
        else:
            x, y = float(toks[i]), float(toks[i + 1]); i += 2
        pts.append((x, y))
    return pts


def seg_hits(p, q, x0, y0, x1, y1):
    """True when segment p-q passes through the open rectangle (Liang-Barsky)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for a, b in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if a == 0:
            if b <= 0:
                return False
        else:
            t = b / a
            if a < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    return t0 < t1


def walk(el, ids, only=None, seen=()):
    only = el.get("data-only", only)
    if el.get("transform"):
        fails.append("transform attributes are not supported; write final coordinates")
    if el.tag == "use":
        ref = (el.get("href") or el.get("{http://www.w3.org/1999/xlink}href") or "").lstrip("#")
        if ref in ids and ref not in seen:
            yield from walk(ids[ref], ids, only, seen + (ref,))
        else:
            fails.append(f'<use href="#{ref}"> points at nothing')
        return
    yield el, only, bool(seen)
    for child in el:
        yield from walk(child, ids, only, seen)


def along(pts, dist):
    """Point `dist` along a polyline, or its middle when it is shorter than twice that."""
    segs = [(p, q, abs(q[0] - p[0]) + abs(q[1] - p[1]) if p[0] == q[0] or p[1] == q[1]
             else ((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** .5) for p, q in zip(pts, pts[1:])]
    total = sum(s[2] for s in segs)
    left = min(dist, total / 2)
    for p, q, length in segs:
        if left <= length and length:
            f = left / length
            return p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f
        left -= length
    return pts[-1]


def hover(el):
    return el.get("data-warn") is not None or el.get("data-tip") is not None


def check_figure(n, svg, ids, zoom=False):
    where = f"fig{n}"
    vb = [float(v) for v in svg.get("viewBox", "0 0 0 0").split()]
    if len(vb) != 4 or not vb[2]:
        fails.append(f"{where}: svg needs a viewBox")
        return {}, 0, 0, 0
    if svg.get("role") != "img" or not svg.get("aria-label"):
        warns.append(f'{where}: svg should carry role="img" and an aria-label that states the claim')
    items = list(walk(svg, ids))
    views = ["now", "next"] if any(o for _, o, _ in items) else [None]
    units, nb, na, nw = {}, 0, 0, 0
    for el, _, shared in items:
        if not hover(el):
            continue
        said = (el.get("data-warn") or el.get("data-tip") or "").strip()
        what = el.get("data-unit") or el.tag
        if shared:
            fails.append(f"{where}: {what} carries hover text inside a shared group; a reused unit cannot be hovered, so write it in each figure")
        if el.tag not in ("rect", "path", "line"):
            fails.append(f"{where}: hover text belongs on a box, group or arrow, not on <{el.tag}>")
        if not said:
            fails.append(f"{where}: {what} has empty hover text")
        elif len(said) > 240:
            fails.append(f"{where}: hover text on {what} is {len(said)} characters; the limit is 240")
    for view in views:
        tag = f"{where}/{view}" if view else where
        live = [el for el, o, _ in items if o in (None, view)]
        boxes = [Box(el) for el in live if el.tag == "rect"]
        solid = [b for b in boxes if "n" in b.cls]
        labels = [Label(el) for el in live if el.tag == "text"]
        arrows = [arrow_points(el, tag) for el in live if "e" in el.get("class", "").split()]
        arrows = [a for a in arrows if len(a) > 1]
        for b in solid:
            if "in" in b.cls or "ext" in b.cls:
                continue
            if not b.unit:
                if not zoom:
                    fails.append(f"{tag}: box at ({b.x:g},{b.y:g}) has no data-unit")
            elif view in (None, "now"):
                units[b.unit] = (b.x, b.y)
        if view in (None, "now"):
            nb = len([b for b in solid if "in" not in b.cls and "ext" not in b.cls])
            na = len(arrows)
            nw = len([el for el in live if el.get("data-warn") is not None])
        outer = [b for b in solid if "in" not in b.cls]
        for i, a in enumerate(outer):
            for b in outer[i + 1:]:
                if a.x - 8 < b.x + b.w and b.x - 8 < a.x + a.w and a.y - 8 < b.y + b.h and b.y - 8 < a.y + a.h:
                    fails.append(f"{tag}: boxes {a.name} and {b.name} overlap or sit closer than 8px")
        for b in solid:
            if "in" in b.cls and not any(o.holds(b.x, b.y) and o.holds(b.x + b.w, b.y + b.h) for o in outer):
                fails.append(f"{tag}: inner box at ({b.x:g},{b.y:g}) is not inside a unit")
        plain = labels
        for l in plain:
            if l.cls is None:
                fails.append(f'{tag}: label "{l.text}" needs a text class (t tp s m ms cap lane)')
            if l.x0 < 0 or l.y0 < 0 or l.x1 > vb[2] or l.y1 > vb[3]:
                fails.append(f'{tag}: label "{l.text}" leaves the drawing (spans x {l.x0:.0f}..{l.x1:.0f}, viewBox is {vb[2]:g} wide)')
            home = sorted((b for b in solid if b.holds(l.ax, l.ay)), key=lambda b: b.w * b.h)
            if home:
                over = l.x1 - (home[0].x + home[0].w - PAD)
                if over > 0:
                    fails.append(f'{tag}: label "{l.text}" is {over:.0f}px too wide for {home[0].name}')
            else:
                for b in solid:
                    if l.x0 < b.x + b.w and b.x < l.x1 and l.y0 < b.y + b.h and b.y < l.y1:
                        fails.append(f'{tag}: label "{l.text}" overlaps {b.name}')
        for i, a in enumerate(plain):
            for b in plain[i + 1:]:
                if a.hits(b):
                    fails.append(f'{tag}: labels "{a.text}" and "{b.text}" overlap')
        for pts in arrows:
            ends = (("starts", pts[0]), ("ends", pts[-1]))
            for word, p in ends:
                if not any(b.on_edge(*p) for b in boxes):
                    fails.append(f"{tag}: arrow {word} in mid-air at ({p[0]:g},{p[1]:g}); put it on a box or group edge")
            for p, q in zip(pts, pts[1:]):
                for b in solid:
                    if b.holds(*pts[0]) or b.holds(*pts[-1]):
                        continue
                    if seg_hits(p, q, b.x + 2, b.y + 2, b.x + b.w - 2, b.y + b.h - 2):
                        fails.append(f"{tag}: arrow from ({pts[0][0]:g},{pts[0][1]:g}) cuts through {b.name}")
                for l in plain:
                    if seg_hits(p, q, l.x0 + 1, l.y0 + 1, l.x1 - 1, l.y1 - 1):
                        fails.append(f'{tag}: arrow from ({pts[0][0]:g},{pts[0][1]:g}) runs through label "{l.text}"')
        icons = []
        for el in live:
            if not hover(el) or el.tag not in ("rect", "path", "line"):
                continue
            if el.tag == "rect":
                b = Box(el)
                icons.append((b.name, b.x + b.w, b.y))
            else:
                pts = arrow_points(el, tag)
                if len(pts) > 1:
                    icons.append((f"the arrow from ({pts[0][0]:g},{pts[0][1]:g})", *along(pts, 18)))
        for i, (name, cx, cy) in enumerate(icons):
            if cx - 9 < 0 or cy - 9 < 0 or cx + 9 > vb[2] or cy + 9 > vb[3]:
                fails.append(f"{tag}: the ? icon on {name} leaves the drawing; keep 10px free around ({cx:g},{cy:g})")
            for l in plain:
                if l.x0 < cx + 9 and cx - 9 < l.x1 and l.y0 < cy + 9 and cy - 9 < l.y1:
                    fails.append(f'{tag}: the ? icon on {name} covers label "{l.text}"')
            for other, ox, oy in icons[i + 1:]:
                if abs(cx - ox) < 20 and abs(cy - oy) < 20:
                    fails.append(f"{tag}: the ? icons on {name} and {other} overlap")
    if nb > 12:
        warns.append(f"{where}: {nb} boxes, not counting outside systems; consider a zoom figure, but never drop a unit to get under the number")
    if na > 14:
        warns.append(f"{where}: {na} arrows; move part of it into a zoom figure")
    return units, nb, na, nw


def check_sources(body, units, repo):
    block = re.search(r'<details class="src">(.*?)</details>', body, re.S)
    if not block:
        fails.append('no <details class="src"> sources block')
        return
    named, checked = set(), 0
    for li in re.findall(r"<li>(.*?)</li>", block.group(1), re.S):
        unit = re.sub(r"<[^>]+>", "", li.split("<a", 1)[0]).strip()
        named.add(unit)
        for sha, path, line in re.findall(r'href="https://github\.com/[^/"]+/[^/"]+/blob/([0-9a-f]{7,40})/([^#"]+)#L(\d+)', li):
            if not repo:
                continue
            got = subprocess.run(["git", "-C", repo, "show", f"{sha}:{path}"], capture_output=True, text=True)
            if got.returncode:
                fails.append(f"source {unit}: {path} does not exist at {sha[:7]}")
                continue
            rows, at = got.stdout.splitlines(), int(line)
            if at > len(rows) or unit not in "\n".join(rows[max(0, at - 4):at + 3]):
                fails.append(f"source {unit}: not found near {path}:{at} at {sha[:7]}")
            checked += 1
    for u in sorted(set(units) - named):
        fails.append(f"unit {u} is drawn but has no line under Sources")
    print(f"sources: {checked} links checked against git" if repo else "sources: links not checked (pass --repo)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("body")
    ap.add_argument("-o", "--out")
    ap.add_argument("--repo")
    args = ap.parse_args()
    src = Path(args.body)
    body = src.read_text(encoding="utf-8")
    title = re.search(r"<title>.*?</title>", body, re.S)
    if not title:
        sys.exit("build: the body must start with a <title>")
    if "{{" in body or "acme/shop" in body:
        fails.append("template text is still in the body ({{ or acme/shop)")
    figures = re.findall(r"<figure\b.*?</figure>", body, re.S)
    if not figures:
        sys.exit("build: no <figure> found")
    parsed, ids = [], {}
    for n, fig in enumerate(figures, 1):
        m = re.search(r"<svg\b.*?</svg>", fig, re.S)
        if not m:
            sys.exit(f"build: fig{n} has no <svg>")
        try:
            svg = ET.fromstring(m.group(0))
        except ET.ParseError as err:
            sys.exit(f"build: fig{n} svg is not well-formed ({err}); close every tag and write & as &amp;")
        for el in svg.iter():
            if el.get("id"):
                if el.get("id") in ids:
                    fails.append(f'id "{el.get("id")}" is used twice')
                ids[el.get("id")] = el
        zoom = bool(re.match(r'<figure\b[^>]*class="[^"]*\bzoom\b', fig))
        parsed.append((n, svg, zoom))
    all_units, summary = {}, []
    for n, svg, zoom in parsed:
        units, nb, na, nw = check_figure(n, svg, ids, zoom)
        for u, pos in ({} if zoom else units).items():
            if u in all_units and all_units[u][1] != pos:
                was = all_units[u]
                fails.append(f"unit {u} sits at ({pos[0]:g},{pos[1]:g}) in fig{n} but ({was[1][0]:g},{was[1][1]:g}) in fig{was[0]}")
            all_units.setdefault(u, (n, pos))
        summary.append(f"fig{n}: {nb} boxes, {na} arrows, {nw} weak spots")
    check_sources(body, all_units, args.repo)
    for w in warns:
        print("WARN", w)
    for f in dict.fromkeys(fails):
        print("FAIL", f)
    if fails:
        print(f"{len(dict.fromkeys(fails))} to fix; page not written")
        sys.exit(1)
    out = Path(args.out) if args.out else src.with_name("page.html")
    out.write_text(title.group(0) + "\n" + HEAD.read_text(encoding="utf-8") + body.replace(title.group(0), "", 1), encoding="utf-8")
    print("OK", "; ".join(summary))
    print("wrote", out)


if __name__ == "__main__":
    main()
