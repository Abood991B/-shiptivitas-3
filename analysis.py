#!/usr/bin/env python3
"""
Shiptivity analytics - Module 3 (Analyse the latest feature releases)

Runs every query in answer.sql against shiptivity.db and writes a self
contained report, shiptivitas_analytics.html, which contains

  1. the graph of daily active users before and after the Kanban release
  2. the graph of the number of status changes by card
  3. the SQL queries used to produce both
  4. three actionable feature ideas (hypothesis / expected impact / feature)

Usage:  python analysis.py
"""

import html
import math
import os
import sqlite3
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, 'shiptivity.db')
SQL_PATH = os.path.join(HERE, 'answer.sql')
OUT_PATH = os.path.join(HERE, 'shiptivitas_analytics.html')

RELEASE = '2018-06-02'          # Kanban board release
CREATED = '(card created)'      # card_change_history rows with oldStatus IS NULL

BLUE = '#2563eb'
BLUE_LIGHT = '#c9d9f8'
AMBER = '#d97706'
GREEN = '#16a34a'
GREY = '#6b7280'
DARK = '#111827'
GRID = '#e5e7eb'
RED = '#dc2626'

esc = html.escape


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def split_statements(sql_text):
    statements, buffer = [], []
    for line in sql_text.splitlines():
        buffer.append(line)
        if line.rstrip().endswith(';'):
            statements.append('\n'.join(buffer).strip())
            buffer = []
    return statements


def run(con, statement):
    cur = con.cursor()
    cur.execute(statement)
    columns = [d[0] for d in cur.description]
    return columns, [dict(zip(columns, row)) for row in cur.fetchall()]


def one(con, sql, params=()):
    return con.cursor().execute(sql, params).fetchone()[0]


# --------------------------------------------------------------------------- #
# chart 1 - daily active users before / after the feature change
# --------------------------------------------------------------------------- #
def chart_dau(daily, avg_before, avg_after, lift_pct):
    width, height = 960, 420
    ml, mr, mt, mb = 54, 18, 34, 56
    pw, ph = width - ml - mr, height - mt - mb
    n = len(daily)
    values = [row['daily_active_users'] for row in daily]
    ymax = max(int((max(values) + 4) // 5 * 5), 10)

    def x(i):
        return ml + i * pw / (n - 1)

    def y(v):
        return mt + ph - v * ph / ymax

    out = ['<svg viewBox="0 0 %d %d" role="img" '
           'aria-label="Daily active users before and after the Kanban release" '
           'xmlns="http://www.w3.org/2000/svg">' % (width, height)]

    # horizontal grid + y labels
    v = 0
    while v <= ymax:
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s"/>'
                   % (ml, y(v), width - mr, y(v), GRID))
        out.append('<text x="%d" y="%.1f" font-size="11" fill="%s" text-anchor="end">%d</text>'
                   % (ml - 8, y(v) + 4, GREY, v))
        v += 5

    # month ticks
    previous = None
    for i, row in enumerate(daily):
        month = row['day'][:7]
        if month != previous:
            label = datetime.strptime(month, '%Y-%m').strftime("%b '%y")
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s"/>'
                       % (x(i), mt + ph, x(i), mt + ph + 5, GREY))
            out.append('<text x="%.1f" y="%.1f" font-size="10" fill="%s" text-anchor="middle">%s</text>'
                       % (x(i), mt + ph + 20, GREY, label))
        previous = month

    # release marker
    release_index = next(i for i, row in enumerate(daily) if row['day'] >= RELEASE)
    rx = x(release_index)
    out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5" '
               'stroke-dasharray="6 4"/>' % (rx, mt - 6, rx, mt + ph, RED))
    out.append('<text x="%.1f" y="16" font-size="11" font-weight="600" fill="%s" '
               'text-anchor="middle">Kanban board released %s</text>' % (rx, RED, RELEASE))

    # average lines (with a white halo so they stay readable over the data)
    out.append('<line x1="%d" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5" '
               'stroke-dasharray="5 4"/>' % (ml, y(avg_before), rx, y(avg_before), AMBER))
    out.append('<rect x="%d" y="%.1f" width="106" height="15" fill="white" fill-opacity="0.85"/>'
               % (ml + 5, y(avg_before) - 18))
    out.append('<text x="%d" y="%.1f" font-size="11" font-weight="600" fill="%s">'
               'avg before: %.2f</text>' % (ml + 8, y(avg_before) - 7, AMBER, avg_before))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5" '
               'stroke-dasharray="5 4"/>' % (rx, y(avg_after), width - mr, y(avg_after), GREEN))
    out.append('<rect x="%.1f" y="%.1f" width="158" height="15" fill="white" fill-opacity="0.85"/>'
               % (width - mr - 164, y(avg_after) - 18))
    out.append('<text x="%.1f" y="%.1f" font-size="11" font-weight="600" fill="%s" text-anchor="end">'
               'avg after: %.2f  (+%.0f%%)</text>'
               % (width - mr - 6, y(avg_after) - 7, GREEN, avg_after, lift_pct))

    # daily line + 7 day rolling average
    points = ' '.join('%.1f,%.1f' % (x(i), y(value)) for i, value in enumerate(values))
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.4" stroke-opacity="0.85"/>'
               % (points, BLUE_LIGHT))
    rolling = []
    for i, value in enumerate(values):
        window = values[max(0, i - 6):i + 1]
        rolling.append(sum(window) / len(window))
    roll_points = ' '.join('%.1f,%.1f' % (x(i), y(value)) for i, value in enumerate(rolling))
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.6" stroke-linejoin="round"/>'
               % (roll_points, BLUE))

    # peak annotation
    peak = max(range(n), key=lambda i: values[i])
    out.append('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>' % (x(peak), y(values[peak]), BLUE))
    out.append('<text x="%.1f" y="%.1f" font-size="10.5" font-weight="600" fill="%s" '
               'text-anchor="middle">peak %d users (%s)</text>'
               % (x(peak), y(values[peak]) - 9, DARK, values[peak], daily[peak]['day']))

    # legend
    lx, ly = ml + 10, mt + 14
    out.append('<rect x="%d" y="%d" width="192" height="66" fill="white" fill-opacity="0.92" stroke="%s"/>'
               % (lx - 6, ly - 12, GRID))
    legend = [
        (BLUE_LIGHT, 'daily active users', None),
        (BLUE, '7-day rolling average', None),
        (AMBER, 'average before release', '5 4'),
        (GREEN, 'average after release', '5 4'),
    ]
    for k, (colour, label, dash) in enumerate(legend):
        yl = ly + k * 16
        dash_attr = ' stroke-dasharray="%s"' % dash if dash else ''
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="2.5"%s/>'
                   % (lx, yl, lx + 22, yl, colour, dash_attr))
        out.append('<text x="%d" y="%.1f" font-size="10.5" fill="%s">%s</text>'
                   % (lx + 28, yl + 3.5, DARK, label))

    # axis titles
    out.append('<text x="%d" y="%d" font-size="11" fill="%s" text-anchor="middle">day (UTC)</text>'
               % (ml + pw // 2, height - 10, GREY))
    out.append('<text x="14" y="%d" font-size="11" fill="%s" text-anchor="middle" '
               'transform="rotate(-90 14 %d)">daily active users</text>'
               % (mt + ph // 2, GREY, mt + ph // 2))
    out.append('</svg>')
    return '\n'.join(out)


# --------------------------------------------------------------------------- #
# chart 2 - number of status changes by card
# --------------------------------------------------------------------------- #
def chart_cards(rows):
    top = rows[:15]
    width, height = 960, 470
    label_w, right_pad = 336, 56
    x0, x1 = label_w, width - right_pad
    top_margin, row_h, bar_h = 46, 26, 15
    vmax = max(r['status_changes'] for r in top) or 1

    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Status changes by card, top 15 cards" '
           'xmlns="http://www.w3.org/2000/svg">' % (width, height)]

    for v in range(0, vmax + 1):
        gx = x0 + (x1 - x0) * v / vmax
        out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s"/>'
                   % (gx, top_margin - 14, gx, top_margin + row_h * len(top) + 4, GRID))
        out.append('<text x="%.1f" y="%d" font-size="10.5" fill="%s" text-anchor="middle">%d</text>'
                   % (gx, top_margin - 20, GREY, v))
    out.append('<text x="%d" y="%d" font-size="10.5" fill="%s" text-anchor="middle">status changes</text>'
               % ((x0 + x1) // 2, height - 12, GREY))

    for i, row in enumerate(top):
        cy = top_margin + i * row_h + row_h / 2
        bar = (x1 - x0) * row['status_changes'] / vmax
        name = row['card_name']
        if len(name) > 36:
            name = name[:35] + '\u2026'
        out.append('<text x="%d" y="%.1f" font-size="11.5" fill="%s" text-anchor="end">#%s %s</text>'
                   % (label_w - 14, cy + 4, DARK, row['card_id'], esc(name)))
        out.append('<rect x="%d" y="%.1f" width="%.1f" height="%d" rx="2" fill="%s"/>'
                   % (x0, cy - bar_h / 2, max(bar, 1.5), bar_h, BLUE))
        out.append('<text x="%.1f" y="%.1f" font-size="11" font-weight="600" fill="%s">%d</text>'
                   % (x0 + bar + 6, cy + 4, DARK, row['status_changes']))

    out.append('</svg>')
    return '\n'.join(out)


def chart_distribution(distribution):
    width, height = 460, 300
    ml, mr, mt, mb = 46, 16, 34, 56
    pw, ph = width - ml - mr, height - mt - mb
    vmax = max(v for _, v in distribution)
    vmax = max(int(math.ceil(vmax / 20.0)) * 20, 20)
    slot = pw / len(distribution)

    out = ['<svg viewBox="0 0 %d %d" role="img" '
           'aria-label="How many cards were moved 0 to 5 times" '
           'xmlns="http://www.w3.org/2000/svg">' % (width, height)]
    v = 0
    while v <= vmax:
        gy = mt + ph - v * ph / vmax
        out.append('<line x1="%d" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s"/>'
                   % (ml, gy, width - mr, gy, GRID))
        out.append('<text x="%d" y="%.1f" font-size="10.5" fill="%s" text-anchor="end">%d</text>'
                   % (ml - 8, gy + 4, GREY, v))
        v += 20

    for i, (changes, cards) in enumerate(distribution):
        bh = cards * ph / vmax
        bx = ml + i * slot + slot * 0.2
        bw = slot * 0.6
        by = mt + ph - bh
        colour = AMBER if changes == 0 else BLUE
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"/>'
                   % (bx, by, bw, bh, colour))
        out.append('<text x="%.1f" y="%.1f" font-size="11" font-weight="600" fill="%s" '
                   'text-anchor="middle">%d</text>' % (bx + bw / 2, by - 6, DARK, cards))
        out.append('<text x="%.1f" y="%.1f" font-size="11" fill="%s" text-anchor="middle">%d</text>'
                   % (bx + bw / 2, mt + ph + 18, GREY, changes))

    out.append('<text x="%.1f" y="%d" font-size="10.5" fill="%s" text-anchor="middle">'
               'status changes per card</text>' % (ml + pw / 2, height - 26, GREY))
    out.append('<text x="%.1f" y="%d" font-size="10.5" fill="%s" text-anchor="middle">'
               'number of cards (amber = never moved)</text>' % (ml + pw / 2, height - 10, GREY))
    out.append('</svg>')
    return '\n'.join(out)


# --------------------------------------------------------------------------- #
# wireframes (optional but helpful)
# --------------------------------------------------------------------------- #
def wireframe_digest():
    return '''
<svg viewBox="0 0 320 190" xmlns="http://www.w3.org/2000/svg" aria-label="Wireframe of the weekly board digest">
  <rect x="8" y="8" width="304" height="174" fill="#fff" stroke="#9ca3af"/>
  <rect x="8" y="8" width="304" height="26" fill="#f3f4f6" stroke="#9ca3af"/>
  <text x="18" y="25" font-size="11" font-weight="600" fill="#374151">Your board pulse - Mon 9:00</text>
  <text x="18" y="50" font-size="10" fill="#6b7280">3 cards moved - 5 cards waiting on you</text>
  <g>
    <rect x="18" y="58" width="284" height="24" fill="#fff" stroke="#d1d5db"/>
    <rect x="24" y="64" width="12" height="12" fill="#dbeafe"/>
    <text x="44" y="75" font-size="9.5" fill="#374151">O'Kon Group -&gt; complete</text>
  </g>
  <g>
    <rect x="18" y="86" width="284" height="24" fill="#fff" stroke="#d1d5db"/>
    <rect x="24" y="92" width="12" height="12" fill="#fef3c7"/>
    <text x="44" y="103" font-size="9.5" fill="#374151">Kutch-Mueller idle 16 days</text>
  </g>
  <g>
    <rect x="18" y="114" width="284" height="24" fill="#fff" stroke="#d1d5db"/>
    <rect x="24" y="120" width="12" height="12" fill="#dcfce7"/>
    <text x="44" y="131" font-size="9.5" fill="#374151">Backlog: 12 cards untouched over 30d</text>
  </g>
  <rect x="18" y="148" width="112" height="24" rx="3" fill="#2563eb"/>
  <text x="74" y="164" font-size="10" fill="#fff" text-anchor="middle">Open board</text>
</svg>'''


def wireframe_stale():
    return '''
<svg viewBox="0 0 320 190" xmlns="http://www.w3.org/2000/svg" aria-label="Wireframe of the idle card nudge">
  <rect x="8" y="8" width="304" height="174" fill="#fff" stroke="#9ca3af"/>
  <rect x="16" y="16" width="288" height="26" fill="#fef3c7" stroke="#f59e0b"/>
  <text x="24" y="33" font-size="10" font-weight="600" fill="#92400e">4 cards idle over 14 days</text>
  <text x="240" y="33" font-size="9" fill="#92400e">nudge | archive</text>
  <g stroke="#d1d5db" fill="#f9fafb">
    <rect x="16" y="50" width="90" height="124"/>
    <rect x="115" y="50" width="90" height="124"/>
    <rect x="214" y="50" width="90" height="124"/>
  </g>
  <text x="61" y="66" font-size="9.5" font-weight="600" fill="#374151" text-anchor="middle">Backlog</text>
  <text x="160" y="66" font-size="9.5" font-weight="600" fill="#374151" text-anchor="middle">In progress</text>
  <text x="259" y="66" font-size="9.5" font-weight="600" fill="#374151" text-anchor="middle">Complete</text>
  <rect x="22" y="74" width="78" height="34" fill="#fff" stroke="#d1d5db"/>
  <text x="27" y="88" font-size="8" fill="#6b7280">Wiza LLC</text>
  <rect x="27" y="93" width="40" height="11" rx="2" fill="#fef3c7" stroke="#f59e0b"/>
  <text x="31" y="101.5" font-size="7.5" font-weight="600" fill="#92400e">idle 21d</text>
  <rect x="22" y="114" width="78" height="34" fill="#fff" stroke="#d1d5db"/>
  <text x="27" y="128" font-size="8" fill="#6b7280">Boehm and Sons</text>
  <rect x="121" y="74" width="78" height="34" fill="#fff" stroke="#d1d5db"/>
  <text x="126" y="88" font-size="8" fill="#6b7280">Nolan LLC</text>
  <rect x="126" y="93" width="40" height="11" rx="2" fill="#fef3c7" stroke="#f59e0b"/>
  <text x="130" y="101.5" font-size="7.5" font-weight="600" fill="#92400e">idle 17d</text>
  <rect x="121" y="114" width="78" height="34" fill="#fff" stroke="#d1d5db"/>
  <text x="126" y="128" font-size="8" fill="#6b7280">Thompson PLC</text>
  <rect x="220" y="74" width="78" height="34" fill="#fff" stroke="#d1d5db"/>
  <text x="225" y="88" font-size="8" fill="#6b7280">Reilly-King</text>
</svg>'''


def wireframe_mylane():
    return '''
<svg viewBox="0 0 320 190" xmlns="http://www.w3.org/2000/svg" aria-label="Wireframe of the personal lane and daily focus">
  <rect x="8" y="8" width="304" height="174" fill="#fff" stroke="#9ca3af"/>
  <rect x="8" y="8" width="86" height="174" fill="#f9fafb" stroke="#d1d5db"/>
  <text x="16" y="26" font-size="9.5" font-weight="600" fill="#374151">My cards (7)</text>
  <rect x="16" y="34" width="70" height="16" rx="2" fill="#dbeafe"/>
  <text x="20" y="45" font-size="8" fill="#1e40af">Today: 3 cards</text>
  <text x="16" y="66" font-size="8" fill="#6b7280">All boards</text>
  <text x="16" y="82" font-size="8" fill="#6b7280">Idle over 14d</text>
  <rect x="102" y="16" width="202" height="22" fill="#eff6ff" stroke="#bfdbfe"/>
  <text x="110" y="31" font-size="9.5" font-weight="600" fill="#1e40af">Today - move these 3 cards</text>
  <g>
    <rect x="102" y="44" width="202" height="38" fill="#fff" stroke="#d1d5db"/>
    <text x="110" y="59" font-size="9" fill="#374151">Hessel Group -&gt; in progress</text>
    <rect x="110" y="63" width="18" height="14" rx="2" fill="#2563eb"/>
    <text x="119" y="73.5" font-size="8" fill="#fff" text-anchor="middle">1</text>
    <rect x="132" y="63" width="18" height="14" rx="2" fill="#e5e7eb"/>
    <text x="141" y="73.5" font-size="8" fill="#374151" text-anchor="middle">2</text>
    <rect x="154" y="63" width="18" height="14" rx="2" fill="#e5e7eb"/>
    <text x="163" y="73.5" font-size="8" fill="#374151" text-anchor="middle">3</text>
  </g>
  <g>
    <rect x="102" y="88" width="202" height="38" fill="#fff" stroke="#d1d5db"/>
    <text x="110" y="103" font-size="9" fill="#374151">Gerlach Inc -&gt; complete</text>
    <rect x="110" y="107" width="18" height="14" rx="2" fill="#e5e7eb"/>
    <rect x="132" y="107" width="18" height="14" rx="2" fill="#e5e7eb"/>
    <rect x="154" y="107" width="18" height="14" rx="2" fill="#2563eb"/>
  </g>
  <g>
    <rect x="102" y="132" width="202" height="38" fill="#fff" stroke="#d1d5db"/>
    <text x="110" y="147" font-size="9" fill="#374151">Osinski Inc -&gt; next step</text>
    <rect x="110" y="151" width="18" height="14" rx="2" fill="#e5e7eb"/>
    <rect x="132" y="151" width="18" height="14" rx="2" fill="#2563eb"/>
    <rect x="154" y="151" width="18" height="14" rx="2" fill="#e5e7eb"/>
  </g>
  <text x="304" y="31" font-size="9" font-weight="600" fill="#16a34a" text-anchor="end">5-day streak</text>
</svg>'''


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
CSS = """
:root { --blue:#2563eb; --ink:#111827; --muted:#6b7280; --line:#e5e7eb; }
* { box-sizing:border-box; }
body { margin:0; background:#f8fafc; color:var(--ink);
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:1040px; margin:0 auto; padding:32px 20px 72px; }
header h1 { margin:0 0 4px; font-size:30px; letter-spacing:-.4px; }
header p { margin:0; color:var(--muted); }
.tag { display:inline-block; background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;
       border-radius:999px; padding:2px 10px; font-size:12px; font-weight:600; margin:6px 6px 0 0; }
h2 { font-size:21px; margin:44px 0 6px; letter-spacing:-.2px; }
h3 { font-size:16px; margin:26px 0 6px; }
p { margin:8px 0; }
.lead { color:#374151; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:22px 0 6px; }
.kpi { background:#fff; border:1px solid var(--line); border-radius:10px; padding:14px 14px 12px; }
.kpi .v { font-size:25px; font-weight:700; letter-spacing:-.6px; }
.kpi .l { font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.4px; }
.kpi .s { font-size:12.5px; color:#374151; margin-top:4px; }
.kpi.good .v { color:#16a34a; } .kpi.warn .v { color:#d97706; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin-top:14px; }
.figure .cap { font-size:13px; color:var(--muted); margin:6px 0 0; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
svg { width:100%; height:auto; display:block; }
pre { background:#0b1220; color:#dbeafe; padding:14px 16px; border-radius:10px; overflow:auto;
      font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
code { font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.idea { background:#fff; border:1px solid var(--line); border-left:4px solid var(--blue);
        border-radius:10px; padding:16px 18px; margin-top:16px; }
.idea h3 { margin-top:0; font-size:17px; }
.idea .num { display:inline-block; width:22px; height:22px; line-height:22px; text-align:center;
             background:var(--blue); color:#fff; border-radius:50%; font-size:12px; margin-right:8px; }
.idea dt { font-size:11.5px; font-weight:700; letter-spacing:.6px; text-transform:uppercase;
           color:var(--blue); margin-top:12px; }
.idea dd { margin:3px 0 0; }
.wf { background:#f9fafb; border:1px solid var(--line); border-radius:8px; padding:8px; margin-top:10px; }
.wf .t { font-size:11.5px; color:var(--muted); margin:0 0 4px 2px; }
.wf svg { max-width:440px; margin:0 auto; }
table { border-collapse:collapse; width:100%; font-size:13.5px; background:#fff; }
th,td { border:1px solid var(--line); padding:7px 10px; text-align:left; }
th { background:#f3f4f6; font-weight:600; }
td.n, th.n { text-align:right; }
ul { margin:8px 0; padding-left:20px; } li { margin:5px 0; }
footer { margin-top:46px; color:var(--muted); font-size:13px; border-top:1px solid var(--line); padding-top:14px; }
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr);} .grid2{grid-template-columns:1fr;} }
"""


def build_html(ctx):
    daily_svg = chart_dau(ctx['daily'], ctx['avg_before'], ctx['avg_after'], ctx['lift_pct'])
    cards_svg = chart_cards(ctx['card_rows'])
    dist_svg = chart_distribution(ctx['distribution'])
    sql_block = esc(ctx['sql_text'])

    transition_rows = ''.join(
        '<tr><td>%s</td><td>%s</td><td class="n">%d</td><td class="n">%.1f%%</td></tr>'
        % (esc(r['from_status']), esc(r['to_status']), r['moves'], 100.0 * r['moves'] / ctx['all_events'])
        for r in ctx['transitions'])

    parts = []
    parts.append('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append('<title>Shiptivity analytics - Kanban release impact</title>')
    parts.append('<style>%s</style>\n</head>\n<body><div class="wrap">' % CSS)

    parts.append('<header>')
    parts.append('<h1>Shiptivity - what the Kanban release did to our core metric</h1>')
    parts.append('<p><span class="tag">data %s &rarr; %s</span><span class="tag">release %s</span>'
                 '<span class="tag">100 users</span><span class="tag">200 cards</span></p>'
                 % (ctx['first_day'], ctx['last_day'], RELEASE))
    parts.append('<p class="lead">Two graphs, the SQL behind them and three ideas to move daily active users. '
                 'Generated by <code>python analysis.py</code> from <code>answer.sql</code> and '
                 '<code>shiptivity.db</code>.</p>')
    parts.append('</header>')

    parts.append('<div class="kpis">')
    parts.append('<div class="kpi good"><div class="l">avg DAU before</div><div class="v">%.2f</div>'
                 '<div class="s">%d days, %s to %s</div></div>'
                 % (ctx['avg_before'], ctx['before_days'], ctx['first_day'], ctx['release_date']))
    parts.append('<div class="kpi good"><div class="l">avg DAU after</div><div class="v">%.2f</div>'
                 '<div class="s">+%.0f%% - the release worked</div></div>'
                 % (ctx['avg_after'], ctx['lift_pct']))
    parts.append('<div class="kpi warn"><div class="l">board actions / day</div><div class="v">%.2f</div>'
                 '<div class="s">only %d of %d days had a move</div></div>'
                 % (ctx['changes_per_day'], ctx['days_with_moves'], ctx['after_days']))
    parts.append('<div class="kpi warn"><div class="l">cards never moved</div><div class="v">%d</div>'
                 '<div class="s">%d%% of all cards sit untouched</div></div>'
                 % (ctx['never_moved'], ctx['never_moved_pct']))
    parts.append('</div>')

    # --- graph 1 ---
    parts.append('<h2>Graph 1 - daily average users before and after the feature change</h2>')
    parts.append('<div class="card figure">')
    parts.append(daily_svg)
    parts.append('<p class="cap">Distinct users who logged in each UTC day (<code>login_history</code>), '
                 'zero-login days included. The dashed lines are the period averages the ticket asks for. '
                 'The Kanban board went live on %s.</p>' % RELEASE)
    parts.append('<table style="margin-top:12px"><thead><tr><th>period</th><th class="n">days</th>'
                 '<th class="n">avg daily active users</th><th class="n">avg sessions / day</th>'
                 '<th class="n">peak DAU</th><th class="n">distinct users</th></tr></thead><tbody>')
    for row in ctx['summary_rows']:
        label = 'before release' if row['period'] == 'before' else 'after release'
        parts.append('<tr><td><b>%s</b></td><td class="n">%d</td><td class="n"><b>%.2f</b></td>'
                     '<td class="n">%.2f</td><td class="n">%d</td><td class="n">%d</td></tr>'
                     % (label, row['days'], row['avg_daily_active_users'],
                        row['avg_sessions_per_day'], row['peak_daily_active_users'],
                        row['distinct_users_in_period']))
    parts.append('</tbody></table></div>')

    # --- graph 2 ---
    parts.append('<h2>Graph 2 - number of status changes by card</h2>')
    parts.append('<div class="card figure">')
    parts.append(cards_svg)
    parts.append('<p class="cap">Top 15 cards by real status changes. Rows where <code>oldStatus IS NULL</code> '
                 'are the card-creation events (one per card, not a user action) and are excluded.</p>')
    parts.append('</div>')
    parts.append('<div class="grid2">')
    parts.append('<div class="card figure"><h3 style="margin-top:0">How many times was each card moved?</h3>%s'
                 '<p class="cap">%d cards have never been moved since launch.</p></div>'
                 % (dist_svg, ctx['never_moved']))
    parts.append('<div class="card"><h3 style="margin-top:0">Where cards move (and where they bounce)</h3>'
                 '<table><thead><tr><th>from</th><th>to</th><th class="n">moves</th>'
                 '<th class="n">share of all events</th></tr></thead><tbody>%s</tbody></table>'
                 '<p class="cap">%d of %d real moves (%.1f%%) go backwards - work that was sent back.</p></div>'
                 % (transition_rows, ctx['backward'], ctx['real_moves'],
                    100.0 * ctx['backward'] / ctx['real_moves']))
    parts.append('</div>')

    # --- sql ---
    parts.append('<h2>The SQL queries</h2>')
    parts.append('<p class="lead">Everything above comes from <code>answer.sql</code> (5 statements, SQLite). '
                 'Run it with <code>sqlite3 ./shiptivity.db &lt; answer.sql</code>. '
                 'Query <b>1a</b> powers graph 1, query <b>2a</b> powers graph 2; '
                 '1b, 2b and 2c are the supporting cuts.</p>')
    parts.append('<pre><code>%s</code></pre>' % sql_block)

    # --- insights ---
    parts.append('<h2>What the data says</h2>')
    parts.append('<div class="card"><ul>')
    for point in ctx['insights']:
        parts.append('<li>%s</li>' % point)
    parts.append('</ul></div>')

    # --- ideas ---
    parts.append('<h2>Three ideas to move daily active users</h2>')
    parts.append('<p class="lead">Format required by the ticket: Hypothesis / Expected impact / '
                 'What the feature is. Sketches are wireframe quality.</p>')
    for idea in ctx['ideas']:
        parts.append('<div class="idea">')
        parts.append('<h3><span class="num">%d</span>%s</h3>' % (idea['n'], esc(idea['title'])))
        parts.append('<dl>')
        parts.append('<dt>Hypothesis</dt><dd>%s</dd>' % idea['hypothesis'])
        parts.append('<dt>Expected impact</dt><dd>%s</dd>' % idea['impact'])
        parts.append('<dt>What the feature is</dt><dd>%s</dd>' % idea['feature'])
        parts.append('</dl>')
        parts.append('<div class="wf"><p class="t">Wireframe</p>%s</div>' % idea['wireframe'])
        parts.append('</div>')

    parts.append('<footer>Generated %s UTC by <code>analysis.py</code> &middot; queries in '
                 '<code>answer.sql</code> &middot; source <code>shiptivity.db</code> '
                 '(restore with <code>sqlite3 shiptivity.db &lt; shiptivity.dump</code>)</footer>'
                 % datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'))
    parts.append('</div></body>\n</html>')
    return '\n'.join(parts)


# --------------------------------------------------------------------------- #
def main():
    with open(SQL_PATH, encoding='utf-8') as handle:
        sql_text = handle.read()

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    statements = split_statements(sql_text)
    results = [run(con, statement) for statement in statements]
    daily = results[0][1]
    summary_rows = results[1][1]
    card_rows = results[2][1]
    distribution = [(r['status_changes'], r['number_of_cards']) for r in results[3][1]]
    transitions = results[4][1]

    before = next(r for r in summary_rows if r['period'] == 'before')
    after = next(r for r in summary_rows if r['period'] == 'after')
    avg_before = before['avg_daily_active_users']
    avg_after = after['avg_daily_active_users']
    lift_pct = (avg_after / avg_before - 1) * 100

    # ---- context numbers the ideas lean on (kept out of answer.sql on purpose) ----
    all_events = one(con, 'SELECT COUNT(*) FROM card_change_history')
    real_moves = one(con, 'SELECT COUNT(*) FROM card_change_history WHERE oldStatus IS NOT NULL')
    days_with_moves = one(con, "SELECT COUNT(*) FROM (SELECT date(timestamp,'unixepoch') d "
                               'FROM card_change_history WHERE oldStatus IS NOT NULL GROUP BY d)')
    after_days = len([r for r in daily if r['day'] >= RELEASE])
    never_moved = next(cards for changes, cards in distribution if changes == 0)
    never_moved_pct = 100.0 * never_moved / sum(cards for _, cards in distribution)
    backward = sum(r['moves'] for r in transitions
                   if (r['from_status'], r['to_status']) in (('in-progress', 'backlog'),
                                                             ('complete', 'in-progress')))
    changes_per_day = real_moves / after_days
    in_progress = one(con, "SELECT COUNT(*) FROM card WHERE status = 'in-progress'")

    # monthly averages, built from the same zero filled series as graph 1
    monthly = {}
    for row in daily:
        monthly.setdefault(row['day'][:7], []).append(row['daily_active_users'])
    full_months = {m: v for m, v in monthly.items() if len(v) >= 28}
    avg_by_month = {m: sum(v) / len(v) for m, v in full_months.items()}
    peak_month = max(avg_by_month, key=avg_by_month.get)
    latest_month = max(avg_by_month)

    last_month_mau = one(con, "SELECT COUNT(DISTINCT user_id) FROM login_history "
                              "WHERE strftime('%Y-%m', login_timestamp, 'unixepoch') = ?", (latest_month,))
    june_users = {r[0] for r in con.execute(
        "SELECT DISTINCT user_id FROM login_history "
        "WHERE date(login_timestamp, 'unixepoch') BETWEEN ? AND '2018-06-30'", (RELEASE,))}
    latest_users = {r[0] for r in con.execute(
        "SELECT DISTINCT user_id FROM login_history "
        "WHERE strftime('%Y-%m', login_timestamp, 'unixepoch') = ?", (latest_month,))}
    retained = 100.0 * len(june_users & latest_users) / len(june_users)

    logins_per_user = [r[0] for r in con.execute('SELECT COUNT(*) FROM login_history GROUP BY user_id')]
    ordered = sorted(logins_per_user, reverse=True)
    top20_share = 100.0 * sum(ordered[:20]) / sum(logins_per_user)
    dormant = sum(1 for c in logins_per_user if c <= 5)
    dau_mau = 100.0 * avg_after / last_month_mau

    insights = [
        '<b>The release worked.</b> Average daily active users went from <b>%.2f</b> to <b>%.2f</b> '
        '(+%.0f%%, %.1fx) after the Kanban board shipped on %s, and monthly actives jumped from 24 in '
        'May to %d in June.' % (avg_before, avg_after, lift_pct, avg_after / avg_before, RELEASE,
                                one(con, "SELECT COUNT(DISTINCT user_id) FROM login_history "
                                         "WHERE strftime('%Y-%m', login_timestamp, 'unixepoch') = '2018-06'")),
        '<b>But the lift is flattening.</b> Best month was %s (%.1f DAU), the latest full month is %s '
        '(%.1f DAU) - a %.0f%% slide off the peak. We acquired the users; we have not built a daily '
        'habit.' % (peak_month, avg_by_month[peak_month], latest_month, avg_by_month[latest_month],
                    100 * (1 - avg_by_month[latest_month] / avg_by_month[peak_month])),
        '<b>Retention is fine, frequency is not.</b> %d of 100 registered users were active in the last '
        'full month (MAU) but only %.2f of them show up on a given day - a DAU/MAU ratio of %.0f%%, so '
        'the average user visits about once a month.' % (last_month_mau, avg_after, dau_mau),
        '<b>The board is used far less than it is viewed.</b> %d real status changes since launch is '
        '<b>%.2f per day</b>, and only %d of %d post-release days (%.0f%%) contain any move at all.'
        % (real_moves, changes_per_day, days_with_moves, after_days,
           100.0 * days_with_moves / after_days),
        '<b>Work stalls.</b> %d of 200 cards (%.0f%%) have never been moved, %d cards are parked in '
        'in-progress, and %.1f%% of real moves go backwards (%d moves were sent back).'
        % (never_moved, never_moved_pct, in_progress, 100.0 * backward / real_moves, backward),
        '<b>Engagement is concentrated.</b> The top 20 users produce %.0f%% of all logins and %d users '
        'have logged in 5 times or fewer in a year - a long tail we can reactivate.'
        % (top20_share, dormant),
    ]

    slide_pct = 100 * (1 - avg_by_month[latest_month] / avg_by_month[peak_month])
    ideas = [
        {
            'n': 1,
            'title': 'Board Pulse - a weekly "what changed" digest (email + in-app banner)',
            'hypothesis': 'Users come back when something pulls them back. Churn is not our problem '
                          '(%.0f%% of last month\'s actives were already active in June) but DAU/MAU is '
                          'only %.0f%%, which means people visit roughly once a month and only when they '
                          'happen to remember. A scheduled, personal summary of board activity creates a '
                          'recurring reason to open the app between sessions.' % (retained, dau_mau),
            'impact': '+20%% on today\'s baseline of %.2f avg DAU - about <b>+%.1f daily active users '
                      'per day</b> and one extra session a week for the %d monthly actives. That is '
                      'enough on its own to undo the %.0f%% slide from the %s peak (%.1f) back to the '
                      'latest month (%.1f).'
                      % (avg_after, 0.2 * avg_after, last_month_mau, slide_pct, peak_month,
                         avg_by_month[peak_month], avg_by_month[latest_month]),
            'feature': 'Every Monday at 9am each user gets an email plus an in-app banner: "3 cards moved '
                       'since your last visit, 2 cards are waiting on you, 5 cards in your lane have been '
                       'idle for 14+ days". Each line deep-links straight to that card on the board, with '
                       'one primary button - <i>Open board</i>. The digest is a plain SQL query (cards '
                       'changed in the last 7 days plus cards assigned to the recipient), so it is a '
                       'one-sprint build with no new UI surface.',
            'wireframe': wireframe_digest(),
        },
        {
            'n': 2,
            'title': 'Idle-card radar - flag stalled cards and offer nudge / archive',
            'hypothesis': 'Cards stop moving because nothing surfaces them: %d of 200 cards (%.0f%%) have '
                          'never been moved, %d cards sit in in-progress, and the whole board records only '
                          '%.2f status changes per day. If stalled work is visible and actionable on the '
                          'board itself, every visit comes with a specific task instead of an empty column.'
                          % (never_moved, never_moved_pct, in_progress, changes_per_day),
            'impact': '+50%% board actions per day (%.2f &rarr; %.2f status changes), clearing the %d '
                      'untouched cards within two weeks, plus an estimated +5-10%% DAU from a visible, '
                      'self-updating reason to open the board.'
                      % (changes_per_day, 1.5 * changes_per_day, never_moved),
            'feature': 'A card with no status change in 14 days gets an amber <i>idle 14d</i> chip. A '
                       'banner above the board lists the worst offenders with two actions - <i>Nudge '
                       'owner</i> (assign and notify) and <i>Archive</i>. Once a week a one-click "revive '
                       'or archive" review walks through the idle cards, so the backlog stays a real '
                       'queue instead of a graveyard.',
            'wireframe': wireframe_stale(),
        },
        {
            'n': 3,
            'title': 'My lane - a personal board with a 3-card daily focus',
            'hypothesis': 'A returning user lands on 200 undifferentiated cards with no obvious next '
                          'action, so the daily habit falls to the %d power users who already generate '
                          '%.0f%% of all logins. A personal default view plus a tiny, finishable daily '
                          'task list makes the first action of every session obvious and short.'
                          % (20, top20_share),
            'impact': 'Lift DAU/MAU from %.0f%% to ~25%%, i.e. <b>about +%.0f daily active users</b> at '
                      'today\'s MAU of %d, and double the board actions taken per session. It is also the '
                      'cleanest fix for the %d users who have logged in 5 times or fewer in a year.'
                      % (dau_mau, 0.25 * last_month_mau - avg_after, last_month_mau, dormant),
            'feature': 'Add an owner to a card. The board defaults to <i>My cards</i> with a "Today" '
                       'panel showing at most 3 cards that need action, each movable with the keys '
                       '<code>1 / 2 / 3</code> (backlog / in progress / complete) - no dragging, no '
                       'scanning. A streak badge shows consecutive days with at least one move, and a '
                       '<i>Board</i> toggle keeps the full shared view one click away.',
            'wireframe': wireframe_mylane(),
        },
    ]

    ctx = {
        'daily': daily,
        'summary_rows': summary_rows,
        'card_rows': card_rows,
        'distribution': distribution,
        'transitions': transitions,
        'all_events': all_events,
        'real_moves': real_moves,
        'avg_before': avg_before,
        'avg_after': avg_after,
        'lift_pct': lift_pct,
        'before_days': before['days'],
        'after_days': after_days,
        'first_day': daily[0]['day'],
        'last_day': daily[-1]['day'],
        'release_date': RELEASE,
        'changes_per_day': changes_per_day,
        'days_with_moves': days_with_moves,
        'never_moved': never_moved,
        'never_moved_pct': never_moved_pct,
        'backward': backward,
        'sql_text': sql_text,
        'insights': insights,
        'ideas': ideas,
    }

    with open(OUT_PATH, 'w', encoding='utf-8') as handle:
        handle.write(build_html(ctx))
    con.close()

    print('queries run      : %d' % len(statements))
    print('days analysed    : %d (%s -> %s)' % (len(daily), daily[0]['day'], daily[-1]['day']))
    print('avg DAU before   : %.2f' % avg_before)
    print('avg DAU after    : %.2f  (+%.1f%%)' % (avg_after, lift_pct))
    print('status changes   : %d real (%.2f/day), %d cards never moved'
          % (real_moves, changes_per_day, never_moved))
    print('best / latest mo : %s %.1f / %s %.1f'
          % (peak_month, avg_by_month[peak_month], latest_month, avg_by_month[latest_month]))
    print('report written   : %s' % OUT_PATH)


if __name__ == '__main__':
    main()
