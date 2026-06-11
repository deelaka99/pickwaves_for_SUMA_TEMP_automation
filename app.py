import html
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = ROOT_DIR / "suma_temp.py"
MAX_LOG_LINES = 1000


def _init_state() -> None:
    defaults = {
        "process": None,
        "reader_thread": None,
        "log_queue": queue.Queue(),
        "logs": [],
        "started_at": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _is_running(process: Optional[subprocess.Popen]) -> bool:
    return process is not None and process.poll() is None


def _reader(process: subprocess.Popen, log_queue: queue.Queue) -> None:
    if process.stdout is None:
        return

    for line in iter(process.stdout.readline, ""):
        log_queue.put(line.rstrip("\n"))

    exit_code = process.wait()
    log_queue.put(f"[APP] Automation process exited with code {exit_code}.")


def _drain_logs() -> None:
    while True:
        try:
            line = st.session_state.log_queue.get_nowait()
        except queue.Empty:
            break
        st.session_state.logs.append(line)

    if len(st.session_state.logs) > MAX_LOG_LINES:
        st.session_state.logs = st.session_state.logs[-MAX_LOG_LINES:]


def _start_automation() -> None:
    if _is_running(st.session_state.process):
        return

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        [sys.executable, "-u", str(SCRIPT_PATH)],
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    st.session_state.process = process
    st.session_state.started_at = time.time()
    st.session_state.logs.append(
        f"[APP] Started {SCRIPT_PATH.name} with PID {process.pid}."
    )

    reader_thread = threading.Thread(
        target=_reader,
        args=(process, st.session_state.log_queue),
        daemon=True,
    )
    reader_thread.start()
    st.session_state.reader_thread = reader_thread


def _stop_automation() -> None:
    process = st.session_state.process
    if not _is_running(process):
        return

    st.session_state.logs.append(f"[APP] Stopping PID {process.pid}...")
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _status_text(process: Optional[subprocess.Popen]) -> str:
    if _is_running(process):
        return "Running"
    if process is None:
        return "Idle"
    return f"Stopped ({process.poll()})"


def _render_logs() -> None:
    escaped_logs = html.escape("\n".join(st.session_state.logs) or "No logs yet.")
    st.markdown(
        f"""
        <div class="log-panel"><pre>{escaped_logs}</pre></div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="SUMA TEMP Automation", page_icon="S", layout="wide")
    _init_state()
    _drain_logs()

    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1.5rem;
                max-width: 1100px;
            }
            .status-card {
                border: 1px solid #d8dee9;
                border-radius: 8px;
                padding: 0.75rem 1rem;
                background: #f8fafc;
            }
            .log-panel {
                height: 460px;
                overflow-y: auto;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background: #0f172a;
                color: #e5e7eb;
                padding: 0.9rem;
            }
            .log-panel pre {
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
                font-size: 0.9rem;
                line-height: 1.45;
                font-family: Consolas, "Courier New", monospace;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("SUMA TEMP Automation")

    process = st.session_state.process
    running = _is_running(process)

    col_start, col_stop, col_status = st.columns([1, 1, 3])
    with col_start:
        if st.button(
            "Start", type="primary", disabled=running, use_container_width=True
        ):
            _start_automation()
            st.rerun()
    with col_stop:
        if st.button("Stop", disabled=not running, use_container_width=True):
            _stop_automation()
            st.rerun()
    with col_status:
        st.markdown(
            f"<div class='status-card'><strong>Status:</strong> {_status_text(process)}</div>",
            unsafe_allow_html=True,
        )

    st.subheader("Logs")
    _render_logs()

    if running:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
