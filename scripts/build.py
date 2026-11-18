#!/usr/bin/env python3
"""Generates every redesigned cubic-glass SVG card (light + dark), README.md,
and pkg/preview.html from profile.config.json (plus keeps preview.html data synced).
No third-party dependencies.

Usage:  python scripts/build.py
Env:    GITHUB_TOKEN  -> fetch real contributions (otherwise sample data is used)
"""
import base64
import datetime as dt
import json
import os
import re
import sys
import textwrap
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "profile.config.json").read_text(encoding="utf-8"))
USER = CFG["username"]
PROFILE_URL = f"https://github.com/{USER}"

HEAD = "'Plus Jakarta Sans',system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Cormorant Garamond','Times New Roman',serif"
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

LIGHT = dict(
    card="#FFFFFF",
    subtle="#F1F3F6",
    tile="rgba(255,255,255,0.76)",
    pill="rgba(255,255,255,0.92)",
    border="rgba(15,23,42,0.09)",
    border_strong="rgba(15,23,42,0.16)",
    text="#0F172A",
    secondary="#475569",
    muted="#64748B",
    green="#0D6E4C",
    green_bright="#16A34A",
    red="#DC2626",
    amber="#F5B700",
    cobalt="#2563EB",
    gbar="#E2E8F0",
    grid_line="rgba(15,23,42,0.045)",
    cube_hi="rgba(255,255,255,0.82)",
    cube_lo="rgba(15,23,42,0.07)",
    cube_stroke="rgba(255,255,255,0.72)",
    heat=["#EEF2F6", "#BBF7D0", "#6EE7B7", "#10B981", "#065F46"],
    heat_border="rgba(15,23,42,0.06)",
    shadow_opacity="0.08",
    btn_bg="#0F172A",
    btn_fg="#FFFFFF",
    arrow_bg="#F1F3F6",
    tool_bg="rgba(251,191,36,0.13)",
    tool_border="rgba(245,183,0,0.42)",
)

DARK = dict(
    card="#111620",
    subtle="#161C28",
    tile="rgba(22,28,40,0.84)",
    pill="rgba(24,31,44,0.90)",
    border="rgba(255,255,255,0.10)",
    border_strong="rgba(255,255,255,0.18)",
    text="#F8FAFC",
    secondary="#94A3B8",
    muted="#64748B",
    green="#34D399",
    green_bright="#4ADE80",
    red="#F87171",
    amber="#FBBF24",
    cobalt="#60A5FA",
    gbar="#222B3A",
    grid_line="rgba(255,255,255,0.045)",
    cube_hi="rgba(255,255,255,0.22)",
    cube_lo="rgba(0,0,0,0.42)",
    cube_stroke="rgba(255,255,255,0.14)",
    heat=["#171E2B", "#064E3B", "#047857", "#10B981", "#4ADE80"],
    heat_border="rgba(255,255,255,0.07)",
    shadow_opacity="0.45",
    btn_bg="#F8FAFC",
    btn_fg="#0F172A",
    arrow_bg="#161C28",
    tool_bg="rgba(251,191,36,0.10)",
    tool_border="rgba(251,191,36,0.34)",
)

INK = "#0F172A"


# ------------------------------------------------------------------ helpers
def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def est(s, size, k=0.56):
    return len(s) * size * k


def T(x, y, s, size, fill, weight=400, fam=HEAD, ls=0, anchor="start", tl=None, style=None):
    a = f'x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" font-weight="{weight}" fill="{fill}"'
    if style:
        a += f' font-style="{style}"'
    if ls:
        a += f' letter-spacing="{ls}"'
    if anchor != "start":
        a += f' text-anchor="{anchor}"'
    if tl:
        a += f' textLength="{tl:.1f}" lengthAdjust="spacingAndGlyphs"'
    return f"<text {a}>{esc(s)}</text>"


def H_fit(x, y, s, size, fill, maxw=None, weight=800, anchor="start", fam=HEAD, ls=-1.2):
    w = est(s, size, 0.56)
    tl = maxw if (maxw and w > maxw) else None
    return T(x, y, s, size, fill, weight, fam, ls, anchor, tl=tl)


def wrap(s, n):
    return textwrap.wrap(s, n)


def arrow_ne(x, y, s, color, sw=2):
    return (
        f'<path d="M{x:.1f},{y+s:.1f} L{x+s:.1f},{y:.1f} '
        f'M{x+s*0.25:.1f},{y:.1f} H{x+s:.1f} V{y+s*0.75:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def arrow_r(x, y, s, color, sw=1.8):
    cy = y + s * 0.5
    return (
        f'<path d="M{x:.1f},{cy:.1f} H{x+s:.1f} '
        f'M{x+s*0.62:.1f},{y+s*0.18:.1f} L{x+s:.1f},{cy:.1f} L{x+s*0.62:.1f},{y+s*0.82:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def kicker(x, y, s, fill, dot, size=12):
    return (
        f'<rect x="{x:.1f}" y="{y-9:.1f}" width="8" height="8" rx="2" fill="{dot}"/>'
        + T(x + 16, y, s.upper(), size, fill, 600, MONO, ls=1.2)
    )


def round_top_bar(x, y, w, h, rt=6, rb=3):
    rt = min(rt, w / 2, h / 2)
    rb = min(rb, w / 2, h / 2)
    return (
        f"M{x+rt:.1f},{y:.1f} H{x+w-rt:.1f} "
        f"Q{x+w:.1f},{y:.1f} {x+w:.1f},{y+rt:.1f} "
        f"V{y+h-rb:.1f} Q{x+w:.1f},{y+h:.1f} {x+w-rb:.1f},{y+h:.1f} "
        f"H{x+rb:.1f} Q{x:.1f},{y+h:.1f} {x:.1f},{y+h-rb:.1f} "
        f"V{y+rt:.1f} Q{x:.1f},{y:.1f} {x+rt:.1f},{y:.1f} Z"
    )


def svg(w, h, defs, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" '
        f'width="{w:g}" height="{h:g}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title><defs>{defs}</defs>{body}</svg>"
    )


def card_shell(w, h, t, pad=36, ix=10, iy=10, rx=24):
    cw, ch = w - 2 * ix, h - 2 * iy
    defs = (
        f'<filter id="sh" x="-10%" y="-10%" width="120%" height="130%">'
        f'<feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="#0F172A" flood-opacity="{t["shadow_opacity"]}"/>'
        f"</filter>"
        f'<clipPath id="clip">'
        f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" rx="{rx}"/>'
        f"</clipPath>"
    )
    bg_rect = (
        f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" rx="{rx}" '
        f'fill="{t["card"]}" filter="url(#sh)"/>'
    )
    border_rect = (
        f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" rx="{rx}" '
        f'fill="none" stroke="{t["border"]}" stroke-width="1.5"/>'
    )
    return defs, bg_rect, border_rect, ix, iy, cw, ch, ix + pad, ix + cw - pad


def cubic_pattern_defs(uid, t, size=36):
    return (
        f'<linearGradient id="cbGrad-{uid}" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{t["cube_hi"]}"/>'
        f'<stop offset="48%" stop-color="#FFFFFF" stop-opacity="0"/>'
        f'<stop offset="100%" stop-color="{t["cube_lo"]}"/>'
        f"</linearGradient>"
        f'<pattern id="cbPat-{uid}" width="{size}" height="{size}" patternUnits="userSpaceOnUse">'
        f'<rect width="{size}" height="{size}" fill="url(#cbGrad-{uid})"/>'
        f'<path d="M{size},0 H0 V{size}" fill="none" stroke="{t["cube_stroke"]}" stroke-width="1"/>'
        f"</pattern>"
    )


def cubic_orb_defs(uid, w, h, t, cx, cy, r, stops, mask_cx, mask_cy, mask_rx, mask_ry):
    stop_xml = "".join(
        f'<stop offset="{off}" stop-color="{col}" stop-opacity="{op}"/>'
        for off, col, op in stops
    )
    fade_r = max(float(mask_rx), float(mask_ry))
    return (
        cubic_pattern_defs(uid, t)
        + f'<radialGradient id="mesh-{uid}" cx="{cx}" cy="{cy}" r="{r}">{stop_xml}</radialGradient>'
        + f'<radialGradient id="fade-{uid}" gradientUnits="userSpaceOnUse" cx="{mask_cx}" cy="{mask_cy}" r="{fade_r:g}">'
        + f'<stop offset="0%" stop-color="#FFFFFF" stop-opacity="1"/>'
        + f'<stop offset="52%" stop-color="#FFFFFF" stop-opacity="0.58"/>'
        + f'<stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>'
        + f"</radialGradient>"
        + f'<mask id="mask-{uid}" maskUnits="userSpaceOnUse" x="0" y="0" width="{w:g}" height="{h:g}">'
        + f'<ellipse cx="{mask_cx}" cy="{mask_cy}" rx="{mask_rx}" ry="{mask_ry}" fill="url(#fade-{uid})"/>'
        + f"</mask>"
    )


def cubic_orb_layer(uid, ix, iy, cw, ch, opacity=0.92):
    return (
        f'<g clip-path="url(#clip)">'
        f'<g mask="url(#mask-{uid})" opacity="{opacity}">'
        f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" fill="url(#mesh-{uid})"/>'
        f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" fill="url(#cbPat-{uid})"/>'
        f"</g></g>"
    )


# ------------------------------------------------------------ contribution data
def load_contributions():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
    end = dt.date.today()
    if token:
        try:
            frm = end - dt.timedelta(days=364)
            q = (
                "query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t)"
                "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"
            )
            payload = json.dumps(
                {
                    "query": q,
                    "variables": {
                        "u": USER,
                        "f": frm.isoformat() + "T00:00:00Z",
                        "t": end.isoformat() + "T23:59:59Z",
                    },
                }
            ).encode()
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                payload,
                {
                    "Authorization": f"bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "profile-builder",
                },
            )
            data = json.load(urllib.request.urlopen(req, timeout=15))
            weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            days = {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
            print("Using live GitHub GraphQL data")
            try:
                (ROOT / "data" / "sample-contributions.json").write_text(
                    json.dumps({"end": end.isoformat(), "days": days}, indent=1),
                    encoding="utf-8",
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
                    json.dumps({"end": end.isoformat(), "days": days}, indent=1),
                    encoding="utf-8",
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
        cur += 1
        d -= dt.timedelta(days=1)
    longest = run = 0
    for d in win:
        run = run + 1 if cnt(d) > 0 else 0
        longest = max(longest, run)
    months = []
    y, m = end.year, end.month
    for _ in range(12):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    mt = [sum(c for k, c in days.items() if k[:7] == f"{y}-{m:02d}") for y, m in months]
    names = [dt.date(y, m, 1).strftime("%b") for y, m in months]
    return dict(total=total, active=active, busiest=busiest, cur=cur, longest=longest, mt=mt, names=names)


# ------------------------------------------------------------------ cards
def hero(t, dark):
    w, h = 1000, 480
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=40, rx=24)

    # Vertical hairline editorial grid + cubic mesh gradient
    defs += (
        f'<pattern id="vlines" width="56" height="56" patternUnits="userSpaceOnUse">'
        f'<line x1="0" y1="0" x2="0" y2="56" stroke="{t["grid_line"]}" stroke-width="1"/>'
        f"</pattern>"
        f'<linearGradient id="goldPill" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="#FFD43B"/>'
        f'<stop offset="100%" stop-color="#F5B700"/>'
        f"</linearGradient>"
        + cubic_pattern_defs("hero", t)
        + f'<radialGradient id="hm1" cx="84%" cy="84%" r="52%">'
        + f'<stop offset="0%" stop-color="#10B981" stop-opacity="{"0.46" if not dark else "0.34"}"/>'
        + f'<stop offset="55%" stop-color="#FBBF24" stop-opacity="{"0.24" if not dark else "0.16"}"/>'
        + f'<stop offset="100%" stop-color="#2563EB" stop-opacity="0"/>'
        + f"</radialGradient>"
        + f'<radialGradient id="hmaskGrad" cx="84%" cy="82%" r="68%">'
        + f'<stop offset="0%" stop-color="#FFFFFF" stop-opacity="1"/>'
        + f'<stop offset="55%" stop-color="#FFFFFF" stop-opacity="0.45"/>'
        + f'<stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>'
        + f"</radialGradient>"
        + f'<mask id="hmask"><rect x="{ix}" y="{iy}" width="{cw}" height="{ch}" fill="url(#hmaskGrad)"/></mask>'
    )

    b = bg
    b += (
        f'<g clip-path="url(#clip)">'
        f'<rect x="{ix}" y="{iy}" width="{cw}" height="{ch}" fill="url(#vlines)"/>'
        f'<g mask="url(#hmask)">'
        f'<rect x="{ix}" y="{iy}" width="{cw}" height="{ch}" fill="url(#hm1)"/>'
        f'<rect x="{ix}" y="{iy}" width="{cw}" height="{ch}" fill="url(#cbPat-hero)"/>'
        f"</g></g>"
    )

    # Kicker
    b += kicker(px, 60, "01. Profile · Open to opportunities", t["muted"], t["red"], size=12)

    # Name
    n1, n2 = CFG["name"]
    b += H_fit(px, 134, n1, 74, t["text"], maxw=460, weight=800, ls=-3.0)
    pw = est(n2, 74, 0.56) + 34
    b += f'<rect x="{px}" y="148" width="{pw:.1f}" height="82" rx="14" fill="url(#goldPill)"/>'
    b += H_fit(px + 17, 214, n2, 74, INK, maxw=pw - 24, weight=800, ls=-2.8)

    # Floating tilted handle pill
    handle = f"@{USER}"
    hw = est(handle, 13, 0.62) + 30
    b += (
        f'<g transform="translate({px+2}, 248) rotate(-1.5)">'
        f'<rect x="0" y="0" width="{hw:.1f}" height="32" rx="16" fill="{t["pill"]}" stroke="{t["border_strong"]}" stroke-width="1"/>'
        + T(hw / 2, 20.5, handle, 13, t["cobalt"], 600, MONO, anchor="middle")
        + "</g>"
    )

    # Role + Tagline
    b += T(px, 316, CFG["label"], 16, t["text"], 700, HEAD, ls=-0.2)
    for i, ln in enumerate(wrap(CFG["tagline"], 44)[:2]):
        b += T(px, 344 + i * 24, ln, 16, t["secondary"], 400, HEAD)

    # Action visual controls
    bw = 166
    b += f'<rect x="{px}" y="396" width="{bw}" height="40" rx="12" fill="{t["btn_bg"]}"/>'
    b += T(px + 18, 421, "View Portfolio", 13.5, t["btn_fg"], 600, HEAD)
    b += arrow_ne(px + bw - 28, 410, 10, t["btn_fg"], sw=2)
    b += T(px + bw + 20, 421, "Browse Repositories", 13.5, t["secondary"], 600, HEAD)
    b += arrow_r(px + bw + 170, 410, 12, t["secondary"], sw=1.8)

    # Right media frame (always warm paper #F3F1E7 matching hero.gif)
    mx, my, mw, mh = 610, 40, 340, 400
    b += f'<rect x="{mx}" y="{my}" width="{mw}" height="{mh}" rx="20" fill="#F3F1E7" stroke="{t["border_strong"]}" stroke-width="1.5"/>'
    p_gif = ROOT / "assets" / "hero.gif"
    p_png = ROOT / "assets" / "hero.png"
    p = p_gif if p_gif.exists() else p_png
    if p.exists():
        mime = "image/gif" if p.suffix.lower() == ".gif" else "image/png"
        uri = base64.b64encode(p.read_bytes()).decode()
        b += (
            f'<image x="{mx+16}" y="{my+16}" width="{mw-32}" height="{mh-32}" '
            f'preserveAspectRatio="xMidYMid meet" href="data:{mime};base64,{uri}"/>'
        )
    b += br
    return svg(w, h, defs, b, "Tarun Suthar, AI-assisted developer. Building secure Java, Android, and Python applications.")


def heatmap(t, dark, end, days):
    w, h = 1000, 318
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    b = bg
    b += kicker(px, 56, "02. Activity · Refreshed daily", t["muted"], t["green_bright"], size=12)
    b += (
        f'<text x="{px}" y="100" font-family="{HEAD}" font-size="38" font-weight="800" letter-spacing="-1.4" fill="{t["text"]}">'
        f'Building <tspan font-family="{SERIF}" font-style="italic" font-weight="600" font-size="42" fill="{t["green"]}">in public</tspan></text>'
    )

    start = end - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    pitch, cs = 17.15, 13.6
    lvl = lambda c: 0 if c == 0 else 1 if c < 3 else 2 if c < 6 else 3 if c < 10 else 4
    gy = 128
    active = sum(1 for i in range(365) if days.get((end - dt.timedelta(days=i)).isoformat(), 0) > 0)

    for i in range((end - start).days + 1):
        d = start + dt.timedelta(days=i)
        col, row = i // 7, i % 7
        l = lvl(days.get(d.isoformat(), 0))
        cx = px + col * pitch
        cy = gy + row * pitch
        b += (
            f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cs}" height="{cs}" rx="3.5" '
            f'fill="{t["heat"][l]}" stroke="{t["heat_border"]}" stroke-width="1"/>'
        )

    # Footer
    fy = 278
    b += T(px, fy, f"Last 12 months · {active} active days", 12, t["muted"], 500, MONO)
    lx = pr - 166
    b += T(lx, fy, "less", 12, t["muted"], 500, MONO)
    for i in range(5):
        b += (
            f'<rect x="{lx+38+i*18}" y="{fy-11}" width="13" height="13" rx="3.2" '
            f'fill="{t["heat"][i]}" stroke="{t["heat_border"]}" stroke-width="1"/>'
        )
    b += T(lx + 38 + 5 * 18 + 4, fy, "more", 12, t["muted"], 500, MONO)
    b += br
    return svg(w, h, defs, b, "GitHub contribution heatmap for the last 12 months, building in public.")


def stats_card(t, dark, S):
    w, h = 1000, 420
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    defs += (
        f'<linearGradient id="barPeak" x1="0%" y1="0%" x2="0%" y2="100%">'
        f'<stop offset="0%" stop-color="#EF4444"/><stop offset="100%" stop-color="#B91C1C"/>'
        f"</linearGradient>"
        f'<linearGradient id="barCur" x1="0%" y1="0%" x2="0%" y2="100%">'
        f'<stop offset="0%" stop-color="#10B981"/><stop offset="100%" stop-color="#047857"/>'
        f"</linearGradient>"
    )
    b = bg
    b += kicker(px, 56, "Contributions · Last 12 months", t["muted"], t["red"], size=12)
    b += T(px, 134, str(S["total"]), 78, t["text"], 800, HEAD, ls=-3.5)
    b += T(px, 166, "contributions across repositories", 16, t["secondary"], 600, HEAD)

    # Monthly bars
    mt, names = S["mt"], S["names"]
    mx = max(mt) or 1
    top1 = sorted(range(12), key=lambda i: -mt[i])[0]
    base, maxh, pitch, bw = 358, 136, 44.5, 34
    for i, v in enumerate(mt):
        bh = max(7, v / mx * maxh)
        fill = t["gbar"]
        if i == top1 and v > 0:
            fill = "url(#barPeak)"
        if i == 11:
            fill = "url(#barCur)"
        bx = px + i * pitch
        b += f'<path d="{round_top_bar(bx, base - bh, bw, bh, rt=6, rb=3)}" fill="{fill}"/>'
        if v >= mx * 0.25 and v > 0:
            b += T(bx + bw / 2, base - bh - 9, str(v), 12, t["secondary"], 600, MONO, anchor="middle")
        b += T(bx + bw / 2, 382, names[i], 11.5, t["muted"], 500, MONO, anchor="middle")

    # Right KPI column
    div_x = 612
    b += f'<line x1="{div_x}" y1="42" x2="{div_x}" y2="{h-42}" stroke="{t["border"]}" stroke-width="1.2"/>'
    rx = 644

    def kpi_block(y, num, unit, cap):
        nw = est(num, 38, 0.58)
        out = T(rx, y, num, 38, t["text"], 800, HEAD, ls=-1.5)
        if unit:
            out += T(rx + nw + 8, y, unit, 16, t["secondary"], 600, HEAD)
        out += T(rx, y + 26, cap, 12.5, t["muted"], 500, MONO)
        return out

    b += kpi_block(96, str(S["cur"]), "days", f'current streak · longest {S["longest"]} days')
    b += f'<line x1="{rx}" y1="154" x2="{pr}" y2="154" stroke="{t["border"]}" stroke-width="1.2"/>'
    b += kpi_block(216, str(S["active"]), "/ 365", "days with a commit")
    b += f'<line x1="{rx}" y1="274" x2="{pr}" y2="274" stroke="{t["border"]}" stroke-width="1.2"/>'
    b += kpi_block(336, str(S["busiest"]), "", "commits on the busiest day")
    b += br
    return svg(
        w,
        h,
        defs,
        b,
        f'{S["total"]} contributions in the last 12 months, current streak {S["cur"]} days, longest {S["longest"]}, {S["active"]} of 365 days with a commit, busiest day {S["busiest"]}.',
    )


def tile(kind, t, dark):
    w, h = 333.33, 370
    c = CFG["tiles"][kind]
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=26, ix=7, iy=8, rx=24)

    orb_stops = {
        "build": [("0%", "#BEF264", "0.95"), ("38%", "#10B981", "0.78"), ("72%", "#047857", "0.52"), ("100%", "#047857", "0")],
        "solve": [("0%", "#FDE047", "0.92"), ("34%", "#FB7185", "0.76"), ("70%", "#DC2626", "0.52"), ("100%", "#DC2626", "0")],
        "create": [("0%", "#FEF08A", "0.95"), ("40%", "#FBBF24", "0.80"), ("74%", "#EA580C", "0.54"), ("100%", "#EA580C", "0")],
    }[kind]
    defs += cubic_orb_defs(kind, w, h, t, "50%", "96%", "62%", orb_stops, "166", "345", "185", "175")

    b = bg
    b += cubic_orb_layer(kind, ix, iy, cw, ch, opacity=0.90 if not dark else 0.78)

    # Top row: uppercase mono label + rounded arrow badge
    b += T(px, 56, kind.upper(), 12, t["muted"], 700, MONO, ls=1.6)
    b += f'<rect x="{pr-30}" y="36" width="30" height="30" rx="10" fill="{t["subtle"]}" stroke="{t["border"]}" stroke-width="1"/>'
    b += arrow_ne(pr - 19.5, 46.5, 9, t["text"], sw=1.8)

    # Metric + text
    if kind == "create":
        b += H_fit(px, 114, c["big"], 38, t["text"], maxw=pr - px, weight=800, ls=-1.5)
        dy = 148
    else:
        nw = est(c["big"], 38, 0.58)
        b += T(px, 114, c["big"], 38, t["text"], 800, HEAD, ls=-1.5)
        b += T(px + nw + 8, 114, c["unit"], 16, t["secondary"], 600, HEAD)
        dy = 148

    for i, ln in enumerate(wrap(c["text"], 30)[:3]):
        b += T(px, dy + i * 22, ln, 14, t["secondary"], 400, HEAD)

    if kind == "create":
        cy = 204
        b += f'<rect x="{px}" y="{cy}" width="144" height="34" rx="10" fill="{t["pill"]}" stroke="{t["border_strong"]}" stroke-width="1"/>'
        b += T(px + 14, cy + 21, "View Portfolio", 12, t["text"], 700, MONO)
        b += arrow_ne(px + 122, cy + 12, 8.5, t["text"], sw=1.8)

    b += br
    u = c.get("unit", "")
    title_str = f'{kind.capitalize()}: {c["big"]} {u}'.replace("  ", " ").strip() + f'. {c["text"]}'
    return svg(w, h, defs, b, title_str)


def education(t, dark):
    w, h = 500, 248
    e = CFG["education"]
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=32, ix=8, iy=8, rx=24)
    b = bg
    b += kicker(px, 54, "Education", t["muted"], t["green_bright"], size=12)
    b += H_fit(px, 102, e["degree"], 25, t["text"], maxw=pr - px, weight=700, ls=-0.6)
    sw = est(e["score"], 58, 0.58)
    b += T(px, 198, e["score"], 58, t["text"], 800, HEAD, ls=-2.6)
    b += T(px + sw + 10, 198, e["scoreLabel"], 18, t["green"], 700, HEAD)
    b += br
    return svg(w, h, defs, b, f'Education: {e["degree"]}, {e["score"]} {e["scoreLabel"]}.')


def learning(t, dark):
    w, h = 500, 248
    L = CFG["learning"]
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=32, ix=8, iy=8, rx=24)
    stops = [("0%", "#FBBF24", "0.48"), ("65%", "#F59E0B", "0.20"), ("100%", "#F59E0B", "0")]
    defs += cubic_orb_defs("learn", w, h, t, "90%", "88%", "65%", stops, "440", "210", "245", "175")

    b = bg
    b += cubic_orb_layer("learn", ix, iy, cw, ch, opacity=0.90 if not dark else 0.75)
    b += kicker(px, 54, "Currently learning", t["muted"], t["amber"], size=12)
    lines = wrap(L["title"], 28)
    for i, ln in enumerate(lines[:2]):
        b += H_fit(px, 100 + i * 30, ln, 25, t["text"], maxw=pr - px, weight=700, ls=-0.6)

    # 3 proportionally balanced frosted tile blocks
    chips = L["chips"][:3]
    gap = 10
    avail = pr - px - gap * (len(chips) - 1)
    raw_w = [max(76.0, est(ch, 12.0, 0.62) + 34.0) for ch in chips]
    scale = avail / max(1.0, sum(raw_w))
    cx = px
    cy = 166
    for idx, chip in enumerate(chips):
        tw = raw_w[idx] * scale
        b += f'<rect x="{cx:.1f}" y="{cy}" width="{tw:.1f}" height="42" rx="12" fill="{t["tile"]}" stroke="{t["border"]}" stroke-width="1"/>'
        b += T(cx + tw / 2, cy + 25.5, chip, 12.0, t["text"], 600, MONO, anchor="middle")
        cx += tw + gap

    b += br
    return svg(w, h, defs, b, "Currently learning: " + ", ".join(L["chips"]) + ".")


def tech(t, dark):
    w, h = 1000, 266
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    b = bg
    b += kicker(px, 54, "Tech stack", t["muted"], t["red"], size=12)
    b += T(px, 98, "What I use", 34, t["text"], 800, HEAD, ls=-1.2)

    gap = 10
    cols = 4
    cell_w = (pr - px - gap * (cols - 1)) / cols
    cell_h = 52
    for idx, s in enumerate(CFG["stack"]):
        r, c = divmod(idx, cols)
        cx = px + c * (cell_w + gap)
        cy = 122 + r * (cell_h + gap)
        b += f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cell_w:.1f}" height="{cell_h}" rx="14" fill="{t["subtle"]}" stroke="{t["border"]}" stroke-width="1"/>'
        b += T(cx + 18, cy + 31, s, 15, t["text"], 600, HEAD)
        b += T(cx + cell_w - 18, cy + 30.5, f"{idx+1:02d}", 11.5, t["muted"], 500, MONO, anchor="end")

    b += br
    return svg(w, h, defs, b, "Tech stack: " + ", ".join(CFG["stack"]) + ".")


def how(t, dark):
    w, h = 1000, 232
    H_ = CFG["howIWork"]
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    b = bg
    b += kicker(px, 54, "How I work", t["muted"], t["green_bright"], size=12)

    clean_text = H_["text"].rstrip(" ,…") + ":"
    lines = wrap(clean_text, 62)
    y = 92
    for ln in lines[:2]:
        b += T(px, y, ln, 21, t["text"], 600, HEAD, ls=-0.4)
        y += 30

    gap = 10
    tools = H_["tools"]
    tw = (pr - px - gap * (len(tools) - 1)) / max(1, len(tools))
    ty = 148
    for idx, tool in enumerate(tools):
        cx = px + idx * (tw + gap)
        b += f'<rect x="{cx:.1f}" y="{ty}" width="{tw:.1f}" height="52" rx="14" fill="{t["tool_bg"]}" stroke="{t["tool_border"]}" stroke-width="1"/>'
        b += T(cx + 18, ty + 31, tool, 15, t["text"], 700, HEAD)
        b += f'<rect x="{cx + tw - 26:.1f}" y="{ty + 22}" width="8" height="8" rx="2" fill="{t["amber"]}"/>'

    b += br
    return svg(w, h, defs, b, "How I work: " + H_["text"] + " " + ", ".join(H_["tools"]) + ".")


def coding_label(t, dark):
    w, h = 1000, 44
    b = kicker(14, 28, "What I'm coding", t["muted"], t["red"], size=12)
    b += T(w - 30, 28, "All Repositories", 13.5, t["secondary"], 600, HEAD, anchor="end")
    b += arrow_ne(w - 22, 18.5, 9, t["secondary"], sw=1.8)
    return svg(w, h, "", b, "What I'm coding")


def project(p, t, dark):
    w, h = 333.33, 288
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=24, ix=7, iy=8, rx=24)

    palette = {
        "green": (t["green_bright"], "Java · Security", [("0%", "#10B981", "0.62"), ("55%", "#059669", "0.26"), ("100%", "#059669", "0")]),
        "red": (t["red"], "Android · Sync", [("0%", "#EF4444", "0.58"), ("55%", "#DC2626", "0.24"), ("100%", "#DC2626", "0")]),
        "yellow": (t["amber"], "Python · MySQL", [("0%", "#FBBF24", "0.62"), ("55%", "#F59E0B", "0.25"), ("100%", "#F59E0B", "0")]),
    }
    dot_col, sub_tag, stops = palette.get(p["color"], palette["green"])
    defs += cubic_orb_defs(p["slug"], w, h, t, "88%", "74%", "58%", stops, "280", "205", "165", "150")

    b = bg
    b += cubic_orb_layer(p["slug"], ix, iy, cw, ch, opacity=0.84 if not dark else 0.72)

    # Unboxed metadata line
    b += kicker(px, 50, f'{p["tag"]} · {sub_tag}', t["muted"], dot_col, size=11)

    # Title (camelCase split cleanly)
    spaced_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", p["name"])
    title_lines = wrap(spaced_name, 20)
    if len(title_lines) == 1:
        b += H_fit(px, 86, title_lines[0], 21, t["text"], maxw=pr - px, weight=700, ls=-0.5)
        dy = 114
    else:
        b += H_fit(px, 84, title_lines[0], 21, t["text"], maxw=pr - px, weight=700, ls=-0.5)
        b += H_fit(px, 108, title_lines[1], 21, t["text"], maxw=pr - px, weight=700, ls=-0.5)
        dy = 136

    for i, ln in enumerate(wrap(p["desc"], 29)[:3]):
        b += T(px, dy + i * 21, ln, 13.8, t["secondary"], 400, HEAD)

    # Bottom footer bar
    b += f'<line x1="{px}" y1="214" x2="{pr}" y2="214" stroke="{t["border"]}" stroke-width="1"/>'
    b += T(px, 246, "README", 12, t["text"], 700, MONO)
    b += f'<rect x="{pr-30}" y="226" width="30" height="30" rx="10" fill="{t["subtle"]}" stroke="{t["border"]}" stroke-width="1"/>'
    b += arrow_ne(pr - 19.5, 236.5, 9, t["text"], sw=1.8)
    b += br
    return svg(w, h, defs, b, f'{p["name"]}: {p["desc"]} ({p["tag"]}). Opens the repository.')


def contact_header(t, dark):
    w, h = 1000, 162
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    stops = [
        ("0%", "#8B5CF6", "0.46" if not dark else "0.42"),
        ("45%", "#2563EB", "0.32"),
        ("80%", "#FBBF24", "0.18"),
        ("100%", "#2563EB", "0"),
    ]
    defs += cubic_orb_defs("contact", w, h, t, "82%", "50%", "55%", stops, "820", "82", "360", "130")

    b = bg
    b += cubic_orb_layer("contact", ix, iy, cw, ch, opacity=0.95)
    b += kicker(px, 56, "Contact", t["muted"], t["red"], size=12)
    b += (
        f'<text x="{px}" y="114" font-family="{HEAD}" font-size="48" font-weight="800" letter-spacing="-1.8" fill="{t["text"]}">'
        f'Let\'s <tspan font-family="{SERIF}" font-style="italic" font-weight="600" font-size="52">talk.</tspan></text>'
    )

    bw = 166
    bx = pr - bw
    b += f'<rect x="{bx}" y="78" width="{bw}" height="40" rx="12" fill="{t["btn_bg"]}"/>'
    b += T(bx + 18, 103, "Open Portfolio", 13.5, t["btn_fg"], 600, HEAD)
    b += arrow_ne(bx + bw - 28, 92, 10, t["btn_fg"], sw=2)
    b += br
    return svg(w, h, defs, b, "Contact. Let's talk.")


def contact_btn(name, filled, yellow, t, dark):
    w, h = 200, 108
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=18, ix=6, iy=6, rx=16)

    if yellow:
        defs += (
            '<linearGradient id="goldBtn" x1="0%" y1="0%" x2="100%" y2="100%">'
            '<stop offset="0%" stop-color="#FFD43B"/><stop offset="100%" stop-color="#F5B700"/>'
            "</linearGradient>"
        )
        b = (
            f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" rx="16" fill="url(#goldBtn)" filter="url(#sh)"/>'
            f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" rx="16" fill="none" stroke="rgba(15,23,42,0.16)" stroke-width="1.5"/>'
        )
        b += T(px, 40, name, 14.5, INK, 700, HEAD)
        b += arrow_ne(pr - 12, 29, 9, INK, sw=2)
        b += T(px, 78, "Open live site", 11, "rgba(15,23,42,0.72)", 600, MONO)
    elif filled:
        b = bg
        b += T(px, 40, name, 14.5, t["text"], 700, HEAD)
        b += arrow_ne(pr - 12, 29, 9, t["text"], sw=2)
        b += T(px, 78, "Connect", 11, t["muted"], 500, MONO)
        b += br
    else:
        b = f'<g opacity="0.72">{bg}'
        b += T(px, 40, name, 14.5, t["text"], 700, HEAD)
        b += T(pr - 4, 40, "·", 14.5, t["muted"], 700, MONO, anchor="end")
        b += T(px, 78, "Coming soon", 11, t["muted"], 500, MONO)
        b += br + "</g>"

    return svg(w, h, defs, b, f"{name} link" + ("" if filled else " (coming soon)"))


# ------------------------------------------------------------------ layout
def href(v, mail=False):
    if not v:
        return None
    if mail and not v.startswith("mailto:"):
        return "mailto:" + v
    return v


def build():
    end, days = load_contributions()
    S = stats(end, days)
    L = CFG["links"]

    def add(name, fn, *a):
        for mode, tk in (("light", LIGHT), ("dark", DARK)):
            d = ROOT / "assets" / mode
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{name}.svg").write_text(fn(*a, tk, mode == "dark"), encoding="utf-8")

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
    btns = [
        ("portfolio", "Portfolio", href(L["portfolio"]), True),
        ("linkedin", "LinkedIn", href(L["linkedin"]), False),
        ("email", "Email", href(L["email"], True), False),
        ("resume", "Resume", href(L["resume"]), False),
        ("leetcode", "LeetCode", href(L["leetcode"]), False),
    ]
    for key, nm, url, yel in btns:
        add(f"contact-{key}", lambda t, d, nm=nm, url=url, yel=yel: contact_btn(nm, bool(url), yel, t, d))

    repos = f"{PROFILE_URL}?tab=repositories"
    rows = [
        [("hero", 100, L["portfolio"], "Tarun Suthar, AI-assisted developer building secure Java, Android and Python applications")],
        [("heatmap", 100, PROFILE_URL, "Contribution heatmap, building in public")],
        [("stats", 100, PROFILE_URL, f"{S['total']} contributions in the last 12 months with streak and activity stats")],
        [
            ("tile-build", 33.3, repos, "Build: 3 apps"),
            ("tile-solve", 33.3, href(L["leetcode"]) or PROFILE_URL, "Solve: 120+ LeetCode problems"),
            ("tile-create", 33.3, L["portfolio"], "Create: AI visual design and digital storytelling"),
        ],
        [
            ("education", 50, None, f"Education: {CFG['education']['degree']}, {CFG['education']['score']} CGPA"),
            ("learning", 50, None, "Currently learning: " + ", ".join(CFG["learning"]["chips"])),
        ],
        [("tech", 100, None, "Tech stack: " + ", ".join(CFG["stack"]))],
        [("how-i-work", 100, None, "How I work: AI-assisted development with " + ", ".join(CFG["howIWork"]["tools"]))],
        [("coding-label", 100, repos, "What I'm coding")],
        [(f"project-{p['slug']}", 33.3, p["repo"] or repos, f"{p['name']}: {p['desc']}") for p in CFG["projects"]],
        [("contact-header", 100, L["portfolio"], "Contact. Let's talk.")],
        [(f"contact-{k}", 20, (u or PROFILE_URL), f"{nm} link") for k, nm, u, _ in btns],
    ]

    def pic(prefix, name, w, link, alt):
        img = (
            f'<picture>'
            f'<source media="(prefers-color-scheme: dark)" srcset="{prefix}assets/dark/{name}.svg">'
            f'<source media="(prefers-color-scheme: light)" srcset="{prefix}assets/light/{name}.svg">'
            f'<img alt="{esc(alt)}" src="{prefix}assets/light/{name}.svg" width="{w}%" align="top">'
            f"</picture>"
        )
        return f'<a href="{link}">{img}</a>' if link else img

    md = ["<!-- AUTO-GENERATED by scripts/build.py. Edit profile.config.json, then run: python scripts/build.py -->"]
    for r in rows:
        md.append("<div>" + "".join(pic("", *c) for c in r) + "</div>")
    (ROOT / "README.md").write_text("\n\n".join(md) + "\n", encoding="utf-8")

    # Keep pkg/preview.html as an SVG README inspector so both Light/Dark/Adaptive SVGs can be verified directly
    def render_cards(cls, prefix="../"):
        return "".join(
            "<div>"
            + "".join(
                (f'<a href="{c[2]}" target="_blank">' if c[2] else "")
                + f'<img src="{prefix}assets/{cls}/{c[0]}.svg" alt="{esc(c[3])}" width="{c[1]}%" align="top">'
                + ("</a>" if c[2] else "")
                for c in r
            )
            + "</div>"
            for r in rows
        )

    def render_adaptive(prefix="../"):
        return "".join("<div>" + "".join(pic(prefix, *c) for c in r) + "</div>" for r in rows)

    light_body = render_cards("light")
    dark_body = render_cards("dark")
    adaptive_body = render_adaptive()

    pkg_html = f"""<!doctype html>
<html lang="en" data-color-mode="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SVG README Preview · Tarun Suthar</title>
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
      top: 0; left: 0; right: 0;
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
    }}
    .btn-group button.active {{ background: #21262d; color: #f0f6fc; }}
    .preview-container {{ max-width: 960px; margin: 24px auto; padding: 0 16px; }}
    .split-layout {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      max-width: 1920px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .card-shell {{ border-radius: 16px; padding: 24px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }}
    .shell-light {{ background: #ffffff; color: #1f2328; border: 1px solid #d0d7de; }}
    .shell-dark {{ background: #0d1117; color: #f0f6fc; border: 1px solid #30363d; }}
    .shell-header {{
      font-size: 12px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
      margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid rgba(128,128,128,0.2);
      display: flex; justify-content: space-between;
    }}
    .shell-light .shell-header {{ color: #57606a; }}
    .shell-dark .shell-header {{ color: #8b949e; }}
    picture {{ display: inline; }}
    img {{ display: inline-block; vertical-align: top; }}
    #content-single > div, .card-shell > div > div {{ margin-bottom: 2px; }}
  </style>
</head>
<body>
  <div class="nav-bar">
    <div class="nav-title">Tarun Suthar SVG README <span>GitHub Parity Preview</span></div>
    <div class="btn-group">
      <button id="btn-light" onclick="setMode('light')" class="active">Light Mode</button>
      <button id="btn-dark" onclick="setMode('dark')">Dark Mode</button>
      <button id="btn-split" onclick="setMode('split')">Side-by-Side</button>
      <button id="btn-adaptive" onclick="setMode('adaptive')">Adaptive</button>
    </div>
  </div>
  <div id="view-single" class="preview-container">
    <div id="target-shell" class="card-shell shell-light">
      <div class="shell-header"><span id="shell-label">Light Mode (../assets/light/*.svg)</span><span>GitHub README View</span></div>
      <div id="content-single">{light_body}</div>
    </div>
  </div>
  <div id="view-split" class="split-layout" style="display: none;">
    <div class="card-shell shell-light"><div class="shell-header"><span>Light Mode</span><span>../assets/light/*.svg</span></div><div>{light_body}</div></div>
    <div class="card-shell shell-dark"><div class="shell-header"><span>Dark Mode</span><span>../assets/dark/*.svg</span></div><div>{dark_body}</div></div>
  </div>
  <script>
    const bodies = {{ light: {json.dumps(light_body)}, dark: {json.dumps(dark_body)}, adaptive: {json.dumps(adaptive_body)} }};
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
          label.textContent = 'Light Mode (../assets/light/*.svg)';
        }} else if (mode === 'dark') {{
          document.body.style.background = '#010409';
          shell.className = 'card-shell shell-dark';
          label.textContent = 'Dark Mode (../assets/dark/*.svg)';
        }} else {{
          const isDarkOS = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
          document.body.style.background = isDarkOS ? '#010409' : '#f6f8fa';
          shell.className = isDarkOS ? 'card-shell shell-dark' : 'card-shell shell-light';
          label.textContent = 'Adaptive Mode (<picture> prefers-color-scheme: ' + (isDarkOS ? 'dark' : 'light') + ')';
        }}
      }}
    }}
  </script>
</body>
</html>"""
    pkg_dir = ROOT / "pkg"
    pkg_dir.mkdir(exist_ok=True)
    (pkg_dir / "preview.html").write_text(pkg_html, encoding="utf-8")

    print("Built", sum(1 for _ in (ROOT / "assets").rglob("*.svg")), "SVGs + README.md + pkg/preview.html")


if __name__ == "__main__":
    build()
