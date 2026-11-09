"""VIGILENS desktop application. UI polling never accesses the webcam directly."""
import os
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from config import APP_NAME, APP_FULL_NAME, PROJECT_ROOT
from database.database import Database
from services.alert_service import AlertService
from services.camera_service import CameraService
from services.monitoring_service import MonitoringService, RUNNING, STARTING, STOPPING
from services.session_service import SessionService, format_duration
from services.settings_service import SettingsService, AppSettings, SettingsValidationError


# Midnight Teal Theme - Accessibility Revised
BG = "#EDF2F1"
NAVY = "#173B3A"
SLATE = "#285B59"
TEAL = "#8EDBD0"
RED = "#B64D4D"
WHITE = "#FAFCFB"
TEXT = "#263F3E"
MUTED = "#526B67"
BORDER = "#D8E4E1"
HOVER = "#34716D"


class VigilensApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title(f"{APP_NAME} | {APP_FULL_NAME}")
        self.geometry("1360x850")
        self.minsize(1120, 720)
        self.configure(fg_color=BG)

        self.db = Database()
        self.db.close_unfinished_sessions()
        self.settings_service = SettingsService(self.db)
        self.settings = self.settings_service.load()
        self.sessions = SessionService(self.db)
        self.alerts = AlertService()
        self.monitor = MonitoringService(self.db, self.alerts)
        self._photo = None
        self._active_page = None
        self._pages = {}
        self._monitor_after = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_shell()
        self.show_page("Dashboard")

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self, width=230, corner_radius=0, fg_color=NAVY
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="VIGILENS",
            font=ctk.CTkFont(size=27, weight="bold"),
            text_color=WHITE
        ).pack(anchor="w", padx=24, pady=(30, 2))

        ctk.CTkLabel(
            self.sidebar,
            text="VISUAL ALERTNESS MONITOR",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=TEAL
        ).pack(anchor="w", padx=25, pady=(0, 34))

        self.nav_buttons = {}

        for name, symbol in [
            ("Dashboard", "⌂"),
            ("Live Monitoring", "◉"),
            ("Session History", "📂"),
            ("Analytics", "📈"),
            ("Settings", "⛭"),
            ("About", "ⓘ")
        ]:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {symbol}     {name}",
                anchor="w",
                height=44,
                fg_color="transparent",
                hover_color=HOVER,
                text_color="#EAF1F4",
                font=ctk.CTkFont(size=14),
                command=lambda n=name: self.show_page(n)
            )
            btn.pack(fill="x", padx=13, pady=3)
            self.nav_buttons[name] = btn

        ctk.CTkLabel(
            self.sidebar,
            text="Educational prototype\nNot a certified safety device",
            text_color="#B8CECA",
            justify="left",
            font=ctk.CTkFont(size=10)
        ).pack(side="bottom", anchor="w", padx=24, pady=22)

        self.content = ctk.CTkFrame(
            self, fg_color=BG, corner_radius=0
        )
        self.content.grid(
            row=0, column=1, sticky="nsew", padx=0, pady=0
        )
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(
            self.content, fg_color=WHITE, corner_radius=0, height=72
        )
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)

        self.page_title = ctk.CTkLabel(
            self.header,
            text="Dashboard",
            text_color=NAVY,
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.page_title.grid(
            row=0, column=0, sticky="w", padx=28, pady=20
        )

        self.header_status = ctk.CTkLabel(
            self.header,
            text="●  CAMERA NOT CHECKED",
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.header_status.grid(row=0, column=1, padx=26)

        self.page_host = ctk.CTkFrame(
            self.content, fg_color=BG, corner_radius=0
        )
        self.page_host.grid(
            row=1, column=0, sticky="nsew", padx=24, pady=22
        )
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)

    def show_page(self, name):
        if self.monitor.is_running and name != "Live Monitoring":
            if not messagebox.askyesno(
                "Monitoring is active",
                "Monitoring is currently running. Stop it before leaving Live Monitoring?"
            ):
                name = "Live Monitoring"
            else:
                stopped = self.monitor.stop(timeout=8)
                if not stopped:
                    messagebox.showwarning(
                        "Monitoring is still stopping",
                        "The monitoring session has not finished saving yet. "
                        "Please wait a moment, then try navigating again."
                    )
                    return

        if self._monitor_after:
            self.after_cancel(self._monitor_after)
            self._monitor_after = None

        for child in self.page_host.winfo_children():
            child.destroy()

        self.page_title.configure(text=name)

        for n, b in self.nav_buttons.items():
            b.configure(fg_color=SLATE if n == name else "transparent")

        builders = {
            "Dashboard": self._dashboard,
            "Live Monitoring": self._live,
            "Session History": self._history,
            "Analytics": self._analytics,
            "Settings": self._settings_page,
            "About": self._about,
        }

        self._active_page = name
        self._update_header_status()
        builders[name]()

    def _update_header_status(self):
        """Keep the header's camera and monitoring status current."""
        try:
            snap = self.monitor.snapshot()

            if snap.state in (RUNNING, STARTING, STOPPING):
                camera_text = (
                    "CAMERA ACTIVE" if snap.camera_ok
                    else "CAMERA STARTING"
                )
                text = f"●  MONITORING {snap.state}  •  {camera_text}"
                color = SLATE if snap.camera_ok else MUTED
            else:
                text = "●  MONITORING STOPPED  •  CAMERA INACTIVE"
                color = MUTED

            self.header_status.configure(
                text=text, text_color=color
            )

        except Exception:
            self.header_status.configure(
                text="●  STATUS UNAVAILABLE",
                text_color=MUTED
            )

    def _scroll(self):
        frame = ctk.CTkScrollableFrame(
            self.page_host, fg_color="transparent"
        )
        frame.grid(row=0, column=0, sticky="nsew")
        return frame

    def _section(self, parent, title, subtitle=None):
        """Display the page description once below the main header."""
        if subtitle:
            ctk.CTkLabel(
                parent,
                text=subtitle,
                text_color=MUTED,
                font=ctk.CTkFont(size=13),
                wraplength=900,
                justify="left"
            ).pack(anchor="w", pady=(0, 20))

    def _card(self, parent, title, value, note=""):
        card = ctk.CTkFrame(
            parent,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER
        )

        ctk.CTkLabel(
            card,
            text=title.upper(),
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(anchor="w", padx=18, pady=(16, 5))

        ctk.CTkLabel(
            card,
            text=str(value),
            text_color=NAVY,
            font=ctk.CTkFont(size=29, weight="bold")
        ).pack(anchor="w", padx=18)

        if note:
            ctk.CTkLabel(
                card,
                text=note,
                text_color=MUTED,
                font=ctk.CTkFont(size=11)
            ).pack(anchor="w", padx=18, pady=(3, 15))
        else:
            ctk.CTkLabel(card, text="", height=12).pack()

        return card

    def _dashboard(self):
        f = self._scroll()

        self._section(
            f,
            "Welcome to VIGILENS",
            "Real-time visual monitoring of facial indicators associated with possible drowsiness."
        )

        refresh_row = ctk.CTkFrame(
            f, fg_color="transparent"
        )
        refresh_row.pack(fill="x", pady=(0, 10))

        refreshed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        ctk.CTkLabel(
            refresh_row,
            text=f"Statistics last refreshed: {refreshed_at}",
            text_color=MUTED,
            font=ctk.CTkFont(size=11)
        ).pack(side="left")

        ctk.CTkButton(
            refresh_row,
            text="Refresh Dashboard",
            width=145,
            fg_color=SLATE,
            hover_color=HOVER,
            command=lambda: self.show_page("Dashboard")
        ).pack(side="right")

        stats = self.sessions.get_dashboard_stats()
        snapshot = self.monitor.snapshot()

        monitoring_active = snapshot.state in (
            RUNNING, STARTING, STOPPING
        )
        camera_status = (
            "Active" if snapshot.camera_ok else "Inactive"
        )
        monitoring_status = (
            "Active" if monitoring_active else "Stopped"
        )

        status_panel = ctk.CTkFrame(
            f,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER
        )
        status_panel.pack(fill="x", pady=(0, 14))

        status_row = ctk.CTkFrame(
            status_panel, fg_color="transparent"
        )
        status_row.pack(fill="x", padx=20, pady=15)
        status_row.grid_columnconfigure(0, weight=1)
        status_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            status_row,
            text=f"CAMERA STATUS   •   {camera_status.upper()}",
            text_color=SLATE if snapshot.camera_ok else MUTED,
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )

        ctk.CTkLabel(
            status_row,
            text=f"MONITORING STATUS   •   {monitoring_status.upper()}",
            text_color=SLATE if monitoring_active else MUTED,
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=1, sticky="w")

        grid = ctk.CTkFrame(f, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 20))

        for i, (title, val, note) in enumerate([
            ("Monitoring sessions", stats["total_sessions"], "Completed sessions"),
            ("Drowsiness alerts", stats["total_alerts"], "Recorded prolonged eye closures"),
            ("Possible yawns", stats["total_yawns"], "Recorded mouth-opening events")
        ]):
            grid.grid_columnconfigure(i, weight=1)
            self._card(
                grid, title, val, note
            ).grid(
                row=0,
                column=i,
                sticky="ew",
                padx=(0 if i == 0 else 10, 0)
            )

        panel = ctk.CTkFrame(
            f,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER
        )
        panel.pack(fill="x", pady=8)

        ctk.CTkLabel(
            panel,
            text="Start a monitoring session",
            text_color=NAVY,
            font=ctk.CTkFont(size=19, weight="bold")
        ).pack(anchor="w", padx=22, pady=(20, 6))

        ctk.CTkLabel(
            panel,
            text="Connect a webcam, position your face clearly in view, and begin monitoring.",
            text_color=MUTED
        ).pack(anchor="w", padx=22)

        ctk.CTkButton(
            panel,
            text="Open Live Monitoring",
            fg_color=SLATE,
            hover_color=HOVER,
            command=lambda: self.show_page("Live Monitoring")
        ).pack(anchor="w", padx=22, pady=20)

        latest = stats["latest_session"]

        info = ctk.CTkFrame(
            f,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER
        )
        info.pack(fill="x", pady=8)

        ctk.CTkLabel(
            info,
            text="Latest completed session",
            text_color=NAVY,
            font=ctk.CTkFont(size=17, weight="bold")
        ).pack(anchor="w", padx=22, pady=(18, 8))

        if latest:
            text = (
                f"Session #{latest.session_id}   •   {latest.date}   •   "
                f"{latest.duration_text}   •   {latest.alerts} alerts   •   "
                f"{latest.yawns} possible yawns"
            )
        else:
            text = (
                "No completed sessions yet. Your session summaries "
                "will appear here after monitoring."
            )

        ctk.CTkLabel(
            info,
            text=text,
            text_color=MUTED
        ).pack(anchor="w", padx=22, pady=(0, 20))

        ctk.CTkLabel(
            f,
            text="VIGILENS is an educational prototype. It does not diagnose a medical condition or guarantee driver safety.",
            text_color=MUTED,
            wraplength=850,
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", pady=18)

    def _live(self):
        f = self._scroll()

        self._section(
            f,
            "Live Monitoring",
            "Keep your face, eyes, and mouth visible to the webcam during monitoring."
        )

        body = ctk.CTkFrame(
            f,
            fg_color="transparent"
        )
        body.pack(fill="both", expand=True)

        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0, minsize=350)
        body.grid_rowconfigure(0, weight=1)

        video_card = ctk.CTkFrame(
            body,
            fg_color=NAVY,
            corner_radius=12
        )
        video_card.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 12)
        )

        video_card.grid_columnconfigure(0, weight=1)
        video_card.grid_rowconfigure(0, weight=1)

        self.video_label = ctk.CTkLabel(
            video_card,
            text="Camera preview will appear here\n\nPress Start Monitoring",
            text_color="#E0ECE9",
            font=ctk.CTkFont(size=16),
            width=760,
            height=470
        )
        self.video_label.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=12
        )

        right = ctk.CTkFrame(
            body,
            fg_color="transparent",
            width=350
        )
        right.grid(
            row=0,
            column=1,
            sticky="nsew"
        )
        right.grid_propagate(False)

        status = ctk.CTkFrame(
            right,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
            width=350,
            height=105
        )
        status.pack(
            fill="x",
            pady=(0, 10)
        )
        status.pack_propagate(False)

        ctk.CTkLabel(
            status,
            text="CURRENT STATUS",
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(
            anchor="w",
            padx=17,
            pady=(15, 5)
        )

        self.status_value = ctk.CTkLabel(
            status,
            text="NOT MONITORING",
            text_color=MUTED,
            font=ctk.CTkFont(size=18, weight="bold"),
            width=310,
            height=32,
            anchor="w",
            wraplength=310,
            justify="left"
        )
        self.status_value.pack(
            anchor="w",
            padx=17,
            pady=(0, 10)
        )

        metrics = ctk.CTkFrame(
            right,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER
        )
        metrics.pack(
            fill="x",
            pady=10
        )

        self.metric_labels = {}

        metric_rows = [
            ("eye_status", "Eye Status"),
            ("ear", "Eye Aspect Ratio"),
            ("mar", "Mouth Aspect Ratio"),
            ("closure", "Eye-closure duration"),
            ("elapsed", "Session duration"),
            ("alerts", "Drowsiness alerts"),
            ("yawns", "Possible yawns"),
            ("fps", "Processing FPS")
        ]

        for key, label in metric_rows:
            row = ctk.CTkFrame(
                metrics,
                fg_color="transparent",
                height=32
            )
            row.pack(
                fill="x",
                padx=16,
                pady=5
            )
            row.pack_propagate(False)

            ctk.CTkLabel(
                row,
                text=label,
                text_color=MUTED,
                anchor="w"
            ).pack(
                side="left",
                fill="x",
                expand=True
            )

            val = ctk.CTkLabel(
                row,
                text="—",
                text_color=NAVY,
                font=ctk.CTkFont(size=14, weight="bold"),
                width=105,
                anchor="e"
            )
            val.pack(side="right")

            self.metric_labels[key] = val

        controls = ctk.CTkFrame(
            right,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER
        )
        controls.pack(
            fill="x",
            pady=10
        )

        self.start_btn = ctk.CTkButton(
            controls,
            text="Start Monitoring",
            fg_color=SLATE,
            hover_color=HOVER,
            command=self._start_monitoring
        )
        self.start_btn.pack(
            fill="x",
            padx=16,
            pady=(16, 8)
        )

        self.stop_btn = ctk.CTkButton(
            controls,
            text="Stop Monitoring",
            fg_color=RED,
            hover_color="#963F3F",
            command=self._stop_monitoring,
            state="disabled"
        )
        self.stop_btn.pack(
            fill="x",
            padx=16,
            pady=(0, 16)
        )

        self.live_message = ctk.CTkLabel(
            f,
            text=(
                "Audio alerts: enabled"
                if self.settings.audio_enabled
                else "Audio alerts: disabled"
            ),
            text_color=MUTED,
            anchor="w",
            wraplength=1000
        )
        self.live_message.pack(
            fill="x",
            pady=8
        )

        self._poll_monitor()

    def _start_monitoring(self):
        self.settings = self.settings_service.load()

        if not self.monitor.start(self.settings):
            messagebox.showwarning(
                "Already monitoring",
                "A monitoring session is already running."
            )
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.live_message.configure(
            text="Starting camera and loading the facial landmark model…"
        )

    def _stop_monitoring(self):
        self.stop_btn.configure(state="disabled")
        self.live_message.configure(
            text="Stopping monitoring and saving session…"
        )

        stopped = self.monitor.stop(timeout=8)
        self._refresh_live_snapshot()

        if not stopped:
            self.live_message.configure(
                text="Monitoring is still stopping. Please wait while the session is saved."
            )

    def _poll_monitor(self):
        if self._active_page != "Live Monitoring":
            return

        self._refresh_live_snapshot()
        self._monitor_after = self.after(
            35, self._poll_monitor
        )

    def _refresh_live_snapshot(self):
        snap = self.monitor.snapshot()

        if snap.frame is not None:
            rgb = cv2.cvtColor(
                snap.frame, cv2.COLOR_BGR2RGB
            )
            h, w = rgb.shape[:2]
            max_w, max_h = 760, 470
            scale = min(max_w / w, max_h / h)

            image = Image.fromarray(rgb).resize(
                (int(w * scale), int(h * scale)),
                Image.Resampling.LANCZOS
            )

            self._photo = ImageTk.PhotoImage(image)
            self.video_label.configure(
                image=self._photo, text=""
            )
        else:
            self.video_label.configure(
                image="",
                text="Camera preview will appear here\n\nPress Start Monitoring"
            )
            self._photo = None

        if "ALERT" in snap.status:
            status_color = RED
        elif snap.status in ("EYES CLOSED", "YAWNING"):
            status_color = "#8A5A00"
        elif snap.status == "NORMAL":
            status_color = SLATE
        else:
            status_color = MUTED

        self.status_value.configure(
            text=snap.status,
            text_color=status_color
        )

        if snap.ear is None:
            eye_status = "NOT DETECTED"
        else:
            eye_status = (
                "CLOSED" if snap.eyes_closed else "OPEN"
            )

        values = {
            "eye_status": eye_status,
            "ear": f"{snap.ear:.3f}" if snap.ear is not None else "—",
            "mar": f"{snap.mar:.3f}" if snap.mar is not None else "—",
            "closure": f"{snap.closure_duration:.1f} s",
            "elapsed": format_duration(snap.elapsed),
            "alerts": snap.drowsiness_alerts,
            "yawns": snap.yawning_events,
            "fps": f"{snap.fps:.1f}"
        }

        for key, value in values.items():
            self.metric_labels[key].configure(
                text=str(value)
            )

        if snap.error_message:
            self.live_message.configure(
                text=snap.error_message
            )
        elif snap.warning:
            self.live_message.configure(
                text=snap.warning
            )
        elif snap.state == RUNNING:
            self.live_message.configure(
                text=f"Session #{snap.session_id} • {snap.audio_status}"
            )
        elif snap.state not in (STARTING, STOPPING):
            self.live_message.configure(
                text=f"Camera: {'available' if snap.camera_ok else 'not active'} • {snap.audio_status}"
            )

        if snap.state not in (RUNNING, STARTING, STOPPING):
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
        else:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")

        self._update_header_status()

    def _history(self):
        f = self._scroll()

        self._section(
            f,
            "Session History",
            "Review completed monitoring sessions and their recorded detection events."
        )

        rows = self.sessions.list_sessions()

        toolbar = ctk.CTkFrame(
            f, fg_color="transparent"
        )
        toolbar.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            toolbar,
            text=f"{len(rows)} completed session(s) • Session IDs are identifiers, not a total count.",
            text_color=MUTED,
            font=ctk.CTkFont(size=12)
        ).pack(side="left")

        ctk.CTkButton(
            toolbar,
            text="Refresh",
            width=100,
            command=lambda: self.show_page("Session History")
        ).pack(side="right")

        table_frame = ctk.CTkFrame(
            f,
            fg_color=WHITE,
            corner_radius=10,
            border_width=1,
            border_color=BORDER
        )
        table_frame.pack(fill="x")

        style = ttk.Style()
        style.configure(
            "Vigilens.Treeview",
            rowheight=30,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Vigilens.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 8)
        )

        cols = (
            "id", "date", "start", "end",
            "duration", "alerts", "yawns"
        )

        tree = ttk.Treeview(
            table_frame,
            columns=cols,
            show="headings",
            height=15,
            style="Vigilens.Treeview"
        )

        labels = {
            "id": "Session",
            "date": "Date",
            "start": "Start",
            "end": "End",
            "duration": "Duration",
            "alerts": "Alerts",
            "yawns": "Possible yawns"
        }

        widths = {
            "id": 75,
            "date": 120,
            "start": 100,
            "end": 100,
            "duration": 120,
            "alerts": 90,
            "yawns": 120
        }

        for col in cols:
            tree.heading(col, text=labels[col])
            tree.column(
                col,
                width=widths[col],
                anchor="center"
            )

        for r in rows:
            tree.insert(
                "",
                "end",
                iid=str(r.session_id),
                values=(
                    r.session_id,
                    r.date,
                    r.start_time,
                    r.end_time,
                    r.duration_text,
                    r.alerts,
                    r.yawns
                )
            )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=tree.yview
        )
        tree.configure(
            yscrollcommand=scrollbar.set
        )

        tree.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(10, 0),
            pady=10
        )
        scrollbar.pack(
            side="right",
            fill="y",
            padx=(0, 10),
            pady=10
        )

        actions = ctk.CTkFrame(
            f, fg_color="transparent"
        )
        actions.pack(fill="x", pady=12)

        def details():
            selected = tree.selection()

            if not selected:
                messagebox.showinfo(
                    "Select a session",
                    "Choose a session to view its events."
                )
                return

            self._show_session_details(
                int(selected[0])
            )

        def delete():
            selected = tree.selection()

            if not selected:
                messagebox.showinfo(
                    "Select a session",
                    "Choose a session to delete."
                )
                return

            sid = int(selected[0])

            if messagebox.askyesno(
                "Delete session",
                f"Delete session #{sid} and its associated events and samples? This cannot be undone."
            ):
                self.sessions.delete_session(sid)
                messagebox.showinfo(
                    "Session deleted",
                    f"Session #{sid} was deleted."
                )
                self.show_page("Session History")

        ctk.CTkButton(
            actions,
            text="View Events",
            fg_color=SLATE,
            command=details
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions,
            text="Delete Selected",
            fg_color=RED,
            hover_color="#963F3F",
            command=delete
        ).pack(side="left")

        if not rows:
            ctk.CTkLabel(
                f,
                text="No completed sessions yet.",
                text_color=MUTED
            ).pack(anchor="w", pady=16)

    def _show_session_details(self, sid):
        win = ctk.CTkToplevel(self)
        win.title(f"Session #{sid} events")
        win.geometry("720x430")
        win.transient(self)

        ctk.CTkLabel(
            win,
            text=f"Detection events — Session #{sid}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=NAVY
        ).pack(anchor="w", padx=20, pady=18)

        tree = ttk.Treeview(
            win,
            columns=("time", "type", "ear", "mar", "closure"),
            show="headings",
            height=13
        )

        for col, label, width in [
            ("time", "Time", 110),
            ("type", "Event", 190),
            ("ear", "EAR", 90),
            ("mar", "MAR", 90),
            ("closure", "Closure (s)", 110)
        ]:
            tree.heading(col, text=label)
            tree.column(
                col, width=width, anchor="center"
            )

        for e in self.sessions.get_session_events(sid):
            tree.insert(
                "",
                "end",
                values=(
                    e["time"],
                    e["type"],
                    f'{e["ear"]:.3f}' if e["ear"] is not None else "—",
                    f'{e["mar"]:.3f}' if e["mar"] is not None else "—",
                    f'{e["closure_seconds"]:.2f}'
                )
            )

        tree.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20)
        )

    def _analytics(self):
        f = self._scroll()

        self._section(
            f,
            "Analytics",
            "Charts and summaries are generated from completed sessions stored in your local database."
        )

        analytics_toolbar = ctk.CTkFrame(
            f, fg_color="transparent"
        )
        analytics_toolbar.pack(
            fill="x", pady=(0, 10)
        )

        ctk.CTkLabel(
            analytics_toolbar,
            text="These totals use the same completed-session records as the Dashboard.",
            text_color=MUTED,
            font=ctk.CTkFont(size=11)
        ).pack(side="left")

        ctk.CTkButton(
            analytics_toolbar,
            text="Refresh Analytics",
            width=145,
            fg_color=SLATE,
            hover_color=HOVER,
            command=lambda: self.show_page("Analytics")
        ).pack(side="right")

        data = self.sessions.get_analytics()

        cards = ctk.CTkFrame(
            f, fg_color="transparent"
        )
        cards.pack(fill="x", pady=(0, 18))

        for i, (title, value, note) in enumerate([
            ("Sessions", data["total_sessions"], "Completed"),
            ("Drowsiness alerts", data["total_alerts"], "Recorded events"),
            ("Possible yawns", data["total_yawns"], "Recorded events"),
            ("Average duration", data["avg_duration_text"], "Per completed session")
        ]):
            cards.grid_columnconfigure(i, weight=1)
            self._card(
                cards, title, value, note
            ).grid(
                row=0,
                column=i,
                sticky="ew",
                padx=(0 if i == 0 else 8, 0)
            )

        ctk.CTkLabel(
            f,
            text=f'Average event frequency: {data["events_per_hour"]:.2f} events/hour of recorded monitoring',
            text_color=SLATE,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 14))

        chart_box = ctk.CTkFrame(
            f,
            fg_color=WHITE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER
        )
        chart_box.pack(fill="x", pady=8)

        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig = Figure(figsize=(8.8, 3.2), dpi=100)
            ax = fig.add_subplot(111)

            per = data["per_session"]

            if per:
                labels = [p["label"] for p in per]
                alerts = [p["alerts"] for p in per]
                yawns = [p["yawns"] for p in per]

                x = list(range(len(labels)))
                width = .36

                ax.bar(
                    [v - width / 2 for v in x],
                    alerts,
                    width,
                    label="Drowsiness alerts"
                )
                ax.bar(
                    [v + width / 2 for v in x],
                    yawns,
                    width,
                    label="Possible yawns"
                )

                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=0)
                ax.set_ylabel("Number of recorded events")
                ax.set_xlabel("Completed session ID")
                ax.legend(frameon=False)
                ax.set_title("Recorded events per session")
                ax.grid(axis="y", alpha=0.2)
                ax.set_axisbelow(True)

            else:
                ax.text(
                    .5,
                    .5,
                    "No completed session data yet",
                    ha="center",
                    va="center",
                    transform=ax.transAxes
                )
                ax.set_axis_off()

            fig.tight_layout()

            canvas = FigureCanvasTkAgg(
                fig, master=chart_box
            )
            canvas.draw()
            canvas.get_tk_widget().pack(
                fill="x", padx=12, pady=12
            )

            if data["ear_series"]:
                ear_box = ctk.CTkFrame(
                    f, fg_color=WHITE, corner_radius=12
                )
                ear_box.pack(fill="x", pady=8)

                fig2 = Figure(
                    figsize=(8.8, 2.8), dpi=100
                )
                ax2 = fig2.add_subplot(111)
                series = data["ear_series"]

                ax2.plot(
                    series["seconds"],
                    series["ear"],
                    linewidth=1.5
                )
                ax2.set_title(
                    f'Eye Aspect Ratio (EAR) over time — Session #{series["session_id"]}'
                )
                ax2.set_xlabel("Elapsed time (seconds)")
                ax2.set_ylabel("Eye Aspect Ratio")
                ax2.grid(alpha=0.2)

                fig2.tight_layout()

                cv = FigureCanvasTkAgg(
                    fig2, master=ear_box
                )
                cv.draw()
                cv.get_tk_widget().pack(
                    fill="x", padx=12, pady=12
                )

            else:
                ctk.CTkLabel(
                    f,
                    text="EAR trend will appear after a completed session has enough recorded samples.",
                    text_color=MUTED
                ).pack(anchor="w", pady=10)

        except Exception as exc:
            ctk.CTkLabel(
                chart_box,
                text=f"Chart could not be displayed: {exc}",
                text_color=RED
            ).pack(padx=20, pady=20)

        ctk.CTkLabel(
            f,
            text="These summaries describe recorded visual measurements and events. They are not clinical assessments.",
            text_color=MUTED,
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", pady=12)

    def _settings_page(self):
        f = self._scroll()

        self._section(
            f,
            "Settings",
            "Changes are saved locally and will be used in future monitoring sessions."
        )

        s = self.settings_service.load()

        form = ctk.CTkFrame(
            f, fg_color=WHITE, corner_radius=12
        )
        form.pack(fill="x", padx=2)
        form.grid_columnconfigure(1, weight=1)

        self.setting_vars = {}

        fields = [
            (
                "ear_threshold",
                "EAR threshold",
                str(s.ear_threshold),
                "Lower EAR values indicate more closed eyes."
            ),
            (
                "mar_threshold",
                "MAR threshold",
                str(s.mar_threshold),
                "Higher MAR values indicate a wider mouth opening."
            ),
            (
                "eye_closure_duration",
                "Eye-closure alert duration (seconds)",
                str(s.eye_closure_duration),
                "How long the eyes must remain closed before an alert."
            ),
            (
                "camera_index",
                "Camera index",
                str(s.camera_index),
                "Usually 0 for the default webcam. Change if another camera is used."
            )
        ]

        for i, (key, label, value, help_text) in enumerate(fields):
            ctk.CTkLabel(
                form,
                text=label,
                text_color=TEXT
            ).grid(
                row=i,
                column=0,
                sticky="w",
                padx=22,
                pady=13
            )

            var = tk.StringVar(value=value)
            self.setting_vars[key] = var

            ctk.CTkEntry(
                form,
                textvariable=var,
                width=180
            ).grid(
                row=i,
                column=1,
                sticky="w",
                padx=20,
                pady=13
            )

            ctk.CTkLabel(
                form,
                text=help_text,
                text_color=MUTED,
                font=ctk.CTkFont(size=10),
                wraplength=300,
                justify="left"
            ).grid(
                row=i,
                column=2,
                sticky="w",
                padx=(0, 18),
                pady=8
            )

        sounds = (
            self.settings_service.available_sounds()
            or [s.alert_sound]
        )

        ctk.CTkLabel(
            form,
            text="Alert sound",
            text_color=TEXT
        ).grid(
            row=4, column=0, sticky="w", padx=22, pady=13
        )

        self.sound_var = tk.StringVar(
            value=s.alert_sound if s.alert_sound in sounds else sounds[0]
        )

        ctk.CTkOptionMenu(
            form,
            values=sounds,
            variable=self.sound_var
        ).grid(
            row=4, column=1, sticky="w", padx=20, pady=13
        )

        self.audio_var = tk.BooleanVar(
            value=s.audio_enabled
        )

        ctk.CTkLabel(
            form,
            text="Audio alerts",
            text_color=TEXT
        ).grid(
            row=5, column=0, sticky="w", padx=22, pady=13
        )

        ctk.CTkSwitch(
            form,
            text="Enable audio alerts",
            variable=self.audio_var,
            onvalue=True,
            offvalue=False
        ).grid(
            row=5, column=1, sticky="w", padx=20, pady=13
        )

        buttons = ctk.CTkFrame(
            f, fg_color="transparent"
        )
        buttons.pack(fill="x", pady=16)

        ctk.CTkButton(
            buttons,
            text="Save Settings",
            fg_color=SLATE,
            hover_color=HOVER,
            command=self._save_settings
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            buttons,
            text="Reset Defaults",
            fg_color=SLATE,
            hover_color=HOVER,
            command=self._reset_settings
        ).pack(side="left")

        camera_tools = ctk.CTkFrame(
            f, fg_color="transparent"
        )
        camera_tools.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            camera_tools,
            text="Scan Available Cameras",
            fg_color=SLATE,
            hover_color=HOVER,
            command=self._scan_cameras
        ).pack(side="left")

        self.camera_scan_note = ctk.CTkLabel(
            camera_tools,
            text="Camera index 0 is the usual default.",
            text_color=MUTED
        )
        self.camera_scan_note.pack(
            side="left", padx=12
        )

        ctk.CTkLabel(
            f,
            text="Thresholds are starting values. Test them under your camera and lighting conditions; they are not universal measurements.",
            text_color=MUTED,
            wraplength=850
        ).pack(anchor="w", pady=8)

    def _scan_cameras(self):
        if self.monitor.is_running:
            messagebox.showwarning(
                "Monitoring active",
                "Stop monitoring before scanning for cameras."
            )
            return

        self.camera_scan_note.configure(
            text="Scanning camera indexes 0–4…"
        )
        self.update_idletasks()

        try:
            found = CameraService.list_available(
                max_index=5
            )

            if found:
                if (
                    self.setting_vars["camera_index"].get().strip()
                    not in [str(i) for i in found]
                ):
                    self.setting_vars["camera_index"].set(
                        str(found[0])
                    )

                self.camera_scan_note.configure(
                    text="Available camera indexes: "
                    + ", ".join(map(str, found))
                )
            else:
                self.camera_scan_note.configure(
                    text="No available camera detected. Check Windows camera permissions."
                )

        except Exception as exc:
            self.camera_scan_note.configure(
                text=f"Camera scan failed: {exc}"
            )

    def _save_settings(self):
        if self.monitor.is_running:
            messagebox.showwarning(
                "Monitoring active",
                "Stop monitoring before changing settings."
            )
            return

        raw = {
            k: v.get()
            for k, v in self.setting_vars.items()
        }

        raw.update(
            audio_enabled=self.audio_var.get(),
            alert_sound=self.sound_var.get()
        )

        try:
            self.settings = self.settings_service.save(raw)
            messagebox.showinfo(
                "Settings saved",
                "Your settings have been saved locally."
            )

        except SettingsValidationError as exc:
            messagebox.showerror(
                "Invalid settings", str(exc)
            )

        except Exception as exc:
            messagebox.showerror(
                "Could not save settings", str(exc)
            )

    def _reset_settings(self):
        if self.monitor.is_running:
            messagebox.showwarning(
                "Monitoring active",
                "Stop monitoring before changing settings."
            )
            return

        self.settings = self.settings_service.reset_defaults()
        self.show_page("Settings")

        messagebox.showinfo(
            "Defaults restored",
            "Default settings have been saved."
        )

    def _about(self):
        f = self._scroll()

        self._section(
            f,
            "About VIGILENS",
            "Visual Monitoring for Driver Alertness"
        )

        panel = ctk.CTkFrame(
            f, fg_color=WHITE, corner_radius=12
        )
        panel.pack(fill="x")

        paragraphs = [
            (
                "Project overview",
                "VIGILENS is an educational desktop application that uses a webcam and computer vision to monitor visible facial indicators associated with possible drowsiness."
            ),
            (
                "Main objectives",
                "To detect facial features through classical computer-vision techniques; measure eye and mouth indicators using facial landmarks; monitor prolonged eye closure over time; provide visual and optional audio alerts; and record monitoring sessions and detection events for later review."
            ),
            (
                "How it works",
                "The system detects a face using an OpenCV Haar Cascade, estimates 68 facial landmarks using dlib, calculates Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR), and monitors eye-closure duration over time."
            ),
            (
                "Computer vision topics",
                "Haar Cascade face detection; facial landmark detection; image analysis and geometric transformation through EAR and MAR; image operations including grayscale conversion, resizing, histogram equalization, and visual overlays. Image segmentation and motion/object tracking are not implemented or claimed."
            ),
            (
                "Technology stack",
                "Python, OpenCV, dlib, NumPy, CustomTkinter, Pillow, Matplotlib, SQLite, and pygame."
            ),
            (
                "Basic instructions",
                "Open Live Monitoring, make sure the webcam is available, and select Start Monitoring. Keep your face reasonably centered and visible. Stop monitoring to save the session, then review it in Session History or Analytics."
            ),
            (
                "Limitations and safety",
                "Performance can be affected by lighting, glasses, occlusion, head pose, camera quality, and individual facial differences. Yawning is only a secondary indicator. VIGILENS is not a medical diagnostic tool, certified driver safety equipment, or a guarantee against accidents. Do not rely on it as a substitute for rest or safe driving practices."
            )
        ]

        for title, body in paragraphs:
            ctk.CTkLabel(
                panel,
                text=title,
                text_color=NAVY,
                font=ctk.CTkFont(size=16, weight="bold")
            ).pack(
                anchor="w", padx=22, pady=(18, 4)
            )

            ctk.CTkLabel(
                panel,
                text=body,
                text_color=MUTED,
                wraplength=900,
                justify="left"
            ).pack(
                anchor="w", padx=22, pady=(0, 8)
            )

        ctk.CTkLabel(
            panel,
            text="VIGILENS • CSC 126 Computer Vision Midterm Project",
            text_color=SLATE,
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(
            anchor="w", padx=22, pady=(20, 4)
        )

        ctk.CTkLabel(
            panel,
            text="Project build: Academic midterm prototype",
            text_color=MUTED,
            font=ctk.CTkFont(size=10)
        ).pack(
            anchor="w", padx=22, pady=(0, 20)
        )

    def on_close(self):
        if self.monitor.is_running:
            if not messagebox.askyesno(
                "Exit VIGILENS",
                "Monitoring is active. Stop monitoring and exit?"
            ):
                return

        try:
            self.monitor.shutdown()
        finally:
            self.db.close()
            self.destroy()


def run_app():
    app = VigilensApp()
    app.mainloop()