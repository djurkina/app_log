import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, ttk
import threading
import time
import json
from datetime import datetime
import queue

from drive_service import (
    extract_file_id, extract_folder_id, list_files_in_folder,
    copy_file, delete_file, set_file_permission,
    get_file_hierarchy, copy_new_items
)
from config import GOOGLE_ROOT_ID

# Files for monitor tasks and change logs
MONITOR_TASKS_FILE = "monitor_tasks.json"
CHANGES_LOG_FILE = "changes_log.json"

# Queue for log messages from background threads
log_queue = queue.Queue()

def load_json(filepath: str):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_json(filepath: str, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")

def add_change_record(operation, file_name, file_id, source_id="", dest_id="", comment=""):
    log_data = load_json(CHANGES_LOG_FILE)
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operation": operation,
        "file_name": file_name,
        "file_id": file_id,
        "source_folder_id": source_id,
        "dest_folder_id": dest_id,
        "comment": comment
    }
    log_data.append(record)
    save_json(CHANGES_LOG_FILE, log_data)

def add_monitor_task(source_id, dest_id, copied_map=None):
    if copied_map is None:
        copied_map = {}
    tasks = load_json(MONITOR_TASKS_FILE)
    for t in tasks:
        if t["source_folder_id"] == source_id and t["dest_folder_id"] == dest_id:
            return False
    tasks.append({
        "source_folder_id": source_id,
        "dest_folder_id": dest_id,
        "copied_files": copied_map
    })
    save_json(MONITOR_TASKS_FILE, tasks)
    return True

def remove_monitor_task(source_id, dest_id):
    tasks = load_json(MONITOR_TASKS_FILE)
    new_tasks = []
    removed = False
    for t in tasks:
        if t["source_folder_id"] == source_id and t["dest_folder_id"] == dest_id:
            removed = True
            continue
        new_tasks.append(t)
    if removed:
        save_json(MONITOR_TASKS_FILE, new_tasks)
    return removed

def get_monitor_tasks():
    return load_json(MONITOR_TASKS_FILE)

def check_monitor_tasks(log_callback):
    tasks = load_json(MONITOR_TASKS_FILE)
    updated = False
    for task in tasks:
        source_id = task["source_folder_id"]
        dest_id = task["dest_folder_id"]
        copied_map = task.get("copied_files", {})
        try:
            new_map = copy_new_items(source_id, dest_id, copied_map.copy(), base_path="")
        except Exception as e:
            log_callback(f"[Monitor] Copy error: {e}")
            continue
        if len(new_map) > len(copied_map):
            task["copied_files"] = new_map
            updated = True
            log_callback(f"[Monitor] New files/folders copied.")
    if updated:
        save_json(MONITOR_TASKS_FILE, tasks)

def monitor_worker(log_callback):
    while True:
        check_monitor_tasks(log_callback)
        time.sleep(10)

class DriveApp:
    def __init__(self, master):
        self.master = master
        master.title("Google Drive Manager")
        master.geometry("900x600")

        # Frame for main commands
        self.frame_commands = tk.Frame(master)
        self.frame_commands.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        commands = [
            ("Copy", self.copy_files),
            ("Monitor", self.show_monitor_tasks),
            ("AddMonitor", self.add_monitor_task_cmd),
            ("RemoveMonitor", self.remove_monitor_task_cmd),
            ("Report", self.show_report),
            ("SetPermissions", self.set_permissions)
        ]
        for (text, cmd) in commands:
            btn = tk.Button(self.frame_commands, text=text, width=20, command=cmd)
            btn.pack(side=tk.LEFT, padx=5)

        # Frame for "Cancel All Operations" button
        self.frame_cancel = tk.Frame(master)
        self.frame_cancel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        btn_cancel = tk.Button(self.frame_cancel, text="Cancel All Operations", width=25, command=self.cancel_all_operations)
        btn_cancel.pack(side=tk.LEFT, padx=5)

        self.log_area = scrolledtext.ScrolledText(master, width=100, height=25)
        self.log_area.pack(padx=10, pady=10)

        self.master.after(200, self.process_log_queue)
        self.monitor_thread = threading.Thread(target=monitor_worker, args=(self.threadsafe_log,), daemon=True)
        self.monitor_thread.start()

    def process_log_queue(self):
        while not log_queue.empty():
            msg = log_queue.get()
            self.log(msg)
        self.master.after(200, self.process_log_queue)

    def threadsafe_log(self, message):
        log_queue.put(message)

    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def copy_files(self):
        source_link = simpledialog.askstring("Copy", "Enter source folder URL:")
        if source_link is None:
            return
        dest_link = simpledialog.askstring("Copy", "Enter destination folder URL (leave blank for root):")
        if dest_link is None:
            return

        source_id = extract_folder_id(source_link)
        if not source_id:
            messagebox.showerror("Error", "Could not extract source folder ID.")
            return

        if dest_link.strip() == "":
            dest_id = GOOGLE_ROOT_ID
        else:
            dest_id = extract_folder_id(dest_link)
            if not dest_id:
                messagebox.showerror("Error", "Could not extract destination folder ID.")
                return

        def worker():
            self.threadsafe_log("Starting recursive copy (Copy)...")
            try:
                copied_map = copy_new_items(source_id, dest_id, {}, base_path="")
                self.threadsafe_log(f"Copy finished. Total objects copied: {len(copied_map)}")
                tasks = get_monitor_tasks()
                exists = any(t["source_folder_id"] == source_id and t["dest_folder_id"] == dest_id for t in tasks)
                if not exists:
                    add_monitor_task(source_id, dest_id, copied_map)
                    self.threadsafe_log("Monitor task created.")
                add_change_record("copy", "(multiple objects)", "(multiple)", source_id, dest_id, "Recursive copy via Copy")
            except Exception as e:
                self.threadsafe_log(f"Copy error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def show_monitor_tasks(self):
        tasks = get_monitor_tasks()
        if not tasks:
            messagebox.showinfo("Monitor", "No monitor tasks.")
            return
        win = tk.Toplevel(self.master)
        win.title("Monitor Tasks")
        tree = ttk.Treeview(win, columns=("Source", "Destination", "CopiedCount"), show="headings")
        tree.heading("Source", text="Source Folder")
        tree.heading("Destination", text="Destination Folder")
        tree.heading("CopiedCount", text="Objects Copied")
        tree.pack(fill=tk.BOTH, expand=True)
        for task in tasks:
            tree.insert("", tk.END,
                        values=(
                            task["source_folder_id"],
                            task["dest_folder_id"],
                            len(task.get("copied_files", {}))
                        ))

    def add_monitor_task_cmd(self):
        source_link = simpledialog.askstring("AddMonitor", "Enter source folder URL:")
        if source_link is None:
            return
        dest_link = simpledialog.askstring("AddMonitor", "Enter destination folder URL (leave blank for root):")
        if dest_link is None:
            return

        source_id = extract_folder_id(source_link)
        if not source_id:
            messagebox.showerror("Error", "Could not extract source folder ID.")
            return

        if dest_link.strip() == "":
            dest_id = GOOGLE_ROOT_ID
        else:
            dest_id = extract_folder_id(dest_link)
            if not dest_id:
                messagebox.showerror("Error", "Could not extract destination folder ID.")
                return

        def worker():
            self.threadsafe_log("Starting initial copy for AddMonitor...")
            try:
                copied_map = copy_new_items(source_id, dest_id, {}, base_path="")
                self.threadsafe_log(f"Initial copy finished. Total objects copied: {len(copied_map)}")
                if add_monitor_task(source_id, dest_id, copied_map):
                    self.threadsafe_log(f"New monitor task added:\nSource: {source_id}\nDestination: {dest_id}")
                else:
                    self.threadsafe_log("Monitor task already exists!")
            except Exception as e:
                self.threadsafe_log(f"Initial copy error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def remove_monitor_task_cmd(self):
        source_link = simpledialog.askstring("RemoveMonitor", "Enter source folder URL:")
        if source_link is None:
            return
        dest_link = simpledialog.askstring("RemoveMonitor", "Enter destination folder URL (leave blank for root):")
        if dest_link is None:
            return

        source_id = extract_folder_id(source_link)
        if not source_id:
            messagebox.showerror("Error", "Could not extract source folder ID.")
            return
        if dest_link.strip() == "":
            dest_id = GOOGLE_ROOT_ID
        else:
            dest_id = extract_folder_id(dest_link)
            if not dest_id:
                messagebox.showerror("Error", "Could not extract destination folder ID.")
                return

        removed = remove_monitor_task(source_id, dest_id)
        if removed:
            self.log(f"Monitor task removed:\nSource: {source_id}\nDestination: {dest_id}")
        else:
            self.log("No monitor task found with the given paths.")

    def cancel_all_operations(self):
        def worker():
            self.threadsafe_log("Starting cancellation of all operations...")
            tasks = get_monitor_tasks()
            if not tasks:
                self.threadsafe_log("No monitor tasks to cancel.")
                return
            for task in tasks:
                source_id = task.get("source_folder_id", "Unknown")
                dest_id = task.get("dest_folder_id", "Unknown")
                self.threadsafe_log(f"Cancelling monitor task: Source: {source_id} -> Destination: {dest_id}")
                copied_map = task.get("copied_files", {})
                for rel_path, data in copied_map.items():
                    # data should be a dict with key "id"
                    obj_id = data.get("id") if isinstance(data, dict) else None
                    if not obj_id or len(obj_id.strip()) < 5:
                        self.threadsafe_log(f"Skipping deletion of object '{rel_path}': invalid ID '{obj_id}'")
                        continue
                    try:
                        delete_file(obj_id)
                        self.threadsafe_log(f"Deleted object '{rel_path}' (ID: {obj_id})")
                    except Exception as e:
                        self.threadsafe_log(f"Error deleting object '{rel_path}': {e}")
            save_json(MONITOR_TASKS_FILE, [])
            self.threadsafe_log("All monitor tasks cancelled; all copied objects deleted.")
        threading.Thread(target=worker, daemon=True).start()

    def show_report(self):
        changes = load_json(CHANGES_LOG_FILE)
        report_lines = ["==== Full Change Report ===="]
        report_lines.append(f"Google Root ID: {GOOGLE_ROOT_ID}")
        report_lines.append("")
        if changes:
            for rec in sorted(changes, key=lambda x: x["timestamp"]):
                line = f"{rec['timestamp']} | {rec['operation']} | File: {rec['file_name']} (ID: {rec['file_id']})"
                if rec['source_folder_id']:
                    line += f" | From: {rec['source_folder_id']}"
                if rec['dest_folder_id']:
                    line += f" | To: {rec['dest_folder_id']}"
                if rec['comment']:
                    line += f" | {rec['comment']}"
                report_lines.append(line)
        else:
            report_lines.append("No change records found.")
        report = "\n".join(report_lines)
        win = tk.Toplevel(self.master)
        win.title("Change Report")
        txt = scrolledtext.ScrolledText(win, width=100, height=30)
        txt.insert(tk.END, report)
        txt.pack()

    def set_permissions(self):
        file_link = simpledialog.askstring("SetPermissions", "Enter file/folder URL:")
        if not file_link:
            return
        file_id = extract_file_id(file_link)
        if not file_id:
            file_id = extract_folder_id(file_link)
            if not file_id:
                messagebox.showerror("Error", "Could not extract file/folder ID.")
                return
        email = simpledialog.askstring("SetPermissions", "Enter user email:")
        if not email:
            return
        role = simpledialog.askstring("SetPermissions", "Enter role (reader, writer, owner):")
        if not role or role.lower() not in ['reader', 'writer', 'owner']:
            messagebox.showerror("Error", "Invalid role.")
            return
        try:
            perm_id = set_file_permission(file_id, email, role.lower())
            self.log(f"Permissions set successfully. Permission ID: {perm_id}")
            add_change_record("setpermissions", "(unknown)", file_id, comment=f"Permissions {role} for {email}")
            messagebox.showinfo("SetPermissions", "Permissions set successfully.")
        except Exception as e:
            self.log(f"Error setting permissions: {e}")
            messagebox.showerror("Error", "Error setting permissions.")

if __name__ == '__main__':
    root = tk.Tk()
    app = DriveApp(root)
    root.mainloop()
