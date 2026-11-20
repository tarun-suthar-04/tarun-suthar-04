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
import struct
import sys
import textwrap
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "profile.config.json").read_text(encoding="utf-8"))
USER = CFG["username"]
PROFILE_URL = f"https://github.com/{USER}"

HEAD = "'TeX Gyre Adventor','TeXGyreAdventor',system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
SERIF = "'Instrument Serif',Georgia,'Times New Roman',serif"
MONO = "'Geist Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


def _sfnt_to_woff(sfnt_bytes):
    sfnt_ver, num_tables = struct.unpack(">4sH", sfnt_bytes[:6])
    entries = []
    total_sfnt = 12 + 16 * num_tables
    for i in range(num_tables):
        off = 12 + i * 16
        tag, csum, offset, length = struct.unpack(">4sIII", sfnt_bytes[off : off + 16])
        raw = sfnt_bytes[offset : offset + length]
        comp = zlib.compress(raw, 9)
        use = comp if len(comp) < len(raw) else raw
        entries.append((tag, use, len(use), length, csum))
        total_sfnt += (length + 3) & ~3
    out_chunks = []
    dir_entries = []
    cur = 44 + 20 * num_tables
    for tag, use, comp_len, orig_len, csum in entries:
        pad = (4 - (comp_len % 4)) % 4
        dir_entries.append(struct.pack(">4sIIII", tag, cur, comp_len, orig_len, csum))
        out_chunks.append(use + b"\x00" * pad)
        cur += comp_len + pad
    header = struct.pack(
        ">4s4sIHHIHHIIIII",
        b"wOFF", sfnt_ver, cur, num_tables, 0, total_sfnt, 1, 0, 0, 0, 0, 0, 0,
    )
    return header + b"".join(dir_entries) + b"".join(out_chunks)


_FONT_CACHE = {}


def _load_font_b64(filename):
    if filename not in _FONT_CACHE:
        p = ROOT / "fonts" / filename
        raw = p.read_bytes()
        if p.suffix.lower() in (".ttf", ".otf"):
            raw = _sfnt_to_woff(raw)
        _FONT_CACHE[filename] = base64.b64encode(raw).decode()
    return _FONT_CACHE[filename]


_FONT_SPECS = {
    "a400": ("TeX Gyre Adventor", "normal", "400 500", "texgyreadventor-regular.otf"),
    "a400i": ("TeX Gyre Adventor", "italic", "400 500", "texgyreadventor-italic.otf"),
    "a700": ("TeX Gyre Adventor", "normal", "600 900", "texgyreadventor-bold.otf"),
    "a700i": ("TeX Gyre Adventor", "italic", "600 900", "texgyreadventor-bolditalic.otf"),
    "s400": ("Instrument Serif", "normal", "400 700", "serif-400.woff"),
    "s400i": ("Instrument Serif", "italic", "400 700", "serif-italic.woff"),
    "m400": ("Geist Mono", "normal", "400 700", "geistmono-400.woff"),
}


def font_style(*keys):
    rules = []
    for k in keys:
        fam, st, wt, fn = _FONT_SPECS[k]
        p = ROOT / "fonts" / fn
        if p.exists():
            raw_bytes = p.read_bytes()
            fam_clean = fam.replace(" ", "")
            if p.suffix.lower() == ".otf":
                b64_otf = base64.b64encode(raw_bytes).decode()
                b64_woff = _load_font_b64(fn)
                src = (
                    f"local('{fam}'), local('{fam_clean}'), "
                    f"url(data:font/otf;base64,{b64_otf}) format('opentype'), "
                    f"url(data:font/woff;base64,{b64_woff}) format('woff')"
                )
            else:
                b64 = _load_font_b64(fn)
                src = f"url(data:font/woff;base64,{b64}) format('woff')"

            # Generate rules for standard discrete weights so all browsers match correctly
            weights = wt.split() if isinstance(wt, str) and " " in wt else [wt]
            if any(x in weights for x in ("600", "700", "800", "900")) or wt in ("700", "800", "bold"):
                weights = ["600", "700", "800", "900", "bold"]
            elif any(x in weights for x in ("400", "500")) or wt in ("400", "normal"):
                weights = ["400", "500", "normal"]

            for w_val in weights:
                rules.append(
                    f"@font-face{{font-family:'{fam}';font-style:{st};font-weight:{w_val};src:{src};font-display:swap;}}"
                )
                if " " in fam:
                    rules.append(
                        f"@font-face{{font-family:'{fam_clean}';font-style:{st};font-weight:{w_val};src:{src};font-display:swap;}}"
                    )
    return f"<style>{''.join(rules)}</style>" if rules else ""

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
    heat=["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    heat_border="rgba(27,31,35,0.06)",
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
    heat=["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    heat_border="rgba(255,255,255,0.05)",
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


def T(x, y, s, size, fill, weight=400, fam=HEAD, ls=None, anchor="start", tl=None, style=None):
    if ls is None and fam == HEAD:
        ls = round(-0.028 * size, 2)
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


def H_fit(x, y, s, size, fill, maxw=None, weight=800, anchor="start", fam=HEAD, ls=-2.0):
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


def cubic_orb_defs(uid, w, h, t, cx, cy, r, stops, mask_cx, mask_cy, mask_rx, mask_ry, tile_size=36):
    stop_xml = "".join(
        f'<stop offset="{off}" stop-color="{col}" stop-opacity="{op}"/>'
        for off, col, op in stops
    )
    fade_r = max(float(mask_rx), float(mask_ry))
    return (
        cubic_pattern_defs(uid, t, size=tile_size)
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
            print("GraphQL fetch failed, trying public profile fallback:", e, file=sys.stderr)

    # Scrape GitHub public contributions endpoint (matches GitHub live calendar 1:1, no token needed)
    try:
        url = f"https://github.com/users/{USER}/contributions"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
        tds = re.findall(
            r'<td[^>]*id="(contribution-day-component-[^"]+)"[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d+)"',
            html,
        )
        if not tds:
            tds = re.findall(
                r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-[^"]+)"[^>]*data-level="(\d+)"',
                html,
            )
            tds = [(cid, d, lvl) for d, cid, lvl in tds]
        tooltips = dict(
            re.findall(
                r'<tool-tip[^>]*for="(contribution-day-component-[^"]+)"[^>]*>(.*?)</tool-tip>',
                html,
                re.DOTALL,
            )
        )
        days = {}
        for cid, d, lvl in tds:
            tip = tooltips.get(cid, "")
            count_match = re.search(r'(\d+)\s+contribution', tip)
            days[d] = int(count_match.group(1)) if count_match else 0
        if days:
            sorted_dates = sorted(days.keys())
            fetch_end = dt.date.fromisoformat(sorted_dates[-1])
            # Merge with local sample data if today has contributions not yet refreshed in public endpoint
            if (ROOT / "data" / "sample-contributions.json").exists():
                try:
                    s_data = json.loads((ROOT / "data" / "sample-contributions.json").read_text(encoding="utf-8"))
                    for k, v in s_data.get("days", {}).items():
                        if k not in days or v > days[k]:
                            days[k] = v
                    s_end = dt.date.fromisoformat(s_data.get("end", "2000-01-01"))
                    if s_end > fetch_end:
                        fetch_end = s_end
                except Exception:
                    pass
            print("Using live GitHub data via public contributions page")
            try:
                (ROOT / "data" / "sample-contributions.json").write_text(
                    json.dumps({"end": fetch_end.isoformat(), "days": days}, indent=1),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return fetch_end, days
    except Exception as e:
        print("Public profile endpoint unavailable, trying public API fallback:", e, file=sys.stderr)

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
def _media_dims(path):
    b = path.read_bytes()
    if path.suffix.lower() == ".gif" and len(b) >= 10:
        return struct.unpack("<HH", b[6:10])
    if path.suffix.lower() == ".png" and len(b) >= 24:
        return struct.unpack(">II", b[16:24])
    return (280, 239)


def hero(t, dark):
    w, h = 1000, 360
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=40, rx=24)

    # Embedded fonts + Vertical hairline editorial grid + cubic mesh gradient
    defs += font_style("a400", "a700", "m400") + (
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

    # 1. Kicker placed JUST ABOVE the Name
    b += f'<rect x="{px}" y="56" width="7" height="7" rx="2" fill="{t["green_bright"]}"/>'
    b += T(px + 14, 63.5, "AI-Assisted Developer", 12.5, t["secondary"], 700, MONO, ls=0.8)

    # 2. First Name: Tarun
    n1, n2 = CFG["name"]
    b += T(px, 134, n1, 68, t["text"], 700, HEAD, ls=-3.2)

    # 3. Last Name: Suthar with exact snug yellow highlight box
    pad_x = 14.0
    w_suthar = 188.0  # exact glyph advance in TeX Gyre Adventor bold at 68px (ls=-3.2)
    pw = w_suthar + 2 * pad_x  # 216.0px (exact equal 14px padding on both sides)
    b += f'<rect x="{px}" y="152" width="{pw:.1f}" height="78" rx="16" fill="url(#goldPill)"/>'
    b += T(px + pad_x, 212, n2, 68, INK, 700, HEAD, ls=-3.2)

    # 4. Tagline below (handle @tarun-suthar-04 completely removed)
    for i, ln in enumerate(wrap(CFG["tagline"], 44)[:2]):
        b += T(px, 268 + i * 23, ln, 15, t["secondary"], 400, HEAD, ls=-0.4)

    # 5. Right media frame: smaller aspect ratio
    p_gif = ROOT / "assets" / "hero.gif"
    p_png = ROOT / "assets" / "hero.png"
    p = p_gif if p_gif.exists() else p_png
    vid_w, vid_h = _media_dims(p) if p.exists() else (280, 239)
    ratio = vid_w / vid_h
    mw = 310.0
    pad_x_m = 12.0
    pad_y_m = pad_x_m / ratio
    vw = mw - 2 * pad_x_m
    vh = vw / ratio
    mh = vh + 2 * pad_y_m
    mx = pr - mw
    my = (h - mh) / 2
    b += f'<rect x="{mx:.1f}" y="{my:.1f}" width="{mw:.1f}" height="{mh:.1f}" rx="18" fill="#F3F1E7" stroke="{t["border_strong"]}" stroke-width="1.5"/>'
    if p.exists():
        mime = "image/gif" if p.suffix.lower() == ".gif" else "image/png"
        uri = base64.b64encode(p.read_bytes()).decode()
        b += (
            f'<image x="{mx+pad_x_m:.1f}" y="{my+pad_y_m:.1f}" width="{vw:.1f}" height="{vh:.1f}" '
            f'preserveAspectRatio="xMidYMid meet" href="data:{mime};base64,{uri}"/>'
        )
    b += br
    return svg(w, h, defs, b, "Tarun Suthar, AI-assisted developer. Building secure Java, Android, and Python applications.")


def heatmap(t, dark, end, days):
    w, h = 1000, 294
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    defs += font_style("a700", "s400i", "m400")
    b = bg
    b += (
        f'<text x="{px}" y="76" font-family="{HEAD}" font-size="38" font-weight="800" letter-spacing="-1.9" fill="{t["text"]}">'
        f'Building <tspan font-family="{SERIF}" font-style="italic" font-weight="600" font-size="42" letter-spacing="-0.4" fill="{t["green"]}">in public</tspan></text>'
    )

    start = end - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    gx, gy = 78, 110
    pitch, cs = 16.5, 12.5
    lvl = lambda c: 0 if c == 0 else 1 if c <= 2 else 2 if c <= 5 else 3 if c <= 7 else 4

    active = sum(1 for i in range(365) if days.get((end - dt.timedelta(days=i)).isoformat(), 0) > 0)
    total = sum(days.get((end - dt.timedelta(days=i)).isoformat(), 0) for i in range(365))

    b += (
        f'<text x="{pr}" y="76" text-anchor="end" font-family="{HEAD}" font-size="18" font-weight="700" letter-spacing="-0.5" fill="{t["secondary"]}">'
        f'{total} contributions <tspan font-family="{MONO}" font-size="14" font-weight="500" fill="{t["muted"]}">in the last year</tspan></text>'
    )

    # Weekday labels on the left (matching GitHub: Mon, Wed, Fri)
    weekdays = [(1, "Mon"), (3, "Wed"), (5, "Fri")]
    for r, name in weekdays:
        wy = gy + r * pitch + 9.5
        b += f'<text x="{px}" y="{wy:.1f}" font-family="{MONO}" font-size="10.5" font-weight="500" fill="{t["muted"]}">{name}</text>'

    # Month labels above columns (matching GitHub calendar headers)
    last_col = -5
    num_days = (end - start).days + 1
    num_cols = (num_days + 6) // 7
    for col in range(num_cols):
        first_d = start + dt.timedelta(days=col * 7)
        if (col == 0 or first_d.day <= 7) and (col - last_col >= 3):
            mx = gx + col * pitch
            m_name = first_d.strftime("%b")
            b += f'<text x="{mx:.1f}" y="98" font-family="{MONO}" font-size="11" font-weight="500" fill="{t["muted"]}">{m_name}</text>'
            last_col = col

    # Contribution grid
    for i in range(num_days):
        d = start + dt.timedelta(days=i)
        col, row = i // 7, i % 7
        l = lvl(days.get(d.isoformat(), 0))
        cx = gx + col * pitch
        cy = gy + row * pitch
        b += (
            f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cs}" height="{cs}" rx="2.5" '
            f'fill="{t["heat"][l]}" stroke="{t["heat_border"]}" stroke-width="1"/>'
        )

    # Footer
    fy = 256
    b += T(px, fy, f"Last 12 months · {active} active days ({total} contributions)", 12, t["muted"], 500, MONO)
    lx = pr - 160
    b += T(lx, fy, "Less", 12, t["muted"], 500, MONO)
    for i in range(5):
        b += (
            f'<rect x="{lx+34+i*17}" y="{fy-10.5}" width="12" height="12" rx="2.5" '
            f'fill="{t["heat"][i]}" stroke="{t["heat_border"]}" stroke-width="1"/>'
        )
    b += T(lx + 34 + 5 * 17 + 4, fy, "More", 12, t["muted"], 500, MONO)
    b += br
    return svg(w, h, defs, b, "GitHub contribution heatmap for the last 12 months, building in public.")


def stats_card(t, dark, S):
    w, h = 1000, 398
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    defs += font_style("a700", "m400") + (
        f'<linearGradient id="barPeak" x1="0%" y1="0%" x2="0%" y2="100%">'
        f'<stop offset="0%" stop-color="#EF4444"/><stop offset="100%" stop-color="#B91C1C"/>'
        f"</linearGradient>"
        f'<linearGradient id="barCur" x1="0%" y1="0%" x2="0%" y2="100%">'
        f'<stop offset="0%" stop-color="#10B981"/><stop offset="100%" stop-color="#047857"/>'
        f"</linearGradient>"
    )
    b = bg
    b += T(px, 110, str(S["total"]), 78, t["text"], 800, HEAD, ls=-4.6)
    b += T(px, 142, "contributions across repositories", 16, t["secondary"], 600, HEAD, ls=-0.45)

    # Monthly bars
    mt, names = S["mt"], S["names"]
    mx = max(mt) or 1
    top1 = sorted(range(12), key=lambda i: -mt[i])[0]
    base, maxh, pitch, bw = 338, 136, 44.5, 34
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
        b += T(bx + bw / 2, 362, names[i], 11.5, t["muted"], 500, MONO, anchor="middle")

    # Right KPI column
    div_x = 612
    b += f'<line x1="{div_x}" y1="42" x2="{div_x}" y2="{h-42}" stroke="{t["border"]}" stroke-width="1.2"/>'
    rx = 644

    def kpi_block(y, num, unit, cap):
        unit_span = (
            f'<tspan dx="8" font-size="16" font-weight="600" letter-spacing="-0.4" fill="{t["secondary"]}">{esc(unit)}</tspan>'
            if unit else ""
        )
        out = (
            f'<text x="{rx:.1f}" y="{y:.1f}" font-family="{HEAD}" font-size="38" font-weight="800" '
            f'letter-spacing="-2.1" fill="{t["text"]}">{esc(num)}{unit_span}</text>'
        )
        out += T(rx, y + 26, cap, 12.5, t["muted"], 400, MONO)
        return out

    b += kpi_block(82, str(S["cur"]), "days", f'current streak · longest {S["longest"]} days')
    b += f'<line x1="{rx}" y1="140" x2="{pr}" y2="140" stroke="{t["border"]}" stroke-width="1.2"/>'
    b += kpi_block(200, str(S["active"]), "/ 365", "days with a commit")
    b += f'<line x1="{rx}" y1="258" x2="{pr}" y2="258" stroke="{t["border"]}" stroke-width="1.2"/>'
    b += kpi_block(318, str(S["busiest"]), "", "commits on the busiest day")
    b += br
    return svg(
        w,
        h,
        defs,
        b,
        f'{S["total"]} contributions in the last 12 months, current streak {S["cur"]} days, longest {S["longest"]}, {S["active"]} of 365 days with a commit, busiest day {S["busiest"]}.',
    )


def tile(kind, t, dark):
    w, h = 333.33, 240
    c = CFG["tiles"][kind]
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=26, ix=7, iy=8, rx=24)

    orb_stops = {
        "build": [("0%", "#BEF264", "0.95"), ("38%", "#10B981", "0.78"), ("72%", "#047857", "0.52"), ("100%", "#047857", "0")],
        "solve": [("0%", "#FDE047", "0.92"), ("34%", "#FB7185", "0.76"), ("70%", "#DC2626", "0.52"), ("100%", "#DC2626", "0")],
        "create": [("0%", "#FEF08A", "0.95"), ("40%", "#FBBF24", "0.80"), ("74%", "#EA580C", "0.54"), ("100%", "#EA580C", "0")],
    }[kind]
    defs += font_style("a400", "a700", "m400") + cubic_orb_defs(kind, w, h, t, "50%", "96%", "62%", orb_stops, "166", "225", "185", "130")

    b = bg
    b += cubic_orb_layer(kind, ix, iy, cw, ch, opacity=0.90 if not dark else 0.78)

    # Top row: uppercase mono label + rounded arrow badge
    b += T(px, 56, kind.upper(), 12, t["muted"], 600, MONO, ls=1.6)
    b += f'<rect x="{pr-30}" y="36" width="30" height="30" rx="10" fill="{t["subtle"]}" stroke="{t["border"]}" stroke-width="1"/>'
    b += arrow_ne(pr - 19.5, 46.5, 9, t["text"], sw=1.8)

    # Metric + text
    if kind == "create":
        b += H_fit(px, 114, c["big"], 38, t["text"], maxw=pr - px, weight=800, ls=-2.1)
        dy = 148
    else:
        unit_span = (
            f'<tspan dx="8" font-size="16" font-weight="600" letter-spacing="-0.4" fill="{t["secondary"]}">{esc(c["unit"])}</tspan>'
            if c.get("unit") else ""
        )
        b += (
            f'<text x="{px:.1f}" y="114.0" font-family="{HEAD}" font-size="38" font-weight="800" '
            f'letter-spacing="-2.1" fill="{t["text"]}">{esc(c["big"])}{unit_span}</text>'
        )
        dy = 148

    for i, ln in enumerate(wrap(c["text"], 27)[:3]):
        b += T(px, dy + i * 22, ln, 14, t["secondary"], 400, HEAD)

    b += br
    u = c.get("unit", "")
    title_str = f'{kind.capitalize()}: {c["big"]} {u}'.replace("  ", " ").strip() + f'. {c["text"]}'
    return svg(w, h, defs, b, title_str)


def tech(t, dark):
    w, h = 1000, 344
    L = CFG["learning"]
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)
    stops = [("0%", "#FBBF24", "0.44"), ("65%", "#F59E0B", "0.18"), ("100%", "#F59E0B", "0")]
    defs += font_style("a700", "m400") + cubic_orb_defs("learn", w, h, t, "92%", "90%", "58%", stops, "890", "292", "340", "195")

    b = bg
    b += cubic_orb_layer("learn", ix, iy, cw, ch, opacity=0.88 if not dark else 0.72)
    b += T(px, 78, "Tech I use", 34, t["text"], 800, HEAD, ls=-1.7)

    gap = 10
    cols = 4
    cell_w = (pr - px - gap * (cols - 1)) / cols
    cell_h = 50
    for idx, s in enumerate(CFG["stack"]):
        r, c = divmod(idx, cols)
        cx = px + c * (cell_w + gap)
        cy = 104 + r * (cell_h + gap)
        b += f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cell_w:.1f}" height="{cell_h}" rx="14" fill="{t["subtle"]}" stroke="{t["border"]}" stroke-width="1"/>'
        b += T(cx + cell_w / 2, cy + 30, s, 14.5, t["text"], 600, HEAD, anchor="middle")

    # Divider separating Tech I use and Currently learning strip
    b += f'<line x1="{px}" y1="236" x2="{pr}" y2="236" stroke="{t["border"]}" stroke-width="1"/>'

    # Bottom strip: Currently learning heading on left, 3 balanced frosted chips on right
    b += H_fit(px, 286, L["title"], 23, t["text"], maxw=416, weight=700, ls=-0.95)

    chips = L["chips"][:3]
    chip_x0 = 514.0
    chip_gap = 10.0
    avail = pr - chip_x0 - chip_gap * (len(chips) - 1)
    raw_w = [max(76.0, est(ch, 12.0, 0.62) + 34.0) for ch in chips]
    scale = avail / max(1.0, sum(raw_w))
    cx = chip_x0
    cy = 256.0
    for idx, chip in enumerate(chips):
        tw = raw_w[idx] * scale
        b += f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{tw:.1f}" height="44" rx="12" fill="{t["tile"]}" stroke="{t["border"]}" stroke-width="1"/>'
        b += T(cx + tw / 2, cy + 26.5, chip, 12.0, t["text"], 600, MONO, anchor="middle")
        cx += tw + chip_gap

    b += br
    return svg(w, h, defs, b, "Tech I use: " + ", ".join(CFG["stack"]) + ". Currently learning: " + ", ".join(L["chips"]) + ".")


def how(t, dark):
    w, h = 1000, 192
    steps = CFG["workflow"]
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=36, rx=24)

    accents = {
        "amber": {
            "col": "#D97706" if not dark else "#FBBF24",
            "tint": "rgba(217,119,6,0.12)" if not dark else "rgba(251,191,36,0.15)",
            "ring": "rgba(217,119,6,0.28)" if not dark else "rgba(251,191,36,0.30)",
        },
        "cobalt": {
            "col": "#0284C7" if not dark else "#38BDF8",
            "tint": "rgba(2,132,199,0.12)" if not dark else "rgba(56,189,248,0.15)",
            "ring": "rgba(2,132,199,0.28)" if not dark else "rgba(56,189,248,0.30)",
        },
        "green": {
            "col": "#16A34A" if not dark else "#34D399",
            "tint": "rgba(22,163,74,0.12)" if not dark else "rgba(52,211,153,0.15)",
            "ring": "rgba(22,163,74,0.28)" if not dark else "rgba(52,211,153,0.30)",
        },
        "violet": {
            "col": "#7C3AED" if not dark else "#A78BFA",
            "tint": "rgba(124,58,237,0.12)" if not dark else "rgba(167,139,250,0.15)",
            "ring": "rgba(124,58,237,0.28)" if not dark else "rgba(167,139,250,0.30)",
        },
    }

    wf_css = """
    <style>
      .wf-flow { animation: wfFlow 1.2s linear infinite; }
      .wf-live { animation: wfPulse 2s ease-in-out infinite; }
      .wf-node-on { opacity: 0; animation: wfActive 8s ease-in-out infinite; }
      @keyframes wfFlow { to { stroke-dashoffset: -12; } }
      @keyframes wfPulse { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
      @keyframes wfActive {
        0%, 100% { opacity: 0; }
        5%, 22%  { opacity: 1; }
        30%      { opacity: 0; }
      }
      @media (prefers-reduced-motion: reduce) {
        .wf-flow, .wf-live, .wf-node-on { animation: none !important; }
        .wf-node-on { opacity: 0.6; }
      }
    </style>
    """

    stops = [
        ("0%", "#10B981", "0.18" if not dark else "0.15"),
        ("50%", "#0284C7" if not dark else "#38BDF8", "0.10"),
        ("100%", "#7C3AED" if not dark else "#A78BFA", "0"),
    ]
    defs += (
        font_style("a700", "m400")
        + cubic_orb_defs("wf", w, h, t, "92%", "16%", "52%", stops, "900", "50", "300", "130")
        + wf_css
    )

    b = bg
    b += cubic_orb_layer("wf", ix, iy, cw, ch, opacity=0.76 if not dark else 0.62)

    # Centered Header: live pulsing dot + 'MY WORKFLOW'
    b += f'<rect class="wf-live" x="440.5" y="21" width="7" height="7" rx="2" fill="{t["green_bright"]}"/>'
    b += T(455.5, 28, "MY WORKFLOW", 11, t["muted"], 700, MONO, ls=1.5)

    col_w = 214.0
    gap = 24.0
    node_cx = [px + i * (col_w + gap) + col_w / 2.0 for i in range(4)]
    cy = 74.0

    # 4 Node Icons (enlarged for prominent visual presence)
    def render_icon(idx, cx, cy, col):
        if idx == 0:  # 01 IDEATE: spark/idea bulb
            return (
                f'<g transform="translate({cx:.1f} {cy:.1f})" fill="none" stroke="{col}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
                f'<circle cx="0" cy="-2.5" r="6"/>'
                f'<path d="M -3 7.5 h 6 M -1.8 11 h 3.6 M -10.5 -2.5 h -2.2 M 10.5 -2.5 h 2.2 M -7.5 -10 l -1.6 -1.6 M 7.5 -10 l 1.6 -1.6"/>'
                f'</g>'
            )
        if idx == 1:  # 02 PLAN: blueprint specs tree
            return (
                f'<g transform="translate({cx:.1f} {cy:.1f})" fill="none" stroke="{col}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
                f'<path d="M -8 -6 h 12 M -8 0 h 16 M -8 6 h 9"/>'
                f'<circle cx="9" cy="6" r="1.8" fill="{col}" stroke="none"/>'
                f'</g>'
            )
        if idx == 2:  # 03 BUILD: code brackets < / >
            return (
                f'<g transform="translate({cx:.1f} {cy:.1f})" fill="none" stroke="{col}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
                f'<path d="M -5.5 -6.5 l -6.5 6.5 6.5 6.5 M 5.5 -6.5 l 6.5 6.5 -6.5 6.5 M 2 -9.5 l -4 19"/>'
                f'</g>'
            )
        # 04 REFINE: loop cycle
        return (
            f'<g transform="translate({cx:.1f} {cy:.1f})" fill="none" stroke="{col}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M 8 -2.5 a 8 8 0 1 0 1 5.2"/>'
            f'<path d="M 8.5 -10 v 7.5 h -7.5"/>'
            f'</g>'
        )

    for idx, st in enumerate(steps):
        cx = node_cx[idx]
        ac = accents[st["color"]]
        col = ac["col"]
        tint = ac["tint"]
        ring = ac["ring"]
        delay = idx * 2.0

        # Connecting flow line to next node
        if idx < 3:
            next_cx = node_cx[idx + 1]
            x1 = cx + 24.0 + 10.0
            x2 = next_cx - 24.0 - 10.0
            mx = (x1 + x2) / 2.0
            b += f'<line x1="{x1:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{cy:.1f}" stroke="{t["border_strong"]}" stroke-width="1.3" stroke-linecap="round"/>'
            b += f'<line class="wf-flow" x1="{x1:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{cy:.1f}" stroke="{col}" stroke-width="2" stroke-linecap="round" stroke-dasharray="6 6"/>'
            b += f'<path d="M {mx-4:.1f} {cy-5:.1f} L {mx+2:.1f} {cy:.1f} L {mx-4:.1f} {cy+5:.1f}" fill="none" stroke="{t["muted"]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'

        # Node Icon Box (48x48, rx=14)
        box_x = cx - 24.0
        box_y = cy - 24.0
        b += f'<rect x="{box_x:.1f}" y="{box_y:.1f}" width="48" height="48" rx="14" fill="{t["subtle"]}" stroke="{t["border_strong"]}" stroke-width="1.2"/>'
        # Animated active glow pulse
        b += (
            f'<g class="wf-node-on" style="animation-delay:{delay:.1f}s">'
            f'<rect x="{box_x-3:.1f}" y="{box_y-3:.1f}" width="54" height="54" rx="17" fill="none" stroke="{ring}" stroke-width="1.5"/>'
            f'<rect x="{box_x:.1f}" y="{box_y:.1f}" width="48" height="48" rx="14" fill="{tint}" stroke="{col}" stroke-width="1.6"/>'
            f'</g>'
        )
        b += render_icon(idx, cx, cy, col)

        # Centered Step Label: Dot + Title
        title_text = f'{st["num"]} — {st["title"]}'
        est_title_w = len(title_text) * 7.2 + 12.0
        dot_x = cx - est_title_w / 2.0
        text_x = dot_x + 12.0
        b += f'<rect x="{dot_x:.1f}" y="117.5" width="6" height="6" rx="1.8" fill="{col}"/>'
        b += T(text_x, 124, title_text, 12, t["text"], 700, MONO, ls=0.6)

        # Centered Tools Chips below
        tools = st.get("tools", [])
        if not tools and st["num"] == "04":
            tools = ["Codex", "Antigravity"]
        if tools:
            chip_widths = [est(tl, 11, 0.60) + 20.0 for tl in tools]
            chip_gap = 6.0
            tot_w = sum(chip_widths) + chip_gap * (len(tools) - 1)
            cur_x = cx - tot_w / 2.0
            for tl_idx, tl in enumerate(tools):
                cw_val = chip_widths[tl_idx]
                b += f'<rect x="{cur_x:.1f}" y="140" width="{cw_val:.1f}" height="26" rx="8" fill="{t["subtle"]}" stroke="{t["border_strong"]}" stroke-width="1"/>'
                b += T(cur_x + cw_val / 2.0, 156.5, tl, 11, t["text"], 600, MONO, anchor="middle")
                cur_x += cw_val + chip_gap

    b += br
    return svg(
        w,
        h,
        defs,
        b,
        "My Workflow: 01 Ideate (ChatGPT, Claude), 02 Plan (ChatGPT, Claude), 03 Build (Codex, Antigravity), 04 Refine (Codex, Antigravity).",
    )


def coding_label(t, dark):
    w, h = 1000, 44
    defs = font_style("a700", "m400")
    b = kicker(14, 28, "What I Built", t["muted"], t["red"], size=12)
    b += T(w - 30, 28, "All Repositories", 13.5, t["secondary"], 600, HEAD, anchor="end")
    b += arrow_ne(w - 22, 18.5, 9, t["secondary"], sw=1.8)
    return svg(w, h, defs, b, "What I Built")


def project(p, t, dark):
    w, h = 333.33, 204
    defs, bg, br, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=24, ix=7, iy=8, rx=24)

    palette = {
        "green": (t["green_bright"], "Java · Security", [("0%", "#10B981", "0.62"), ("55%", "#059669", "0.26"), ("100%", "#059669", "0")]),
        "red": (t["red"], "Android · Sync", [("0%", "#EF4444", "0.58"), ("55%", "#DC2626", "0.24"), ("100%", "#DC2626", "0")]),
        "yellow": (t["amber"], "Python · MySQL", [("0%", "#FBBF24", "0.62"), ("55%", "#F59E0B", "0.25"), ("100%", "#F59E0B", "0")]),
    }
    dot_col, sub_tag, stops = palette.get(p["color"], palette["green"])
    defs += font_style("a400", "a700", "m400") + cubic_orb_defs(p["slug"], w, h, t, "88%", "74%", "58%", stops, "280", "150", "165", "120")

    b = bg
    b += cubic_orb_layer(p["slug"], ix, iy, cw, ch, opacity=0.84 if not dark else 0.72)

    # Unboxed metadata line
    b += kicker(px, 50, f'{p["tag"]} · {sub_tag}', t["muted"], dot_col, size=10.5)

    # Title (camelCase split cleanly)
    spaced_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", p["name"])
    title_lines = wrap(spaced_name, 19)
    if len(title_lines) == 1:
        b += H_fit(px, 86, title_lines[0], 20.5, t["text"], maxw=pr - px, weight=700, ls=-0.8)
        dy = 114
    else:
        b += H_fit(px, 84, title_lines[0], 20.5, t["text"], maxw=pr - px, weight=700, ls=-0.8)
        b += H_fit(px, 108, title_lines[1], 20.5, t["text"], maxw=pr - px, weight=700, ls=-0.8)
        dy = 136

    for i, ln in enumerate(wrap(p["desc"], 27)[:3]):
        b += T(px, dy + i * 21, ln, 13.5, t["secondary"], 400, HEAD, ls=-0.35)

    # Arrow badge only (README text removed per user request)
    b += f'<rect x="{pr-28}" y="{h-44}" width="28" height="28" rx="9" fill="{t["subtle"]}" stroke="{t["border"]}" stroke-width="1"/>'
    b += arrow_ne(pr - 18.5, h - 34.5, 8.5, t["text"], sw=1.8)
    b += br
    return svg(w, h, defs, b, f'{p["name"]}: {p["desc"]} ({p["tag"]}). Opens the repository.')


CONTACT_THEMES = {
    "portfolio": dict(
        stops=[("0%", "#FEF08A", "0.90"), ("42%", "#FBBF24", "0.68"), ("80%", "#F59E0B", "0.30"), ("100%", "#F59E0B", "0")],
        dot_light="#D97706", dot_dark="#FBBF24",
        border_light="rgba(245,158,11,0.42)", border_dark="rgba(251,191,36,0.36)",
    ),
    "linkedin": dict(
        stops=[("0%", "#93C5FD", "0.88"), ("42%", "#0A66C2", "0.66"), ("82%", "#1D4ED8", "0.28"), ("100%", "#1D4ED8", "0")],
        dot_light="#0A66C2", dot_dark="#38BDF8",
        border_light="rgba(10,102,194,0.32)", border_dark="rgba(56,189,248,0.32)",
    ),
    "fiverr": dict(
        stops=[("0%", "#A7F3D0", "0.88"), ("42%", "#1DBF73", "0.66"), ("82%", "#059669", "0.28"), ("100%", "#059669", "0")],
        dot_light="#15803D", dot_dark="#34D399",
        border_light="rgba(29,191,115,0.32)", border_dark="rgba(52,211,153,0.32)",
    ),
    "hackerrank": dict(
        stops=[("0%", "#86EFAC", "0.90"), ("42%", "#00EA64", "0.66"), ("82%", "#16A34A", "0.28"), ("100%", "#16A34A", "0")],
        dot_light="#16A34A", dot_dark="#00EA64",
        border_light="rgba(22,163,74,0.34)", border_dark="rgba(0,234,100,0.34)",
    ),
    "leetcode": dict(
        stops=[("0%", "#FED7AA", "0.90"), ("42%", "#FFA116", "0.68"), ("82%", "#EA580C", "0.28"), ("100%", "#EA580C", "0")],
        dot_light="#EA580C", dot_dark="#FFA116",
        border_light="rgba(234,88,12,0.32)", border_dark="rgba(255,161,22,0.32)",
    ),
}


def contact_btn(key, name, filled, yellow, t, dark):
    w, h = 250, 64
    defs, bg, _, ix, iy, cw, ch, px, pr = card_shell(w, h, t, pad=18, ix=6, iy=6, rx=16)
    ct = CONTACT_THEMES.get(key, CONTACT_THEMES["linkedin"])
    border_col = ct["border_dark"] if dark else ct["border_light"]
    dot_col = ct["dot_dark"] if dark else ct["dot_light"]

    defs += font_style("a700", "m400") + cubic_orb_defs(
        f"c-{key}", w, h, t, "84%", "86%", "78%", ct["stops"], "206", "54", "185", "54", tile_size=20
    )

    orb_op = (0.86 if not dark else 0.72) if filled else (0.64 if not dark else 0.52)
    b = bg
    b += cubic_orb_layer(f"c-{key}", ix, iy, cw, ch, opacity=orb_op)
    b += f'<rect x="{ix}" y="{iy}" width="{cw:g}" height="{ch:g}" rx="16" fill="none" stroke="{border_col}" stroke-width="1.5"/>'

    text_op = "1" if filled else "0.78"
    mid_y = h / 2.0
    b += f'<g opacity="{text_op}">'
    b += f'<rect x="{px}" y="{mid_y - 4:.1f}" width="8" height="8" rx="2.5" fill="{dot_col}"/>'
    b += T(px + 15, mid_y + 4.5, name, 13.5, t["text"], 700, HEAD)
    if filled:
        b += arrow_ne(pr - 10, mid_y - 4.5, 9, t["text"], sw=2)
    else:
        b += T(pr - 4, mid_y + 4.5, "·", 14, t["muted"], 700, MONO, anchor="end")
    b += "</g>"
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
    add("tech", lambda t, d: tech(t, d))
    add("how-i-work", lambda t, d: how(t, d))
    add("coding-label", lambda t, d: coding_label(t, d))
    for p in CFG["projects"]:
        add(f"project-{p['slug']}", lambda t, d, p=p: project(p, t, d))
    btns = [
        ("linkedin", "LinkedIn", href(L.get("linkedin")), False),
        ("fiverr", "Fiverr", href(L.get("fiverr")), False),
        ("hackerrank", "HackerRank", href(L.get("hackerrank")), False),
        ("leetcode", "LeetCode", href(L.get("leetcode")), False),
    ]
    for key, nm, url, yel in btns:
        add(f"contact-{key}", lambda t, d, key=key, nm=nm, url=url, yel=yel: contact_btn(key, nm, bool(url), yel, t, d))

    repos = f"{PROFILE_URL}?tab=repositories"
    rows = [
        [("hero", 100, L["portfolio"], "Tarun Suthar, AI-assisted developer building secure Java, Android and Python applications")],
        [("heatmap", 100, PROFILE_URL, "Contribution heatmap, building in public")],
        [("stats", 100, PROFILE_URL, f"{S['total']} contributions in the last 12 months with streak and activity stats")],
        [
            ("tile-build", 33.3, repos, "Build: 3 apps"),
            ("tile-solve", 33.3, href(L.get("leetcode")) or PROFILE_URL, "Solve: 120+ LeetCode problems"),
            ("tile-create", 33.3, L["portfolio"], "Create: AI visual design and digital storytelling"),
        ],
        [("tech", 100, None, "Tech I use: " + ", ".join(CFG["stack"]) + ". Currently learning: " + ", ".join(CFG["learning"]["chips"]))],
        [("how-i-work", 100, None, "My Workflow: 01 Ideate, 02 Plan, 03 Build, 04 Refine")],
        [("coding-label", 100, repos, "What I Built")],
        [(f"project-{p['slug']}", 33.3, p["repo"] or repos, f"{p['name']}: {p['desc']}") for p in CFG["projects"]],
        [(f"contact-{k}", 25, (u or PROFILE_URL), f"{nm} link") for k, nm, u, _ in btns],
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

    # Generate preview.html (at root and pkg/preview.html) so SVG README can be previewed directly
    def render_cards(cls, prefix=""):
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

    def render_adaptive(prefix=""):
        return "".join("<div>" + "".join(pic(prefix, *c) for c in r) + "</div>" for r in rows)

    def generate_preview_page(prefix=""):
        light_b = render_cards("light", prefix=prefix)
        dark_b = render_cards("dark", prefix=prefix)
        adaptive_b = render_adaptive(prefix=prefix)
        label_light = f"Light Mode ({prefix}assets/light/*.svg)"
        label_dark = f"Dark Mode ({prefix}assets/dark/*.svg)"

        return f"""<!doctype html>
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
      <div class="shell-header"><span id="shell-label">{label_light}</span><span>GitHub README View</span></div>
      <div id="content-single">{light_b}</div>
    </div>
  </div>
  <div id="view-split" class="split-layout" style="display: none;">
    <div class="card-shell shell-light"><div class="shell-header"><span>Light Mode</span><span>{prefix}assets/light/*.svg</span></div><div>{light_b}</div></div>
    <div class="card-shell shell-dark"><div class="shell-header"><span>Dark Mode</span><span>{prefix}assets/dark/*.svg</span></div><div>{dark_b}</div></div>
  </div>
  <script>
    const bodies = {{ light: {json.dumps(light_b)}, dark: {json.dumps(dark_b)}, adaptive: {json.dumps(adaptive_b)} }};
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
          label.textContent = '{label_light}';
        }} else if (mode === 'dark') {{
          document.body.style.background = '#010409';
          shell.className = 'card-shell shell-dark';
          label.textContent = '{label_dark}';
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

    (ROOT / "preview.html").write_text(generate_preview_page(prefix=""), encoding="utf-8")
    pkg_dir = ROOT / "pkg"
    pkg_dir.mkdir(exist_ok=True)
    (pkg_dir / "preview.html").write_text(generate_preview_page(prefix="../"), encoding="utf-8")

    print("Built", sum(1 for _ in (ROOT / "assets").rglob("*.svg")), "SVGs + README.md + preview.html + pkg/preview.html")


if __name__ == "__main__":
    build()
