"""Photo Agents service hub.

A zero-dependency tkinter launcher that discovers reflect/ scripts and
client/ frontends, and lets the user start / stop them with a checkbox.
Output for the selected service is tailed live.
"""

import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
from collections import deque
from tkinter import ttk

# Gate before doing anything else.
from photoagents.auth import ensure_authenticated

ensure_authenticated()


LOCK_PORT = 19_735
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_DIR = os.path.dirname(_HERE)
_REPO_DIR = os.path.dirname(_PKG_DIR)


def acquire_singleton():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        return s
    except OSError:
        return None


def discover_services():
    services = []

    evo_dir = os.path.join(_PKG_DIR, "evolution")
    if os.path.isdir(evo_dir):
        for f in sorted(os.listdir(evo_dir)):
            if f.endswith(".py") and not f.startswith("_"):
                services.append({
                    "name": f"evolution/{f}",
                    "cmd": [sys.executable, "-m", "photoagents",
                            "--reflect", os.path.join(evo_dir, f)],
                })

    clients_dir = os.path.join(_PKG_DIR, "clients")
    if os.path.isdir(clients_dir):
        for f in sorted(os.listdir(clients_dir)):
            if not f.endswith(".py") or f == "client_common.py":
                continue
            full = os.path.join(clients_dir, f)
            if "web_app" in f:
                cmd = [sys.executable, "-m", "streamlit", "run", full,
                       "--server.headless=true"]
            elif "client" in f:
                cmd = [sys.executable, full]
            else:
                continue
            services.append({"name": f"clients/{f}", "cmd": cmd})

    return services


class ServiceManager:
    def __init__(self):
        self.procs = {}
        self.buffers = {}

    def start(self, name, cmd):
        if name in self.procs and self.procs[name].poll() is None:
            return
        self.buffers[name] = deque(maxlen=500)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        kw = dict(cwd=_REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                  text=True, bufsize=1, env=env)
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, **kw)
        self.procs[name] = proc
        threading.Thread(target=self._reader, args=(name, proc), daemon=True).start()

    def _reader(self, name, proc):
        try:
            for line in proc.stdout:
                self.buffers[name].append(line)
        except Exception:
            pass

    def stop(self, name):
        proc = self.procs.get(name)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def is_running(self, name):
        proc = self.procs.get(name)
        return proc is not None and proc.poll() is None

    def stop_all(self):
        for name in list(self.procs):
            self.stop(name)

    def get_output(self, name):
        buf = self.buffers.get(name)
        return list(buf) if buf else []


class HubApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Agents Hub")
        self.root.geometry("720x740")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.mgr = ServiceManager()
        self.services = discover_services()
        self.check_vars = {}
        self.selected = None

        self._build_ui()
        self._poll()

    def _build_ui(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(header, text="Services", font=("", 10, "bold")).pack(side="left")
        ttk.Button(header, text="\u27f3 Rescan", width=10,
                   command=self._rescan).pack(side="right")

        svc_frame = ttk.LabelFrame(self.root, padding=5)
        svc_frame.pack(fill="x", padx=8, pady=(2, 4))

        self.svc_container = ttk.Frame(svc_frame)
        self.svc_container.pack(fill="x")

        self.status_labels = {}
        self.row_frames = {}
        self.name_labels = {}
        self._build_service_rows()

        self.output_frame = ttk.LabelFrame(self.root, text="Output", padding=5)
        self.output_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.output_text = tk.Text(
            self.output_frame, wrap="word", state="disabled",
            bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 9), insertbackground="white")
        sb = ttk.Scrollbar(self.output_frame, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.output_text.pack(fill="both", expand=True)

    def _build_service_rows(self):
        for svc in self.services:
            name = svc["name"]
            row = tk.Frame(self.svc_container, cursor="hand2", padx=4, pady=2)
            row.pack(fill="x", pady=1)
            self.row_frames[name] = row

            running = self.mgr.is_running(name)
            var = self.check_vars.get(name, tk.BooleanVar(value=running))
            if running:
                var.set(True)
            self.check_vars[name] = var
            cb = ttk.Checkbutton(
                row, variable=var,
                command=lambda n=name, v=var, s=svc: self._toggle(n, v, s))
            cb.pack(side="left")

            name_lbl = tk.Label(row, text=name, anchor="w", cursor="hand2",
                                bg=row.cget("bg"))
            name_lbl.pack(side="left", fill="x", expand=True)
            self.name_labels[name] = name_lbl

            st = "running" if running else "stopped"
            fg = "green" if running else "gray"
            lbl = ttk.Label(row, text=st, foreground=fg, width=10)
            lbl.pack(side="right")
            self.status_labels[name] = lbl

            name_lbl.bind("<Button-1>", lambda e, n=name: self._select(n))
            row.bind("<Button-1>", lambda e, n=name: self._select(n))

    def _rescan(self):
        # Remember which services are currently running.
        running_names = {n for n in self.mgr.procs if self.mgr.is_running(n)}
        for w in self.svc_container.winfo_children():
            w.destroy()
        self.status_labels.clear()
        self.row_frames.clear()
        self.name_labels.clear()
        # Drop check_vars that no longer correspond to anything.
        old_vars = {k: v for k, v in self.check_vars.items() if k in running_names}
        self.check_vars.clear()
        self.check_vars.update(old_vars)
        # Rescan disk.
        self.services = discover_services()
        self._build_service_rows()
        # If the selected service vanished, clear the selection.
        svc_names = {s["name"] for s in self.services}
        if self.selected and self.selected not in svc_names:
            self.selected = None
            self.output_frame.configure(text="Output")

    def _toggle(self, name, var, svc):
        if var.get():
            self.mgr.start(name, svc["cmd"])
            self._select(name)
        else:
            self.mgr.stop(name)

    def _select(self, name):
        self.selected = name
        for n, row in self.row_frames.items():
            if n == name:
                row.configure(bg="#cce5ff")
                self.name_labels[n].configure(bg="#cce5ff")
            else:
                row.configure(bg="SystemButtonFace")
                self.name_labels[n].configure(bg="SystemButtonFace")
        self.output_frame.configure(text=f"Output - {name}")
        self.root.after(50, self._refresh_output)

    def _refresh_output(self):
        if not self.selected:
            return
        lines = self.mgr.get_output(self.selected)
        new_text = "".join(lines[-200:])

        # Skip identical refreshes to avoid flicker / scroll jitter.
        current = self.output_text.get("1.0", "end-1c")
        if new_text.rstrip("\n") == current.rstrip("\n"):
            return

        # Capture scroll state so we can restore it sensibly.
        _top, bot = self.output_text.yview()
        at_bottom = bot >= 0.99

        if not at_bottom:
            old_total = int(self.output_text.index("end-1c").split(".")[0])
            first_vis = int(float(self.output_text.index("@0,0")))
            offset_from_end = old_total - first_vis

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("end", new_text)
        self.output_text.configure(state="disabled")

        if at_bottom:
            self.output_text.see("end")
        else:
            new_total = int(self.output_text.index("end-1c").split(".")[0])
            target = max(1, new_total - offset_from_end)
            self.output_text.yview_moveto(0)
            self.output_text.see(f"{target}.0")

    def _poll(self):
        for svc in self.services:
            name = svc["name"]
            running = self.mgr.is_running(name)
            lbl = self.status_labels[name]
            if running:
                lbl.configure(text="running", foreground="green")
            else:
                lbl.configure(text="stopped", foreground="gray")
                if self.check_vars[name].get():
                    self.check_vars[name].set(False)
        self._refresh_output()
        self.root.after(1000, self._poll)

    def on_close(self):
        self.mgr.stop_all()
        self.root.destroy()


if __name__ == "__main__":
    lock = acquire_singleton()
    if lock is None:
        try:
            import tkinter.messagebox as mb
            r = tk.Tk()
            r.withdraw()
            mb.showinfo("Photo Agents Hub", "Already running.")
            r.destroy()
        except Exception:
            pass
        sys.exit(0)

    root = tk.Tk()
    app = HubApp(root)
    root.mainloop()
    lock.close()
