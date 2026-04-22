"""
Weekly Dashboard Generator
Creates an HTML dashboard with charts showing:
- Incident counts per system
- Fibre incidents per region
- Status breakdown (Resolved / Assigned / Ongoing)
- Timeline of incidents
Uses Plotly (pip install plotly) — generates a single self-contained HTML file.
"""
import os
import json
from datetime import datetime, timedelta
from collections import Counter
from core.database import get_weekly_data, get_all_shifts

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")


def generate_weekly_dashboard(start_date: str = None, end_date: str = None) -> str:
    """
    Generate HTML dashboard for the given week.
    Dates in 'YYYY-MM-DD' format.
    Returns path to the HTML file.
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=6)
        start_date = start_dt.strftime("%Y-%m-%d")

    os.makedirs(EXPORTS_DIR, exist_ok=True)

    sys_incidents, fibre_incidents = get_weekly_data(start_date, end_date)

    # ── Compute stats ─────────────────────────────────────
    total_sys = len(sys_incidents)
    total_fibre = len(fibre_incidents)

    sys_resolved = sum(1 for i in sys_incidents if i.get("status") == "Resolved")
    sys_ongoing = sum(1 for i in sys_incidents if i.get("status") == "Ongoing")
    sys_escalated = sum(1 for i in sys_incidents if i.get("status") == "Escalated")
    sys_assigned = total_sys - sys_resolved - sys_ongoing - sys_escalated

    fibre_resolved = sum(1 for i in fibre_incidents if i.get("report_status") == "Resolved")
    fibre_ongoing = sum(1 for i in fibre_incidents if i.get("report_status") == "Ongoing")
    fibre_assigned = total_fibre - fibre_resolved - fibre_ongoing

    system_counter = Counter(i.get("system_name", "Unknown") for i in sys_incidents)
    region_counter = Counter(i.get("region", "Unknown") for i in fibre_incidents)

    # Build per-day breakdown
    day_sys = Counter()
    day_fibre = Counter()
    for i in sys_incidents:
        day = (i.get("start_time") or i.get("date_time") or "")[:10]
        day_sys[day] += 1
    for i in fibre_incidents:
        day = (i.get("start_time") or i.get("date_reported") or "")[:10]
        day_fibre[day] += 1

    # Build all days in range
    all_days = []
    d = datetime.strptime(start_date, "%Y-%m-%d")
    end_d = datetime.strptime(end_date, "%Y-%m-%d")
    while d <= end_d:
        all_days.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    fmt_label = lambda ds: datetime.strptime(ds, "%Y-%m-%d").strftime("%d %b") if ds else ""

    # ── Build HTML with embedded Plotly ──────────────────
    # We inline the chart data as JSON and use Plotly CDN
    sys_by_system_labels = list(system_counter.keys())
    sys_by_system_values = list(system_counter.values())

    fibre_region_labels = list(region_counter.keys())
    fibre_region_values = list(region_counter.values())

    daily_labels = [fmt_label(d) for d in all_days]
    daily_sys_vals = [day_sys.get(d, 0) for d in all_days]
    daily_fibre_vals = [day_fibre.get(d, 0) for d in all_days]

    # Recent incidents table rows
    recent_sys_rows = ""
    for inc in sorted(sys_incidents, key=lambda x: x.get("date_time", ""), reverse=True)[:10]:
        status_class = {
            "Resolved": "badge-resolved",
            "Ongoing": "badge-ongoing",
            "Escalated": "badge-escalated",
            "Assigned": "badge-assigned",
        }.get(inc.get("status", ""), "badge-assigned")
        recent_sys_rows += f"""
        <tr>
            <td>{inc.get('system_name','')}</td>
            <td>{inc.get('description','')[:60]}</td>
            <td>{inc.get('date_time','')}</td>
            <td>{inc.get('duration','')}</td>
            <td><span class="badge {status_class}">{inc.get('status','')}</span></td>
            <td>{inc.get('agent_name','')}</td>
        </tr>"""

    recent_fibre_rows = ""
    for inc in sorted(fibre_incidents, key=lambda x: x.get("date_reported", ""), reverse=True)[:10]:
        st = inc.get("report_status", "")
        status_class = {"Resolved": "badge-resolved", "Ongoing": "badge-ongoing"}.get(st, "badge-assigned")
        recent_fibre_rows += f"""
        <tr>
            <td>{inc.get('region','')}</td>
            <td>{inc.get('description','')[:60]}</td>
            <td>{inc.get('ref_no','')}</td>
            <td>{inc.get('date_reported','')}</td>
            <td>{inc.get('duration','')}</td>
            <td><span class="badge {status_class}">{st}</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NOC Weekly Dashboard – {start_date} to {end_date}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #f0e040;
    --green: #3fb950; --orange: #f0883e; --red: #f85149; --blue: #58a6ff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'IBM Plex Sans', sans-serif; padding: 24px; }}
  .top-bar {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 32px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }}
  .logo {{ font-family: 'IBM Plex Mono', monospace; font-size: 1.1rem; color: var(--accent); letter-spacing: 2px; }}
  .period {{ font-size: 0.85rem; color: var(--muted); font-family: 'IBM Plex Mono', monospace; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
  .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }}
  .kpi-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
  .kpi-value {{ font-size: 2.2rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }}
  .kpi-sub {{ font-size: 0.75rem; color: var(--muted); margin-top: 4px; }}
  .kpi-accent {{ color: var(--accent); }}
  .kpi-green {{ color: var(--green); }}
  .kpi-orange {{ color: var(--orange); }}
  .kpi-red {{ color: var(--red); }}
  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 32px; }}
  .chart-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
  .chart-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 12px; font-family: 'IBM Plex Mono', monospace; }}
  .full-width {{ grid-column: 1 / -1; }}
  .table-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  .table-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 12px; font-family: 'IBM Plex Mono', monospace; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 8px 12px; color: var(--muted); font-weight: 400; border-bottom: 1px solid var(--border); }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #21262d; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #1c2128; }}
  .badge {{ padding: 2px 8px; border-radius: 3px; font-size: 0.72rem; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }}
  .badge-resolved {{ background: #0d3321; color: var(--green); }}
  .badge-ongoing {{ background: #3d2000; color: var(--orange); }}
  .badge-escalated {{ background: #3d0000; color: var(--red); }}
  .badge-assigned {{ background: #0d2040; color: var(--blue); }}
  .section-label {{ font-size: 1rem; font-weight: 600; margin-bottom: 12px; color: var(--text); }}
</style>
</head>
<body>
<div class="top-bar">
  <div class="logo">◈ NOC OPERATIONS DASHBOARD</div>
  <div class="period">Week: {start_date} → {end_date} &nbsp;|&nbsp; Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}</div>
</div>

<!-- KPI Cards -->
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">System Incidents</div>
    <div class="kpi-value kpi-accent">{total_sys}</div>
    <div class="kpi-sub">{sys_resolved} resolved · {sys_ongoing} ongoing · {sys_escalated} escalated</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Fibre Incidents</div>
    <div class="kpi-value kpi-orange">{total_fibre}</div>
    <div class="kpi-sub">{fibre_resolved} resolved · {fibre_ongoing} ongoing · {fibre_assigned} assigned</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Resolution Rate (Systems)</div>
    <div class="kpi-value kpi-green">{round(sys_resolved/total_sys*100) if total_sys else 0}%</div>
    <div class="kpi-sub">{sys_resolved} of {total_sys} resolved</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Resolution Rate (Fibre)</div>
    <div class="kpi-value kpi-green">{round(fibre_resolved/total_fibre*100) if total_fibre else 0}%</div>
    <div class="kpi-sub">{fibre_resolved} of {total_fibre} resolved</div>
  </div>
</div>

<!-- Charts -->
<div class="charts-grid">
  <div class="chart-card full-width">
    <div class="chart-title">Daily Incident Volume</div>
    <div id="dailyChart"></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">System Incidents by System</div>
    <div id="sysChart"></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Fibre Incidents by Region</div>
    <div id="regionChart"></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">System Incident Status</div>
    <div id="sysStatusChart"></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Fibre Incident Status</div>
    <div id="fibreStatusChart"></div>
  </div>
</div>

<!-- Tables -->
<div class="section-label">Recent System Incidents</div>
<div class="table-card">
  <table>
    <thead><tr><th>System</th><th>Description</th><th>Date/Time</th><th>Duration</th><th>Status</th><th>Agent</th></tr></thead>
    <tbody>{recent_sys_rows or '<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:20px">No system incidents this week</td></tr>'}</tbody>
  </table>
</div>

<div class="section-label">Recent Fibre Incidents</div>
<div class="table-card">
  <table>
    <thead><tr><th>Region</th><th>Description</th><th>Ref No</th><th>Date Reported</th><th>Duration</th><th>Status</th></tr></thead>
    <tbody>{recent_fibre_rows or '<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:20px">No fibre incidents this week</td></tr>'}</tbody>
  </table>
</div>

<script>
const plotConfig = {{responsive: true, displayModeBar: false}};
const plotLayout = {{
  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
  font: {{color: '#8b949e', family: 'IBM Plex Sans', size: 11}},
  margin: {{l:40,r:10,t:10,b:40}},
  xaxis: {{gridcolor: '#21262d', linecolor: '#30363d'}},
  yaxis: {{gridcolor: '#21262d', linecolor: '#30363d'}},
}};

// Daily chart
Plotly.newPlot('dailyChart', [
  {{type:'bar', name:'System Incidents', x:{json.dumps(daily_labels)}, y:{json.dumps(daily_sys_vals)},
    marker:{{color:'#f0e040', opacity:0.85}}}},
  {{type:'bar', name:'Fibre Incidents', x:{json.dumps(daily_labels)}, y:{json.dumps(daily_fibre_vals)},
    marker:{{color:'#f0883e', opacity:0.85}}}}
], {{...plotLayout, barmode:'group', height:200, showlegend:true,
    legend:{{orientation:'h',x:0,y:1.2,font:{{size:10}}}}}}, plotConfig);

// System bar chart
Plotly.newPlot('sysChart', [
  {{type:'bar', orientation:'h', x:{json.dumps(sys_by_system_values)}, y:{json.dumps(sys_by_system_labels)},
    marker:{{color:'#58a6ff'}}}}
], {{...plotLayout, height:250, xaxis:{{...plotLayout.xaxis, title:'Count'}}}}, plotConfig);

// Region bar chart
Plotly.newPlot('regionChart', [
  {{type:'bar', orientation:'h', x:{json.dumps(fibre_region_values)}, y:{json.dumps(fibre_region_labels)},
    marker:{{color:'#3fb950'}}}}
], {{...plotLayout, height:250}}, plotConfig);

// Status pies
Plotly.newPlot('sysStatusChart', [
  {{type:'pie', values:[{sys_resolved},{sys_ongoing},{sys_escalated},{sys_assigned}],
    labels:['Resolved','Ongoing','Escalated','Assigned'],
    marker:{{colors:['#3fb950','#f0883e','#f85149','#58a6ff']}},
    textinfo:'label+percent', hole:0.4}}
], {{...plotLayout, height:220, margin:{{l:10,r:10,t:10,b:10}}}}, plotConfig);

Plotly.newPlot('fibreStatusChart', [
  {{type:'pie', values:[{fibre_resolved},{fibre_ongoing},{fibre_assigned}],
    labels:['Resolved','Ongoing','Assigned'],
    marker:{{colors:['#3fb950','#f0883e','#58a6ff']}},
    textinfo:'label+percent', hole:0.4}}
], {{...plotLayout, height:220, margin:{{l:10,r:10,t:10,b:10}}}}, plotConfig);
</script>
</body>
</html>"""

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = os.path.join(EXPORTS_DIR, f"NOC_Weekly_Dashboard_{start_date}_{end_date}_{ts}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[Dashboard] Saved: {out_path}")
    return out_path
