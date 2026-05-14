import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime, timedelta
import json
import os
import threading
import time
import subprocess
import sys

from main import run_agent

# ── Optional notification library ──
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════
#  S C H E D U L E R   E N G I N E
# ═══════════════════════════════════════════════════════════════════
class TaskScheduler:
    """Background scheduler that checks for due tasks every N seconds."""

    def __init__(self, app_ref):
        self.app = app_ref
        self._running = False
        self._thread: threading.Thread | None = None
        self._notified_ids: set[int] = set()   # ids already notified this cycle
        self._exec_log: list[str] = []          # execution log for display

    # ── Start / Stop ──
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    # ── Main loop ──
    def _run_loop(self):
        check_interval = 5          # seconds between checks
        while self._running:
            now = datetime.now()
            due_tasks = self._find_due_tasks(now)

            for task in due_tasks:
                self._trigger_task(task)

            time.sleep(check_interval)

    def _find_due_tasks(self, now: datetime) -> list[dict]:
        """Return tasks where scheduled_date is set and is <= now."""
        due = []
        for task in self.app.tasks:
            if not task.get("scheduled_date") or task.get("completed"):
                continue
            # Skip if already notified in current session
            if task["id"] in self._notified_ids:
                continue
            try:
                sched = datetime.fromisoformat(task["scheduled_date"])
                if sched <= now:
                    due.append(task)
            except (ValueError, TypeError):
                continue
        return due

    def _trigger_task(self, task: dict):

        task_id = task["id"]

        self._notified_ids.add(task_id)

        title = task.get("title", "Unnamed Task")

        priority = task.get("priority", "Medium")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._exec_log.append(
            f"[{timestamp}] ⏳ Started: '{title}'"
        )

        def run_task():

            try:

                result = run_agent(title)

                success = True if result != False else False

                message = result

                finished_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if success:

                    log_entry = (
                        f"[{finished_time}] ✅ COMPLETED: "
                        f"'{title}' | {message}"
                    )

                    # auto-complete successful tasks
                    task["completed"] = True

                else:

                    log_entry = (
                        f"[{finished_time}] ❌ FAILED: "
                        f"'{title}' | {message}"
                    )

                self._exec_log.append(log_entry)

                self.app.save_tasks()

                self.app.after(
                    0,
                    self.app._populate_task_list
                )

            except Exception as e:

                error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                self._exec_log.append(
                    f"[{error_time}] ❌ CRASHED: "
                    f"'{title}' | {str(e)}"
                )

            # Keep logs clean
            if len(self._exec_log) > 100:
                self._exec_log.pop(0)

        threading.Thread(
            target=run_task,
            daemon=True
        ).start()

    def _run_command(self, task: dict):
        """Execute a custom shell command or script associated with the task."""
        cmd = task.get("command", "").strip()
        if not cmd:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] ▶ Executing: {cmd}"
        self._exec_log.append(entry)

        try:
            # Determine if it's a Python script or shell command
            if os.fspath(cmd).endswith(".py"):
                # Run Python script
                result = subprocess.run(
                    [sys.executable, cmd],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            else:
                # Run shell command
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

            out = result.stdout.strip() if result.stdout else "(no output)"
            err = result.stderr.strip() if result.stderr else ""
            status = "✅ Success" if result.returncode == 0 else f"❌ Exit {result.returncode}"

            log = f"[{timestamp}] {status} | stdout: {out[:120]} | stderr: {err[:120]}"
            self._exec_log.append(log)

        except subprocess.TimeoutExpired:
            self._exec_log.append(f"[{timestamp}] ❌ Command timed out after 60s")
        except Exception as e:
            self._exec_log.append(f"[{timestamp}] ❌ Error: {str(e)}")

        # Keep last 100 entries
        if len(self._exec_log) > 100:
            self._exec_log.pop(0)

    def get_log(self) -> list[str]:
        return list(self._exec_log)


# ═══════════════════════════════════════════════════════════════════
#  M A I N   A P P L I C A T I O N   C L A S S
# ═══════════════════════════════════════════════════════════════════
class TaskManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── Window Configuration ──
        self.title("TaskFlow – Task Manager")
        self.geometry("1000x650")
        self.minsize(800, 500)

        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        # ── Data Store ──
        self.tasks: list[dict] = []
        self.load_tasks()

        # ── Start Scheduler ──
        self.scheduler = TaskScheduler(self)
        self.scheduler.start()

        # ── Build UI ──
        self._build_sidebar()
        self._build_main_area()
        self._populate_task_list()
        self._refresh_all_stats()

        # ── Track active dialogs ──
        self.active_alerts: list[ctk.CTkToplevel] = []

        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def _change_theme(self, theme_name):
        theme_map = {
            "Blue": "blue",
            "Dark-Blue": "dark-blue",
            "Green": "green",
        }

        selected = theme_map.get(theme_name, "blue")

        ctk.set_default_color_theme(selected)

        messagebox.showinfo(
            "Theme Changed",
            "Theme updated.\nPlease restart the application to fully apply changes.",
            parent=self
        )

    # ═══════════════════════════════════════════════════════════════
    #  S I D E B A R
    # ═══════════════════════════════════════════════════════════════
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=260, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # App Title
        ctk.CTkLabel(sidebar, text="✅ TaskFlow", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(25, 5))
        ctk.CTkLabel(sidebar, text="Stay organised, stay ahead.", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 20))
        ctk.CTkFrame(sidebar, height=2, fg_color="gray30").pack(fill="x", padx=20, pady=(0, 15))

        # Navigation buttons
        self.sidebar_buttons: dict[str, ctk.CTkButton] = {}
        for text, icon in [
            ("📋  All Tasks", "all"),
            ("🔔  Scheduled", "scheduled"),
            # ("⭐  Priority", "priority"),
            ("📊  Statistics", "stats"),
            ("📜  Execution Log", "log"),
        ]:
            btn = ctk.CTkButton(
                sidebar, text=text, anchor="w",
                fg_color="transparent", hover_color=("gray75", "gray30"),
                height=40, corner_radius=10,
                font=ctk.CTkFont(size=14),
                command=lambda mode=icon: self._switch_tab(mode),
            )
            btn.pack(fill="x", padx=15, pady=3)
            self.sidebar_buttons[icon] = btn

        self._highlight_sidebar_button("all")

        # Separator
        ctk.CTkFrame(sidebar, height=2, fg_color="gray30").pack(fill="x", padx=20, pady=(15, 10))

        # Appearance mode
        mode_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        mode_frame.pack(fill="x", padx=20, pady=(5, 5))
        ctk.CTkLabel(mode_frame, text="Appearance", font=ctk.CTkFont(size=12)).pack(side="left")
        self.appearance_menu = ctk.CTkOptionMenu(
            mode_frame, values=["System", "Light", "Dark"],
            width=90,
            command=lambda v: ctk.set_appearance_mode(v.lower()),
        )
        self.appearance_menu.pack(side="right")

        # Separator
        ctk.CTkFrame(sidebar, height=2, fg_color="gray30").pack(fill="x", padx=20, pady=(15, 10))

        # Quick stats
        stats_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(5, 5))
        self.lbl_total = ctk.CTkLabel(stats_frame, text="Total: 0", font=ctk.CTkFont(size=12))
        self.lbl_total.pack(anchor="w")
        self.lbl_done = ctk.CTkLabel(stats_frame, text="Done: 0", font=ctk.CTkFont(size=12), text_color="green")
        self.lbl_done.pack(anchor="w", pady=(2, 0))
        self.lbl_pending = ctk.CTkLabel(stats_frame, text="Pending: 0", font=ctk.CTkFont(size=12), text_color="orange")
        self.lbl_pending.pack(anchor="w", pady=(2, 0))
        self.lbl_scheduled = ctk.CTkLabel(stats_frame, text="Scheduled: 0", font=ctk.CTkFont(size=12), text_color="#3498db")
        self.lbl_scheduled.pack(anchor="w", pady=(2, 0))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(sidebar, height=12, corner_radius=6)
        self.progress_bar.pack(fill="x", padx=20, pady=(10, 5))
        self.progress_bar.set(0)
        self.lbl_progress = ctk.CTkLabel(sidebar, text="0% complete", font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_progress.pack()

        # Spacer
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(expand=True, fill="both")

        # Footer
        ctk.CTkLabel(sidebar, text="© 2025 TaskFlow", font=ctk.CTkFont(size=10), text_color="gray50").pack(pady=(0, 10))

    # ═══════════════════════════════════════════════════════════════
    #  M A I N   A R E A
    # ═══════════════════════════════════════════════════════════════
    def _build_main_area(self):
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.pack(side="left", fill="both", expand=True)

        self.tabview = ctk.CTkTabview(self.main_container, corner_radius=12)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        self.tab_all = self.tabview.add("📋  All Tasks")
        self.tab_scheduled = self.tabview.add("🔔  Scheduled")
        self.tab_stats = self.tabview.add("📊  Statistics")
        self.tab_log = self.tabview.add("📜  Log")

        self._build_all_tasks_tab()
        self._build_scheduled_tab()
        self._build_stats_tab()
        self._build_log_tab()

    # ──────────────────────────────────────────────────────────────
    #  All Tasks Tab
    # ──────────────────────────────────────────────────────────────
    def _build_all_tasks_tab(self):
        top_bar = ctk.CTkFrame(self.tab_all, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkButton(
            top_bar, text="＋ New Task", font=ctk.CTkFont(size=14, weight="bold"),
            height=36, corner_radius=10, command=self._open_add_task_dialog,
        ).pack(side="left")

        self.filter_combo = ctk.CTkComboBox(
            top_bar,
            values=["All", "Pending", "Completed", "Scheduled"],
            width=160,
            command=lambda _: self._populate_task_list(),
        )
        self.filter_combo.pack(side="right", padx=(10, 0))
        ctk.CTkLabel(top_bar, text="Filter:", font=ctk.CTkFont(size=12)).pack(side="right")

        self.task_scroll_frame = ctk.CTkScrollableFrame(self.tab_all, corner_radius=10)
        self.task_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    # ──────────────────────────────────────────────────────────────
    #  Scheduled Tab
    # ──────────────────────────────────────────────────────────────
    def _build_scheduled_tab(self):
        header = ctk.CTkFrame(self.tab_scheduled, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header,
            text="🔔  Upcoming Scheduled Tasks",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        self.scheduled_scroll_frame = ctk.CTkScrollableFrame(self.tab_scheduled, corner_radius=10)
        self.scheduled_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    # ──────────────────────────────────────────────────────────────
    #  Statistics Tab
    # ──────────────────────────────────────────────────────────────
    def _build_stats_tab(self):
        ctk.CTkLabel(
            self.tab_stats, text="📊  Your Productivity Overview",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 5))

        self.lbl_stats_total = ctk.CTkLabel(self.tab_stats, text="", font=ctk.CTkFont(size=14))
        self.lbl_stats_total.pack()
        self.lbl_stats_done = ctk.CTkLabel(self.tab_stats, text="", font=ctk.CTkFont(size=14))
        self.lbl_stats_done.pack()
        self.lbl_stats_pending = ctk.CTkLabel(self.tab_stats, text="", font=ctk.CTkFont(size=14))
        self.lbl_stats_pending.pack()
        self.lbl_stats_scheduled = ctk.CTkLabel(self.tab_stats, text="", font=ctk.CTkFont(size=14), text_color="#3498db")
        self.lbl_stats_scheduled.pack()

        self.stats_progress = ctk.CTkProgressBar(self.tab_stats, width=300, height=16, corner_radius=8)
        self.stats_progress.pack(pady=(20, 5))
        self.stats_progress.set(0)
        self.lbl_stats_pct = ctk.CTkLabel(self.tab_stats, text="0%", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_stats_pct.pack()

        ctk.CTkButton(
            self.tab_stats, text="🗑  Clear Completed Tasks",
            fg_color="#c0392b", hover_color="#e74c3c",
            command=self._clear_completed,
        ).pack(pady=(25, 10))

        ctk.CTkButton(
            self.tab_stats, text="📋  Export Tasks to JSON",
            fg_color="gray30", hover_color="gray50",
            command=self._export_tasks,
        ).pack(pady=(5, 10))

    # ──────────────────────────────────────────────────────────────
    #  Execution Log Tab
    # ──────────────────────────────────────────────────────────────
    def _build_log_tab(self):
        ctk.CTkLabel(
            self.tab_log, text="📜  Execution & Trigger Log",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 5))
        ctk.CTkLabel(
            self.tab_log, text="Shows scheduled task triggers and command executions",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).pack()

        btn_row = ctk.CTkFrame(self.tab_log, fg_color="transparent")
        btn_row.pack(pady=(10, 5))

        ctk.CTkButton(
            btn_row, text="🔄  Refresh Log", width=120, corner_radius=8,
            fg_color="gray30", hover_color="gray50",
            command=lambda: self._refresh_log(),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_row, text="🗑  Clear Log", width=100, corner_radius=8,
            fg_color="transparent", border_width=1, border_color="#c0392b",
            text_color="#e74c3c", hover_color="#c0392b",
            command=self._clear_log,
        ).pack(side="left", padx=5)

        self.log_scroll = ctk.CTkScrollableFrame(self.tab_log, corner_radius=10)
        self.log_scroll.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    # ═══════════════════════════════════════════════════════════════
    #  T A S K   D I A L O G   (Add / Edit)
    # ═══════════════════════════════════════════════════════════════
    def _open_add_task_dialog(self, task: dict | None = None):
        is_edit = task is not None
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Task" if is_edit else "New Task")
        dialog.geometry("480x620")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self)

        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 480) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 620) // 2
        dialog.geometry(f"+{x}+{y}")

        # ── Title ──
        ctk.CTkLabel(dialog, text="Task Title *", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(15, 2), anchor="w", padx=25)
        entry_title = ctk.CTkEntry(dialog, width=420, height=36, corner_radius=8)
        entry_title.pack(padx=25, pady=(0, 10))

        # ── Schedule Section ──
        ctk.CTkFrame(dialog, height=2, fg_color="gray30").pack(fill="x", padx=25, pady=(5, 8))

        ctk.CTkLabel(dialog, text="⏰  Schedule (Date & Time)", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0, 5), anchor="w", padx=25)

        enable_schedule = ctk.BooleanVar(value=bool(task and task.get("scheduled_date")))
        ctk.CTkCheckBox(
            dialog, text="Enable scheduled execution",
            variable=enable_schedule, font=ctk.CTkFont(size=12),
            command=lambda: self._toggle_schedule_ui(
                enable_schedule.get(),
                entry_date, entry_time,
            ),
        ).pack(anchor="w", padx=25)

        # Date row
        date_row = ctk.CTkFrame(dialog, fg_color="transparent")
        date_row.pack(fill="x", padx=25, pady=3)
        ctk.CTkLabel(date_row, text="Date (YYYY-MM-DD):", width=170, anchor="w").pack(side="left")
        entry_date = ctk.CTkEntry(date_row, width=230, corner_radius=6)
        entry_date.pack(side="left", padx=(0, 5))
        entry_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Time row
        time_row = ctk.CTkFrame(dialog, fg_color="transparent")
        time_row.pack(fill="x", padx=25, pady=3)
        ctk.CTkLabel(time_row, text="Time (HH:MM):", width=170, anchor="w").pack(side="left")
        entry_time = ctk.CTkEntry(time_row, width=230, corner_radius=6)
        entry_time.pack(side="left", padx=(0, 5))
        entry_time.insert(0, (datetime.now() + timedelta(minutes=30)).strftime("%H:%M"))



        # ── Pre-fill if editing ──
        if is_edit:
            entry_title.insert(0, task.get("title", ""))
            # priority_var.set(task.get("priority", "Medium"))
            if task.get("scheduled_date"):
                try:
                    dt = datetime.fromisoformat(task["scheduled_date"])
                    entry_date.delete(0, "end")
                    entry_date.insert(0, dt.strftime("%Y-%m-%d"))
                    entry_time.delete(0, "end")
                    entry_time.insert(0, dt.strftime("%H:%M"))
                except (ValueError, TypeError):
                    pass

        # Set initial schedule UI state
        self._toggle_schedule_ui(
            enable_schedule.get(),
            entry_date, entry_time
        )

        # ── Buttons ──
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(15, 15))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color="#B35353",
            border_width=0,
            hover_color="#a04040",
            border_color="#B35353",
            command=dialog.destroy,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="💾 Save Task",
            command=lambda: self._save_task_from_dialog(
                dialog,
                entry_title.get().strip(),
                # priority_var.get(),
                enable_schedule.get(),
                entry_date.get().strip(),
                entry_time.get().strip(),
                # auto_complete_var.get(),
                task["id"] if is_edit else None,
            ),
        ).pack(side="right")

    @staticmethod
    def _toggle_schedule_ui(enabled, entry_date, entry_time):
        state = "normal" if enabled else "disabled"

        entry_date.configure(state=state)
        entry_time.configure(state=state)

    def _browse_script(self):
        path = filedialog.askopenfilename(
            title="Select Script or Executable",
            filetypes=[
                ("Python scripts", "*.py"),
                ("Executables", "*.exe *.bat *.sh"),
                ("All files", "*.*"),
            ],
        )
        return path if path else ""

    def _save_task_from_dialog(
        self,
        dialog,
        title,
        enable_schedule,
        date_str,
        time_str,
        auto_complete,
        task_id=None,
    ):
        if not title:
            messagebox.showwarning(
                "Missing Title",
                "Please enter a task title.",
                parent=dialog
            )
            return

        # Validate date/time
        scheduled_dt = ""

        if enable_schedule:
            try:
                date_part = datetime.strptime(date_str, "%Y-%m-%d")
                time_part = datetime.strptime(time_str, "%H:%M")

                combined = date_part.replace(
                    hour=time_part.hour,
                    minute=time_part.minute
                )

                scheduled_dt = combined.isoformat()

            except ValueError:
                messagebox.showwarning(
                    "Invalid Date/Time",
                    "Use YYYY-MM-DD and HH:MM format.",
                    parent=dialog
                )
                return

        # EDIT EXISTING TASK
        if task_id is not None:

            for t in self.tasks:
                if t["id"] == task_id:
                    t["title"] = title
                    t["scheduled_date"] = scheduled_dt
                    t["auto_complete"] = auto_complete
                    break

        # CREATE NEW TASK
        else:

            task = {
                "id": self._generate_id(),
                "title": title,
                "scheduled_date": scheduled_dt,
                "auto_complete": auto_complete,
                "completed": False,
                "created_at": datetime.now().isoformat(),
            }

            self.tasks.append(task)

        # SAVE + REFRESH
        self.save_tasks()
        self._populate_task_list()
        self._refresh_all_stats()

        dialog.destroy()

    def _generate_id(self) -> int:
        return max((t["id"] for t in self.tasks), default=0) + 1

    # ═══════════════════════════════════════════════════════════════
    #  T A S K   L I S T   R E N D E R I N G
    # ═══════════════════════════════════════════════════════════════
    def _populate_task_list(self):
        for w in self.task_scroll_frame.winfo_children():
            w.destroy()

        filter_val = self.filter_combo.get()
        filtered = self._filter_tasks(filter_val)

        if not filtered:
            self._show_empty_state(self.task_scroll_frame, "🎉 No tasks here!", "Click '+ New Task' to create one.")
        else:
            for task in filtered:
                self._create_task_card(task, self.task_scroll_frame)

        self._populate_scheduled_tab()
        # self._populate_priority_tab()
        self._refresh_all_stats()

    def _populate_scheduled_tab(self):
        for w in self.scheduled_scroll_frame.winfo_children():
            w.destroy()

        scheduled = [t for t in self.tasks if t.get("scheduled_date") and not t["completed"]]
        scheduled.sort(key=lambda t: t["scheduled_date"])

        if not scheduled:
            self._show_empty_state(self.scheduled_scroll_frame, "📅 No scheduled tasks", "Enable 'Scheduled' when creating a task.")
        else:
            ctk.CTkLabel(
                self.tab_scheduled,
                text=f"🔔 {len(scheduled)} task(s) scheduled",
                font=ctk.CTkFont(size=13),
                text_color="gray70",
            ).pack(pady=(5, 0))

            for task in scheduled:
                self._create_task_card(task, self.scheduled_scroll_frame)

    def _filter_tasks(self, filter_val: str) -> list[dict]:
        mapping = {
            "All": None,
            "Pending": lambda t: not t["completed"],
            "Completed": lambda t: t["completed"],
            "Scheduled": lambda t: bool(t.get("scheduled_date")),
        }
        fn = mapping.get(filter_val)
        tasks = self.tasks if fn is None else [t for t in self.tasks if fn(t)]
        return sorted(tasks, key=lambda t: (t["completed"], t.get("scheduled_date") or "", t["id"]))

    def _show_empty_state(self, parent, title, subtitle):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14), text_color="gray60").pack(pady=(40, 5))
        ctk.CTkLabel(frame, text=subtitle, font=ctk.CTkFont(size=12), text_color="gray50").pack()

    def _create_task_card(self, task: dict, parent):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill="x", padx=0, pady=3)

        # Top row
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 2))

        completed_var = ctk.BooleanVar(value=task["completed"])
        ctk.CTkCheckBox(
            top_row, text="", width=22, variable=completed_var,
            command=lambda t=task, v=completed_var: self._toggle_completed(t, v.get()),
        ).pack(side="left")

        title_text = f"✅ {task['title']}" if task["completed"] else task["title"]
        ctk.CTkLabel(top_row, text=title_text, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(side="left", padx=(8, 0))

        # Badges
        badges = ctk.CTkFrame(top_row, fg_color="transparent")
        badges.pack(side="right")

        # Scheduled badge
        if task.get("scheduled_date"):
            try:
                dt = datetime.fromisoformat(task["scheduled_date"])
                is_overdue = dt < datetime.now() and not task["completed"]
                color = "#c0392b" if is_overdue else "#2980b9"
                badge = ctk.CTkFrame(badges, fg_color=color, corner_radius=6)
                badge.pack(side="right", padx=(5, 0))
                badge.pack_propagate(False)
                icon = "⚠️" if is_overdue else "⏰"
                ctk.CTkLabel(badge, text=f"{icon} {dt.strftime('%m/%d %H:%M')}", font=ctk.CTkFont(size=10), text_color="white").pack(padx=8, pady=2)
            except (ValueError, TypeError):
                pass

        # Description
        if task.get("description"):
            ctk.CTkLabel(card, text=task["description"], font=ctk.CTkFont(size=11), text_color="gray70", anchor="w").pack(fill="x", padx=40, pady=(0, 5))

        # Action buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=32, pady=(0, 8))

        ctk.CTkButton(btn_row, text="✏️ Edit", width=60, height=26, font=ctk.CTkFont(size=11), corner_radius=6, fg_color="gray30", hover_color="gray50", command=lambda t=task: self._open_add_task_dialog(t)).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row, text="🗑 Delete", width=70, height=26, font=ctk.CTkFont(size=11), corner_radius=6, fg_color="transparent", border_width=1, border_color="#c0392b", text_color="#e74c3c", hover_color="#c0392b", command=lambda t=task: self._delete_task(t)).pack(side="left")

    def _toggle_completed(self, task, completed):
        task["completed"] = completed
        self.save_tasks()
        self._populate_task_list()

    def _delete_task(self, task):
        if messagebox.askyesno("Confirm Delete", f'Delete "{task["title"]}"?', parent=self):
            self.tasks = [t for t in self.tasks if t["id"] != task["id"]]
            self.save_tasks()
            self._populate_task_list()

    def _clear_completed(self):
        count = sum(1 for t in self.tasks if t["completed"])
        if count == 0:
            messagebox.showinfo("Nothing to clear", "No completed tasks found.", parent=self)
            return
        if messagebox.askyesno("Confirm", f"Delete {count} completed task(s)?", parent=self):
            self.tasks = [t for t in self.tasks if not t["completed"]]
            self.save_tasks()
            self._populate_task_list()

    def _export_tasks(self):
        path = filedialog.asksaveasfilename(
            title="Export Tasks",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.tasks, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Exported", f"Tasks exported to:\n{path}", parent=self)
            except Exception as e:
                messagebox.showerror("Export Error", str(e), parent=self)

    # ═══════════════════════════════════════════════════════════════
    #  E X E C U T I O N   L O G
    # ═══════════════════════════════════════════════════════════════
    def _refresh_log(self):
        for w in self.log_scroll.winfo_children():
            w.destroy()

        log_entries = self.scheduler.get_log()
        if not log_entries:
            ctk.CTkLabel(self.log_scroll, text="📭 No log entries yet.", font=ctk.CTkFont(size=13), text_color="gray60").pack(pady=30)
            return

        for entry in reversed(log_entries):
            color = "green" if "✅" in entry else ("red" if "❌" in entry else ("#3498db" if "Triggered" in entry else "gray70"))
            frame = ctk.CTkFrame(self.log_scroll, corner_radius=6, fg_color=("gray20", "gray85"))
            frame.pack(fill="x", pady=2)
            ctk.CTkLabel(frame, text=entry, font=ctk.CTkFont(size=11), text_color=color, anchor="w").pack(padx=10, pady=5)

    def _clear_log(self):
        self.scheduler._exec_log.clear()
        self._refresh_log()

    # ═══════════════════════════════════════════════════════════════
    #  S T A T I S T I C S
    # ═══════════════════════════════════════════════════════════════
    def _refresh_all_stats(self):
        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t["completed"])
        pending = total - done
        scheduled_count = sum(1 for t in self.tasks if t.get("scheduled_date") and not t["completed"])
        pct = (done / total * 100) if total > 0 else 0

        self.lbl_total.configure(text=f"Total: {total}")
        self.lbl_done.configure(text=f"Done: {done}")
        self.lbl_pending.configure(text=f"Pending: {pending}")
        self.lbl_scheduled.configure(text=f"Scheduled: {scheduled_count}")
        self.progress_bar.set(done / total if total else 0)
        self.lbl_progress.configure(text=f"{pct:.0f}% complete")

        self.lbl_stats_total.configure(text=f"📌 Total Tasks: {total}")
        self.lbl_stats_done.configure(text=f"✅ Completed: {done}")
        self.lbl_stats_pending.configure(text=f"⏳ Pending: {pending}")
        self.lbl_stats_scheduled.configure(text=f"⏰ Scheduled: {scheduled_count}")
        self.stats_progress.set(done / total if total else 0)
        self.lbl_stats_pct.configure(text=f"{pct:.0f}%")

    # ═══════════════════════════════════════════════════════════════
    #  N A V I G A T I O N
    # ═══════════════════════════════════════════════════════════════
    def _switch_tab(self, mode):
        self._highlight_sidebar_button(mode)
        tab_map = {
            "all": "📋  All Tasks",
            "scheduled": "🔔  Scheduled",
            "stats": "📊  Statistics",
            "log": "📜  Log",
        }
        self.tabview.set(tab_map[mode])
        if mode == "log":
            self._refresh_log()

    def _highlight_sidebar_button(self, active: str):
        for key, btn in self.sidebar_buttons.items():
            if key == active:
                btn.configure(
                    fg_color=("gray75", "gray30"),
                    text_color="black"
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("black", "white")
                )

    # ═══════════════════════════════════════════════════════════════
    #  P E R S I S T E N C E
    # ═══════════════════════════════════════════════════════════════
    def load_tasks(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.tasks = []
        else:
            self.tasks = []

    def save_tasks(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except IOError as e:
            messagebox.showerror("Save Error", f"Could not save tasks:\n{e}", parent=self)

    def on_close(self):
        self.scheduler.stop()
        self.save_tasks()
        self.destroy()


# ── Entry Point ─────────────────────────────────────────────────────
import sys
import os

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)

DATA_FILE = os.path.join(get_base_path(), "tasks_data.json")

if __name__ == "__main__":
    app = TaskManagerApp()
    app.mainloop()