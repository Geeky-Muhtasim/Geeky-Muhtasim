"""
The arena card: live GitHub numbers for the profile README, drawn as an SVG
in the same theme as the other cards. Run daily by .github/workflows/arena.yml.

Standard library only. Reads public data through the GitHub GraphQL API with
the workflow's GITHUB_TOKEN:
  - contributions over the last year, the current and longest daily streaks
  - public repositories and stars on repositories the user owns
  - the top languages across owned, non-fork repositories, by bytes of code

Usage: python scripts/arena.py <out.svg>
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = os.environ.get("ARENA_USER", "Geeky-Muhtasim")
HERE = Path(__file__).resolve().parent

BG, PANEL, LINE, SCAN = "#0f2420", "#123026", "#1e3b36", "#163a2e"
CREAM, PHOSPHOR, GOLD, SIGNAL, MOSS, SOFT = "#f1e7cf", "#7fe0a0", "#e9b872", "#ec6c5e", "#4f7f64", "#9dbfac"
LANG_COLORS = [PHOSPHOR, GOLD, SIGNAL, CREAM, "#5fb3a1", "#c9875a"]
W, H = 1000, 250
CW = 0.6

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes {
        isFork
        stargazerCount
        languages(first: 10, orderBy: { field: SIZE, direction: DESC }) { edges { size node { name } } }
      }
    }
  }
}
"""


def fetch() -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GraphQL errors: {body['errors']}")
    return body["data"]["user"]


def streaks(days: list[dict]) -> tuple[int, int]:
    """Current streak (today may still be empty) and longest streak, in days."""
    counts = [d["contributionCount"] for d in sorted(days, key=lambda d: d["date"])]
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1  # today is not over yet
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    return current, longest


def languages(repos: list[dict]) -> list[tuple[str, float]]:
    total: dict[str, int] = {}
    for r in repos:
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            total[e["node"]["name"]] = total.get(e["node"]["name"], 0) + e["size"]
    s = sum(total.values()) or 1
    top = sorted(total.items(), key=lambda kv: -kv[1])[:6]
    return [(name, size / s) for name, size in top]


def font(name: str, family: str) -> str:
    data = base64.b64encode((HERE / "fonts" / name).read_bytes()).decode()
    return f"@font-face{{font-family:{family};src:url(data:font/woff2;base64,{data}) format('woff2');}}"


def text(x, y, s, fam="PM", size=14, fill=CREAM, anchor="start", ls=0, opacity=1.0) -> str:
    a = f'x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{fill}"'
    if anchor != "start":
        a += f' text-anchor="{anchor}"'
    if ls:
        a += f' letter-spacing="{ls}"'
    if opacity != 1:
        a += f' opacity="{opacity}"'
    return f"<text {a}>{escape(s)}</text>"


def render(u: dict) -> str:
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    current, longest = streaks(days)
    repos = u["repositories"]
    stars = sum(r["stargazerCount"] for r in repos["nodes"] if not r["isFork"])
    langs = languages(repos["nodes"])
    today = dt.date.today().isoformat()

    p = [
        f'<defs><pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{SCAN}"/></pattern>'
        f'<clipPath id="panel"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>'
        f'<clipPath id="bar"><rect x="40" y="196" width="{W - 80}" height="14" rx="7"/></clipPath></defs>',
        f'<g clip-path="url(#panel)"><rect width="{W}" height="{H}" fill="{BG}"/><rect width="{W}" height="{H}" fill="url(#scan)" opacity="0.55"/></g>',
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="{LINE}" stroke-width="2"/>',
        text(40, 44, "ARENA", "PMM", 13, SIGNAL, ls=3),
        text(W - 40, 44, f"LIVE FROM GITHUB · UPDATED {today}", "PM", 12, MOSS, anchor="end", ls=1.5),
        f'<line x1="40" y1="60" x2="{W - 40}" y2="60" stroke="{LINE}" stroke-width="1.5"/>',
    ]
    tiles = [
        ("CONTRIBUTIONS, 1Y", f"{cal['totalContributions']:,}", ""),
        ("CURRENT STREAK", str(current), "days"),
        ("LONGEST STREAK", str(longest), "days"),
        ("PUBLIC REPOS", str(repos["totalCount"]), ""),
        ("STARS EARNED", str(stars), ""),
    ]
    tw, gap = (W - 80 - 4 * 12) / 5, 12
    for i, (label, value, unit) in enumerate(tiles):
        x = 40 + i * (tw + gap)
        p.append(f'<rect x="{x:.1f}" y="76" width="{tw:.1f}" height="88" rx="8" fill="{PANEL}" stroke="{LINE}" stroke-width="1.5"/>')
        p.append(text(round(x + 14), 100, label, "PMM", 10.5, SOFT, ls=1.2))
        p.append(text(round(x + 14), 144, value, "PMM", 34, GOLD))
        if unit:
            p.append(text(round(x + 20 + len(value) * 34 * CW), 144, unit, "PM", 13, CREAM, opacity=0.7))
    # Languages: one bar split by share, with a legend beneath.
    x = 40.0
    p.append(f'<g clip-path="url(#bar)"><rect x="40" y="196" width="{W - 80}" height="14" fill="{PANEL}"/>')
    for k, (name, share) in enumerate(langs):
        w = (W - 80) * share
        p.append(f'<rect x="{x:.1f}" y="196" width="{w:.1f}" height="14" fill="{LANG_COLORS[k % len(LANG_COLORS)]}"/>')
        x += w
    p.append("</g>")
    p.append(text(40, 186, "TOP LANGUAGES", "PMM", 10.5, SOFT, ls=2))
    lx = 40.0
    for k, (name, share) in enumerate(langs):
        color = LANG_COLORS[k % len(LANG_COLORS)]
        label = f"{name} {share * 100:.1f}%"
        p.append(f'<rect x="{lx:.1f}" y="222" width="10" height="10" rx="2" fill="{color}"/>')
        p.append(text(round(lx + 16), 231, label, "PM", 12, CREAM))
        lx += 16 + len(label) * 12 * CW + 22

    style = f"<style>{font('plex-mono-400.woff2', 'PM')}{font('plex-mono-500.woff2', 'PMM')}</style>"
    title = f"GitHub arena: {cal['totalContributions']} contributions in the last year, current streak {current} days"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title>{style}{''.join(p)}</svg>"
    )


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "arena.svg")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(fetch()), encoding="utf8")
    print("wrote", out)
