"""
ShimaTTS launcher. This is the only frozen binary in the distribution.

First run: provisions a private Python environment next to the exe using the
bundled uv binary - CUDA torch when an Nvidia GPU is present, CPU otherwise.
Every run after that: spawns the app from that environment in ~1s.

Keeping torch/f5-tts out of the frozen bundle keeps the download small
(GitHub caps release assets at 2 GB - CUDA torch alone is 4+ GB on disk)
and makes GPU support possible at all.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
EXE_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).parent
RUNTIME = EXE_DIR / "runtime"
LOG_PATH = EXE_DIR / "launcher.log"

PYTHON_VERSION = "3.11"
TORCH_PINS = ["torch==2.5.1", "torchaudio==2.5.1"]
F5_PIN = "f5-tts==1.1.20"
CUDA_INDEX = "https://download.pytorch.org/whl/cu121"
CPU_INDEX = "https://download.pytorch.org/whl/cpu"

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_log_file = open(LOG_PATH, "a", encoding="utf-8")


def log(msg: str) -> None:
    _log_file.write(msg.rstrip() + "\n")
    _log_file.flush()


def has_nvidia_gpu() -> bool:
    return shutil.which("nvidia-smi") is not None


def torch_index() -> str:
    override = os.environ.get("SHIMA_TORCH_INDEX")
    if override:
        return override
    return CUDA_INDEX if has_nvidia_gpu() else CPU_INDEX


def uv_env() -> dict:
    env = os.environ.copy()
    env["UV_PYTHON_INSTALL_DIR"] = str(EXE_DIR / "pydist")
    env["UV_CACHE_DIR"] = str(EXE_DIR / "uv-cache")
    env["UV_PYTHON_PREFERENCE"] = "only-managed"
    return env


def provision_stamp() -> str:
    h = hashlib.sha256()
    h.update((EXE_DIR / "requirements.txt").read_bytes())
    h.update(" ".join(TORCH_PINS + [F5_PIN, PYTHON_VERSION, torch_index()]).encode())
    return h.hexdigest()


def is_provisioned() -> bool:
    stamp_file = RUNTIME / ".provisioned"
    return stamp_file.exists() and stamp_file.read_text().strip() == provision_stamp()


def provision(on_line) -> None:
    uv = str(EXE_DIR / "uv.exe")
    py = str(RUNTIME / "Scripts" / "python.exe")
    req = str(EXE_DIR / "requirements.txt")
    index = torch_index()
    gpu = "Nvidia GPU detected - installing CUDA build" if index == CUDA_INDEX \
        else "No Nvidia GPU detected - installing CPU build (TTS will be slow)"

    steps = [
        (f"Setting up Python {PYTHON_VERSION}...",
         [uv, "venv", str(RUNTIME), "--clear", "--python", PYTHON_VERSION]),
        (f"Installing PyTorch ({gpu})... this is the big one, several GB",
         [uv, "pip", "install", "--python", py, *TORCH_PINS, "--index-url", index]),
        ("Installing F5-TTS...",
         [uv, "pip", "install", "--python", py, "--no-deps", F5_PIN]),
        ("Installing remaining dependencies...",
         [uv, "pip", "install", "--python", py, "-r", req]),
    ]

    env = uv_env()
    for title, cmd in steps:
        on_line(f"\n=== {title}")
        log(f"RUN: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=CREATE_NO_WINDOW, env=env, cwd=str(EXE_DIR),
        )
        for line in proc.stdout:
            log(line)
            on_line(line)
        if proc.wait() != 0:
            raise RuntimeError(f"Step failed ({title}) - see launcher.log")

    on_line("\n=== Cleaning up download cache...")
    subprocess.run([str(EXE_DIR / "uv.exe"), "cache", "clean"],
                   creationflags=CREATE_NO_WINDOW, env=env,
                   capture_output=True)
    (RUNTIME / ".provisioned").write_text(provision_stamp())
    on_line("\n=== Setup complete!")


def provision_with_gui() -> bool:
    import queue
    import tkinter as tk
    from tkinter import ttk

    lines: "queue.Queue[object]" = queue.Queue()
    result = {"ok": False}

    def worker():
        try:
            provision(lines.put)
            result["ok"] = True
            lines.put(None)
        except Exception as e:
            log(f"PROVISION FAILED: {e}")
            lines.put(f"\nERROR: {e}\n")
            lines.put(None)

    root = tk.Tk()
    root.title("ShimaTTS - First-time setup")
    root.geometry("640x420")
    root.configure(bg="#0d0d1a")
    tk.Label(
        root, text="Setting up ShimaTTS (one time only, several GB download)",
        bg="#0d0d1a", fg="#e0e0e0", font=("Segoe UI", 11),
    ).pack(pady=(14, 6))
    bar = ttk.Progressbar(root, mode="indeterminate", length=560)
    bar.pack(pady=4)
    bar.start(12)
    text = tk.Text(root, bg="#13132a", fg="#9aa", height=18, borderwidth=0,
                   font=("Consolas", 8), state="disabled")
    text.pack(fill="both", expand=True, padx=12, pady=10)

    threading.Thread(target=worker, daemon=True).start()

    def poll():
        done = False
        try:
            while True:
                item = lines.get_nowait()
                if item is None:
                    done = True
                    break
                text.configure(state="normal")
                text.insert("end", item if item.endswith("\n") else item + "\n")
                text.see("end")
                text.configure(state="disabled")
        except queue.Empty:
            pass
        if done:
            if result["ok"]:
                root.destroy()
            else:
                bar.stop()
                tk.Label(root, text="Setup failed - see launcher.log next to the exe.",
                         bg="#0d0d1a", fg="#fca5a5", font=("Segoe UI", 10)).pack(pady=4)
        else:
            root.after(100, poll)

    root.after(100, poll)
    root.mainloop()
    return result["ok"]


def attach_parent_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.AttachConsole(-1)
    except Exception:
        pass


def launch_app(args: list) -> int:
    console_mode = any(a.startswith("--test") or a in ("--smoke", "-h", "--help") for a in args)
    scripts = RUNTIME / "Scripts"
    interpreter = scripts / ("python.exe" if console_mode else "pythonw.exe")
    env = os.environ.copy()
    env["SHIMA_HOME"] = str(EXE_DIR)
    # PyInstaller sets TCL_LIBRARY/TK_LIBRARY to its temp extraction dir,
    # which is gone once the launcher exits - point the app at the managed
    # Python's own Tcl/Tk instead so tkinter works in the runtime
    for var, sub in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
        env.pop(var, None)
        found = next((EXE_DIR / "pydist").glob(f"*/tcl/{sub}"), None)
        if found:
            env[var] = str(found)
    cmd = [str(interpreter), "-m", "src.main", *args]
    log(f"LAUNCH: {' '.join(cmd)}")
    if console_mode:
        attach_parent_console()
        return subprocess.run(cmd, cwd=str(EXE_DIR), env=env).returncode
    subprocess.Popen(cmd, cwd=str(EXE_DIR), env=env, creationflags=CREATE_NO_WINDOW)
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:]]
    provision_only = "--provision-only" in args
    if provision_only:
        args.remove("--provision-only")

    if not is_provisioned():
        log("Runtime missing or outdated - provisioning")
        if provision_only:
            try:
                provision(lambda line: None)
            except Exception as e:
                log(f"PROVISION FAILED: {e}")
                return 1
        else:
            if not provision_with_gui():
                return 1

    if provision_only:
        return 0
    return launch_app(args)


if __name__ == "__main__":
    sys.exit(main())
