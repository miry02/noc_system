"""
NOC Report System - Database Layer
Uses SQLite so no external DB server is needed.
Everything is stored in a single local file: noc_data.db
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "noc_data.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like access to rows
    return conn


def init_db():
    """Create all tables if they don't exist yet."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    c = conn.cursor()

    # SHIFTS
    # Each row = one shift worked by one agent.
    # shift_type: Day / Night / Afternoon
    c.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name  TEXT NOT NULL,
            shift_type  TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT,
            notes       TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # SYSTEM INCIDENTS (critical systems/service table)
    # Tracks outages or errors on monitored systems like AMI, INCMS, etc.
    c.execute("""
        CREATE TABLE IF NOT EXISTS system_incidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id        INTEGER NOT NULL,
            description     TEXT NOT NULL,
            system_name     TEXT NOT NULL,
            date_time       TEXT NOT NULL,
            end_time        TEXT,
            duration        TEXT,
            incident_no     TEXT,
            action_to       TEXT,
            status          TEXT DEFAULT 'Ongoing',
            activities      TEXT,
            report_provided INTEGER DEFAULT 0,
            FOREIGN KEY(shift_id) REFERENCES shifts(id)
        )
    """)

    # FIBRE INCIDENTS
    # Fibre faults tracked by calling clients/engineers, NOT auto-detected.
    # region: Nairobi / Western / Central / Coast etc.
    c.execute("""
        CREATE TABLE IF NOT EXISTS fibre_incidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id        INTEGER NOT NULL,
            region          TEXT DEFAULT 'NAIROBI REGION',
            description     TEXT NOT NULL,
            ref_no          TEXT,
            date_reported   TEXT NOT NULL,
            duration        TEXT,
            person_assigned TEXT,
            report_status   TEXT DEFAULT 'Assigned',
            handover_notes  TEXT,
            FOREIGN KEY(shift_id) REFERENCES shifts(id)
        )
    """)

    # SYSTEM UPTIME 
    # Filled in at end of shift. Tracks uptime days and last outage per system.
    c.execute("""
        CREATE TABLE IF NOT EXISTS system_uptime (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id            INTEGER NOT NULL,
            system_name         TEXT NOT NULL,
            uptime_days         INTEGER,
            last_outage_date    TEXT,
            FOREIGN KEY(shift_id) REFERENCES shifts(id)
        )
    """)

    # SCREENSHOTS 
    # Paths to screenshots taken during the shift.
    c.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id    INTEGER NOT NULL,
            filepath    TEXT NOT NULL,
            caption     TEXT,
            system_name TEXT,
            taken_at    TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(shift_id) REFERENCES shifts(id)
        )
    """)

    # TIMELINE ENTRIES 
    # Free-form timestamped notes added during the shift.
    c.execute("""
        CREATE TABLE IF NOT EXISTS timeline (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id    INTEGER NOT NULL,
            timestamp   TEXT NOT NULL,
            note        TEXT NOT NULL,
            FOREIGN KEY(shift_id) REFERENCES shifts(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Database ready at: {DB_PATH}")


# CRUD helpers 

def create_shift(agent_name, shift_type, start_time):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO shifts (agent_name, shift_type, start_time) VALUES (?,?,?)",
        (agent_name, shift_type, start_time)
    )
    shift_id = c.lastrowid
    conn.commit()
    conn.close()
    return shift_id


def close_shift(shift_id, end_time, notes=""):
    conn = get_connection()
    conn.execute(
        "UPDATE shifts SET end_time=?, notes=? WHERE id=?",
        (end_time, notes, shift_id)
    )
    conn.commit()
    conn.close()


def get_shift(shift_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM shifts WHERE id=?", (shift_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_shifts():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM shifts ORDER BY start_time DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_system_incident(shift_id, data: dict):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO system_incidents
        (shift_id, description, system_name, date_time, end_time, duration,
         incident_no, action_to, status, activities, report_provided)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        shift_id, data.get("description"), data.get("system_name"),
        data.get("date_time"), data.get("end_time"), data.get("duration"),
        data.get("incident_no"), data.get("action_to"), data.get("status", "Ongoing"),
        data.get("activities"), 1 if data.get("report_provided") else 0
    ))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_system_incident(incident_id, data: dict):
    conn = get_connection()
    conn.execute("""
        UPDATE system_incidents SET
        description=?, system_name=?, date_time=?, end_time=?, duration=?,
        incident_no=?, action_to=?, status=?, activities=?, report_provided=?
        WHERE id=?
    """, (
        data.get("description"), data.get("system_name"), data.get("date_time"),
        data.get("end_time"), data.get("duration"), data.get("incident_no"),
        data.get("action_to"), data.get("status"), data.get("activities"),
        1 if data.get("report_provided") else 0, incident_id
    ))
    conn.commit()
    conn.close()


def delete_system_incident(incident_id):
    conn = get_connection()
    conn.execute("DELETE FROM system_incidents WHERE id=?", (incident_id,))
    conn.commit()
    conn.close()


def get_system_incidents(shift_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM system_incidents WHERE shift_id=?", (shift_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_fibre_incident(shift_id, data: dict):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO fibre_incidents
        (shift_id, region, description, ref_no, date_reported, duration,
         person_assigned, report_status, handover_notes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        shift_id, data.get("region", "NAIROBI REGION"), data.get("description"),
        data.get("ref_no"), data.get("date_reported"), data.get("duration"),
        data.get("person_assigned"), data.get("report_status", "Assigned"),
        data.get("handover_notes")
    ))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_fibre_incident(incident_id, data: dict):
    conn = get_connection()
    conn.execute("""
        UPDATE fibre_incidents SET
        region=?, description=?, ref_no=?, date_reported=?, duration=?,
        person_assigned=?, report_status=?, handover_notes=?
        WHERE id=?
    """, (
        data.get("region"), data.get("description"), data.get("ref_no"),
        data.get("date_reported"), data.get("duration"), data.get("person_assigned"),
        data.get("report_status"), data.get("handover_notes"), incident_id
    ))
    conn.commit()
    conn.close()


def delete_fibre_incident(incident_id):
    conn = get_connection()
    conn.execute("DELETE FROM fibre_incidents WHERE id=?", (incident_id,))
    conn.commit()
    conn.close()


def get_fibre_incidents(shift_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM fibre_incidents WHERE shift_id=?", (shift_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_uptime(shift_id, uptime_list: list):
    """Replace all uptime records for this shift."""
    conn = get_connection()
    conn.execute("DELETE FROM system_uptime WHERE shift_id=?", (shift_id,))
    for item in uptime_list:
        conn.execute(
            "INSERT INTO system_uptime (shift_id, system_name, uptime_days, last_outage_date) VALUES (?,?,?,?)",
            (shift_id, item["system_name"], item["uptime_days"], item["last_outage_date"])
        )
    conn.commit()
    conn.close()


def get_uptime(shift_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM system_uptime WHERE shift_id=?", (shift_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_screenshot(shift_id, filepath, caption="", system_name=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO screenshots (shift_id, filepath, caption, system_name) VALUES (?,?,?,?)",
        (shift_id, filepath, caption, system_name)
    )
    conn.commit()
    conn.close()


def get_screenshots(shift_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM screenshots WHERE shift_id=?", (shift_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_screenshot(screenshot_id):
    conn = get_connection()
    conn.execute("DELETE FROM screenshots WHERE id=?", (screenshot_id,))
    conn.commit()
    conn.close()


def add_timeline_entry(shift_id, note, timestamp=None):
    if not timestamp:
        timestamp = datetime.now().strftime("%d/%m/%Y@%H%Mhrs")
    conn = get_connection()
    conn.execute(
        "INSERT INTO timeline (shift_id, timestamp, note) VALUES (?,?,?)",
        (shift_id, timestamp, note)
    )
    conn.commit()
    conn.close()


def get_timeline(shift_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM timeline WHERE shift_id=? ORDER BY id", (shift_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_shift():
    """Return the currently open shift (no end_time), or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM shifts WHERE end_time IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_shifts_for_date(date_str: str):
    """Return all shifts that started on a given date (YYYY-MM-DD)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM shifts WHERE DATE(start_time)=? ORDER BY start_time DESC",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# GLOBAL UPTIME DEFAULTS 
# These are shared across all shifts — the "current known" uptime for each system.
# When a new shift opens, it pre-fills from these defaults.
# Agents can override per-shift; the override is also saved back here.

def get_uptime_defaults():
    """Get the latest known uptime for every system (global, not per-shift)."""
    conn = get_connection()
    # Create table if missing (safe migration)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uptime_defaults (
            system_name         TEXT PRIMARY KEY,
            last_outage_date    TEXT DEFAULT ''
        )
    """)
    conn.commit()
    rows = conn.execute("SELECT * FROM uptime_defaults").fetchall()
    conn.close()
    return {r["system_name"]: dict(r) for r in rows}


def save_uptime_defaults(uptime_list: list):
    """Persist last_outage_date globally so next shift pre-fills correctly."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uptime_defaults (
            system_name         TEXT PRIMARY KEY,
            last_outage_date    TEXT DEFAULT ''
        )
    """)
    for item in uptime_list:
        conn.execute("""
            INSERT INTO uptime_defaults (system_name, last_outage_date)
            VALUES (?, ?)
            ON CONFLICT(system_name) DO UPDATE SET last_outage_date=excluded.last_outage_date
        """, (item["system_name"], item.get("last_outage_date", "")))
    conn.commit()
    conn.close()


def reset_screenshot_sequence(shift_id: int):
    """Screenshots are numbered 1..N per shift for display; handled in query."""
    pass  # numbering done at query time, not in DB


def get_screenshots_numbered(shift_id: int):
    """Return screenshots with 1-based display IDs scoped to this shift."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM screenshots WHERE shift_id=? ORDER BY id", (shift_id,)
    ).fetchall()
    conn.close()
    result = []
    for i, r in enumerate(rows, start=1):
        d = dict(r)
        d["display_id"] = i   # always 1, 2, 3... per shift
        result.append(d)
    return result


def add_regional_incident(shift_id, data: dict):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO regional_incidents
        (shift_id, description, ref_no, date_reported, duration,
         person_assigned, report_status, handover_notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        shift_id, data.get("description"), data.get("ref_no"),
        data.get("date_reported"), data.get("duration"),
        data.get("person_assigned"), data.get("report_status", "Assigned"),
        data.get("handover_notes")
    ))
    row_id = c.lastrowid
    conn.commit(); conn.close()
    return row_id


def update_regional_incident(incident_id, data: dict):
    conn = get_connection()
    conn.execute("""
        UPDATE regional_incidents SET
        description=?, ref_no=?, date_reported=?, duration=?,
        person_assigned=?, report_status=?, handover_notes=?
        WHERE id=?
    """, (
        data.get("description"), data.get("ref_no"), data.get("date_reported"),
        data.get("duration"), data.get("person_assigned"),
        data.get("report_status"), data.get("handover_notes"), incident_id
    ))
    conn.commit(); conn.close()


def delete_regional_incident(incident_id):
    conn = get_connection()
    conn.execute("DELETE FROM regional_incidents WHERE id=?", (incident_id,))
    conn.commit(); conn.close()


def get_regional_incidents(shift_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM regional_incidents WHERE shift_id=?", (shift_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_data(start_date: str, end_date: str):
    """Pull all incidents between two dates for weekly dashboard."""
    conn = get_connection()
    system_inc = conn.execute("""
        SELECT si.*, s.agent_name, s.shift_type, s.start_time
        FROM system_incidents si
        JOIN shifts s ON si.shift_id = s.id
        WHERE DATE(s.start_time) BETWEEN ? AND ?
    """, (start_date, end_date)).fetchall()

    fibre_inc = conn.execute("""
        SELECT fi.*, s.agent_name, s.shift_type, s.start_time
        FROM fibre_incidents fi
        JOIN shifts s ON fi.shift_id = s.id
        WHERE DATE(s.start_time) BETWEEN ? AND ?
    """, (start_date, end_date)).fetchall()

    conn.close()
    return [dict(r) for r in system_inc], [dict(r) for r in fibre_inc]
