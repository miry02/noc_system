# NOC Report System
### Automated shift reporting for Network Operations Centre

---

## What this does

At the end of every shift, instead of manually writing the Word report from paper notes, you:
1. **Run the app** (double-click `START_NOC_SYSTEM.bat` on Windows)
2. **Fill in incidents** during the shift — system incidents, fibre incidents, uptime
3. **Attach screenshots** from your monitoring systems
4. Click **Generate & Send** — the report is built and emailed automatically

---

## Requirements

- **Python 3.9 or newer** — download from https://python.org (free)
- **Internet connection** only for sending email (report generation works offline)

---

## Installation (one time only)

### Windows
1. Install Python 3.9+ from https://python.org  
   Check "Add Python to PATH" during install
2. Copy the `noc_system` folder to your desktop or any folder
3. Double-click `START_NOC_SYSTEM.bat`  
   It will install dependencies and launch automatically.

### Linux / Mac
```bash
cd noc_system
chmod +x start_noc.sh
./start_noc.sh
```

---

## How to use (shift workflow)

### 1. Start of shift → **Shift tab**
- Enter your name
- Select shift type (Day / Afternoon / Night)
- Click **Start Shift**

Your shift is now tracked. The app saves to a local database file — if you close and reopen the app, you can **Resume** your shift.

### 2. During shift → fill in as incidents happen

**System Incidents tab**
- Log any outage or error on monitored systems (AMI, INCMS, PREPAID, etc.)
- Fields: System name, date/time, end time, incident number, who it was assigned to, status
- Paste your handover notes in the "Activities" box
- Tick "Incident Report Provided" if one was filed

**Fibre Incidents tab**
- Log fibre faults you're following up by phone/WhatsApp with engineers
- Use **Stamp Timestamp** button to auto-insert the current time into handover notes
  (e.g. `14/04/2026@1456hrs: `)
- Select the region, fill in the LAN Support ref number

**System Uptime tab**
- Fill in uptime days and last outage date for each system at end of shift

**Screenshots tab**
- Click **Add Screenshot** and browse to your system screenshots
- Label each one with the system name (e.g. "KPLC Postpaid Service")
- These get embedded in the report AND are tracked in the database

### 3. End of shift → **Generate & Send tab**
- Select your shift from the dropdown
- Click **Generate & Send**
- The report is created as a `.docx` file and emailed to all configured recipients

The report matches the standard format:
- Header: Date / Shift / Agent
- Section 1: System Incidents table (yellow headers)
- Section 2: Fibre Incidents by region (orange region headers)
- Section 3: System Uptime table
- Attached screenshots

### 4. Weekly dashboard → **Weekly Dashboard tab**
- Set the date range (defaults to last 7 days)
- Click **Generate Dashboard**
- Click **Open in Browser** — an interactive HTML dashboard opens showing:
  - Total incidents per week
  - Resolution rates
  - Incidents per system (bar chart)
  - Fibre incidents by region
  - Status breakdown (pie charts)
  - Daily volume trend chart
  - Recent incidents tables

---

## Email setup (one time only)

Go to **Settings tab**:

| Field | Value |
|-------|-------|
| SMTP Host | `smtp.gmail.com` |
| SMTP Port | `587` |
| Sender Email | Your Gmail address |
| App Password | See below |

**For Gmail App Password:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Search for "App Passwords"
4. Create one named "NOC Report"
5. Paste the 16-character password here

Add recipients one per line (supervisors, head of fibre, managers etc.)

Click **🧪 Test Connection** to verify before using in production.

---

## File locations

After running the app, these folders are created:

```
noc_system/
├── data/
│   ├── noc_data.db        ← All shift data (never delete this!)
│   └── email_config.json  ← Email credentials
├── reports/               ← Generated .docx reports
├── exports/               ← Generated weekly dashboards (.html)
└── screenshots/           ← (optional) copy screenshots here
```

**Back up `noc_data.db` regularly** — it contains all historical shift data for quarterly reviews.

---

## Common issues

**"Python not found"** → Install Python from python.org, tick "Add to PATH"

**Email fails with "Authentication"** → Use App Password, not your regular Gmail password

**Report looks empty** → Make sure you selected the correct shift in "Generate & Send"

**Screenshots not in report** → The file path must still exist on disk when you generate

---

## For quarterly reviews

The SQLite database stores all incidents with full history. Management can:
1. Use **Weekly Dashboard** with a wider date range (e.g. 90 days)
2. Filter by status, system, or region in the dashboard tables
3. Or access the `noc_data.db` file directly in any SQLite viewer (free tool: DB Browser for SQLite)
