#!/usr/bin/env python3
"""Render the profile's CRT terminal panels (Fallout-style termlink) as SVGs.

Text lives in the constants below; GitHub numbers are fetched live.
Run locally:   GITHUB_TOKEN=$(gh auth token) python3 scripts/build.py
In CI:         .github/workflows/update-profile.yml runs it daily.
"""

import base64
import json
import os
import textwrap
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

LOGIN = 'jusiann'
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets'
FONT_B64 = base64.b64encode((OUT / 'fonts' / 'vt323-subset.woff2').read_bytes()).decode()

GREEN = '#7ddc9c'
DIM = '#3f8f5d'
FAINT = '#173524'
SCREEN = '#0c1c13'
EDGE = '#050c08'
BEZEL = '#111611'

PERSONNEL = [
    ('ROLE', 'SOFTWARE DEVELOPER · WEB, MOBILE & AI'),
    ('EDUCATION', 'COMPUTER ENGINEERING'),
    ('', 'ISTANBUL RUMELI UNIV. [FINAL YEAR]'),
    ('LOCATION', 'ISTANBUL, TÜRKİYE'),
    ('STACK', 'REACT · REACT NATIVE · NODE.JS'),
    ('', 'POSTGRESQL'),
    ('LEARNING', 'SWIFTUI · LANGGRAPH'),
]
DIRECTIVE = '"THE MODEL READS NUMBERS, NEVER MAKES THEM."'

BUTTONS = [('portfolio', 'PORTFOLIO'), ('linkedin', 'LINKEDIN'), ('mail', 'MAIL')]

MONOGRAM = [
    '.###..#####',
    '#...#.#....',
    '#...#.#....',
    '#####.####.',
    '#...#.#....',
    '#...#.#....',
    '#...#.#####',
]


def graphql(query, variables, token):
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps({'query': query, 'variables': variables}).encode(),
        headers={'Authorization': f'bearer {token}', 'User-Agent': LOGIN},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if 'errors' in body:
        raise RuntimeError(body['errors'])
    return body['data']


def fetch_stats(token):
    data = graphql('''
        query($login: String!) {
          user(login: $login) {
            createdAt
            followers { totalCount }
            contributionsCollection { contributionCalendar { totalContributions } }
            repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
              totalCount
              nodes {
                stargazerCount
                languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                  edges { size node { name } }
                }
              }
            }
          }
        }''', {'login': LOGIN}, token)['user']

    langs = {}
    for repo in data['repositories']['nodes']:
        for edge in repo['languages']['edges']:
            langs[edge['node']['name']] = langs.get(edge['node']['name'], 0) + edge['size']

    commits = 0
    start = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00')).year
    for year in range(start, datetime.now(timezone.utc).year + 1):
        c = graphql('''
            query($login: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                  totalCommitContributions restrictedContributionsCount
                }
              }
            }''', {'login': LOGIN, 'from': f'{year}-01-01T00:00:00Z', 'to': f'{year}-12-31T23:59:59Z'},
            token)['user']['contributionsCollection']
        commits += c['totalCommitContributions'] + c['restrictedContributionsCount']

    return {
        'repos': data['repositories']['totalCount'],
        'stars': sum(r['stargazerCount'] for r in data['repositories']['nodes']),
        'followers': data['followers']['totalCount'],
        'commits': commits,
        'contributions': data['contributionsCollection']['contributionCalendar']['totalContributions'],
        'languages': sorted(langs.items(), key=lambda kv: kv[1], reverse=True),
    }


class Screen:
    """One CRT panel. Lines are revealed left-to-right like a teletype."""

    def __init__(self, width, height, title, size=20, start=0.3):
        self.w, self.h, self.title, self.size = width, height, title, size
        self.cw = size * 0.4
        self.t = start
        self.items = []

    def typed(self, x, y, content, chars, speed=0.014):
        dur = max(chars * speed, 0.05)
        self.items.append(
            f'<g class="ty" style="animation-delay:{self.t:.2f}s;animation-duration:{dur:.2f}s;'
            f'animation-timing-function:steps({max(chars, 1)})">{content}</g>')
        self.t += dur + 0.04

    def text(self, x, y, s, cls='t', anchor=None):
        a = f' text-anchor="{anchor}"' if anchor else ''
        if anchor == 'middle':
            x -= len(s) * self.cw / 2
            a = ''
        self.typed(x, y, f'<text x="{x:.1f}" y="{y}" class="{cls}"{a}>{escape(s)}</text>', len(s))

    def inverse(self, x, y, s, pad=6):
        w = len(s) * self.cw + pad * 2
        self.typed(x, y, f'<rect x="{x:.1f}" y="{y - self.size * 0.78:.1f}" width="{w:.1f}" height="{self.size * 0.98:.1f}" fill="{GREEN}"/>'
                         f'<text x="{x + pad:.1f}" y="{y}" class="inv">{escape(s)}</text>', len(s) + 2)

    def pause(self, s):
        self.t += s

    def raw(self, svg):
        self.items.append(svg)

    def cursor(self, x, y):
        self.raw(f'<rect x="{x:.1f}" y="{y - self.size * 0.72:.1f}" width="{self.cw:.1f}" height="{self.size * 0.8:.1f}" fill="{GREEN}" '
                 f'class="cursor" style="animation-delay:{self.t:.2f}s"/>')

    def render(self, label):
        w, h = self.w, self.h
        head = f'JUSIANN TERMLINK // {self.title}'
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
<defs>
<style>
  @font-face {{ font-family: 'VT'; src: url(data:font/woff2;base64,{FONT_B64}) format('woff2'); }}
  text {{ font-family: 'VT', ui-monospace, Menlo, monospace; font-size: {self.size}px; fill: {GREEN}; white-space: pre; }}
  .d {{ fill: {DIM}; }}
  .inv {{ fill: {SCREEN}; }}
  .head {{ font-size: 16px; fill: {DIM}; letter-spacing: 1px; }}
  .big {{ font-size: {self.size * 1.5:.0f}px; }}
  .screen {{ animation: flicker 5s infinite; }}
  .ty {{ animation-name: type; animation-fill-mode: both; }}
  @keyframes type {{ from {{ clip-path: inset(-12px 100% -12px -4px); -webkit-clip-path: inset(-12px 100% -12px -4px); }} to {{ clip-path: inset(-12px -12px -12px -4px); -webkit-clip-path: inset(-12px -12px -12px -4px); }} }}
  .cursor {{ opacity: 0; animation: blink 1s step-end infinite; }}
  @keyframes flicker {{ 0%, 100% {{ opacity: 1; }} 48% {{ opacity: .98; }} }}
  @keyframes blink {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .screen, .cursor, .ty {{ animation: none; }} .cursor {{ opacity: 1; }} }}
</style>
<radialGradient id="bg" cx="50%" cy="50%" r="75%"><stop offset="0" stop-color="{SCREEN}"/><stop offset="1" stop-color="{EDGE}"/></radialGradient>
<radialGradient id="vig" cx="50%" cy="50%" r="72%"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>
<linearGradient id="roll" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GREEN}" stop-opacity="0"/><stop offset=".5" stop-color="{GREEN}" stop-opacity=".035"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="2" fill="#000" opacity=".16"/></pattern>
<filter id="glow" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="0.9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="glass"><rect x="10" y="10" width="{w - 20}" height="{h - 20}" rx="16"/></clipPath>
</defs>
<rect width="{w}" height="{h}" rx="22" fill="{BEZEL}"/>
<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="20" fill="none" stroke="#2a332a" stroke-width="2"/>
<g clip-path="url(#glass)">
<rect x="10" y="10" width="{w - 20}" height="{h - 20}" fill="url(#bg)"/>
<g class="screen" filter="url(#glow)">
<text x="30" y="40" class="head">{escape(head)}</text>
<rect x="30" y="50" width="{w - 60}" height="1.5" fill="{DIM}"/>
{chr(10).join(self.items)}
</g>
<rect x="10" y="-80" width="{w - 20}" height="80" fill="url(#roll)"><animate attributeName="y" from="-80" to="{h}" dur="7s" repeatCount="indefinite"/></rect>
<rect x="10" y="10" width="{w - 20}" height="{h - 20}" fill="url(#scan)"/>
<rect x="10" y="10" width="{w - 20}" height="{h - 20}" fill="url(#vig)"/>
</g>
</svg>
'''


def boot():
    s = Screen(900, 250, 'BOOT', size=24, start=0.2)
    s.text(450, 90, 'JUSIANN INDUSTRIES (TM) TERMLINK PROTOCOL', cls='d', anchor='middle')
    s.pause(0.2)
    s.text(40, 136, '> LOGON ADIL_EFE', cls='d')
    s.pause(0.2)
    s.typed(40, 188, f'<text x="40" y="188" class="big">{escape("WELCOME TO THE VAULT OF ADIL EFE")}</text>', int(33 * 1.5))
    s.text(40, 220, 'SOFTWARE DEVELOPER // WEB, MOBILE & AI', cls='d')
    s.cursor(40 + 39 * s.cw + 4, 220)
    return s.render('JUSIANN INDUSTRIES TERMLINK. Welcome to the vault of Adil Efe, software developer: web, mobile & AI.')


def kv(s, x, y, key, value, width=11):
    if key:
        line = f'{key} {"." * (width - len(key))} '
    else:
        line = ' ' * (width + 2)
    s.typed(x, y, f'<text x="{x}" y="{y}"><tspan class="d">{escape(line)}</tspan>{escape(value)}</text>', len(line) + len(value))


def personnel():
    s = Screen(440, 330, 'PERSONNEL FILE')
    px, ox, oy = 4, 440 - 30 - 11 * 4, 66
    cells = ''.join(f'<rect x="{ox + j * px}" y="{oy + i * px}" width="{px - 1}" height="{px - 1}" fill="{GREEN}"/>'
                    for i, row in enumerate(MONOGRAM) for j, ch in enumerate(row) if ch == '#')
    s.raw(f'<g opacity=".7">{cells}</g>')
    s.text(30, 84, 'ADIL EFE')
    y = 118
    for key, value in PERSONNEL:
        kv(s, 30, y, key, value, width=9)
        y += 24
    s.text(30, y + 16, DIRECTIVE, cls='d')
    s.cursor(30 + len(DIRECTIVE) * s.cw + 4, y + 16)
    return s.render('Adil Efe. ' + '; '.join(f'{k.lower() or "…"}: {v}' for k, v in PERSONNEL) + '. The model reads numbers, never makes them.')


def status(stats):
    s = Screen(440, 330, 'STAT // GITHUB')
    y = 84
    rows = [('REPOSITORIES', stats['repos']), ('COMMITS', stats['commits']), ('CONTRIB. / YR', stats['contributions']),
            ('STARS', stats['stars']), ('FOLLOWERS', stats['followers'])]
    for key, value in rows:
        kv(s, 30, y, key, f'{value:,}', width=15)
        y += 24
    y += 14
    total = sum(size for _, size in stats['languages']) or 1
    segs, seg_w, gap = 18, 9, 3
    for name, size in stats['languages'][:4]:
        pct = size / total * 100
        filled = max(1, round(pct / 100 * segs))
        bx = 30 + 12 * s.cw
        bars = ''.join(
            f'<rect x="{bx + i * (seg_w + gap)}" y="{y - 13}" width="{seg_w}" height="13" '
            + (f'fill="{GREEN}"/>' if i < filled else f'fill="{FAINT}"/>')
            for i in range(segs))
        label = name.upper()
        pct_x = bx + segs * (seg_w + gap) + 6
        s.typed(30, y, f'<text x="30" y="{y}">{escape(label)}</text>{bars}<text x="{pct_x}" y="{y}" class="d">{pct:.0f}%</text>',
                int((pct_x - 30) / s.cw) + 4, speed=0.008)
        y += 24
    return s.render(f"GitHub stats: {stats['repos']} public repositories, {stats['commits']} commits, "
                    f"{stats['contributions']} contributions in the last year, {stats['stars']} stars, {stats['followers']} followers.")


def button(label):
    s = Screen(280, 110, 'LINK', size=24, start=0.2)
    s.inverse(140 - (len(label) + 6) * s.cw / 2 - 6, 90, f'[ {label} ]')
    return s.render(label.title())


def main():
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        raise SystemExit('GITHUB_TOKEN is required')
    stats = fetch_stats(token)

    panels = {
        'boot': boot(),
        'personnel': personnel(),
        'status': status(stats),
    }
    for slug, label in BUTTONS:
        panels[f'button-{slug}'] = button(label)

    for name, svg in panels.items():
        (OUT / f'{name}.svg').write_text(svg, encoding='utf-8')
    print(json.dumps({k: v for k, v in stats.items() if k != 'languages'}))


if __name__ == '__main__':
    main()
