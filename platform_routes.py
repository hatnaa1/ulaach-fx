from __future__ import annotations

import datetime
import html
from typing import Any

import asyncpg
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

UB_TZ = datetime.timezone(datetime.timedelta(hours=8))

WW_DESC: dict[int, str] = {
    0: "Цэлмэг",
    1: "Бага зэргийн үүлтэй",
    2: "Солигдмол үүлтэй",
    3: "Үүлэрхэг",
    5: "Солигдмол үүлтэй",
    7: "Үүлшинэ",
    9: "Ялимгүй цас",
    10: "Ялимгүй хур тунадас",
    20: "Ялимгүй цас",
    21: "Бага зэргийн бороо",
    22: "Ялимгүй цас",
    23: "Нойтон цас",
    24: "Цас орно",
    60: "Бага зэргийн бороо",
    61: "Бороо орно",
    70: "Цас орно",
    71: "Их цас орно",
    80: "Түр зуурын бороо",
    95: "Аадар бороо, дуу цахилгаан",
}


def _ww_text(code: int | None, cloud_nh: int | None = None) -> str:
    if code is not None and code in WW_DESC:
        return WW_DESC[code]
    if cloud_nh is not None:
        if cloud_nh <= 2:
            return "Цэлмэг"
        if cloud_nh <= 6:
            return "Солигдмол үүлтэй"
        return "Үүлэрхэг"
    return "Тогтуун"


def _aqi_badge(aqi: int | None) -> tuple[str, str]:
    if aqi is None:
        return ("—", "#94a3b8")
    if aqi <= 50:
        return ("Цэвэр", "#34d399")
    if aqi <= 100:
        return ("Хэвийн", "#38bdf8")
    if aqi <= 150:
        return ("Бага зэрэг бохирдолтой", "#fbbf24")
    if aqi <= 200:
        return ("Бохирдолтой", "#f97316")
    return ("Маш их бохирдолтой", "#f43f5e")


def extract_visitor_info(request: Request) -> dict[str, Any]:
    h = request.headers
    ip = (
        h.get("cf-connecting-ip")
        or (h.get("x-forwarded-for", "").split(",")[0].strip() if h.get("x-forwarded-for") else "")
        or h.get("x-real-ip")
        or (request.client.host if request.client else "unknown")
    )
    ip_version = "IPv6" if ":" in ip else "IPv4"
    country = h.get("cf-ipcountry") or "MN"
    city = h.get("cf-ipcity") or ""
    region = h.get("cf-region") or ""
    continent = h.get("cf-ipcontinent") or ""
    asn = h.get("cf-asn") or ""
    colo = ""
    ray = h.get("cf-ray") or ""
    if "-" in ray:
        colo = ray.split("-")[-1]
    proto = h.get("x-forwarded-proto") or request.url.scheme or "https"
    ua = h.get("user-agent") or ""
    accept_lang = h.get("accept-language") or ""
    tls_ver = h.get("cf-visitor") or ""

    return {
        "ip": ip,
        "ip_version": ip_version,
        "country": country,
        "city": city or None,
        "region": region or None,
        "continent": continent or None,
        "asn": asn or None,
        "cf_ray": ray or None,
        "cf_edge_colo": colo or None,
        "protocol": proto.upper(),
        "user_agent": ua,
        "accept_language": accept_lang,
        "tls": tls_ver or None,
        "timestamp_ub": datetime.datetime.now(UB_TZ).strftime("%Y-%m-%d %H:%M:%S"),
    }


def _common_head(title: str, active_site: str) -> str:
    def _cls(s: str) -> str:
        return "nav-pill active" if s == active_site else "nav-pill"

    return f"""<!DOCTYPE html>
<html lang="mn">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #090d16;
      --bg-panel: #0f1523;
      --bg-code: #070a12;
      --border: #1e293b;
      --border-strong: #334155;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --dim: #64748b;
      --accent: #38bdf8;
      --green: #34d399;
      --amber: #fbbf24;
      --purple: #a78bfa;
      --sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      color: var(--text);
      background-color: var(--bg);
      background-image:
        linear-gradient(to right, rgba(30, 41, 59, 0.25) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(30, 41, 59, 0.25) 1px, transparent 1px);
      background-size: 32px 32px;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .topbar {{
      position: sticky;
      top: 0;
      z-index: 40;
      backdrop-filter: blur(12px);
      background: rgba(9, 13, 22, 0.88);
      border-bottom: 1px solid var(--border);
    }}
    .topbar-inner {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-family: var(--mono);
      font-weight: 700;
      font-size: 14px;
      color: #f8fafc;
      letter-spacing: -0.02em;
      text-decoration: none !important;
    }}
    .brand-dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 10px var(--green);
    }}
    .nav-links {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .nav-pill {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
      padding: 6px 11px;
      border-radius: 6px;
      border: 1px solid transparent;
      transition: all 0.15s;
      text-decoration: none !important;
    }}
    .nav-pill:hover {{
      color: #f8fafc;
      background: rgba(30, 41, 59, 0.65);
      border-color: var(--border-strong);
    }}
    .nav-pill.active {{
      color: var(--green);
      background: rgba(16, 185, 129, 0.12);
      border-color: rgba(16, 185, 129, 0.35);
      font-weight: 600;
    }}

    .wrap {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 24px 72px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}
    .hero {{
      background: linear-gradient(180deg, rgba(15, 21, 35, 0.95) 0%, rgba(9, 13, 22, 0.95) 100%);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px 28px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .hero h1 {{
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.025em;
      color: #f8fafc;
    }}
    .hero p {{
      margin: 0;
      font-size: 14px;
      color: var(--muted);
      max-width: 820px;
    }}
    .status-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 4px;
    }}
    .stat-chip {{
      font-family: var(--mono);
      font-size: 12px;
      padding: 5px 11px;
      border-radius: 6px;
      background: var(--bg-code);
      border: 1px solid var(--border);
      color: var(--muted);
    }}
    .stat-chip strong {{ color: #f8fafc; }}

    .section-card {{
      background: var(--bg-panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
    }}
    .section-head {{
      padding: 15px 24px;
      border-bottom: 1px solid var(--border);
      background: rgba(7, 10, 18, 0.55);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .section-title {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #f8fafc;
    }}
    .step-badge {{
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 5px;
      background: rgba(16, 185, 129, 0.14);
      color: var(--green);
      border: 1px solid rgba(16, 185, 129, 0.35);
    }}
    .section-meta {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--dim);
    }}
    .section-body {{
      padding: 22px 24px;
    }}

    .ep-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 18px;
    }}
    .ep-item {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 11px 14px;
      background: var(--bg-code);
      border: 1px solid var(--border);
      border-radius: 8px;
      flex-wrap: wrap;
    }}
    .ep-left {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      flex-wrap: wrap;
    }}
    .method-get {{
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 700;
      padding: 3px 7px;
      border-radius: 4px;
      background: rgba(16, 185, 129, 0.15);
      color: var(--green);
      border: 1px solid rgba(16, 185, 129, 0.35);
    }}
    .ep-url {{
      font-family: var(--mono);
      font-size: 13px;
      color: var(--accent);
      font-weight: 500;
      word-break: break-all;
    }}
    .ep-desc {{
      font-size: 12.5px;
      color: var(--muted);
    }}

    .code-split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    @media (max-width: 900px) {{
      .code-split {{ grid-template-columns: 1fr; }}
    }}
    .code-pane {{
      background: var(--bg-code);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .code-pane-bar {{
      padding: 8px 14px;
      background: rgba(15, 23, 42, 0.75);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-family: var(--mono);
      font-size: 11.5px;
      color: var(--muted);
    }}
    .copy-btn {{
      font-family: var(--mono);
      font-size: 11px;
      padding: 3px 9px;
      border-radius: 4px;
      background: rgba(30, 41, 59, 0.8);
      color: var(--text);
      border: 1px solid var(--border-strong);
      cursor: pointer;
    }}
    .copy-btn:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    pre {{
      margin: 0;
      padding: 14px;
      font-family: var(--mono);
      font-size: 12.5px;
      line-height: 1.55;
      color: #cbd5e1;
      overflow-x: auto;
    }}

    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--bg-code);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 9px 12px;
      border-bottom: 1px solid rgba(30, 41, 59, 0.7);
      text-align: left;
      white-space: nowrap;
    }}
    th {{
      background: rgba(15, 23, 42, 0.85);
      color: var(--muted);
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    tbody tr:hover {{
      background: rgba(30, 41, 59, 0.35);
    }}
    .r {{ text-align: right; }}
    .c {{ text-align: center; }}
    .mono {{ font-family: var(--mono); }}
    .bold {{ font-weight: 600; color: #f8fafc; }}
    .muted {{ color: var(--muted); }}
    .code-pill {{
      display: inline-block;
      font-family: var(--mono);
      font-size: 11.5px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 4px;
      background: rgba(16, 185, 129, 0.13);
      color: var(--green);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }}
    code {{
      font-family: var(--mono);
      font-size: 12px;
      background: rgba(15, 23, 42, 0.9);
      border: 1px solid var(--border);
      padding: 2px 6px;
      border-radius: 4px;
      color: var(--accent);
    }}

    .svc-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
    }}
    @media (max-width: 960px) {{
      .svc-grid {{ grid-template-columns: 1fr; }}
    }}
    .svc-card {{
      background: var(--bg-panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 22px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 16px;
      transition: border-color 0.15s, transform 0.15s;
    }}
    .svc-card:hover {{
      border-color: var(--accent);
      transform: translateY(-2px);
    }}
    .svc-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .svc-domain {{
      font-family: var(--mono);
      font-size: 14px;
      font-weight: 700;
      color: var(--accent);
    }}
    .svc-live {{
      font-family: var(--mono);
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgba(16, 185, 129, 0.14);
      color: var(--green);
      border: 1px solid rgba(16, 185, 129, 0.35);
    }}
    .svc-title {{
      margin: 8px 0 6px;
      font-size: 17px;
      font-weight: 700;
      color: #f8fafc;
    }}
    .svc-desc {{
      margin: 0;
      font-size: 13px;
      color: var(--muted);
    }}
    .svc-metric {{
      background: var(--bg-code);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      font-family: var(--mono);
      font-size: 12.5px;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }}
    .svc-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 9px 14px;
      border-radius: 7px;
      font-family: var(--mono);
      font-size: 12.5px;
      font-weight: 600;
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent);
      border: 1px solid rgba(56, 189, 248, 0.35);
      text-decoration: none !important;
    }}
    .svc-btn:hover {{
      background: rgba(56, 189, 248, 0.22);
      color: #fff;
    }}
    .footer {{
      text-align: center;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--dim);
      padding-top: 8px;
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="https://ulaach.cc">
        <span class="brand-dot"></span>
        <span>ulaach.cc // Developer Platform</span>
      </a>
      <nav class="nav-links">
        <a class="{_cls('portal')}" href="https://ulaach.cc">Portal (ulaach.cc)</a>
        <a class="{_cls('fx')}" href="https://fx.ulaach.cc">FX Rates (fx.ulaach.cc)</a>
        <a class="{_cls('weather')}" href="https://weather.ulaach.cc">Weather &amp; AQI (weather.ulaach.cc)</a>
        <a class="{_cls('tool')}" href="https://tool.ulaach.cc">IP &amp; Net Tools (tool.ulaach.cc)</a>
      </nav>
    </div>
  </header>
"""


def render_tool_page(request: Request) -> HTMLResponse:
    info = extract_visitor_info(request)
    h = request.headers
    header_rows = []
    for k in sorted(h.keys()):
        if k.lower() in ("cookie", "authorization"):
            continue
        header_rows.append(
            f"<tr><td class='mono' style='color:#38bdf8;'>{html.escape(k)}</td>"
            f"<td class='mono' style='white-space:normal;word-break:break-all;'>{html.escape(h.get(k, ''))}</td></tr>"
        )

    loc_str = " / ".join(x for x in [info["country"], info["city"] or "", info["region"] or ""] if x)

    html_doc = (
        _common_head("tool.ulaach.cc — What Is My IP & Network Inspector", "tool")
        + f"""
  <main class="wrap">
    <section class="hero">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
        <div>
          <div class="mono" style="font-size:12px;color:var(--green);margin-bottom:4px;">YOUR PUBLIC CONNECTION IP ({html.escape(info['ip_version'])})</div>
          <h1 id="my-ip" class="mono" style="font-size:34px;color:#38bdf8;letter-spacing:-0.02em;">{html.escape(info['ip'])}</h1>
        </div>
        <button class="copy-btn" style="padding:8px 16px;font-size:12.5px;" data-copy="my-ip">Copy IP Address</button>
      </div>
      <p>Хандаж буй хэрэглэгчийн бодит IP хаяг, улс/бүс нутаг, Cloudflare Edge зангилаа, HTTP Request Header-үүд болон CLI / JSON Developer API.</p>
      <div class="status-strip">
        <span class="stat-chip">IP_VERSION: <strong>{html.escape(info['ip_version'])}</strong></span>
        <span class="stat-chip">LOCATION: <strong>{html.escape(loc_str)}</strong></span>
        <span class="stat-chip">CF_EDGE: <strong>{html.escape(info['cf_edge_colo'] or 'Direct')}</strong></span>
        <span class="stat-chip">PROTOCOL: <strong>{html.escape(info['protocol'])}</strong></span>
        <span class="stat-chip">TIME (UB): <strong>{html.escape(info['timestamp_ub'])}</strong></span>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">01</span> Сүлжээ ба Холболтын Дэлгэрэнгүй (Connection Telemetry)</h2>
        <span class="section-meta">Real-Time Client Inspection</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table>
            <tbody>
              <tr><th style="width:240px;">Public IP Address</th><td class="mono bold" style="color:#38bdf8;font-size:14px;">{html.escape(info['ip'])}</td></tr>
              <tr><th>IP Version</th><td class="mono">{html.escape(info['ip_version'])}</td></tr>
              <tr><th>Country Code</th><td class="mono bold">{html.escape(info['country'])}</td></tr>
              <tr><th>Edge Datacenter (Cloudflare Ray)</th><td class="mono">{html.escape(info['cf_ray'] or 'Direct connection')}</td></tr>
              <tr><th>Transport Protocol</th><td class="mono">{html.escape(info['protocol'])}</td></tr>
              <tr><th>Accept-Language</th><td class="mono">{html.escape(info['accept_language'] or '—')}</td></tr>
              <tr><th>User-Agent</th><td class="mono" style="white-space:normal;word-break:break-word;">{html.escape(info['user_agent'])}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">02</span> Developer CLI &amp; JSON Endpoints</h2>
        <span class="section-meta">Script-friendly IP lookup</span>
      </div>
      <div class="section-body">
        <div class="ep-list">
          <div class="ep-item">
            <div class="ep-left">
              <span class="method-get">GET</span>
              <a class="ep-url" href="/ip" target="_blank">/ip</a>
            </div>
            <span class="ep-desc">Зөвхөн IP хаягийг цэвэр текстээр буцаана (<code>text/plain</code>)</span>
          </div>
          <div class="ep-item">
            <div class="ep-left">
              <span class="method-get">GET</span>
              <a class="ep-url" href="/json" target="_blank">/json</a>
            </div>
            <span class="ep-desc">IP, улс, протокол, User-Agent мэдээллийг JSON бүтцээр буцаана</span>
          </div>
          <div class="ep-item">
            <div class="ep-left">
              <span class="method-get">GET</span>
              <a class="ep-url" href="/headers" target="_blank">/headers</a>
            </div>
            <span class="ep-desc">Илгээгдсэн бүх HTTP Request Header-үүдийг JSON-оор буцаана</span>
          </div>
        </div>
        <div class="code-split">
          <div class="code-pane">
            <div class="code-pane-bar">
              <span>Terminal / CLI Usage</span>
              <button class="copy-btn" data-copy="code-cli">Copy</button>
            </div>
            <pre id="code-cli"># Plain text IP
curl -s https://tool.ulaach.cc/ip

# Full JSON telemetry
curl -s https://tool.ulaach.cc/json</pre>
          </div>
          <div class="code-pane">
            <div class="code-pane-bar">
              <span>200 OK — GET /json</span>
            </div>
            <pre>{html.escape(
f'''{{
  "ip": "{info['ip']}",
  "ip_version": "{info['ip_version']}",
  "country": "{info['country']}",
  "cf_edge_colo": "{info['cf_edge_colo'] or 'Direct'}",
  "protocol": "{info['protocol']}"
}}'''
            )}</pre>
          </div>
        </div>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">03</span> HTTP Request Headers ({len(header_rows)})</h2>
        <span class="section-meta">GET /headers</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th style="width:260px;">Header Name</th><th>Value</th></tr>
            </thead>
            <tbody>
              {''.join(header_rows)}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <div class="footer">tool.ulaach.cc • Ulaach Network &amp; IP Inspector</div>
  </main>
  <script>
    document.querySelectorAll('.copy-btn').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var targetId = btn.getAttribute('data-copy');
        var el = document.getElementById(targetId);
        if (!el) return;
        navigator.clipboard.writeText(el.innerText).then(function() {{
          var old = btn.textContent;
          btn.textContent = 'Copied!';
          setTimeout(function() {{ btn.textContent = old; }}, 1200);
        }});
      }});
    }});
  </script>
</body>
</html>"""
    )
    return HTMLResponse(content=html_doc)


async def fetch_weather_hub_data(wx_pool: asyncpg.Pool) -> dict[str, Any]:
    async with wx_pool.acquire() as conn:
        hubs = await conn.fetch(
            """
            SELECT
                s.sid,
                s.aimag_name,
                s.sum_name,
                s.sta_name,
                s.sta_28,
                s.elev,
                o.obs_time AT TIME ZONE 'Asia/Ulaanbaatar' AS obs_time_ub,
                o.temp,
                o.temp_min,
                o.temp_max,
                o.humidity,
                o.wind_speed,
                o.wind_dir,
                o.pressure_slp,
                o.precip,
                o.ww,
                o.cloud_nh
            FROM wx.stations s
            LEFT JOIN LATERAL (
                SELECT *
                FROM wx.obs_data d
                WHERE d.sid = s.sid
                ORDER BY d.obs_time DESC
                LIMIT 1
            ) o ON true
            WHERE s.sta_28 <> 0
            ORDER BY s.sta_28 ASC, s.sid ASC
            """
        )

        aqi_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (sid)
                sid,
                sname,
                aqi,
                pm25_value,
                pm10_value,
                no2_value,
                so2_value,
                obs_time AT TIME ZONE 'Asia/Ulaanbaatar' AS obs_time_ub
            FROM wx.aqi_data
            WHERE obs_time > NOW() - INTERVAL '48 hours'
            ORDER BY sid, obs_time DESC
            """
        )

        ub_fore = await conn.fetch(
            """
            SELECT DISTINCT ON (f_time)
                f_time AT TIME ZONE 'Asia/Ulaanbaatar' AS f_time_ub,
                pre_code,
                temp,
                temp_feels,
                precip_prob,
                wind
            FROM wx.fore_3hours
            WHERE sid = 292 AND f_time >= NOW() - INTERVAL '3 hours'
            ORDER BY f_time ASC, issued_at DESC
            LIMIT 8
            """
        )

        stats = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM wx.stations) AS total_stations,
                (SELECT COUNT(*) FROM wx.obs_data) AS total_obs,
                (SELECT MAX(obs_time AT TIME ZONE 'Asia/Ulaanbaatar') FROM wx.obs_data) AS latest_obs_ub
            """
        )

    hub_list = []
    for r in hubs:
        hub_list.append(
            {
                "sid": r["sid"],
                "aimag": r["aimag_name"],
                "sum": r["sum_name"],
                "station": r["sta_name"],
                "elev_m": r["elev"],
                "obs_time": r["obs_time_ub"].strftime("%Y-%m-%d %H:%M") if r["obs_time_ub"] else None,
                "temp_c": round(float(r["temp"]), 1) if r["temp"] is not None else None,
                "temp_min_c": round(float(r["temp_min"]), 1) if r["temp_min"] is not None else None,
                "temp_max_c": round(float(r["temp_max"]), 1) if r["temp_max"] is not None else None,
                "humidity_pct": r["humidity"],
                "wind_ms": round(float(r["wind_speed"]), 1) if r["wind_speed"] is not None else None,
                "pressure_hpa": round(float(r["pressure_slp"]), 1) if r["pressure_slp"] is not None else None,
                "condition": _ww_text(r["ww"], r["cloud_nh"]),
            }
        )

    aqi_list = []
    for r in aqi_rows:
        status_label, color = _aqi_badge(r["aqi"])
        aqi_list.append(
            {
                "sid": r["sid"],
                "station": r["sname"],
                "aqi": r["aqi"],
                "status": status_label,
                "color": color,
                "pm25": round(float(r["pm25_value"]), 1) if r["pm25_value"] is not None else None,
                "pm10": round(float(r["pm10_value"]), 1) if r["pm10_value"] is not None else None,
                "obs_time": r["obs_time_ub"].strftime("%Y-%m-%d %H:%M") if r["obs_time_ub"] else None,
            }
        )
    aqi_list.sort(key=lambda x: (x["aqi"] is None, -(x["aqi"] or 0)))

    fore_list = []
    for r in ub_fore:
        fore_list.append(
            {
                "time_ub": r["f_time_ub"].strftime("%m-%d %H:%M") if r["f_time_ub"] else "",
                "temp_c": round(float(r["temp"]), 1) if r["temp"] is not None else None,
                "feels_c": round(float(r["temp_feels"]), 1) if r["temp_feels"] is not None else None,
                "wind_ms": round(float(r["wind"]), 1) if r["wind"] is not None else None,
                "precip_prob": r["precip_prob"],
                "condition": _ww_text(r["pre_code"]),
            }
        )

    return {
        "total_stations": stats["total_stations"] if stats else 321,
        "total_obs": stats["total_obs"] if stats else 0,
        "latest_obs_ub": stats["latest_obs_ub"].strftime("%Y-%m-%d %H:%M") if stats and stats["latest_obs_ub"] else "—",
        "hubs": hub_list,
        "aqi": aqi_list,
        "ub_forecast": fore_list,
    }


async def render_weather_page(wx_pool: asyncpg.Pool) -> HTMLResponse:
    data = await fetch_weather_hub_data(wx_pool)
    ub = next((x for x in data["hubs"] if x["sid"] == 292), data["hubs"][0] if data["hubs"] else {})

    hub_rows = []
    for h in data["hubs"]:
        t_val = f"{h['temp_c']:+.1f}°C" if h["temp_c"] is not None else "—"
        t_color = "#fbbf24" if (h["temp_c"] or 0) > 0 else "#38bdf8"
        tmin_max = f"{h['temp_min_c'] if h['temp_min_c'] is not None else '—'}° / {h['temp_max_c'] if h['temp_max_c'] is not None else '—'}°"
        hub_rows.append(
            f"<tr>"
            f"<td class='c'><span class='code-pill'>{h['sid']}</span></td>"
            f"<td class='bold'>{html.escape(h['station'])}</td>"
            f"<td class='muted'>{html.escape(h['aimag'])}</td>"
            f"<td class='r mono bold' style='color:{t_color};'>{t_val}</td>"
            f"<td class='r mono muted'>{tmin_max}</td>"
            f"<td class='r mono'>{h['humidity_pct'] if h['humidity_pct'] is not None else '—'}%</td>"
            f"<td class='r mono' style='color:#34d399;'>{h['wind_ms'] if h['wind_ms'] is not None else '—'} м/с</td>"
            f"<td>{html.escape(h['condition'])}</td>"
            f"<td class='c mono muted'>{html.escape(h['obs_time'] or '—')}</td>"
            f"</tr>"
        )

    aqi_rows = []
    for a in data["aqi"][:25]:
        aqi_rows.append(
            f"<tr>"
            f"<td class='c mono muted'>{html.escape(str(a['sid']))}</td>"
            f"<td class='bold'>{html.escape(a['station'] or '—')}</td>"
            f"<td class='r mono bold' style='color:{a['color']};'>{a['aqi'] if a['aqi'] is not None else '—'}</td>"
            f"<td><span style='color:{a['color']};font-weight:600;'>{html.escape(a['status'])}</span></td>"
            f"<td class='r mono'>{a['pm25'] if a['pm25'] is not None else '—'}</td>"
            f"<td class='r mono'>{a['pm10'] if a['pm10'] is not None else '—'}</td>"
            f"<td class='c mono muted'>{html.escape(a['obs_time'] or '—')}</td>"
            f"</tr>"
        )

    fore_cards = []
    for f in data["ub_forecast"]:
        t_str = f"{f['temp_c']:+.0f}°C" if f["temp_c"] is not None else "—"
        fore_cards.append(
            f"<div style='background:var(--bg-code);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center;'>"
            f"<div class='mono muted' style='font-size:11.5px;'>{html.escape(f['time_ub'])}</div>"
            f"<div class='mono bold' style='font-size:18px;color:#38bdf8;margin:6px 0;'>{t_str}</div>"
            f"<div style='font-size:12px;color:var(--text);'>{html.escape(f['condition'])}</div>"
            f"<div class='mono muted' style='font-size:11px;margin-top:4px;'>Салхи {f['wind_ms']} м/с</div>"
            f"</div>"
        )

    ub_temp_str = f"{ub.get('temp_c'):+.1f}°C" if ub.get("temp_c") is not None else "—"

    html_doc = (
        _common_head("weather.ulaach.cc — Монгол орны Цаг агаар ба Агаарын чанарын Developer API", "weather")
        + f"""
  <main class="wrap">
    <section class="hero">
      <h1>Монгол орны Цаг агаар ба Агаарын чанарын Developer API</h1>
      <p>Монгол улсын 21 аймаг, {data['total_stations']} сум/станцын цаг тутмын бодит ажиглалт, 3 цагийн урьдчилсан мэдээ болон Улаанбаатар / орон нутгийн агаарын чанарын (AQI, PM2.5, PM10) JSON сервис.</p>
      <div class="status-strip">
        <span class="stat-chip">ULAANBAATAR: <strong>{ub_temp_str} ({html.escape(ub.get('condition', 'Тогтуун'))}, салхи {ub.get('wind_ms', '—')} м/с)</strong></span>
        <span class="stat-chip">STATIONS: <strong>{data['total_stations']} станц</strong></span>
        <span class="stat-chip">LAST_OBS (UB): <strong>{html.escape(data['latest_obs_ub'])}</strong></span>
        <span class="stat-chip">TOTAL_RECORDS: <strong>{data['total_obs']:,}</strong></span>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">01</span> Шууд дуудах Цаг агаарын JSON Endpoint-ууд</h2>
        <span class="section-meta">Content-Type: application/json; charset=utf-8</span>
      </div>
      <div class="section-body">
        <div class="ep-list">
          <div class="ep-item">
            <div class="ep-left">
              <span class="method-get">GET</span>
              <a class="ep-url" href="/weather.json" target="_blank">/weather.json</a>
            </div>
            <span class="ep-desc">Улаанбаатар болон 21 аймгийн төвийн (28 гол станц) яг одоогийн цаг агаар</span>
          </div>
          <div class="ep-item">
            <div class="ep-left">
              <span class="method-get">GET</span>
              <a class="ep-url" href="/weather.json?aimag=Нийслэл" target="_blank">/weather.json?aimag=Нийслэл</a>
            </div>
            <span class="ep-desc">Аймгийн нэрээр эсвэл <code>?sid=292</code> станцын дугаараар бүх сумын станцыг шүүх</span>
          </div>
          <div class="ep-item">
            <div class="ep-left">
              <span class="method-get">GET</span>
              <a class="ep-url" href="/aqi.json" target="_blank">/aqi.json</a>
            </div>
            <span class="ep-desc">Улаанбаатар ба аймгийн төвүүдийн агаарын чанарын индекс (AQI, PM2.5, PM10)</span>
          </div>
          <div class="ep-item">
            <div class="ep-left">
              <span class="method-get">GET</span>
              <a class="ep-url" href="/forecast.json?sid=292" target="_blank">/forecast.json?sid=292</a>
            </div>
            <span class="ep-desc">Улаанбаатар болон гол станцуудын 3 цаг тутмын болон өдрийн урьдчилсан мэдээ</span>
          </div>
        </div>

        <div style="margin-top:16px;">
          <div class="mono muted" style="font-size:12px;margin-bottom:10px;">УЛААНБААТАР ХОТЫН ОЙРЫН ЦАГУУДЫН УРЬДЧИЛСАН МЭДЭЭ (SID=292)</div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;">
            {''.join(fore_cards)}
          </div>
        </div>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">02</span> 21 Аймаг ба Гол Станцуудын Бодит Ажиглалт (28 Станц)</h2>
        <span class="section-meta">Шинэчлэгдсэн: {html.escape(data['latest_obs_ub'])} (GET /weather.json)</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="c">SID</th>
                <th>Станц</th>
                <th>Аймаг / Нийслэл</th>
                <th class="r">Одоогийн хэм</th>
                <th class="r">Доод / Дээд</th>
                <th class="r">Чийгшил</th>
                <th class="r">Салхи</th>
                <th>Төлөв</th>
                <th class="c">Ажигласан цаг</th>
              </tr>
            </thead>
            <tbody>
              {''.join(hub_rows)}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">03</span> Агаарын Чанарын Индекс — AQI / PM2.5 / PM10</h2>
        <span class="section-meta">GET /aqi.json</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="c">Код</th>
                <th>Байршил / Станц</th>
                <th class="r">AQI</th>
                <th>Түвшин</th>
                <th class="r">PM2.5 (μg/m³)</th>
                <th class="r">PM10 (μg/m³)</th>
                <th class="c">Хэмжсэн цаг</th>
              </tr>
            </thead>
            <tbody>
              {''.join(aqi_rows)}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <div class="footer">weather.ulaach.cc • Real-time Meteorological &amp; AQI Data API</div>
  </main>
</body>
</html>"""
    )
    return HTMLResponse(content=html_doc)


async def render_portal_page(request: Request, fx_pool: asyncpg.Pool, wx_pool: asyncpg.Pool) -> HTMLResponse:
    visitor = extract_visitor_info(request)

    # Fetch live FX summary
    usd_rate = "—"
    eur_rate = "—"
    cny_rate = "—"
    mnb_date = "—"
    try:
        async with fx_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT code, rate, rate_date
                FROM mnb_rates
                WHERE rate_date = (SELECT MAX(rate_date) FROM mnb_rates)
                  AND code IN ('USD', 'EUR', 'CNY')
                """
            )
            for r in rows:
                mnb_date = r["rate_date"].isoformat()
                val = f"{float(r['rate']):,.2f} ₮"
                if r["code"] == "USD":
                    usd_rate = val
                elif r["code"] == "EUR":
                    eur_rate = val
                elif r["code"] == "CNY":
                    cny_rate = val
    except Exception:
        pass

    # Fetch live Weather summary for Ulaanbaatar (sid=292)
    ub_temp = "—"
    ub_wind = "—"
    ub_cond = "Тогтуун"
    ub_aqi = "—"
    try:
        async with wx_pool.acquire() as conn:
            wrow = await conn.fetchrow(
                """
                SELECT temp, wind_speed, ww, cloud_nh
                FROM wx.obs_data
                WHERE sid = 292
                ORDER BY obs_time DESC
                LIMIT 1
                """
            )
            if wrow and wrow["temp"] is not None:
                ub_temp = f"{float(wrow['temp']):+.1f}°C"
                ub_wind = f"{float(wrow['wind_speed'] or 0):.1f} м/с"
                ub_cond = _ww_text(wrow["ww"], wrow["cloud_nh"])
            arow = await conn.fetchrow(
                """
                SELECT ROUND(AVG(aqi))::int AS avg_aqi
                FROM (
                    SELECT DISTINCT ON (sid) aqi
                    FROM wx.aqi_data
                    WHERE sid LIKE '12%' AND obs_time > NOW() - INTERVAL '12 hours'
                    ORDER BY sid, obs_time DESC
                ) t
                """
            )
            if arow and arow["avg_aqi"] is not None:
                ub_aqi = str(arow["avg_aqi"])
    except Exception:
        pass

    html_doc = (
        _common_head("ulaach.cc — Open Developer APIs & Public Data Platform", "portal")
        + f"""
  <main class="wrap">
    <section class="hero">
      <div class="mono" style="font-size:12px;color:var(--green);">ULAACH OPEN DATA &amp; DEVELOPER ECOSYSTEM</div>
      <h1>Нээлттэй Өгөгдөл ба Developer API Платформ</h1>
      <p>Монголбанк ба арилжааны банкуудын валютын ханш, Монгол орны 321 станцын цаг агаар ба агаарын чанар (AQI), мөн сүлжээний оношилгооны нээлттэй JSON API болон бэлэн веб виджетүүд.</p>
      <div class="status-strip">
        <span class="stat-chip">STATUS: <strong style="color:#34d399;">ALL SYSTEMS OPERATIONAL</strong></span>
        <span class="stat-chip">USD/MNT: <strong>{html.escape(usd_rate)}</strong></span>
        <span class="stat-chip">ULAANBAATAR: <strong>{html.escape(ub_temp)} ({html.escape(ub_cond)})</strong></span>
        <span class="stat-chip">YOUR_IP: <strong>{html.escape(visitor['ip'])} ({html.escape(visitor['country'])})</strong></span>
      </div>
    </section>

    <div class="svc-grid">
      <!-- 1. FX Service -->
      <div class="svc-card">
        <div>
          <div class="svc-head">
            <span class="svc-domain">fx.ulaach.cc</span>
            <span class="svc-live">● LIVE API</span>
          </div>
          <h2 class="svc-title">Валютын Ханшийн API &amp; Виджет</h2>
          <p class="svc-desc">Монголбанкны 38 валютын өдөр тутмын болон түүхэн албан ханш (<code>?date=YYYY-MM-DD</code>), Хаан, Голомт, ХХБ-ны цаг тутмын ханш ба 5 хэлний (<code>MN/EN/CN/JP/KR</code>) IFrame виджет.</p>
        </div>
        <div class="svc-metric">
          <div style="display:flex;justify-content:space-between;"><span class="muted">USD (Албан ханш):</span><strong style="color:#38bdf8;">{html.escape(usd_rate)}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">EUR (Евро):</span><strong style="color:#34d399;">{html.escape(eur_rate)}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">CNY (Юань):</span><strong style="color:#fbbf24;">{html.escape(cny_rate)}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">Ханшийн огноо:</span><span>{html.escape(mnb_date)}</span></div>
        </div>
        <a class="svc-btn" href="https://fx.ulaach.cc">fx.ulaach.cc руу орох →</a>
      </div>

      <!-- 2. Weather Service -->
      <div class="svc-card">
        <div>
          <div class="svc-head">
            <span class="svc-domain">weather.ulaach.cc</span>
            <span class="svc-live">● LIVE API</span>
          </div>
          <h2 class="svc-title">Цаг Агаар ба Агаарын Чанар (AQI)</h2>
          <p class="svc-desc">Монгол улсын 21 аймаг, 321 сум/станцын цаг тутмын бодит ажиглалт, 3 цагийн урьдчилсан мэдээ болон Улаанбаатар хотын агаарын чанарын (PM2.5, PM10) JSON сервис.</p>
        </div>
        <div class="svc-metric">
          <div style="display:flex;justify-content:space-between;"><span class="muted">Улаанбаатар:</span><strong style="color:#38bdf8;">{html.escape(ub_temp)}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">Төлөв / Салхи:</span><strong style="color:#34d399;">{html.escape(ub_cond)} ({html.escape(ub_wind)})</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">УБ дундаж AQI:</span><strong style="color:#fbbf24;">{html.escape(ub_aqi)}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">Хяналтын станц:</span><span>321 станц</span></div>
        </div>
        <a class="svc-btn" href="https://weather.ulaach.cc">weather.ulaach.cc руу орох →</a>
      </div>

      <!-- 3. Network & IP Tool -->
      <div class="svc-card">
        <div>
          <div class="svc-head">
            <span class="svc-domain">tool.ulaach.cc</span>
            <span class="svc-live">● LIVE TOOL</span>
          </div>
          <h2 class="svc-title">What Is My IP &amp; Network Inspector</h2>
          <p class="svc-desc">Хандаж буй хэрэглэгчийн бодит IPv4 / IPv6 хаяг, улс, Cloudflare Edge зангилаа, HTTP Request Header шинжлэгч болон терминалаас шууд дуудах <code>/ip</code>, <code>/json</code> endpoint.</p>
        </div>
        <div class="svc-metric">
          <div style="display:flex;justify-content:space-between;"><span class="muted">Таны IP хаяг:</span><strong style="color:#38bdf8;">{html.escape(visitor['ip'])}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">Хувилбар / Улс:</span><strong style="color:#34d399;">{html.escape(visitor['ip_version'])} / {html.escape(visitor['country'])}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">Протокол:</span><strong style="color:#fbbf24;">{html.escape(visitor['protocol'])}</strong></div>
          <div style="display:flex;justify-content:space-between;"><span class="muted">CLI дуудалт:</span><span>curl tool.ulaach.cc/ip</span></div>
        </div>
        <a class="svc-btn" href="https://tool.ulaach.cc">tool.ulaach.cc руу орох →</a>
      </div>
    </div>

    <section class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">API</span> Хурдан эхлэх командын сан (Quick Reference)</h2>
        <span class="section-meta">CORS: * • Auth: None</span>
      </div>
      <div class="section-body">
        <div class="code-split">
          <div class="code-pane">
            <div class="code-pane-bar"><span>cURL Examples</span></div>
            <pre># 1. Валютын ханш (Монголбанк + Түүхэн огноо)
curl -s "https://fx.ulaach.cc/xansh.json?currency=USD|EUR&date=2026-10-20"

# 2. Арилжааны 3 банкны ханш
curl -s "https://fx.ulaach.cc/banks.json?bank=Khaan|Golomt|TDB&currency=USD"

# 3. Монгол орны цаг агаар ба AQI
curl -s "https://weather.ulaach.cc/weather.json"
curl -s "https://weather.ulaach.cc/aqi.json"

# 4. Өөрийн IP хаягийг шалгах
curl -s "https://tool.ulaach.cc/ip"</pre>
          </div>
          <div class="code-pane">
            <div class="code-pane-bar"><span>Service Endpoints Summary</span></div>
            <pre>https://fx.ulaach.cc/xansh.json       # MNB 38 currencies (5 languages)
https://fx.ulaach.cc/banks.json       # Khaan, Golomt, TDB hourly rates
https://fx.ulaach.cc/xansh.html       # Multilingual embeddable IFrame
https://weather.ulaach.cc/weather.json # 21 aimags & 321 stations weather
https://weather.ulaach.cc/aqi.json    # Real-time PM2.5 / PM10 / AQI
https://weather.ulaach.cc/forecast.json # 3-hour & daily forecasts
https://tool.ulaach.cc/ip             # Plain-text public IP
https://tool.ulaach.cc/json           # Full connection & header JSON</pre>
          </div>
        </div>
      </div>
    </section>

    <div class="footer">ulaach.cc • Open Data &amp; Developer APIs Platform</div>
  </main>
</body>
</html>"""
    )
    return HTMLResponse(content=html_doc)
