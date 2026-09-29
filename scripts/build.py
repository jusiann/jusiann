#!/usr/bin/env python3
"""Render the profile's retro CRT monitor panels (Fallout-style termlink) as SVGs.

Text lives in the constants below; GitHub numbers are fetched live.
Run locally:   GITHUB_TOKEN=$(gh auth token) python3 scripts/build.py
In CI:         .github/workflows/update-profile.yml runs it daily.
"""

import base64
import json
import math
import os
import re
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

LOGIN = 'jusiann'
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets'
FONT_B64 = base64.b64encode((OUT / 'fonts' / 'vt323-subset.woff2').read_bytes()).decode()

GREEN = '#7ddc9c'
DIM = '#4a9a67'
FAINT = '#173524'
SCREEN = '#0c1c13'
EDGE = '#040a06'

WIDTH = 900
BEZEL = 18
CHIN = 34

PERSONNEL = [
    ('ROLE', 'SOFTWARE DEVELOPER · WEB, MOBILE & AI'),
    ('EDUCATION', 'COMPUTER ENGINEERING · ISTANBUL RUMELI UNIV.'),
    ('STATUS', 'FINAL YEAR · ISTANBUL, TÜRKİYE'),
    ('STACK', 'REACT · REACT NATIVE · NODE.JS · POSTGRESQL'),
    ('LEARNING', 'SWIFTUI (NATIVE IOS) · LANGGRAPH (AI AGENTS)'),
]
DIRECTIVE = '"THE MODEL READS NUMBERS, NEVER MAKES THEM."'

LINKS = [('portfolio', 'PORTFOLIO'), ('linkedin', 'LINKEDIN'), ('mail', 'MAIL')]

ICONS = {
    'portfolio': [
        '....###....',
        '..##.#.##..',
        '.#...#...#.',
        '.#...#...#.',
        '###########',
        '#....#....#',
        '###########',
        '.#...#...#.',
        '.#...#...#.',
        '..##.#.##..',
        '....###....',
    ],
    'linkedin': [
        '###########',
        '#.........#',
        '#.##......#',
        '#.........#',
        '#.##.####.#',
        '#.##.##.#.#',
        '#.##.##.#.#',
        '#.##.##.#.#',
        '#.##.##.#.#',
        '#.........#',
        '###########',
    ],
    'mail': [
        '.............',
        '#############',
        '##.........##',
        '#.#.......#.#',
        '#..#.....#..#',
        '#...#...#...#',
        '#....#.#....#',
        '#.....#.....#',
        '#...........#',
        '#############',
        '.............',
    ],
}


def pixels(grid, x, y, px, fill=GREEN):
    return ''.join(f'<rect x="{x + j * px:.1f}" y="{y + i * px:.1f}" width="{px - 1}" height="{px - 1}" fill="{fill}"/>'
                   for i, row in enumerate(grid) for j, ch in enumerate(row) if ch == '#')


def logo(n=31):
    """The mark: an outlined triangle with a ring at its incenter, drawn pixel by pixel."""
    h = (n - 1) * math.sqrt(3) / 2
    top = (n - 1 - h) / 2
    a, b, c = ((n - 1) / 2, top), (0, top + h), (n - 1, top + h)
    cx, cy, rin = a[0], top + h * 2 / 3, h / 3

    def dist(x, y, p, q):
        d = ((q[0] - p[0]) * (y - p[1]) - (q[1] - p[1]) * (x - p[0])) / math.hypot(q[0] - p[0], q[1] - p[1])
        return d if (q[0] - p[0]) * (cy - p[1]) - (q[1] - p[1]) * (cx - p[0]) > 0 else -d

    grid = []
    for y in range(n):
        row = ''
        for x in range(n):
            e = min(dist(x, y, a, b), dist(x, y, b, c), dist(x, y, c, a))
            r = math.hypot(x - cx, y - cy)
            row += '#' if (-0.5 <= e < 1.6) or (rin - 5.2 <= r <= rin - 3.4) else '.'
        grid.append(row)
    return grid


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
            contributionsCollection { contributionCalendar { totalContributions weeks { contributionDays { contributionCount } } } }
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
        'calendar': [[d['contributionCount'] for d in w['contributionDays']]
                     for w in data['contributionsCollection']['contributionCalendar']['weeks']],
    }


class Monitor:
    """One CRT monitor. Coordinates are relative to the glass; lines type out like a teletype."""

    def __init__(self, inner_h, size=22, start=0.2):
        self.iw = WIDTH - BEZEL * 2
        self.ih = inner_h
        self.h = BEZEL + inner_h + CHIN
        self.size = size
        self.cw = size * 0.4
        self.t = start
        self.items = []

    def typed(self, content, chars, speed=0.014):
        dur = max(chars * speed, 0.05)
        self.items.append(
            f'<g class="ty" style="animation-delay:{self.t:.2f}s;animation-duration:{dur:.2f}s;'
            f'animation-timing-function:steps({max(chars, 1)})">{content}</g>')
        self.t += dur + 0.04

    def text(self, x, y, s, cls='t', center=False, size=None):
        cw = (size or self.size) * 0.4
        if center:
            x = (self.iw - len(s) * cw) / 2
        style = f' style="font-size:{size}px"' if size else ''
        self.typed(f'<text x="{x:.1f}" y="{y}" class="{cls}"{style}>{escape(s)}</text>', len(s))

    def inverse(self, x, y, s, pad=8):
        w = len(s) * self.cw + pad * 2
        self.typed(f'<rect x="{x:.1f}" y="{y - self.size * 0.8:.1f}" width="{w:.1f}" height="{self.size:.1f}" fill="{GREEN}"/>'
                   f'<text x="{x + pad:.1f}" y="{y}" class="inv">{escape(s)}</text>', len(s) + 2)

    def kv(self, x, y, key, value, width):
        dots = f'{key} {"." * (width - len(key))} '
        self.typed(f'<text x="{x}" y="{y}"><tspan class="d">{escape(dots)}</tspan>{escape(value)}</text>', len(dots) + len(value))

    def pause(self, s):
        self.t += s

    def raw(self, svg):
        self.items.append(svg)

    def cursor(self, x, y):
        self.raw(f'<rect x="{x:.1f}" y="{y - self.size * 0.72:.1f}" width="{self.cw:.1f}" height="{self.size * 0.8:.1f}" '
                 f'fill="{GREEN}" class="cursor" style="animation-delay:{self.t:.2f}s"/>')

    def render(self, label):
        w, h, b, iw, ih = WIDTH, self.h, BEZEL, self.iw, self.ih
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
<defs>
<style>
  @font-face {{ font-family: 'VT'; src: url(data:font/woff2;base64,{FONT_B64}) format('woff2'); }}
  text {{ font-family: 'VT', ui-monospace, Menlo, monospace; font-size: {self.size}px; fill: {GREEN}; white-space: pre; }}
  .d {{ fill: {DIM}; }}
  .inv {{ fill: {SCREEN}; }}
  .brand {{ font-size: 15px; fill: #5d6158; letter-spacing: 4px; }}
  .screen {{ animation: flicker 6s infinite; }}
  .ty {{ animation-name: type; animation-fill-mode: both; }}
  .cursor {{ opacity: 0; animation: blink 1s step-end infinite; }}
  @keyframes type {{ from {{ clip-path: inset(-12px 100% -12px -4px); -webkit-clip-path: inset(-12px 100% -12px -4px); }} to {{ clip-path: inset(-12px -12px -12px -4px); -webkit-clip-path: inset(-12px -12px -12px -4px); }} }}
  @keyframes flicker {{ 0%, 100% {{ opacity: 1; }} 48% {{ opacity: .97; }} }}
  @keyframes blink {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .screen, .cursor, .ty {{ animation: none; }} .cursor {{ opacity: 1; }} }}
</style>
<linearGradient id="plastic" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3d36"/><stop offset="1" stop-color="#22241f"/></linearGradient>
<radialGradient id="bg" cx="50%" cy="50%" r="75%"><stop offset="0" stop-color="{SCREEN}"/><stop offset="1" stop-color="{EDGE}"/></radialGradient>
<radialGradient id="vig" cx="50%" cy="50%" r="70%"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".7"/></radialGradient>
<linearGradient id="roll" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GREEN}" stop-opacity="0"/><stop offset=".5" stop-color="{GREEN}" stop-opacity=".035"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient>
<linearGradient id="glare" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".05"/><stop offset=".35" stop-color="#fff" stop-opacity="0"/></linearGradient>
<pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="1.2" fill="#000" opacity=".22"/></pattern>
<filter id="glow" x="-5%" y="-10%" width="110%" height="120%"><feGaussianBlur stdDeviation="0.9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="soft"><feGaussianBlur stdDeviation="3"/></filter>
<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>
<clipPath id="glass"><rect x="{b}" y="{b}" width="{iw}" height="{ih}" rx="26"/></clipPath>
</defs>
<rect width="{w}" height="{h}" rx="16" fill="url(#plastic)"/>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="15" fill="none" stroke="#50544b" stroke-opacity=".6"/>
<rect x="{b - 5}" y="{b - 5}" width="{iw + 10}" height="{ih + 10}" rx="30" fill="#0b0c0a"/>
<g clip-path="url(#glass)">
<rect x="{b}" y="{b}" width="{iw}" height="{ih}" fill="url(#bg)"/>
<g transform="translate({b} {b})"><g class="screen" filter="url(#glow)">
{chr(10).join(self.items)}
</g></g>
<rect x="{b}" y="-90" width="{iw}" height="90" fill="url(#roll)"><animate attributeName="y" from="-90" to="{h}" dur="8s" repeatCount="indefinite"/></rect>
<rect x="{b}" y="{b}" width="{iw}" height="{ih}" fill="url(#scan)"/>
<rect x="{b}" y="{b}" width="{iw}" height="{ih}" filter="url(#grain)" opacity=".05"/>
<rect x="{b}" y="{b}" width="{iw}" height="{ih}" fill="url(#vig)"/>
<rect x="{b}" y="{b}" width="{iw}" height="{ih}" fill="url(#glare)"/>
</g>
<text x="{b + 8}" y="{h - CHIN / 2 + 5}" class="brand">JUSIANN</text>
<circle cx="{w - b - 12}" cy="{h - CHIN / 2}" r="6" fill="{GREEN}" opacity=".25" filter="url(#soft)"/>
<circle cx="{w - b - 12}" cy="{h - CHIN / 2}" r="3" fill="{GREEN}"/>
</svg>
'''


def boot():
    m = Monitor(330, start=0.2)
    m.text(0, 46, 'JUSIANN INDUSTRIES UNIFIED OPERATING SYSTEM', center=True)
    m.text(0, 72, 'COPYRIGHT 2024-2026 JUSIANN INDUSTRIES', cls='d', center=True)
    m.text(0, 98, '-SERVER 1-', cls='d', center=True)
    m.pause(0.2)
    m.text(30, 144, '>SET TERMINAL/INQUIRE', cls='d')
    m.text(30, 170, '>LOGON ADIL_EFE')
    m.text(30, 196, 'PASSWORD: ********', cls='d')
    m.pause(0.2)
    m.text(30, 222, 'ACCESS GRANTED.')
    m.pause(0.2)
    m.text(30, 276, 'WELCOME TO THE VAULT OF ADIL EFE', size=34)
    mark_px = 5
    mark_x = m.iw - 70 - 31 * mark_px
    m.raw(f'<g class="ty" style="animation-delay:{m.t:.2f}s;animation-duration:.6s;animation-timing-function:steps(12)">'
          f'{pixels(logo(), mark_x, 116, mark_px)}'
          f'<text x="{mark_x + 31 * mark_px / 2 - 4 * m.cw:.1f}" y="296" class="d">VAULT 01</text></g>')
    subtitle = 'SOFTWARE DEVELOPER // WEB, MOBILE & AI'
    m.text(30, 306, subtitle, cls='d')
    m.cursor(30 + (len(subtitle) + 1) * m.cw, 306)
    return m.render('JUSIANN INDUSTRIES UNIFIED OPERATING SYSTEM. Logon Adil_Efe. Access granted. '
                    'Welcome to the vault of Adil Efe, software developer: web, mobile & AI.')


def personnel():
    m = Monitor(290)
    px = 3
    ox, oy = m.iw - 40 - 31 * px, 36
    m.raw(f'<g opacity=".85">{pixels(logo(), ox, oy, px)}</g>'
          f'<rect x="{ox - 16}" y="{oy - 16}" width="{31 * px + 32}" height="{31 * px + 58}" fill="none" stroke="{DIM}" stroke-dasharray="4 4"/>'
          f'<text x="{ox + 31 * px / 2 - 3.5 * 7.2:.1f}" y="{oy + 31 * px + 30}" class="d" style="font-size:18px">ID #0001</text>')
    m.text(30, 44, '>RUN PERSONNEL/ADIL_EFE.F', cls='d')
    m.inverse(30, 84, 'ADIL EFE')
    y = 124
    for key, value in PERSONNEL:
        m.kv(30, y, key, value, width=10)
        y += 28
    m.text(30, y + 14, f'>DIRECTIVE: {DIRECTIVE}')
    m.cursor(30 + (len(DIRECTIVE) + 13) * m.cw, y + 14)
    return m.render('Personnel file — Adil Efe. ' + '; '.join(f'{k.lower()}: {v}' for k, v in PERSONNEL)
                    + '. Directive: the model reads numbers, never makes them.')


def status(stats):
    m = Monitor(410)
    m.text(30, 44, '>RUN STAT/GITHUB.EXE', cls='d')
    rows = [('REPOSITORIES', stats['repos']), ('COMMITS', stats['commits']), ('CONTRIB./YR', stats['contributions']),
            ('STARS', stats['stars']), ('FOLLOWERS', stats['followers'])]
    y = 88
    for key, value in rows:
        m.kv(30, y, key, f'{value:,}', width=13)
        y += 28

    total = sum(size for _, size in stats['languages']) or 1
    lx = 450
    segs, seg_w, gap = 20, 10, 3
    y = 88
    for name, size in stats['languages'][:5]:
        pct = size / total * 100
        filled = max(1, round(pct / 100 * segs))
        bx = lx + 12 * m.cw
        bars = ''.join(f'<rect x="{bx + i * (seg_w + gap)}" y="{y - 14}" width="{seg_w}" height="14" fill="{GREEN if i < filled else FAINT}"/>'
                       for i in range(segs))
        pct_x = bx + segs * (seg_w + gap) + 8
        m.typed(f'<text x="{lx}" y="{y}">{escape(name.upper())}</text>{bars}<text x="{pct_x}" y="{y}" class="d">{pct:.0f}%</text>',
                int((pct_x - lx) / m.cw) + 4, speed=0.008)
        y += 28

    weeks = stats['calendar'][-53:]
    shades = [FAINT, '#24593a', DIM, GREEN]
    cell, gap = 12, 3
    hx = (m.iw - len(weeks) * (cell + gap) + gap) / 2
    hy = 268
    m.text(30, hy - 22, f'>ACTIVITY.LOG  {stats["contributions"]:,} CONTRIBUTIONS / LAST 12 MONTHS', cls='d')
    for wi, week in enumerate(weeks):
        col = ''.join(
            f'<rect x="{hx + wi * (cell + gap):.1f}" y="{hy + di * (cell + gap)}" width="{cell}" height="{cell}" '
            f'fill="{shades[0 if c == 0 else 1 if c <= 2 else 2 if c <= 5 else 3]}"/>'
            for di, c in enumerate(week))
        m.typed(col, 1, speed=0.02)
    return m.render(f"GitHub stats: {stats['repos']} public repositories, {stats['commits']} commits, "
                    f"{stats['contributions']} contributions in the last year, {stats['stars']} stars, {stats['followers']} followers. "
                    'Languages: ' + ', '.join(n for n, _ in stats['languages'][:5]) + '.')


def links():
    """One monitor with all links, cut into vertical slices so each slice can carry its own <a> in the README."""
    m = Monitor(200)
    m.text(30, 44, '>OPEN NETWORK/LINKS.F', cls='d')
    third = WIDTH / len(LINKS)
    px = 5
    for i, (slug, label) in enumerate(LINKS):
        cx = third * i + third / 2 - BEZEL
        icon = ICONS[slug]
        m.typed(pixels(icon, cx - len(icon[0]) * px / 2, 72, px), 6)
        s = f'[ {label} ]'
        m.inverse(cx - (len(s) * m.cw + 16) / 2, 172, s)
    m.cursor(30 + 22 * m.cw, 44)
    full = m.render('Links')
    slices = {}
    for i, (slug, label) in enumerate(LINKS):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{third:.0f}" height="{m.h}" '
                f'viewBox="{third * i:.0f} 0 {third:.0f} {m.h}" role="img" aria-label="{label.title()}">')
        slices[f'link-{slug}'] = re.sub(r'<svg [^>]+>', head, full, count=1)
    return slices


def main():
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        raise SystemExit('GITHUB_TOKEN is required')
    stats = fetch_stats(token)

    panels = {'boot': boot(), 'personnel': personnel(), 'status': status(stats), **links()}
    for old in OUT.glob('*.svg'):
        old.unlink()
    for name, svg in panels.items():
        (OUT / f'{name}.svg').write_text(svg, encoding='utf-8')
    print(json.dumps({k: v for k, v in stats.items() if k not in ('languages', 'calendar')}))


if __name__ == '__main__':
    main()
