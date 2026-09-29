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
BEZEL = 28
CHIN = 80

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


# Turkey outline (lon, lat), Natural Earth via johan/world.geo.json — public domain.
TURKEY = [[[36.91,41.34],[38.35,40.95],[39.51,41.1],[40.37,41.01],[41.55,41.54],[42.62,41.58],[43.58,41.09],[43.75,40.74],[43.66,40.25],[44.4,40.01],[44.79,39.71],[44.11,39.43],[44.42,38.28],[44.23,37.97],[44.77,37.17],[44.29,37.0],[43.94,37.26],[42.78,37.39],[42.35,37.23],[41.21,37.07],[40.67,37.09],[39.52,36.72],[38.7,36.71],[38.17,36.9],[37.07,36.62],[36.74,36.82],[36.69,36.26],[36.42,36.04],[36.15,35.82],[35.78,36.27],[36.16,36.65],[35.55,36.57],[34.71,36.8],[34.03,36.22],[32.51,36.11],[31.7,36.64],[30.62,36.68],[30.39,36.26],[29.7,36.14],[28.73,36.68],[27.64,36.66],[27.05,37.65],[26.32,38.21],[26.8,38.99],[26.17,39.46],[27.28,40.42],[28.82,40.46],[29.24,41.22],[31.15,41.09],[32.35,41.74],[33.51,42.02],[35.17,42.04],[36.91,41.34]],[[27.19,40.69],[26.36,40.15],[26.04,40.62],[26.06,40.82],[26.29,40.94],[26.6,41.56],[26.12,41.83],[27.14,42.14],[28.0,42.01],[28.12,41.62],[28.99,41.3],[28.81,41.05],[27.62,41.0],[27.19,40.69]]]
ISTANBUL = (28.98, 41.01)


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

    def mark(self, caption, top=116, px=5):
        """The triangle-ring logo on the right side of the screen, with a caption under it."""
        x = self.iw - 70 - 31 * px
        self.raw(f'<g class="ty" style="animation-delay:{self.t:.2f}s;animation-duration:.6s;animation-timing-function:steps(12)">'
                 f'{pixels(logo(), x, top, px)}'
                 f'<text x="{x + 31 * px / 2 - len(caption) / 2 * self.cw:.1f}" y="{top + 31 * px + 26}" class="d">{escape(caption)}</text></g>')

    def pause(self, s):
        self.t += s

    def raw(self, svg):
        self.items.append(svg)

    def cursor(self, x, y):
        self.raw(f'<rect x="{x:.1f}" y="{y - self.size * 0.72:.1f}" width="{self.cw:.1f}" height="{self.size * 0.8:.1f}" '
                 f'fill="{GREEN}" class="cursor" style="animation-delay:{self.t:.2f}s"/>')

    def chassis(self):
        """Screws, brand plate, vents, knobs and power LED of the terminal housing."""
        w, h = WIDTH, self.h
        cy = BEZEL + self.ih + 13 + (CHIN - 13) / 2
        parts = []
        for x, y in [(15, 15), (w - 15, 15), (15, h - 15), (w - 15, h - 15)]:
            parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="url(#stud)" stroke="#16170f"/>'
                         f'<line x1="{x - 3}" y1="{y + 2}" x2="{x + 3}" y2="{y - 2}" stroke="#1d1e18" stroke-width="1.4"/>')
        px = BEZEL + 14
        parts.append(f'<rect x="{px}" y="{cy - 17}" width="196" height="34" rx="3" fill="#1c1d17" stroke="#6f7264" stroke-opacity=".45"/>'
                     f'<text x="{px + 12}" y="{cy - 1}" class="brand">JUSIANN</text>'
                     f'<text x="{px + 12}" y="{cy + 12}" class="model">TERMLINK · MODEL JT-01</text>')
        for i in range(18):
            parts.append(f'<rect x="{w / 2 - 18 * 5 + i * 10 + 1}" y="{cy - 12}" width="4" height="24" rx="2" fill="#15160f" stroke="#000" stroke-opacity=".4"/>')
        for i, kx in enumerate([w - BEZEL - 140, w - BEZEL - 100]):
            ang = [-50, 35][i]
            ex, ey = 9 * math.sin(math.radians(ang)), -9 * math.cos(math.radians(ang))
            parts.append(f'<circle cx="{kx}" cy="{cy}" r="13" fill="url(#knob)" stroke="#0f100c"/>'
                         f'<line x1="{kx}" y1="{cy}" x2="{kx + ex:.1f}" y2="{cy + ey:.1f}" stroke="#a4a795" stroke-width="2" stroke-linecap="round"/>')
        lx = w - BEZEL - 52
        parts.append(f'<circle cx="{lx}" cy="{cy - 5}" r="7" fill="{GREEN}" opacity=".3" filter="url(#soft)"/>'
                     f'<circle cx="{lx}" cy="{cy - 5}" r="3.5" fill="{GREEN}" stroke="#0f100c"/>'
                     f'<text x="{lx - 8}" y="{cy + 15}" class="model" style="font-size:11px">PWR</text>')
        return ''.join(parts)

    def render(self, label):
        w, h, b, iw, ih = WIDTH, self.h, BEZEL, self.iw, self.ih
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
<defs>
<style>
  @font-face {{ font-family: 'VT'; src: url(data:font/woff2;base64,{FONT_B64}) format('woff2'); }}
  text {{ font-family: 'VT', ui-monospace, Menlo, monospace; font-size: {self.size}px; fill: {GREEN}; white-space: pre; }}
  .d {{ fill: {DIM}; }}
  .inv {{ fill: {SCREEN}; }}
  .brand {{ font-size: 17px; fill: #9a9d8b; letter-spacing: 5px; }}
  .model {{ font-size: 12px; fill: #6f7264; letter-spacing: 2px; }}
  .sweep {{ transform-origin: var(--o); animation: spin 4s linear infinite; }}
  .ping {{ transform-box: fill-box; transform-origin: center; animation: ping 2s ease-out infinite; }}
  .blink {{ animation: blink 1.2s step-end infinite; }}
  .needle {{ transform-origin: var(--o); animation: swing 1.6s cubic-bezier(.3,1.4,.5,1) both; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  @keyframes ping {{ 0% {{ transform: scale(.4); opacity: .9; }} 100% {{ transform: scale(2.6); opacity: 0; }} }}
  @keyframes swing {{ from {{ transform: rotate(var(--from)); }} to {{ transform: rotate(0deg); }} }}
  .screen {{ animation: flicker 6s infinite; }}
  .ty {{ animation-name: type; animation-fill-mode: both; }}
  .cursor {{ opacity: 0; animation: blink 1s step-end infinite; }}
  @keyframes type {{ from {{ clip-path: inset(-12px 100% -12px -4px); -webkit-clip-path: inset(-12px 100% -12px -4px); }} to {{ clip-path: inset(-12px -12px -12px -4px); -webkit-clip-path: inset(-12px -12px -12px -4px); }} }}
  @keyframes flicker {{ 0%, 100% {{ opacity: 1; }} 48% {{ opacity: .97; }} }}
  @keyframes blink {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .screen, .cursor, .ty, .sweep, .ping, .needle, .blink {{ animation: none; }} .cursor {{ opacity: 1; }} }}
</style>
<linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f5248"/><stop offset=".45" stop-color="#3a3c34"/><stop offset="1" stop-color="#26271f"/></linearGradient>
<linearGradient id="recess" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d0e0a"/><stop offset="1" stop-color="#6a6d5f"/></linearGradient>
<radialGradient id="stud" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#9a9d8b"/><stop offset="1" stop-color="#2f3029"/></radialGradient>
<radialGradient id="knob" cx="40%" cy="30%" r="80%"><stop offset="0" stop-color="#6f7264"/><stop offset=".7" stop-color="#2c2d26"/><stop offset="1" stop-color="#1a1b16"/></radialGradient>
<filter id="blur8"><feGaussianBlur stdDeviation="8"/></filter>
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
<rect width="{w}" height="{h}" rx="14" fill="url(#metal)"/>
<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="13" fill="none" stroke="#777a6a" stroke-opacity=".5"/>
<rect x="5" y="5" width="{w - 10}" height="{h - 10}" rx="10" fill="none" stroke="#000" stroke-opacity=".3"/>
<rect x="{b - 13}" y="{b - 13}" width="{iw + 26}" height="{ih + 26}" rx="38" fill="#1f201a"/>
<rect x="{b - 13}" y="{b - 13}" width="{iw + 26}" height="{ih + 26}" rx="38" fill="none" stroke="url(#recess)" stroke-width="2"/>
<rect x="{b - 5}" y="{b - 5}" width="{iw + 10}" height="{ih + 10}" rx="31" fill="#060705"/>
{self.chassis()}
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
<ellipse cx="{b + iw * .3:.0f}" cy="{b + 6}" rx="{iw * .38:.0f}" ry="{ih * .2:.0f}" fill="#fff" opacity=".025"/>
<rect x="{b}" y="{b}" width="{iw}" height="{ih}" rx="26" fill="none" stroke="#000" stroke-width="26" opacity=".6" filter="url(#blur8)"/>
</g>
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
    m.mark('VAULT 01')
    subtitle = 'SOFTWARE DEVELOPER // WEB, MOBILE & AI'
    m.text(30, 306, subtitle, cls='d')
    m.cursor(30 + (len(subtitle) + 1) * m.cw, 306)
    return m.render('JUSIANN INDUSTRIES UNIFIED OPERATING SYSTEM. Logon Adil_Efe. Access granted. '
                    'Welcome to the vault of Adil Efe, software developer: web, mobile & AI.')


def personnel():
    m = Monitor(290)
    m.text(30, 44, '>RUN PERSONNEL/ADIL_EFE.F', cls='d')
    m.inverse(30, 84, 'ADIL EFE')
    y = 124
    for key, value in PERSONNEL:
        m.kv(30, y, key, value, width=10)
        y += 28
    m.mark('ID #0001', top=36)
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
    lx = 410
    segs, seg_w, gap = 18, 10, 3
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
    cell, gap = 11, 3
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


def inside(lon, lat, ring):
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def radar():
    """Dot-matrix map of Turkey with a blinking Istanbul marker, plus a mini radar."""
    m = Monitor(360)
    m.text(30, 44, '>RUN LOCATE/OPERATOR.EXE', cls='d')
    lon0, lon1, lat0, lat1 = 25.5, 45.0, 35.7, 42.3
    k = math.cos(math.radians(39))
    step = 7
    ox, oy = 34, 84
    cols = 74
    scale = cols * step / ((lon1 - lon0) * k)
    rows = int((lat1 - lat0) * scale / step) + 1
    grid = [[any(inside(lon0 + (c + .5) * step / scale / k, lat1 - (r + .5) * step / scale, ring) for ring in TURKEY)
             for c in range(cols)] for r in range(rows)]
    dots = []
    for r, row in enumerate(grid):
        for c, on in enumerate(row):
            if not on:
                dots.append(f'<rect x="{ox + c * step + 3}" y="{oy + r * step + 3}" width="1.5" height="1.5" fill="{DIM}" opacity=".35"/>')
                continue
            edge = any(not (0 <= r + dr < rows and 0 <= c + dc < cols and grid[r + dr][c + dc])
                       for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            dots.append(f'<rect x="{ox + c * step}" y="{oy + r * step}" width="{step - 2}" height="{step - 2}" '
                        f'fill="{GREEN if edge else DIM}" opacity="{1 if edge else .55}"/>')
    ix = ox + (ISTANBUL[0] - lon0) * k * scale
    iy = oy + (lat1 - ISTANBUL[1]) * scale
    m.typed(''.join(dots), 40, speed=0.02)
    m.raw(f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="7" fill="none" stroke="{GREEN}" stroke-width="2" class="ping"/>'
          f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="5" fill="{GREEN}" class="blink"/>'
          f'<line x1="{ix:.1f}" y1="{iy:.1f}" x2="{ix + 36:.1f}" y2="{iy - 30:.1f}" stroke="{GREEN}"/>'
          f'<text x="{ix + 40:.1f}" y="{iy - 32:.1f}" style="font-size:18px">ISTANBUL</text>')

    x = ox + cols * step + 36
    y = 196
    for key, value in [('OPERATOR', 'ADIL EFE'), ('LOCATION', 'ISTANBUL, TR'), ('COORDS', '41.01°N 28.98°E'), ('TIMEZONE', 'UTC+3 (TRT)')]:
        m.kv(x, y, key, value, width=8)
        y += 30

    cx, cy, r = x + 110, 112, 50
    o = f'{cx}px {cy}px'
    rings = ''.join(f'<circle cx="{cx}" cy="{cy}" r="{r * j / 2:.1f}" fill="none" stroke="{DIM}" stroke-opacity=".7"/>' for j in (1, 2))
    wedge = (f'<path d="M{cx} {cy} L{cx + r} {cy} A{r} {r} 0 0 0 {cx + r * math.cos(math.radians(-45)):.1f} {cy + r * math.sin(math.radians(-45)):.1f} Z" '
             f'fill="url(#sweep)"/><line x1="{cx}" y1="{cy}" x2="{cx + r}" y2="{cy}" stroke="{GREEN}" stroke-width="1.5"/>')
    m.raw(f'<defs><linearGradient id="sweep" x1="1" y1="1" x2=".7" y2="0"><stop offset="0" stop-color="{GREEN}" stop-opacity=".5"/>'
          f'<stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient></defs>'
          f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{FAINT}" fill-opacity=".5" stroke="{GREEN}" stroke-opacity=".6"/>{rings}'
          f'<line x1="{cx - r}" y1="{cy}" x2="{cx + r}" y2="{cy}" stroke="{DIM}" stroke-opacity=".5"/>'
          f'<line x1="{cx}" y1="{cy - r}" x2="{cx}" y2="{cy + r}" stroke="{DIM}" stroke-opacity=".5"/>'
          f'<g class="sweep" style="--o:{o}">{wedge}</g>'
          f'<circle cx="{cx}" cy="{cy}" r="3.5" fill="{GREEN}" class="blink"/>')
    m.text(30, 340, 'SIGNAL LOCKED. 1 OPERATOR FOUND.')
    m.cursor(30 + 33 * m.cw, 340)
    return m.render('Locate operator: map of Türkiye with Istanbul marked. Adil Efe, Istanbul (41.01°N 28.98°E), UTC+3.')


def streaks(calendar):
    days = [c for week in calendar for c in week]
    last_year = days[-365:]
    tail = days[:-1] if days and days[-1] == 0 else days
    current = 0
    for c in reversed(tail):
        if not c:
            break
        current += 1
    longest = run = 0
    for c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    return current, longest, sum(1 for c in last_year if c)


def gauges(stats):
    m = Monitor(300)
    m.text(30, 44, '>RUN DIAGNOSTICS/ACTIVITY.EXE', cls='d')
    current, longest, active = streaks(stats['calendar'])
    nice = lambda v: next(n for n in (7, 14, 30, 60, 90, 180, 365, 10 ** 6) if n >= v)
    dials = [('CURRENT STREAK', current, nice(max(current, longest)), 'DAYS'),
             ('LONGEST STREAK', longest, nice(longest), 'DAYS'),
             ('ACTIVE DAYS / YR', active, 365, 'DAYS')]
    third = m.iw / 3
    r, cy = 78, 160
    for i, (label, value, top, unit) in enumerate(dials):
        cx = third * i + third / 2
        arc = []
        for k in range(11):
            a = math.radians(-210 + k * 24)
            inner = r - (12 if k % 5 == 0 else 7)
            arc.append(f'<line x1="{cx + inner * math.cos(a):.1f}" y1="{cy + inner * math.sin(a):.1f}" '
                       f'x2="{cx + r * math.cos(a):.1f}" y2="{cy + r * math.sin(a):.1f}" stroke="{GREEN if k % 5 == 0 else DIM}" stroke-width="{2 if k % 5 == 0 else 1.2}"/>')
        red = math.radians(-210 + 240 * .8)
        sx, sy = cx + r * math.cos(red), cy + r * math.sin(red)
        ex, ey = cx + r * math.cos(math.radians(30)), cy + r * math.sin(math.radians(30))
        band = f'<path d="M{sx:.1f} {sy:.1f} A{r} {r} 0 0 1 {ex:.1f} {ey:.1f}" fill="none" stroke="{GREEN}" stroke-opacity=".35" stroke-width="4"/>'
        frac = min(value / top, 1) if top else 0
        ang = -210 + 240 * frac
        nx, ny = cx + (r - 16) * math.cos(math.radians(ang)), cy + (r - 16) * math.sin(math.radians(ang))
        o = f'{cx:.1f}px {cy}px'
        m.raw(f'<circle cx="{cx:.1f}" cy="{cy}" r="{r + 10}" fill="{FAINT}" fill-opacity=".35" stroke="{DIM}" stroke-opacity=".5"/>'
              f'{"".join(arc)}{band}'
              f'<text x="{cx - r + 4:.1f}" y="{cy + r - 4}" class="d" style="font-size:15px">0</text>'
              f'<text x="{cx + r - 4 - len(str(top)) * 6:.1f}" y="{cy + r - 4}" class="d" style="font-size:15px">{top}</text>'
              f'<g class="needle" style="--o:{o};--from:{-240 * frac:.1f}deg"><line x1="{cx:.1f}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="{GREEN}" stroke-width="3" stroke-linecap="round"/></g>'
              f'<circle cx="{cx:.1f}" cy="{cy}" r="7" fill="{GREEN}"/><circle cx="{cx:.1f}" cy="{cy}" r="3" fill="{SCREEN}"/>')
        readout = f'{value:03d}'
        m.inverse(cx - (len(readout) * m.cw + 16) / 2, cy + 52, readout)
        m.text(cx - len(label) * m.cw / 2, cy + 118, label, cls='d')
    return m.render(f'Activity diagnostics: current streak {current} days, longest streak {longest} days, '
                    f'{active} active days in the last year.')


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

    panels = {'boot': boot(), 'personnel': personnel(), 'radar': radar(), 'status': status(stats),
              'gauges': gauges(stats), **links()}
    for old in OUT.glob('*.svg'):
        old.unlink()
    for name, svg in panels.items():
        (OUT / f'{name}.svg').write_text(svg, encoding='utf-8')
    print(json.dumps({k: v for k, v in stats.items() if k not in ('languages', 'calendar')}))


if __name__ == '__main__':
    main()
