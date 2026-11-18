#!/usr/bin/env python3
"""Generates every SVG card (light + dark), README.md and preview.html
from profile.config.json. No third-party dependencies.

Usage:  python scripts/build.py
Env:    GITHUB_TOKEN  -> fetch real contributions (otherwise sample data is used)
"""
import base64, datetime as dt, json, math, os, sys, textwrap, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "profile.config.json").read_text(encoding="utf-8"))
USER = CFG["username"]
PROFILE_URL = f"https://github.com/{USER}"

HEAD = "Inter,'Arial Black',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif"
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

LIGHT = dict(card="#FFFFFF", card2="#FAFAFA", border="#111111", shadow="#111111",
             text="#111111", muted="#555555", green="#0F5C3F", red="#C62020",
             yellow="#FFC400", soft="#FFF4D0", gbar="#D5D9DC", grid="#BFC5CB",
             heat=["#FFFFFF", "#BFE5CC", "#7FCB9B", "#2E8B57", "#0F5C3F"],
             heatstroke="#0F5C3F", chip="#FFFFFF", chiptext="#111111")
DARK = dict(card="#12171D", card2="#12171D", border="#E6EDF3", shadow="#8B949E",
            text="#F0F6FC", muted="#9BA7B4", green="#2FB67C", red="#EF4444",
            yellow="#FFC400", soft="#2A2410", gbar="#2B333C", grid="#2B333C",
            heat=["#1B222A", "#14532D", "#1F8A4C", "#3FD97F", "#7CF0A8"],
            heatstroke="#3FD97F", chip="#1B222A", chiptext="#F0F6FC")
# tiles / highlights keep the same bold colours in both modes
TILE_GREEN, TILE_RED, TILE_YELLOW, INK = "#0F5C3F", "#C62020", "#FFC400", "#111111"

# ------------------------------------------------------------------ helpers
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def est(s, size, k=0.56):
    return len(s) * size * k

def T(x, y, s, size, fill, weight=400, fam=MONO, ls=0, anchor="start", tl=None):
    a = f'x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" font-weight="{weight}" fill="{fill}"'
    if ls: a += f' letter-spacing="{ls}"'
    if anchor != "start": a += f' text-anchor="{anchor}"'
    if tl: a += f' textLength="{tl:.1f}" lengthAdjust="spacingAndGlyphs"'
    return f"<text {a}>{esc(s)}</text>"

def H(x, y, s, size, fill, maxw=None, weight=800, anchor="start"):
    """Headline with textLength so it fits regardless of the fallback font."""
    w = est(s, size, 0.55)
    if maxw: w = min(w, maxw)
    return T(x, y, s, size, fill, weight, HEAD, -size * 0.03, anchor, tl=w), w

def label(x, y, s, fill, dot, size=21):
    return (f'<rect x="{x}" y="{y-14}" width="14" height="14" fill="{dot}"/>' +
            T(x + 26, y, s.upper(), size, fill, 500, MONO, 3))

def arrow(x, y, s, color, sw=3):
    return (f'<path d="M{x},{y+s} L{x+s},{y} M{x+s*0.2},{y} H{x+s} V{y+s*0.8}" '
            f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="square"/>')

def wrap(s, n):
    return textwrap.wrap(s, n)

def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" '
            f'width="{w:g}" height="{h:g}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title>{body}</svg>')

def card(w, h, fill, t, pad=48, sw=2.5, stroke=None, shadow=None):
    """Neo-brutalist card with reduced, crisp 5-unit drop shadow."""
    offset = 5
    bw, bh = w - (offset + 6), h - (offset + 6)
    shadow = shadow or t["shadow"]
    stroke = stroke or t["border"]
    body = (f'<rect x="{3+offset}" y="{3+offset}" width="{bw:g}" height="{bh:g}" fill="{shadow}"/>'
            f'<rect x="3" y="3" width="{bw:g}" height="{bh:g}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    return body, pad, int(bw + 3 - pad)

# ------------------------------------------------------------ contribution data
def load_contributions():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
    end = dt.date.today()
    if token:
        try:
            frm = end - dt.timedelta(days=364)
            q = ("query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t)"
                 "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}")
            payload = json.dumps({"query": q, "variables": {
                "u": USER, "f": frm.isoformat() + "T00:00:00Z", "t": end.isoformat() + "T23:59:59Z"}}).encode()
            req = urllib.request.Request("https://api.github.com/graphql", payload,
                                         {"Authorization": f"bearer {token}", "Content-Type": "application/json",
                                          "User-Agent": "profile-builder"})
            data = json.load(urllib.request.urlopen(req, timeout=15))
            weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            days = {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
            print("Using live GitHub GraphQL data")
            try:
                (ROOT / "data" / "sample-contributions.json").write_text(
                    json.dumps({"end": end.isoformat(), "days": days}, indent=1), encoding="utf-8"
                )
            except Exception:
                pass
            return end, days
        except Exception as e:
            print("GraphQL fetch failed, trying public API fallback:", e, file=sys.stderr)

    # Public contributions API fallback (no token required)
    try:
        url = f"https://github-contributions-api.jogruber.de/v4/{USER}?y=last"
        req = urllib.request.Request(url, headers={"User-Agent": "profile-builder"})
        data = json.load(urllib.request.urlopen(req, timeout=15))
        if "contributions" in data and data["contributions"]:
            days = {item["date"]: item["count"] for item in data["contributions"]}
            print("Using live GitHub data via public contributions API")
            try:
                (ROOT / "data" / "sample-contributions.json").write_text(
                    json.dumps({"end": end.isoformat(), "days": days}, indent=1), encoding="utf-8"
                )
            except Exception:
                pass
            return end, days
    except Exception as e:
        print("Public contributions API unavailable, falling back to local data:", e, file=sys.stderr)

    # Local fallback with date shifting to current date
    s = json.loads((ROOT / "data" / "sample-contributions.json").read_text(encoding="utf-8"))
    sample_end = dt.date.fromisoformat(s["end"])
    offset = (end - sample_end).days
    shifted_days = {}
    for d_str, count in s.get("days", {}).items():
        orig_d = dt.date.fromisoformat(d_str)
        new_d = orig_d + dt.timedelta(days=offset)
        shifted_days[new_d.isoformat()] = count
    print("Using local contributions data (adjusted for preview)")
    return end, shifted_days

def stats(end, days):
    cnt = lambda d: days.get(d.isoformat(), 0)
    start = end - dt.timedelta(days=364)
    win = [start + dt.timedelta(days=i) for i in range(365)]
    total = sum(cnt(d) for d in win)
    active = sum(1 for d in win if cnt(d) > 0)
    busiest = max(cnt(d) for d in win)
    d = end if cnt(end) > 0 else end - dt.timedelta(days=1)
    cur = 0
    while cnt(d) > 0 and d >= start:
        cur += 1; d -= dt.timedelta(days=1)
    longest = run = 0
    for d in win:
        run = run + 1 if cnt(d) > 0 else 0
        longest = max(longest, run)
    months = []
    y, m = end.year, end.month
    for _ in range(12):
        months.append((y, m)); m -= 1
        if m == 0: y, m = y - 1, 12
    months.reverse()
    mt = [sum(c for k, c in days.items() if k[:7] == f"{y}-{m:02d}") for y, m in months]
    names = [dt.date(y, m, 1).strftime("%b") for y, m in months]
    return dict(total=total, active=active, busiest=busiest, cur=cur, longest=longest, mt=mt, names=names)

# ------------------------------------------------------------------ cards
def hero(t, dark):
    w, h = 1000, 520
    b, ix, ir = card(w, h, t["card2"], t)
    b += label(ix, 66, "01 Profile", t["text"], TILE_RED)
    n1, n2 = CFG["name"]
    s1, w1 = H(ix, 175, n1, 110, t["text"])
    w2 = est(n2, 110, 0.55)
    b += s1
    b += f'<rect x="{ix-4}" y="190" width="{w2+30:.1f}" height="124" fill="{TILE_YELLOW}" stroke="{INK}" stroke-width="3"/>'
    b += T(ix + 11, 295, n2, 110, INK, 800, HEAD, -3.3, tl=w2)
    b += T(ix, 362, CFG["label"], 24, t["text"], 700, MONO)
    for i, ln in enumerate(wrap(CFG["tagline"], 36)):
        b += T(ix, 402 + i * 36, ln, 28, t["text"], 400, HEAD)
    # illustration box
    bx, by, bw, bh = 600, 42, 340, 430
    box_bg = "#F3F1E7" if not dark else "#1D242C"
    b += f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="28" fill="{box_bg}" stroke="{t["border"]}" stroke-width="3"/>'
    p_gif = ROOT / "assets" / "hero.gif"
    p_png = ROOT / "assets" / "hero.png"
    p = p_gif if p_gif.exists() else p_png
    if p.exists():
        mime = "image/gif" if p.suffix.lower() == ".gif" else "image/png"
        uri = base64.b64encode(p.read_bytes()).decode()
        b += (f'<image x="{bx+14}" y="{by+14}" width="{bw-28}" height="{bh-28}" preserveAspectRatio="xMidYMid meet" '
              f'href="data:{mime};base64,{uri}"/>')
    else:
        b += (f'<rect x="680" y="130" width="180" height="130" fill="{INK}" stroke="{INK}" stroke-width="12"/>'
              f'<rect x="750" y="272" width="40" height="30" fill="{INK}"/><rect x="725" y="300" width="90" height="14" fill="{INK}"/>'
              + T(695, 170, "while True:", 20, "#7CF0A8") + T(695, 200, "build()", 20, TILE_YELLOW) + T(695, 230, "AI { }", 20, "#FFFFFF"))
    return svg(w, h, b, "Tarun Suthar, AI-assisted developer. Building secure Java, Android, and Python applications.")

def heatmap(t, dark, end, days):
    w, h = 1000, 360
    b, ix, ir = card(w, h, t["card"], t)
    b += label(ix, 66, "02 Activity · refreshed daily", t["text"], TILE_RED)
    s, ww = H(ix, 135, "Building ", 52, t["text"])
    b += (f'<text x="{ix}" y="135" font-family="{HEAD}" font-size="52" font-weight="800" letter-spacing="-1.5" fill="{t["text"]}">'
          f'Building <tspan fill="{t["green"]}">in public</tspan></text>')
    start = end - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    pitch, cs = 16.4, 14
    lvl = lambda c: 0 if c == 0 else 1 if c < 3 else 2 if c < 6 else 3 if c < 10 else 4
    gy = 172
    for i in range((end - start).days + 1):
        d = start + dt.timedelta(days=i)
        col, row = i // 7, i % 7
        l = lvl(days.get(d.isoformat(), 0))
        stroke = t["grid"] if l == 0 else t["heatstroke"]
        b += (f'<rect x="{ix + col*pitch:.1f}" y="{gy + row*pitch:.1f}" width="{cs}" height="{cs}" '
              f'fill="{t["heat"][l]}" stroke="{stroke}" stroke-width="1.5"/>')
    # legend
    lx = ir - 5 * 20 - 140
    b += T(lx, 326, "less", 18, t["muted"])
    for i in range(5):
        b += (f'<rect x="{lx+60+i*22}" y="312" width="16" height="16" fill="{t["heat"][i]}" '
              f'stroke="{t["grid"] if i==0 else t["heatstroke"]}" stroke-width="1.5"/>')
    b += T(lx + 60 + 5 * 22 + 4, 326, "more", 18, t["muted"])
    return svg(w, h, b, f"GitHub contribution heatmap for the last 12 months, building in public.")

def stats_card(t, dark, S):
    w, h = 1000, 520
    b, ix, ir = card(w, h, t["card2"], t)
    b += label(ix, 66, "Contributions · last 12 months", t["text"], TILE_RED)
    tot = str(S["total"])
    sh, tw = H(ix, 190, tot, 120, t["text"])
    b += sh + T(ix, 236, "contributions", 26, t["text"], 500, HEAD)
    # bars
    mt, names = S["mt"], S["names"]
    mx = max(mt) or 1
    top2 = sorted(range(12), key=lambda i: -mt[i])[0]
    base, maxh, pitch, bw = 455, 190, 42.5, 34
    for i, v in enumerate(mt):
        bh = max(8, v / mx * maxh)
        col = t["gbar"]
        if i == top2: col = TILE_RED if t is LIGHT else t["red"]
        if i == 11: col = t["green"]
        x = ix + i * pitch
        b += f'<rect x="{x:.1f}" y="{base-bh:.1f}" width="{bw}" height="{bh:.1f}" fill="{col}"/>'
        if v >= mx * 0.3 and v > 0:
            b += T(x + bw / 2, base - bh - 10, str(v), 20, t["text"], 600, MONO, anchor="middle")
        b += T(x + bw / 2, 490, names[i], 16, t["text"], 400, MONO, anchor="middle")
    # right column
    rx = 620
    def block(y, num, unit, cap):
        out, nw = "", 0
        sh, nw = H(rx, y, num, 72, t["text"])
        out += sh + T(rx + nw + 14, y, unit, 26, t["text"], 500, HEAD)
        out += T(rx, y + 40, cap, 20, t["muted"], 400, MONO)
        return out
    b += block(140, str(S["cur"]), "days", f'current streak · longest {S["longest"]}')
    b += f'<line x1="{rx}" y1="212" x2="{ir}" y2="212" stroke="{t["border"]}" stroke-width="2"/>'
    b += block(290, str(S["active"]), "/ 365", "days with a commit")
    b += f'<line x1="{rx}" y1="362" x2="{ir}" y2="362" stroke="{t["border"]}" stroke-width="2"/>'
    b += block(440, str(S["busiest"]), "", "on the busiest day")
    return svg(w, h, b, f'{S["total"]} contributions in the last 12 months, current streak {S["cur"]} days, longest {S["longest"]}, {S["active"]} of 365 days with a commit, busiest day {S["busiest"]}.')

def tile(kind, t, dark):
    w, h = 333.33, 400
    c = CFG["tiles"][kind]
    fill, fg = {"build": (TILE_GREEN, "#FFFFFF"), "solve": (TILE_RED, "#FFFFFF"), "create": (TILE_YELLOW, INK)}[kind]
    b, ix, ir = card(w, h, fill, t, pad=32, stroke=t["border"])
    b += T(ix, 66, kind.upper(), 21, fg, 500, MONO, 4)
    b += f'<rect x="{ir-44}" y="38" width="44" height="44" fill="none" stroke="{fg}" stroke-width="2" opacity="0.8"/>'
    b += arrow(ir - 30, 51, 16, fg, 2.5)
    if kind == "create":
        sh, _ = H(ix, 175, c["big"], 74, fg, maxw=ir - ix)
        b += sh
        y = 232
    else:
        sh, nw = H(ix, 180, c["big"], 66, fg)
        b += sh + T(ix + nw + 10, 180, c["unit"], 22, fg, 700, HEAD)
        y = 240
    for i, ln in enumerate(wrap(c["text"], 23)):
        b += T(ix, y + i * 30, ln, 21, fg, 400, HEAD)
    if kind == "create":
        cy = 322
        b += f'<rect x="{ix}" y="{cy}" width="248" height="46" fill="#FFFFFF" stroke="{INK}" stroke-width="3"/>'
        b += T(ix + 16, cy + 31, "VIEW PORTFOLIO", 19, INK, 700, MONO, 1) + arrow(ix + 212, cy + 15, 14, INK, 2.5)
    u = c.get("unit", "")
    titles = {k2: f'{k2.capitalize()}: {c["big"]} {u}'.replace("  ", " ").strip() + f'. {c["text"]}' for k2 in ("build", "solve", "create")}
    return svg(w, h, b, titles[kind])

def education(t, dark):
    w, h = 500, 300
    e = CFG["education"]
    b, ix, ir = card(w, h, t["card"], t, pad=40)
    b += label(ix, 64, "Education", t["text"], TILE_GREEN if not dark else t["green"])
    sh, _ = H(ix, 135, e["degree"], 34, t["text"], maxw=ir - ix)
    b += sh
    sh, nw = H(ix, 232, e["score"], 92, t["text"])
    b += sh + T(ix + nw + 14, 232, e["scoreLabel"], 32, t["text"], 700, HEAD)
    return svg(w, h, b, f'Education: {e["degree"]}, {e["score"]} {e["scoreLabel"]}.')

def learning(t, dark):
    w, h = 500, 300
    L = CFG["learning"]
    b, ix, ir = card(w, h, t["soft"], t, pad=40)
    b += label(ix, 64, "Currently learning", t["text"], TILE_YELLOW)
    for i, ln in enumerate(wrap(L["title"], 20)):
        sh, _ = H(ix, 125 + i * 44, ln, 36, t["text"], maxw=ir - ix)
        b += sh
    x, y = ix, 205
    for chip in L["chips"]:
        cw = est(chip, 17, 0.6) + 26
        if x + cw > ir + 4: x, y = ix, y + 56
        b += (f'<rect x="{x+4}" y="{y+4}" width="{cw:.1f}" height="40" fill="{INK}"/>'
              f'<rect x="{x}" y="{y}" width="{cw:.1f}" height="40" fill="{TILE_YELLOW}" stroke="{INK}" stroke-width="2.5"/>'
              + T(x + 14, y + 27, chip, 17, INK, 700, MONO))
        x += cw + 14
    return svg(w, h, b, "Currently learning: " + ", ".join(L["chips"]) + ".")

def tech(t, dark):
    w, h = 1000, 330
    b, ix, ir = card(w, h, t["card"], t)
    b += label(ix, 66, "Tech stack", t["text"], TILE_RED)
    sh, _ = H(ix, 135, "What I use", 56, t["text"])
    b += sh
    x, y = ix, 175
    for s in CFG["stack"]:
        cw = est(s, 21, 0.6) + 34
        if x + cw > ir: x, y = ix, y + 62
        b += (f'<rect x="{x+4}" y="{y+4}" width="{cw:.1f}" height="46" fill="{t["shadow"]}"/>'
              f'<rect x="{x}" y="{y}" width="{cw:.1f}" height="46" fill="{t["chip"]}" stroke="{t["border"]}" stroke-width="2.5"/>'
              + T(x + cw / 2, y + 31, s, 21, t["chiptext"], 700, MONO, anchor="middle"))
        x += cw + 18
    return svg(w, h, b, "Tech stack: " + ", ".join(CFG["stack"]) + ".")

def how(t, dark):
    w, h = 1000, 330
    H_ = CFG["howIWork"]
    b, ix, ir = card(w, h, t["card"], t)
    b += label(ix, 66, "How I work", t["text"], TILE_GREEN if not dark else t["green"])
    # Clean text wrapping to 48 characters so text never exceeds card bounds
    clean_text = H_["text"].rstrip(" ,…")
    lines = wrap(clean_text, 48)
    lines[-1] = lines[-1].rstrip(" ,") + ":"
    y = 124
    for ln in lines:
        b += T(ix, y, ln, 25, t["text"], 400, HEAD)
        y += 38
    x, y = ix, y + 10
    for tool in H_["tools"]:
        cw = est(tool, 22, 0.6) + 30
        b += (f'<rect x="{x}" y="{y}" width="{cw:.1f}" height="46" fill="{TILE_YELLOW}"/>'
              + T(x + cw / 2, y + 31, tool, 22, INK, 700, HEAD, anchor="middle"))
        x += cw + 16
    return svg(w, h, b, "How I work: " + H_["text"] + " " + ", ".join(H_["tools"]) + ".")

def coding_label(t, dark):
    w, h = 1000, 70
    b = label(8, 46, "What I'm coding", t["text"], TILE_RED)
    return svg(w, h, b, "What I'm coding")

def project(p, t, dark):
    w, h = 333.33, 340
    col = {"green": t["green"] if dark else TILE_GREEN, "red": t["red"] if dark else TILE_RED, "yellow": TILE_YELLOW}[p["color"]]
    b, ix, ir = card(w, h, t["card"], t, pad=26)
    b += f'<rect x="{ix}" y="50" width="14" height="14" fill="{col}"/>'

    # Split camelCase long names so headings have consistent, regular font size
    import re
    spaced_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', p["name"])
    title_lines = wrap(spaced_name, 20)

    # Uniform 21px bold font for all project card headings
    title_size = 21
    if len(title_lines) == 1:
        sh, _ = H(ix + 24, 63, title_lines[0], title_size, t["text"], maxw=ir - ix - 24)
        b += sh
        desc_start_y = 118
    else:
        sh1, _ = H(ix + 24, 63, title_lines[0], title_size, t["text"], maxw=ir - ix - 24)
        sh2, _ = H(ix + 24, 88, title_lines[1], title_size, t["text"], maxw=ir - ix - 24)
        b += sh1 + sh2
        desc_start_y = 138

    for i, ln in enumerate(wrap(p["desc"], 22)[:3]):
        b += T(ix, desc_start_y + i * 28, ln, 19, t["muted"], 400, HEAD)

    cw = est(p["tag"], 16, 0.6) + 20
    b += f'<rect x="{ix}" y="278" width="{cw:.1f}" height="34" fill="none" stroke="{t["border"]}" stroke-width="2"/>'
    b += T(ix + 10, 301, p["tag"], 16, t["text"], 500, MONO)
    rx = ir - est("README", 16, 0.6) - 24
    b += T(rx, 301, "README", 16, t["text"], 700, MONO) + arrow(ir - 18, 287, 13, t["text"], 2.2)
    b += f'<line x1="{rx}" y1="306" x2="{ir}" y2="306" stroke="{t["text"]}" stroke-width="2"/>'
    return svg(w, h, b, f'{p["name"]}: {p["desc"]} ({p["tag"]}). Opens the repository.')

def contact_header(t, dark):
    w, h = 1000, 170
    bg = "#12171D" if dark else "#FFFFFF"
    fg = "#F0F6FC" if dark else "#111111"
    b, ix, ir = card(w, h, bg, t, pad=36)
    b += f'<rect x="{ix}" y="42" width="14" height="14" fill="{TILE_RED}"/>' + T(ix + 26, 56, "CONTACT", 22, fg, 500, MONO, 3)
    sh, _ = H(ix, 132, "Let's talk.", 64, fg)
    return svg(w, h, b + sh, "Contact. Let's talk.")

def contact_btn(name, filled, yellow, t, dark):
    w, h = 200, 130
    bg = "#12171D" if dark else t["card"]
    fill, shadow = (TILE_YELLOW, t["shadow"]) if yellow else (t["card"], TILE_YELLOW)
    b = f'<rect width="{w}" height="{h}" fill="{bg}"/>'
    b += f'<rect x="40" y="14" width="140" height="92" fill="{shadow}"/>'
    b += f'<rect x="36" y="10" width="140" height="92" fill="{fill}" stroke="{t["border"]}" stroke-width="2.5"/>'
    ty = 52 if filled else 46
    btn_text = INK if yellow else t["text"]
    b += T(106, ty, name.upper(), 19, btn_text, 700, MONO, 1, anchor="middle")
    if not filled:
        b += f'<rect x="58" y="66" width="96" height="22" fill="{TILE_YELLOW}" stroke="{INK}" stroke-width="1.5"/>'
        b += T(106, 81, "COMING SOON", 11, INK, 700, MONO, anchor="middle")
    else:
        b += arrow(154, 22, 14, btn_text, 2.5)
    return svg(w, h, b, f"{name} link" + ("" if filled else " (to be added)"))

# ------------------------------------------------------------------ layout
def href(v, mail=False):
    if not v: return None
    if mail and not v.startswith("mailto:"): return "mailto:" + v
    return v

def build():
    end, days = load_contributions()
    S = stats(end, days)
    L = CFG["links"]
    out = {}
    def add(name, fn, *a):
        for mode, tk in (("light", LIGHT), ("dark", DARK)):
            d = ROOT / "assets" / mode; d.mkdir(parents=True, exist_ok=True)
            (d / f"{name}.svg").write_text(fn(*a, tk, mode == "dark"), encoding="utf-8")
    # remember: fn(*a, t, dark)
    add("hero", lambda t, d: hero(t, d))
    add("heatmap", lambda t, d: heatmap(t, d, end, days))
    add("stats", lambda t, d: stats_card(t, d, S))
    for k in ("build", "solve", "create"):
        add(f"tile-{k}", lambda t, d, k=k: tile(k, t, d))
    add("education", lambda t, d: education(t, d))
    add("learning", lambda t, d: learning(t, d))
    add("tech", lambda t, d: tech(t, d))
    add("how-i-work", lambda t, d: how(t, d))
    add("coding-label", lambda t, d: coding_label(t, d))
    for p in CFG["projects"]:
        add(f"project-{p['slug']}", lambda t, d, p=p: project(p, t, d))
    add("contact-header", lambda t, d: contact_header(t, d))
    btns = [("portfolio", "Portfolio", href(L["portfolio"]), True), ("linkedin", "LinkedIn", href(L["linkedin"]), False),
            ("email", "Email", href(L["email"], True), False), ("resume", "Resume", href(L["resume"]), False),
            ("leetcode", "LeetCode", href(L["leetcode"]), False)]
    for key, nm, url, yel in btns:
        add(f"contact-{key}", lambda t, d, nm=nm, url=url, yel=yel: contact_btn(nm, bool(url), yel, t, d))

    repos = f"{PROFILE_URL}?tab=repositories"
    # rows: list of (asset, width%, link, alt)
    rows = [
        [("hero", 100, L["portfolio"], "Tarun Suthar, AI-assisted developer building secure Java, Android and Python applications")],
        [("heatmap", 100, PROFILE_URL, "Contribution heatmap, building in public")],
        [("stats", 100, PROFILE_URL, f"{S['total']} contributions in the last 12 months with streak and activity stats")],
        [("tile-build", 33.3, repos, "Build: 3 apps"), ("tile-solve", 33.3, href(L["leetcode"]) or PROFILE_URL, "Solve: 120+ LeetCode problems"),
         ("tile-create", 33.3, L["portfolio"], "Create: AI visual design and digital storytelling")],
        [("education", 50, None, f"Education: {CFG['education']['degree']}, {CFG['education']['score']} CGPA"),
         ("learning", 50, None, "Currently learning: " + ", ".join(CFG["learning"]["chips"]))],
        [("tech", 100, None, "Tech stack: " + ", ".join(CFG["stack"]))],
        [("how-i-work", 100, None, "How I work: AI-assisted development with " + ", ".join(CFG["howIWork"]["tools"]))],
        [("coding-label", 100, None, "What I'm coding")],
        [(f"project-{p['slug']}", 33.3, p["repo"] or repos, f"{p['name']}: {p['desc']}") for p in CFG["projects"]],
        [("contact-header", 100, None, "Contact. Let's talk.")],
        [(f"contact-{k}", 20, (u or PROFILE_URL), f"{nm} link") for k, nm, u, _ in btns],
    ]
    def pic(prefix, name, w, link, alt):
        # GitHub Markdown standard for dual light/dark SVGs:
        # <source> provides dark-mode SVG; <img> provides light-mode default fallback
        img = (f'<picture>'
               f'<source media="(prefers-color-scheme: dark)" srcset="{prefix}assets/dark/{name}.svg">'
               f'<img src="{prefix}assets/light/{name}.svg" alt="{esc(alt)}" width="{w}%" align="top">'
               f'</picture>')
        return f'<a href="{link}">{img}</a>' if link else img
    md = ["<!-- AUTO-GENERATED by scripts/build.py. Edit profile.config.json, then run: python scripts/build.py -->"]
    for r in rows:
        md.append("<div>" + "".join(pic("", *c) for c in r) + "</div>")
    (ROOT / "README.md").write_text("\n\n".join(md) + "\n", encoding="utf-8")

    # preview.html: interactive Light, Dark, Split, and Adaptive preview
    def render_cards(cls):
        return "".join("<div>" + "".join(
            (f'<a href="{c[2]}" target="_blank">' if c[2] else "") +
            f'<img src="assets/{cls}/{c[0]}.svg" alt="{esc(c[3])}" width="{c[1]}%" align="top" style="vertical-align:top">' +
            ("</a>" if c[2] else "") for c in r) + "</div>" for r in rows)

    def render_adaptive():
        return "".join("<div>" + "".join(pic("", *c) for c in r) + "</div>" for r in rows)

    light_body = render_cards("light")
    dark_body = render_cards("dark")
    adaptive_body = render_adaptive()

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Profile Preview · Tarun Suthar</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      background: #f6f8fa;
      color: #1f2328;
      padding-top: 64px;
      transition: background 0.2s ease;
    }}
    .nav-bar {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 56px;
      background: #161b22;
      border-bottom: 1px solid #30363d;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      z-index: 1000;
    }}
    .nav-title {{
      font-weight: 700;
      font-size: 15px;
      display: flex;
      align-items: center;
      gap: 10px;
      color: #f0f6fc;
    }}
    .nav-title span {{
      color: #7ee787;
      font-size: 12px;
      background: rgba(46, 160, 67, 0.15);
      border: 1px solid rgba(46, 160, 67, 0.4);
      padding: 2px 8px;
      border-radius: 12px;
    }}
    .btn-group {{
      display: flex;
      background: #0d1117;
      padding: 3px;
      border-radius: 8px;
      border: 1px solid #30363d;
      gap: 2px;
    }}
    .btn-group button {{
      background: transparent;
      border: none;
      color: #8b949e;
      font-size: 13px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    .btn-group button:hover {{
      color: #f0f6fc;
    }}
    .btn-group button.active {{
      background: #21262d;
      color: #f0f6fc;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }}
    .preview-container {{
      max-width: 960px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .split-layout {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      max-width: 1920px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .card-shell {{
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    }}
    .shell-light {{
      background: #ffffff;
      color: #1f2328;
      border: 1px solid #d0d7de;
    }}
    .shell-dark {{
      background: #0d1117;
      color: #f0f6fc;
      border: 1px solid #30363d;
    }}
    .shell-header {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(128,128,128,0.2);
      display: flex;
      justify-content: space-between;
    }}
    .shell-light .shell-header {{ color: #57606a; }}
    .shell-dark .shell-header {{ color: #8b949e; }}
    img, picture {{ display: block; }}
  </style>
</head>
<body>
  <div class="nav-bar">
    <div class="nav-title">
      Tarun Suthar Profile <span>Live Preview</span>
    </div>
    <div class="btn-group">
      <button id="btn-light" onclick="setMode('light')" class="active">☀️ Light Mode</button>
      <button id="btn-dark" onclick="setMode('dark')">🌙 Dark Mode</button>
      <button id="btn-split" onclick="setMode('split')">🌓 Side-by-Side</button>
      <button id="btn-adaptive" onclick="setMode('adaptive')">⚙️ Adaptive (OS Theme)</button>
    </div>
  </div>

  <div id="view-single" class="preview-container">
    <div id="target-shell" class="card-shell shell-light">
      <div class="shell-header">
        <span id="shell-label">☀️ Light Mode (assets/light/*.svg)</span>
        <span>GitHub Profile View</span>
      </div>
      <div id="content-single">{light_body}</div>
    </div>
  </div>

  <div id="view-split" class="split-layout" style="display: none;">
    <div class="card-shell shell-light">
      <div class="shell-header">
        <span>☀️ Light Mode</span>
        <span>assets/light/*.svg</span>
      </div>
      <div>{light_body}</div>
    </div>
    <div class="card-shell shell-dark">
      <div class="shell-header">
        <span>🌙 Dark Mode</span>
        <span>assets/dark/*.svg</span>
      </div>
      <div>{dark_body}</div>
    </div>
  </div>

  <script>
    const bodies = {{
      light: {json.dumps(light_body)},
      dark: {json.dumps(dark_body)},
      adaptive: {json.dumps(adaptive_body)}
    }};

    function setMode(mode) {{
      document.querySelectorAll('.btn-group button').forEach(b => b.classList.remove('active'));
      const btn = document.getElementById('btn-' + mode);
      if (btn) btn.classList.add('active');

      const single = document.getElementById('view-single');
      const split = document.getElementById('view-split');
      const shell = document.getElementById('target-shell');
      const label = document.getElementById('shell-label');
      const content = document.getElementById('content-single');

      if (mode === 'split') {{
        document.body.style.background = '#1b1f24';
        single.style.display = 'none';
        split.style.display = 'grid';
      }} else {{
        split.style.display = 'none';
        single.style.display = 'block';
        content.innerHTML = bodies[mode];

        if (mode === 'light') {{
          document.body.style.background = '#f6f8fa';
          shell.className = 'card-shell shell-light';
          label.textContent = '☀️ Light Mode (assets/light/*.svg)';
        }} else if (mode === 'dark') {{
          document.body.style.background = '#010409';
          shell.className = 'card-shell shell-dark';
          label.textContent = '🌙 Dark Mode (assets/dark/*.svg)';
        }} else {{
          document.body.style.background = '#0d1117';
          shell.className = 'card-shell shell-dark';
          label.textContent = '⚙️ Adaptive Mode (Auto switches via prefers-color-scheme)';
        }}
      }}
    }}
  </script>
</body>
</html>"""
    (ROOT / "preview.html").write_text(html, encoding="utf-8")
    # Also write a pkg/preview.html copy for backward compatibility
    pkg_dir = ROOT / "pkg"
    pkg_dir.mkdir(exist_ok=True)
    pkg_html = html.replace('assets/', '../assets/')
    (pkg_dir / "preview.html").write_text(pkg_html, encoding="utf-8")
    print("Built", sum(1 for _ in (ROOT / "assets").rglob("*.svg")), "SVGs + README.md + preview.html")

if __name__ == "__main__":
    build()
