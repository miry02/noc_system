
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os, sys, json, threading, webbrowser, subprocess, re
from datetime import datetime, date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.database import (
    init_db, create_shift, close_shift, get_shift, get_all_shifts, get_active_shift,
    get_shifts_for_date,
    add_system_incident, update_system_incident, delete_system_incident, get_system_incidents,
    add_regional_incident, update_regional_incident, delete_regional_incident, get_regional_incidents,
    add_fibre_incident, update_fibre_incident, delete_fibre_incident, get_fibre_incidents,
    save_uptime, get_uptime, get_uptime_defaults, save_uptime_defaults,
    add_screenshot, get_screenshots_numbered, delete_screenshot,
)
from core.email_sender import load_config, save_config, send_report
from core.dashboard import generate_weekly_dashboard

BG      = "#0d1117"
SURFACE = "#161b22"
BORDER  = "#30363d"
TEXT    = "#e6edf3"
MUTED   = "#8b949e"
ACCENT  = "#f0e040"
GREEN   = "#3fb950"
ORANGE  = "#f0883e"
RED     = "#f85149"
BLUE    = "#58a6ff"

SYSTEMS = ["AMI","INCMS","INSMM","USSD","CONTACT CENTRE","PREPAID","POSTPAID","TOKEN TRACKER","IPMP","SAP","OTHER"]
REGIONS = ["NAIROBI REGION","WESTERN REGION","CENTRAL REGION","COAST REGION","NORTH RIFT REGION","SOUTH RIFT REGION","NORTHEASTERN REGION"]
SHIFTS  = ["Day: 0700hrs to 1500hrs","Afternoon: 1500hrs to 2300hrs","Night: 2300hrs to 0700hrs"]
STATUSES       = ["Assigned","Ongoing","Resolved","Escalated","Ongoing Degradation"]
FIBRE_STATUSES = ["Assigned","Ongoing","Resolved","Ongoing Degradation"]

def calc_uptime_days(s):
    if not s or not s.strip(): return ""
    c = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', s.strip(), flags=re.IGNORECASE)
    for fmt in ["%d %b %Y","%d %B %Y","%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%B %d %Y","%b %d %Y"]:
        try:
            dt = datetime.strptime(c.strip(), fmt).date()
            return str(max((date.today()-dt).days, 0))
        except: pass
    return ""


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NOC Report System")
        self.geometry("1160x780")
        self.minsize(960, 660)
        self.configure(bg=BG)
        self.current_shift_id = None
        self._load_last_shift()
        self._build_ui()

    def _load_last_shift(self):
        p = os.path.join(BASE_DIR, "data", "session.json")
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                sid = d.get("shift_id")
                if sid:
                    s = get_shift(sid)
                    if s and not s.get("end_time"):
                        self.current_shift_id = sid
            except: pass

    def _save_session(self):
        p = os.path.join(BASE_DIR, "data", "session.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump({"shift_id": self.current_shift_id}, open(p, "w"))

    def _build_ui(self):
        top = tk.Frame(self, bg=SURFACE, pady=10, padx=16)
        top.pack(fill="x", side="top")
        tk.Label(top, text="◈ NOC REPORT SYSTEM", bg=SURFACE, fg=ACCENT,
                 font=("Courier", 13, "bold")).pack(side="left")
        self.shift_label = tk.Label(top, text="No active shift", bg=SURFACE, fg=MUTED,
                                    font=("Courier", 9))
        self.shift_label.pack(side="right", padx=8)
        self._update_shift_label()

        s = ttk.Style(); s.theme_use("clam")
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED,
                    padding=[10, 6], font=("Helvetica", 8))
        s.map("TNotebook.Tab", background=[("selected", ACCENT)],
              foreground=[("selected", "#000000")])

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_shift    = self._mt("Shift")
        self.tab_sys      = self._mt("System Incidents")
        self.tab_regional = self._mt("Regional Networks")
        self.tab_fibre    = self._mt("Fibre Incidents")
        self.tab_uptime   = self._mt("System Uptime")
        self.tab_screens  = self._mt("Screenshots")
        self.tab_generate = self._mt("Generate & Send")
        self.tab_weekly   = self._mt("Weekly Dashboard")
        self.tab_settings = self._mt("Settings")

        self._build_shift_tab()
        self._build_sys_tab()
        self._build_regional_tab()
        self._build_fibre_tab()
        self._build_uptime_tab()
        self._build_screenshots_tab()
        self._build_generate_tab()
        self._build_weekly_tab()
        self._build_settings_tab()

    def _mt(self, label):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text=f"  {label}  ")
        return f

    def _update_shift_label(self):
        if self.current_shift_id:
            s = get_shift(self.current_shift_id)
            if s:
                self.shift_label.config(
                    text=f"● Shift #{s['id']}: {s['agent_name']} | {s['shift_type']} | {s['start_time'][11:16]}",
                    fg=GREEN)
                return
        self.shift_label.config(text="No active shift", fg=MUTED)

    # ── Clear all forms when a new shift starts ───────────
    def _clear_all_forms(self):
        """Reset every input form so a new shift starts completely blank.
        Uptime dates are intentionally NOT cleared — they pre-fill from globals."""
        # System incidents form
        for key, var in self.si_vars.items():
            if key == "system_name": var.set(SYSTEMS[0])
            elif key == "status":    var.set(STATUSES[0])
            elif key == "date_time": var.set(datetime.now().strftime("%d/%m/%Y@%H%Mhrs"))
            else:                    var.set("")
        self.si_report_var.set(False)
        self.si_activities.delete("1.0", "end")
        self._selected_sys_id = None
        self._refresh_sys_list()

        # Regional networks form
        for key, var in self.ri_vars.items():
            if key == "report_status": var.set(FIBRE_STATUSES[0])
            elif key == "date_reported": var.set(datetime.now().strftime("%d/%m/%Y@%H%Mhrs"))
            else: var.set("")
        self.ri_desc.delete("1.0", "end")
        self.ri_notes.delete("1.0", "end")
        self._selected_ri_id = None
        self._refresh_regional_list()

        # Fibre incidents form
        for key, var in self.fi_vars.items():
            if key == "region":        var.set(REGIONS[0])
            elif key == "report_status": var.set(FIBRE_STATUSES[0])
            elif key == "date_reported": var.set(datetime.now().strftime("%d/%m/%Y@%H%Mhrs"))
            else: var.set("")
        self.fi_desc.delete("1.0", "end")
        self.fi_notes.delete("1.0", "end")
        self._selected_fibre_id = None
        self._refresh_fibre_list()

        # Screenshots
        self._refresh_screenshots()

    # TAB 1 – SHIFT
    def _build_shift_tab(self):
        card = self._card(self.tab_shift, "Start / End Shift")

        r = tk.Frame(card, bg=SURFACE); r.pack(fill="x", pady=4)
        tk.Label(r, text="Agent Name:", bg=SURFACE, fg=TEXT, width=14,
                 anchor="w", font=("Helvetica", 9)).pack(side="left")
        self.agent_var = tk.StringVar()
        tk.Entry(r, textvariable=self.agent_var, bg=BORDER, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Helvetica", 10),
                 width=30).pack(side="left", padx=4)

        r2 = tk.Frame(card, bg=SURFACE); r2.pack(fill="x", pady=4)
        tk.Label(r2, text="Shift:", bg=SURFACE, fg=TEXT, width=14,
                 anchor="w", font=("Helvetica", 9)).pack(side="left")
        self.shift_var = tk.StringVar(value=SHIFTS[0])
        ttk.Combobox(r2, textvariable=self.shift_var, values=SHIFTS,
                     state="readonly", width=35).pack(side="left", padx=4)

        br = tk.Frame(card, bg=SURFACE); br.pack(pady=10)
        self._btn(br, "▶  Start Shift", self._start_shift, GREEN).pack(side="left", padx=6)
        self._btn(br, "■  End Shift",   self._end_shift,   RED).pack(side="left", padx=6)

        self.shift_info_label = tk.Label(card, text="", bg=SURFACE, fg=MUTED,
                                         font=("Courier", 9), justify="left")
        self.shift_info_label.pack(pady=4)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=8)
        tk.Label(card, text="Shift History", bg=SURFACE, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(anchor="w")

        cols = ("ID","Date","Agent","Shift","Start","End")
        self.shift_tree = ttk.Treeview(card, columns=cols, show="headings", height=8)
        for c, w in zip(cols, [50,100,160,220,75,75]):
            self.shift_tree.heading(c, text=c); self.shift_tree.column(c, width=w)
        self.shift_tree.pack(fill="x", pady=4)
        self._style_tree(self.shift_tree)

        rr = tk.Frame(card, bg=SURFACE); rr.pack()
        self._btn(rr, "↩  Resume Selected Shift", self._resume_shift, BLUE).pack()

        self._refresh_shift_history()
        self._refresh_shift_info()

    def _start_shift(self):
        name = self.agent_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Please enter your name."); return
        active = get_active_shift()
        if active:
            messagebox.showerror("Shift Already Active",
                f"Shift #{active['id']} for {active['agent_name']} is still active.\n"
                f"End that shift first before starting a new one.")
            return
        st = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.current_shift_id = create_shift(name, self.shift_var.get(), st)
        self._save_session()
        self._update_shift_label()
        self._refresh_shift_history()
        self._refresh_shift_info()
        self._clear_all_forms()   # ← blank every form for the new shift
        self._load_uptime()       # ← reload uptime defaults for the new shift
        messagebox.showinfo("Shift Started", f"Shift #{self.current_shift_id} started for {name}.")

    def _end_shift(self):
        if not self.current_shift_id:
            messagebox.showwarning("No Shift", "No active shift to end."); return
        notes = simpledialog.askstring("Shift Notes", "Final handover notes? (optional)", parent=self)
        et = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        close_shift(self.current_shift_id, et, notes or "")
        messagebox.showinfo("Shift Ended",
            f"Shift #{self.current_shift_id} closed.\n\nGo to 'Generate & Send'.")
        self.current_shift_id = None
        self._save_session(); self._update_shift_label()
        self._refresh_shift_history(); self._refresh_shift_info()

    def _resume_shift(self):
        sel = self.shift_tree.selection()
        if not sel: return
        sid = int(self.shift_tree.item(sel[0])["values"][0])
        s = get_shift(sid)
        if not s: return
        if s.get("end_time"):
            messagebox.showwarning("Ended", "That shift has already been closed."); return
        self.current_shift_id = sid
        self._save_session(); self._update_shift_label(); self._refresh_shift_info()
        # Load that shift's data into the forms
        self._refresh_sys_list(); self._refresh_regional_list()
        self._refresh_fibre_list(); self._refresh_screenshots()
        self._load_uptime()
        messagebox.showinfo("Resumed", f"Resumed shift #{sid} for {s['agent_name']}")

    def _refresh_shift_history(self):
        for r in self.shift_tree.get_children(): self.shift_tree.delete(r)
        for s in get_all_shifts()[:20]:
            end = s["end_time"][11:16] if s.get("end_time") else "● Active"
            self.shift_tree.insert("", "end", values=(
                s["id"], s["start_time"][:10], s["agent_name"],
                s["shift_type"], s["start_time"][11:16], end))

    def _refresh_shift_info(self):
        if self.current_shift_id:
            s = get_shift(self.current_shift_id)
            if s:
                self.shift_info_label.config(
                    text=f"Active: Shift #{s['id']} | {s['agent_name']} | {s['shift_type']} | Started {s['start_time'][11:16]}")
                return
        self.shift_info_label.config(text="No active shift")

    # TAB 2 – SYSTEM INCIDENTS
    def _build_sys_tab(self):
        card = self._card(self.tab_sys, "System Incidents (Outages / Errors on Monitored Systems)")
        fm = tk.Frame(card, bg=SURFACE); fm.pack(fill="x", pady=4)
        self.si_vars = {}

        tk.Label(fm, text="System:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="w", width=12).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.si_vars["system_name"] = tk.StringVar(value=SYSTEMS[0])
        ttk.Combobox(fm, textvariable=self.si_vars["system_name"], values=SYSTEMS, state="readonly", width=18).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Incident No:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="w", width=12).grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.si_vars["incident_no"] = tk.StringVar()
        tk.Entry(fm, textvariable=self.si_vars["incident_no"], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=18).grid(row=0, column=3, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Description:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.si_vars["description"] = tk.StringVar()
        tk.Entry(fm, textvariable=self.si_vars["description"], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=74).grid(row=1, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        for key, label, default, r, c in [
            ("date_time","Date/Time:", datetime.now().strftime("%d/%m/%Y@%H%Mhrs"), 2, 0),
            ("end_time",  "End Time:",  "", 2, 2),
            ("duration",  "Duration:",  "", 3, 0),
            ("action_to", "Action To:", "", 3, 2)]:
            tk.Label(fm, text=label, bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=r, column=c, sticky="w", padx=4, pady=2)
            self.si_vars[key] = tk.StringVar(value=default)
            tk.Entry(fm, textvariable=self.si_vars[key], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=22).grid(row=r, column=c+1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Status:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=4, column=0, sticky="w", padx=4, pady=2)
        self.si_vars["status"] = tk.StringVar(value=STATUSES[0])
        ttk.Combobox(fm, textvariable=self.si_vars["status"], values=STATUSES, state="readonly", width=22).grid(row=4, column=1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Handover Notes:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="nw").grid(row=5, column=0, sticky="nw", padx=4, pady=2)
        self.si_activities = tk.Text(fm, bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=74, height=4, font=("Helvetica",9))
        self.si_activities.grid(row=5, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        sr = tk.Frame(fm, bg=SURFACE); sr.grid(row=6, column=1, sticky="w", padx=4)
        self._btn(sr, "⏱ Stamp Timestamp", self._stamp_sys_ts, ORANGE).pack(side="left")
        self.si_report_var = tk.BooleanVar()
        tk.Checkbutton(sr, text="Incident Report Provided", variable=self.si_report_var,
                       bg=SURFACE, fg=TEXT, selectcolor=BORDER, activebackground=SURFACE,
                       font=("Helvetica",8)).pack(side="left", padx=12)

        br = tk.Frame(card, bg=SURFACE); br.pack(pady=6)
        self._btn(br, "+ Add",            self._add_sys_incident,    ACCENT).pack(side="left", padx=4)
        self._btn(br, "✎ Update Selected", self._update_sys_incident, BLUE).pack(side="left", padx=4)
        self._btn(br, "✕ Delete Selected", self._delete_sys_incident, RED).pack(side="left", padx=4)
        self._btn(br, "⟳ Refresh",         self._refresh_sys_list,   MUTED).pack(side="left", padx=4)

        cols = ("ID","System","Description","Date/Time","Duration","Status","Incident No","Handover Notes")
        self.sys_tree = ttk.Treeview(card, columns=cols, show="headings", height=7)
        for c, w in zip(cols, [40,90,200,130,70,80,80,300]):
            self.sys_tree.heading(c, text=c); self.sys_tree.column(c, width=w, stretch=(c=="Handover Notes"))
        self.sys_tree.pack(fill="x", pady=4); self._style_tree(self.sys_tree)
        self.sys_tree.bind("<<TreeviewSelect>>", self._on_sys_select)
        self._selected_sys_id = None

    def _stamp_sys_ts(self):
        ts = datetime.now().strftime("%d/%m/%Y@%H%Mhrs")
        self.si_activities.insert("end", f"\n{ts}: "); self.si_activities.see("end")

    def _add_sys_incident(self):
        if not self._require_shift(): return
        data = {k: v.get() for k, v in self.si_vars.items()}
        data["activities"] = self.si_activities.get("1.0", "end-1c")
        data["report_provided"] = self.si_report_var.get()
        add_system_incident(self.current_shift_id, data)
        self._refresh_sys_list(); messagebox.showinfo("Added", "System incident added.")

    def _update_sys_incident(self):
        if not self._selected_sys_id:
            messagebox.showwarning("Select", "Select an incident first."); return
        data = {k: v.get() for k, v in self.si_vars.items()}
        data["activities"] = self.si_activities.get("1.0", "end-1c")
        data["report_provided"] = self.si_report_var.get()
        update_system_incident(self._selected_sys_id, data); self._refresh_sys_list()

    def _delete_sys_incident(self):
        if not self._selected_sys_id: return
        if messagebox.askyesno("Confirm", "Delete this incident?"):
            delete_system_incident(self._selected_sys_id)
            self._selected_sys_id = None; self._refresh_sys_list()

    def _on_sys_select(self, _):
        sel = self.sys_tree.selection()
        if not sel: return
        inc_id = self.sys_tree.item(sel[0])["values"][0]; self._selected_sys_id = inc_id
        if not self.current_shift_id: return
        inc = next((i for i in get_system_incidents(self.current_shift_id) if i["id"] == inc_id), None)
        if inc:
            for k, v in self.si_vars.items(): v.set(inc.get(k, "") or "")
            self.si_report_var.set(bool(inc.get("report_provided", 0)))
            self.si_activities.delete("1.0", "end"); self.si_activities.insert("1.0", inc.get("activities", "") or "")

    def _refresh_sys_list(self):
        for r in self.sys_tree.get_children(): self.sys_tree.delete(r)
        if not self.current_shift_id: return
        for inc in get_system_incidents(self.current_shift_id):
            notes = (inc.get("activities","") or "").replace("\n"," ").strip()[:80]
            self.sys_tree.insert("", "end", values=(
                inc["id"], inc.get("system_name",""), inc.get("description","")[:50],
                inc.get("date_time",""), inc.get("duration",""),
                inc.get("status",""), inc.get("incident_no",""), notes))

    # TAB 3 – REGIONAL NETWORKS
    def _build_regional_tab(self):
        card = self._card(self.tab_regional, "Regional Networks (Network issues at customer offices/premises)")
        tk.Label(card,
                 text="Log network unavailability, intermittent issues, and fiber-related downtime at regional offices.",
                 bg=SURFACE, fg=MUTED, font=("Helvetica", 9)).pack(anchor="w", pady=(0,6))

        fm = tk.Frame(card, bg=SURFACE); fm.pack(fill="x", pady=4)
        self.ri_vars = {}

        tk.Label(fm, text="Ref No:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="w", width=14).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.ri_vars["ref_no"] = tk.StringVar()
        tk.Entry(fm, textvariable=self.ri_vars["ref_no"], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=18).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Date Reported:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.ri_vars["date_reported"] = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y@%H%Mhrs"))
        tk.Entry(fm, textvariable=self.ri_vars["date_reported"], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=22).grid(row=0, column=3, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Description:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="nw").grid(row=1, column=0, sticky="nw", padx=4, pady=2)
        self.ri_desc = tk.Text(fm, bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=74, height=3, font=("Helvetica",9))
        self.ri_desc.grid(row=1, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        tk.Label(fm, text="Duration:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self.ri_vars["duration"] = tk.StringVar()
        tk.Entry(fm, textvariable=self.ri_vars["duration"], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=18).grid(row=2, column=1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Person Assigned:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=2, column=2, sticky="w", padx=4, pady=2)
        self.ri_vars["person_assigned"] = tk.StringVar()
        tk.Entry(fm, textvariable=self.ri_vars["person_assigned"], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=22).grid(row=2, column=3, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Status:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=3, column=0, sticky="w", padx=4, pady=2)
        self.ri_vars["report_status"] = tk.StringVar(value=FIBRE_STATUSES[0])
        ttk.Combobox(fm, textvariable=self.ri_vars["report_status"], values=FIBRE_STATUSES, state="readonly", width=20).grid(row=3, column=1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Handover Notes:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="nw").grid(row=4, column=0, sticky="nw", padx=4, pady=2)
        self.ri_notes = tk.Text(fm, bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=74, height=5, font=("Helvetica",9))
        self.ri_notes.grid(row=4, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        nr = tk.Frame(fm, bg=SURFACE); nr.grid(row=5, column=1, sticky="w", padx=4)
        self._btn(nr, "⏱ Stamp Timestamp", self._stamp_ri_ts, ORANGE).pack(side="left")

        br = tk.Frame(card, bg=SURFACE); br.pack(pady=6)
        self._btn(br, "+ Add",            self._add_regional,    ACCENT).pack(side="left", padx=4)
        self._btn(br, "✎ Update Selected", self._update_regional, BLUE).pack(side="left", padx=4)
        self._btn(br, "✕ Delete Selected", self._delete_regional, RED).pack(side="left", padx=4)
        self._btn(br, "⟳ Refresh",         self._refresh_regional_list, MUTED).pack(side="left", padx=4)

        cols = ("ID","Description","Ref No","Date Reported","Duration","Assigned","Status")
        self.ri_tree = ttk.Treeview(card, columns=cols, show="headings", height=7)
        for c, w in zip(cols, [40,300,80,130,70,120,100]):
            self.ri_tree.heading(c, text=c); self.ri_tree.column(c, width=w)
        self.ri_tree.pack(fill="x", pady=4); self._style_tree(self.ri_tree)
        self.ri_tree.bind("<<TreeviewSelect>>", self._on_ri_select)
        self._selected_ri_id = None

    def _stamp_ri_ts(self):
        ts = datetime.now().strftime("%d/%m/%Y@%H%Mhrs")
        self.ri_notes.insert("end", f"\n{ts}: "); self.ri_notes.see("end")

    def _add_regional(self):
        if not self._require_shift(): return
        data = {k: v.get() for k, v in self.ri_vars.items()}
        data["description"]    = self.ri_desc.get("1.0", "end-1c")
        data["handover_notes"] = self.ri_notes.get("1.0", "end-1c")
        add_regional_incident(self.current_shift_id, data)
        self._refresh_regional_list(); messagebox.showinfo("Added", "Regional network incident added.")

    def _update_regional(self):
        if not self._selected_ri_id:
            messagebox.showwarning("Select", "Select an incident to update."); return
        data = {k: v.get() for k, v in self.ri_vars.items()}
        data["description"]    = self.ri_desc.get("1.0", "end-1c")
        data["handover_notes"] = self.ri_notes.get("1.0", "end-1c")
        update_regional_incident(self._selected_ri_id, data); self._refresh_regional_list()

    def _delete_regional(self):
        if not self._selected_ri_id: return
        if messagebox.askyesno("Confirm", "Delete this incident?"):
            delete_regional_incident(self._selected_ri_id)
            self._selected_ri_id = None; self._refresh_regional_list()

    def _on_ri_select(self, _):
        sel = self.ri_tree.selection()
        if not sel: return
        inc_id = self.ri_tree.item(sel[0])["values"][0]; self._selected_ri_id = inc_id
        if not self.current_shift_id: return
        inc = next((i for i in get_regional_incidents(self.current_shift_id) if i["id"] == inc_id), None)
        if inc:
            for k, v in self.ri_vars.items(): v.set(inc.get(k, "") or "")
            self.ri_desc.delete("1.0", "end"); self.ri_desc.insert("1.0", inc.get("description", "") or "")
            self.ri_notes.delete("1.0", "end"); self.ri_notes.insert("1.0", inc.get("handover_notes", "") or "")

    def _refresh_regional_list(self):
        for r in self.ri_tree.get_children(): self.ri_tree.delete(r)
        if not self.current_shift_id: return
        for inc in get_regional_incidents(self.current_shift_id):
            self.ri_tree.insert("", "end", values=(
                inc["id"], inc.get("description","")[:60], inc.get("ref_no",""),
                inc.get("date_reported",""), inc.get("duration",""),
                inc.get("person_assigned",""), inc.get("report_status","")))
            
    # TAB 4 – FIBRE INCIDENTS
    def _build_fibre_tab(self):
        card = self._card(self.tab_fibre, "Fibre Incidents (Follow-up with engineers / clients)")
        fm = tk.Frame(card, bg=SURFACE); fm.pack(fill="x", pady=4)
        self.fi_vars = {}

        tk.Label(fm, text="Region:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="w", width=14).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.fi_vars["region"] = tk.StringVar(value=REGIONS[0])
        ttk.Combobox(fm, textvariable=self.fi_vars["region"], values=REGIONS, state="readonly", width=22).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Ref No:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.fi_vars["ref_no"] = tk.StringVar()
        tk.Entry(fm, textvariable=self.fi_vars["ref_no"], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=18).grid(row=0, column=3, sticky="w", padx=4)

        tk.Label(fm, text="Description:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="nw").grid(row=1, column=0, sticky="nw", padx=4, pady=2)
        self.fi_desc = tk.Text(fm, bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=74, height=3, font=("Helvetica",9))
        self.fi_desc.grid(row=1, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        for key, label, default, r, c in [
            ("date_reported","Date Reported:", datetime.now().strftime("%d/%m/%Y@%H%Mhrs"), 2, 0),
            ("duration",     "Duration:",      "", 2, 2),
            ("person_assigned","Person Assigned:", "", 3, 0)]:
            tk.Label(fm, text=label, bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=r, column=c, sticky="w", padx=4, pady=2)
            self.fi_vars[key] = tk.StringVar(value=default)
            tk.Entry(fm, textvariable=self.fi_vars[key], bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=22).grid(row=r, column=c+1, sticky="w", padx=4, pady=2)

        tk.Label(fm, text="Status:", bg=SURFACE, fg=MUTED, font=("Helvetica",8)).grid(row=3, column=2, sticky="w", padx=4, pady=2)
        self.fi_vars["report_status"] = tk.StringVar(value=FIBRE_STATUSES[0])
        ttk.Combobox(fm, textvariable=self.fi_vars["report_status"], values=FIBRE_STATUSES, state="readonly", width=20).grid(row=3, column=3, sticky="w", padx=4)

        tk.Label(fm, text="Handover Notes:", bg=SURFACE, fg=MUTED, font=("Helvetica",8), anchor="nw").grid(row=4, column=0, sticky="nw", padx=4, pady=2)
        self.fi_notes = tk.Text(fm, bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=74, height=5, font=("Helvetica",9))
        self.fi_notes.grid(row=4, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        nr = tk.Frame(fm, bg=SURFACE); nr.grid(row=5, column=1, sticky="w", padx=4)
        self._btn(nr, "⏱ Stamp Timestamp", self._stamp_fibre_ts, ORANGE).pack(side="left")

        br = tk.Frame(card, bg=SURFACE); br.pack(pady=6)
        self._btn(br, "+ Add",            self._add_fibre,    ACCENT).pack(side="left", padx=4)
        self._btn(br, "✎ Update Selected", self._update_fibre, BLUE).pack(side="left", padx=4)
        self._btn(br, "✕ Delete Selected", self._delete_fibre, RED).pack(side="left", padx=4)
        self._btn(br, "⟳ Refresh",         self._refresh_fibre_list, MUTED).pack(side="left", padx=4)

        cols = ("ID","Region","Description","Ref No","Date Reported","Duration","Assigned","Status")
        self.fibre_tree = ttk.Treeview(card, columns=cols, show="headings", height=6)
        for c, w in zip(cols, [40,110,260,80,130,65,100,90]):
            self.fibre_tree.heading(c, text=c); self.fibre_tree.column(c, width=w)
        self.fibre_tree.pack(fill="x", pady=4); self._style_tree(self.fibre_tree)
        self.fibre_tree.bind("<<TreeviewSelect>>", self._on_fibre_select)
        self._selected_fibre_id = None

    def _stamp_fibre_ts(self):
        ts = datetime.now().strftime("%d/%m/%Y@%H%Mhrs")
        self.fi_notes.insert("end", f"\n{ts}: "); self.fi_notes.see("end")

    def _add_fibre(self):
        if not self._require_shift(): return
        data = {k: v.get() for k, v in self.fi_vars.items()}
        data["description"]    = self.fi_desc.get("1.0", "end-1c")
        data["handover_notes"] = self.fi_notes.get("1.0", "end-1c")
        add_fibre_incident(self.current_shift_id, data)
        self._refresh_fibre_list(); messagebox.showinfo("Added", "Fibre incident added.")

    def _update_fibre(self):
        if not self._selected_fibre_id:
            messagebox.showwarning("Select", "Select an incident to update."); return
        data = {k: v.get() for k, v in self.fi_vars.items()}
        data["description"]    = self.fi_desc.get("1.0", "end-1c")
        data["handover_notes"] = self.fi_notes.get("1.0", "end-1c")
        update_fibre_incident(self._selected_fibre_id, data); self._refresh_fibre_list()

    def _delete_fibre(self):
        if not self._selected_fibre_id: return
        if messagebox.askyesno("Confirm", "Delete?"):
            delete_fibre_incident(self._selected_fibre_id)
            self._selected_fibre_id = None; self._refresh_fibre_list()

    def _on_fibre_select(self, _):
        sel = self.fibre_tree.selection()
        if not sel: return
        inc_id = self.fibre_tree.item(sel[0])["values"][0]; self._selected_fibre_id = inc_id
        if not self.current_shift_id: return
        inc = next((i for i in get_fibre_incidents(self.current_shift_id) if i["id"] == inc_id), None)
        if inc:
            for k, v in self.fi_vars.items(): v.set(inc.get(k, "") or "")
            self.fi_desc.delete("1.0", "end"); self.fi_desc.insert("1.0", inc.get("description", "") or "")
            self.fi_notes.delete("1.0", "end"); self.fi_notes.insert("1.0", inc.get("handover_notes", "") or "")

    def _refresh_fibre_list(self):
        for r in self.fibre_tree.get_children(): self.fibre_tree.delete(r)
        if not self.current_shift_id: return
        for inc in get_fibre_incidents(self.current_shift_id):
            self.fibre_tree.insert("", "end", values=(
                inc["id"], inc.get("region",""), inc.get("description","")[:55],
                inc.get("ref_no",""), inc.get("date_reported",""),
                inc.get("duration",""), inc.get("person_assigned",""), inc.get("report_status","")))

    # TAB 5 – SYSTEM UPTIME
    def _build_uptime_tab(self):
        card = self._card(self.tab_uptime, "System Uptime")
        tk.Label(card,
                 text="Enter the last date of outage. Uptime days are calculated automatically.\n"
                      "These values persist across all shifts — only update when a new outage occurs.",
                 bg=SURFACE, fg=MUTED, font=("Helvetica",9), justify="left").pack(anchor="w", pady=(0,8))

        hdr = tk.Frame(card, bg=BORDER); hdr.pack(fill="x")
        for txt, w in [("System",22),("Last Date of Outage",32),("Uptime Days (auto)",18)]:
            tk.Label(hdr, text=txt, bg=BORDER, fg=TEXT, width=w,
                     font=("Helvetica",9,"bold"), anchor="w").pack(side="left", padx=6, pady=4)

        self.uptime_rows = []
        sc = tk.Frame(card, bg=SURFACE); sc.pack(fill="x")
        defaults = get_uptime_defaults()

        for sys_name in SYSTEMS[:-1]:
            row = tk.Frame(sc, bg=SURFACE); row.pack(fill="x", pady=2)
            tk.Label(row, text=sys_name, bg=SURFACE, fg=TEXT, width=22,
                     font=("Helvetica",9), anchor="w").pack(side="left", padx=4)
            outage_var = tk.StringVar(value=defaults.get(sys_name, {}).get("last_outage_date",""))
            tk.Entry(row, textvariable=outage_var, bg=BORDER, fg=TEXT,
                     insertbackground=TEXT, relief="flat", width=28).pack(side="left", padx=4)
            days_lbl = tk.Label(row, bg=SURFACE, fg=GREEN, font=("Courier",9,"bold"), width=14, anchor="w")
            days_lbl.pack(side="left", padx=8)
            def _upd(var=outage_var, lbl=days_lbl):
                d = calc_uptime_days(var.get()); lbl.config(text=f"{d} days" if d else "—")
            outage_var.trace_add("write", lambda *a, fn=_upd: fn()); _upd()
            self.uptime_rows.append((sys_name, outage_var, days_lbl))

        br = tk.Frame(card, bg=SURFACE); br.pack(pady=10)
        self._btn(br, "💾 Save & Apply to Report", self._save_uptime, GREEN).pack(side="left", padx=4)
        self._btn(br, "⟳ Reload",                  self._load_uptime, BLUE).pack(side="left", padx=4)

    def _save_uptime(self):
        if not self._require_shift(): return
        data = []
        for sys_name, ov, _ in self.uptime_rows:
            outage = ov.get().strip(); d = calc_uptime_days(outage)
            data.append({"system_name": sys_name, "uptime_days": int(d) if d.isdigit() else None, "last_outage_date": outage})
        save_uptime(self.current_shift_id, data); save_uptime_defaults(data)
        messagebox.showinfo("Saved", "Uptime data saved.")

    def _load_uptime(self):
        defaults = get_uptime_defaults()
        shift_uptime = {}
        if self.current_shift_id:
            shift_uptime = {u["system_name"]: u for u in get_uptime(self.current_shift_id)}
        for sys_name, ov, _ in self.uptime_rows:
            if sys_name in shift_uptime: ov.set(shift_uptime[sys_name].get("last_outage_date","") or "")
            elif sys_name in defaults:   ov.set(defaults[sys_name].get("last_outage_date","") or "")

    # TAB 6 – SCREENSHOTS
    def _build_screenshots_tab(self):
        card = self._card(self.tab_screens, "Screenshots")
        tk.Label(card, text="Click a system name to upload its screenshot. IDs restart at 1 for each shift.",
                 bg=SURFACE, fg=MUTED, font=("Helvetica",9)).pack(anchor="w", pady=(0,8))

        bg_frame = tk.Frame(card, bg=SURFACE); bg_frame.pack(fill="x", pady=4)
        tk.Label(bg_frame, text="Upload screenshot for:", bg=SURFACE, fg=TEXT,
                 font=("Helvetica",9,"bold")).pack(anchor="w", pady=(0,6))
        grid = tk.Frame(bg_frame, bg=SURFACE); grid.pack(fill="x")
        for idx, sys_name in enumerate(SYSTEMS[:-1]):
            r, c = divmod(idx, 5)
            tk.Button(grid, text=sys_name, command=lambda s=sys_name: self._upload_ss(s),
                      bg=BORDER, fg=TEXT, font=("Helvetica",8), relief="flat",
                      padx=8, pady=5, cursor="hand2",
                      activebackground=ACCENT, activeforeground="#000").grid(row=r, column=c, padx=4, pady=3, sticky="we")
        tk.Button(grid, text="Other / Custom…", command=lambda: self._upload_ss(None),
                  bg=SURFACE, fg=MUTED, font=("Helvetica",8), relief="flat",
                  padx=8, pady=5, cursor="hand2").grid(row=2, column=0, padx=4, pady=3, sticky="we")

        rr = tk.Frame(card, bg=SURFACE); rr.pack(pady=4)
        self._btn(rr, "✕ Remove Selected", self._remove_screenshot, RED).pack(side="left", padx=4)
        self._btn(rr, "⟳ Refresh",          self._refresh_screenshots, MUTED).pack(side="left", padx=4)

        cols = ("#","System","Caption")
        self.ss_tree = ttk.Treeview(card, columns=cols, show="headings", height=10)
        for c, w in zip(cols, [50,160,500]):
            self.ss_tree.heading(c, text=c); self.ss_tree.column(c, width=w)
        self.ss_tree.pack(fill="x", pady=4); self._style_tree(self.ss_tree)
        self._ss_map = {}

    def _upload_ss(self, system_name):
        if not self._require_shift(): return
        if system_name is None:
            system_name = simpledialog.askstring("System", "System name:", parent=self) or "Other"
        paths = filedialog.askopenfilenames(
            title=f"Screenshot(s) for {system_name}",
            filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.gif"),("All","*.*")])
        if not paths: return
        for path in paths:
            cap = simpledialog.askstring("Caption (optional)", f"Caption for {system_name}?", parent=self) or ""
            add_screenshot(self.current_shift_id, path, cap, system_name)
        self._refresh_screenshots()

    def _remove_screenshot(self):
        sel = self.ss_tree.selection()
        if not sel: return
        disp = self.ss_tree.item(sel[0])["values"][0]
        real_id = self._ss_map.get(disp)
        if real_id and messagebox.askyesno("Confirm", "Remove screenshot?"):
            delete_screenshot(real_id); self._refresh_screenshots()

    def _refresh_screenshots(self):
        for r in self.ss_tree.get_children(): self.ss_tree.delete(r)
        self._ss_map = {}
        if not self.current_shift_id: return
        for ss in get_screenshots_numbered(self.current_shift_id):
            d = ss["display_id"]; self._ss_map[d] = ss["id"]
            self.ss_tree.insert("", "end", values=(d, ss.get("system_name",""), ss.get("caption","")))

    # TAB 7 – GENERATE & SEND
    def _build_generate_tab(self):
        card = self._card(self.tab_generate, "Generate Report & Send Email")
        tk.Label(card, text="Only today's shifts are shown below.",
                 bg=SURFACE, fg=MUTED, font=("Helvetica",9)).pack(anchor="w", pady=(0,6))

        sr = tk.Frame(card, bg=SURFACE); sr.pack(fill="x", pady=4)
        tk.Label(sr, text="Shift:", bg=SURFACE, fg=TEXT, font=("Helvetica",9)).pack(side="left")
        self.gen_shift_var = tk.StringVar()
        self.gen_shift_combo = ttk.Combobox(sr, textvariable=self.gen_shift_var, width=65, state="readonly")
        self.gen_shift_combo.pack(side="left", padx=8)
        self._btn(sr, "⟳", self._refresh_gen_shifts, MUTED).pack(side="left")

        tk.Label(card, bg=SURFACE).pack(pady=4)
        br = tk.Frame(card, bg=SURFACE); br.pack(pady=8)
        self._btn(br, "📄 Generate Report (.docx)", self._generate_report,    ACCENT).pack(side="left", padx=8)
        self._btn(br, "📧 Send Email",               self._send_email,         GREEN).pack(side="left", padx=8)
        self._btn(br, "📄+📧 Generate & Send",        self._generate_and_send, BLUE).pack(side="left", padx=8)

        self.gen_status = tk.Label(card, text="", bg=SURFACE, fg=MUTED,
                                   font=("Helvetica",9), wraplength=640, justify="left")
        self.gen_status.pack(pady=8, anchor="w")
        self.last_report_path = None
        tk.Label(card, text="📌 Fill in all tabs before generating.",
                 bg=SURFACE, fg=MUTED, font=("Helvetica",8)).pack(anchor="w")
        self._refresh_gen_shifts()

    def _refresh_gen_shifts(self):
        today = datetime.now().strftime("%Y-%m-%d")
        shifts = get_shifts_for_date(today); opts = []; self._gen_map = {}
        for s in shifts:
            end_s = s["end_time"][11:16] if s.get("end_time") else "Active"
            lbl = f"Shift #{s['id']} | {s['agent_name']} | {s['shift_type']} | {s['start_time'][11:16]} → {end_s}"
            opts.append(lbl); self._gen_map[lbl] = s["id"]
        self.gen_shift_combo["values"] = opts
        if opts:
            for lbl, sid in self._gen_map.items():
                if sid == self.current_shift_id: self.gen_shift_var.set(lbl); return
            self.gen_shift_var.set(opts[0])
        else:
            self.gen_shift_var.set("")
            self.gen_status.config(text="No shifts found for today. Start a shift first.", fg=ORANGE)

    def _get_gen_sid(self): return self._gen_map.get(self.gen_shift_var.get())

    def _generate_report(self):
        sid = self._get_gen_sid()
        if not sid: messagebox.showwarning("Select", "Please select a shift."); return
        self.gen_status.config(text="⏳ Generating report...", fg=MUTED); self.update()
        def do():
            try:
                from core.report_generator import generate_report
                path = generate_report(sid); self.last_report_path = path
                self.gen_status.config(text=f"✅ Report saved:\n{path}", fg=GREEN)
                if messagebox.askyesno("Open?", "Open the report now?"): self._open_file(path)
            except Exception as e: self.gen_status.config(text=f"❌ Error: {e}", fg=RED)
        threading.Thread(target=do, daemon=True).start()

    def _send_email(self):
        if not self.last_report_path:
            messagebox.showwarning("No Report", "Generate a report first."); return
        sid = self._get_gen_sid(); shift = get_shift(sid) if sid else {}
        self.gen_status.config(text="⏳ Sending...", fg=MUTED); self.update()
        def do():
            ok, msg = send_report(self.last_report_path, shift.get("agent_name",""), shift.get("shift_type",""))
            self.gen_status.config(text=("✅ " if ok else "❌ ")+msg, fg=GREEN if ok else RED)
        threading.Thread(target=do, daemon=True).start()

    def _generate_and_send(self):
        sid = self._get_gen_sid()
        if not sid: messagebox.showwarning("Select", "Please select a shift."); return
        self.gen_status.config(text="⏳ Generating...", fg=MUTED); self.update()
        def do():
            try:
                from core.report_generator import generate_report
                path = generate_report(sid); self.last_report_path = path
                self.gen_status.config(text="⏳ Sending...", fg=MUTED)
                shift = get_shift(sid) or {}
                ok, msg = send_report(path, shift.get("agent_name",""), shift.get("shift_type",""))
                self.gen_status.config(text=f"✅ Report: {path}\n{'✅' if ok else '❌'} Email: {msg}",
                                       fg=GREEN if ok else ORANGE)
            except Exception as e: self.gen_status.config(text=f"❌ Error: {e}", fg=RED)
        threading.Thread(target=do, daemon=True).start()

    # TAB 8 – WEEKLY DASHBOARD
    def _build_weekly_tab(self):
        card = self._card(self.tab_weekly, "Weekly Dashboard")
        tk.Label(card, text="Generate an HTML dashboard for a date range.",
                 bg=SURFACE, fg=MUTED, font=("Helvetica",9)).pack(anchor="w", pady=(0,8))
        dr = tk.Frame(card, bg=SURFACE); dr.pack(fill="x", pady=4)
        tk.Label(dr, text="From (YYYY-MM-DD):", bg=SURFACE, fg=TEXT, font=("Helvetica",9)).pack(side="left")
        self.wk_start = tk.StringVar(value=(datetime.now()-timedelta(days=6)).strftime("%Y-%m-%d"))
        tk.Entry(dr, textvariable=self.wk_start, bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=14).pack(side="left", padx=8)
        tk.Label(dr, text="To (YYYY-MM-DD):", bg=SURFACE, fg=TEXT, font=("Helvetica",9)).pack(side="left")
        self.wk_end = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        tk.Entry(dr, textvariable=self.wk_end, bg=BORDER, fg=TEXT, insertbackground=TEXT, relief="flat", width=14).pack(side="left", padx=8)
        br = tk.Frame(card, bg=SURFACE); br.pack(pady=12)
        self._btn(br, "📊 Generate Dashboard", self._generate_dashboard, ACCENT).pack(side="left", padx=8)
        self._btn(br, "🌐 Open in Browser",     self._open_dashboard,     BLUE).pack(side="left", padx=8)
        self.wk_status = tk.Label(card, text="", bg=SURFACE, fg=MUTED, font=("Helvetica",9), wraplength=600)
        self.wk_status.pack(pady=8); self.last_dashboard_path = None

    def _generate_dashboard(self):
        self.wk_status.config(text="⏳ Generating...", fg=MUTED); self.update()
        def do():
            try:
                path = generate_weekly_dashboard(self.wk_start.get(), self.wk_end.get())
                self.last_dashboard_path = path
                self.wk_status.config(text=f"✅ Saved:\n{path}", fg=GREEN)
            except Exception as e: self.wk_status.config(text=f"❌ Error: {e}", fg=RED)
        threading.Thread(target=do, daemon=True).start()

    def _open_dashboard(self):
        if self.last_dashboard_path and os.path.exists(self.last_dashboard_path):
            webbrowser.open(f"file://{self.last_dashboard_path}")
        else: messagebox.showinfo("Info", "Generate a dashboard first.")

    # TAB 9 – SETTINGS
    def _build_settings_tab(self):
        card = self._card(self.tab_settings, "Email Settings")
        tk.Label(card,
                 text="For Microsoft 365 use smtp.office365.com\n"
                      "For Outlook 2016 use smtp-mail.outlook.com\n"
                      "Port 587 works for both. Use your normal work password.",
                 bg=SURFACE, fg=MUTED, font=("Helvetica",9), justify="left").pack(anchor="w", pady=(0,10))
        cfg = load_config(); self.cfg_vars = {}
        for label, key, placeholder in [
            ("SMTP Host",    "smtp_host",      "smtp.office365.com"),
            ("SMTP Port",    "smtp_port",       "587"),
            ("Sender Email", "sender_email",    ""),
            ("Password",     "sender_password", "")]:
            r = tk.Frame(card, bg=SURFACE); r.pack(fill="x", pady=3)
            tk.Label(r, text=label+":", bg=SURFACE, fg=TEXT, width=16,
                     anchor="w", font=("Helvetica",9)).pack(side="left")
            var = tk.StringVar(value=str(cfg.get(key, placeholder))); self.cfg_vars[key] = var
            tk.Entry(r, textvariable=var, bg=BORDER, fg=TEXT, insertbackground=TEXT,
                     relief="flat", width=42,
                     show="*" if "password" in key.lower() else "").pack(side="left", padx=4)

        tk.Label(card, text="Recipients (one per line):", bg=SURFACE, fg=TEXT,
                 font=("Helvetica",9)).pack(anchor="w", pady=(10,2))
        self.recipients_text = tk.Text(card, bg=BORDER, fg=TEXT, insertbackground=TEXT,
                                       relief="flat", height=4, font=("Helvetica",9))
        self.recipients_text.pack(fill="x", pady=2)
        self.recipients_text.insert("1.0", "\n".join(cfg.get("recipients",[])))

        tk.Label(card, text="CC (one per line, optional):", bg=SURFACE, fg=TEXT,
                 font=("Helvetica",9)).pack(anchor="w", pady=(6,2))
        self.cc_text = tk.Text(card, bg=BORDER, fg=TEXT, insertbackground=TEXT,
                               relief="flat", height=2, font=("Helvetica",9))
        self.cc_text.pack(fill="x", pady=2)
        self.cc_text.insert("1.0", "\n".join(cfg.get("cc",[])))

        br = tk.Frame(card, bg=SURFACE); br.pack(pady=10)
        self._btn(br, "💾 Save Settings",   self._save_email_settings, GREEN).pack(side="left", padx=4)
        self._btn(br, "🧪 Test Connection", self._test_email,          BLUE).pack(side="left", padx=4)

    def _save_email_settings(self):
        cfg = {k: v.get() for k, v in self.cfg_vars.items()}
        cfg["smtp_port"]  = int(cfg.get("smtp_port", 587) or 587)
        cfg["recipients"] = [e.strip() for e in self.recipients_text.get("1.0","end-1c").splitlines() if e.strip()]
        cfg["cc"]         = [e.strip() for e in self.cc_text.get("1.0","end-1c").splitlines() if e.strip()]
        save_config(cfg); messagebox.showinfo("Saved", "Email settings saved.")

    def _test_email(self):
        self._save_email_settings(); cfg = load_config()
        import smtplib
        try:
            with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"])) as s:
                s.ehlo(); s.starttls(); s.login(cfg["sender_email"], cfg["sender_password"])
            messagebox.showinfo("Success", "✅ Connection test passed!")
        except Exception as e:
            messagebox.showerror("Failed", f"❌ Connection failed:\n{e}")

    # HELPERS
    def _card(self, parent, title=""):
        outer = tk.Frame(parent, bg=BG); outer.pack(fill="both", expand=True, padx=12, pady=10)
        if title:
            tk.Label(outer, text=title, bg=BG, fg=ACCENT,
                     font=("Helvetica",11,"bold")).pack(anchor="w", pady=(0,6))
        inner = tk.Frame(outer, bg=SURFACE, bd=0, relief="flat",
                         highlightbackground=BORDER, highlightthickness=1)
        inner.pack(fill="both", expand=True)
        tk.Frame(inner, bg=SURFACE, height=8).pack()
        content = tk.Frame(inner, bg=SURFACE, padx=12); content.pack(fill="both", expand=True)
        tk.Frame(inner, bg=SURFACE, height=8).pack()
        return content

    def _btn(self, parent, text, cmd, color=ACCENT):
        return tk.Button(parent, text=text, command=cmd, bg=color, fg="#000000",
                         font=("Helvetica",9,"bold"), relief="flat", padx=10, pady=4,
                         cursor="hand2", activebackground=color)

    def _style_tree(self, tree):
        s = ttk.Style(); n = f"T{id(tree)}.Treeview"
        s.configure(n, background=SURFACE, foreground=TEXT,
                    fieldbackground=SURFACE, rowheight=22, font=("Helvetica",8))
        s.map(n, background=[("selected",ACCENT)], foreground=[("selected","#000")])
        tree.configure(style=n)

    def _require_shift(self):
        if not self.current_shift_id:
            messagebox.showwarning("No Active Shift", "Go to Shift tab and start a shift first.")
            return False
        return True

    def _open_file(self, path):
        try:
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.run(["open", path])
            else: subprocess.run(["xdg-open", path])
        except Exception as e: messagebox.showerror("Error", f"Could not open: {e}")


if __name__ == "__main__":
    init_db(); app = App(); app.mainloop()
