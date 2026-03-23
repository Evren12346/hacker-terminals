#!/usr/bin/env python3
"""Shared hacker-themed terminal GUI using a persistent bash session."""

from __future__ import annotations

import os
import queue
import random
import re
import signal
import subprocess
import threading
import time
import tkinter as tk
from tkinter import font as tkfont


class HackerTerminal:
    """A lightweight terminal UI that talks to a real bash process through a PTY."""

    # Strip CSI sequences, OSC sequences (window-title etc.), and bare ESC codes.
    ANSI_ESCAPE_RE = re.compile(
        r"\x1b(?:\[[0-?]*[ -/]*[@-~]"       # CSI  — e.g. \x1b[32m
        r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"   # OSC  — e.g. \x1b]0;title\x07
        r"|[@-_][0-?]*[ -/]*[@-~]"          # Fe   — e.g. \x1b= \x1b>
        r"|.)"                               # bare ESC + one char
    )

    _TICKER_TEMPLATES = [
        "NET TRACE :: {noise} :: AUTH-OK",
        "PACKET RELAY :: {noise} :: ENCRYPTED",
        "CIPHER KEY :: {noise} :: ACTIVE",
        "MEM SCAN :: {noise} :: NOMINAL",
        "UPTIME :: {uptime} :: SYS-STABLE",
        "KERNEL {noise} :: HARDENED :: SECURE-BOOT",
        "ENTROPY :: {noise} :: HIGH",
        "THREAT LEVEL :: {noise} :: CONTAINED",
    ]

    def __init__(self, config: dict[str, str]) -> None:
        self.config = config
        self.root = tk.Tk()
        self.root.title(config["title"])
        self.root.geometry(config.get("geometry", "1000x680"))
        self.root.minsize(780, 500)
        self.root.configure(bg=config["bg"])

        self.output_queue: queue.Queue[str] = queue.Queue()
        self.command_history: list[str] = []
        self.history_index = 0
        self.prompt_visible = True
        self.signal_frames = [
            "SIG [|||||]", "SIG [|||| ]", "SIG [|||  ]", "SIG [||   ]",
            "SIG [|    ]", "SIG [     ]", "SIG [|    ]", "SIG [||   ]",
        ]
        self.signal_index = 0
        self._ticker_index = 0
        self._session_start = time.monotonic()
        self._base_font_size = int(config.get("output_font_size", "12"))
        self._current_font_size = self._base_font_size

        self.boot_lines: list[str] = config.get(
            "boot_lines",
            [
                "Initializing secure terminal bus...",
                "Loading shell transport layer...",
                "Mounting command history cache...",
                "Arming prompt subsystem...",
            ],
        )
        self.boot_index = 0
        self.boot_complete = False

        self.master_fd: int | None = None
        self.shell_process: subprocess.Popen[bytes] | None = None

        self._build_ui()
        self._start_shell()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(20, self._flush_output)
        self.root.after(220, self._animate_status_pulse)
        self.root.after(180, self._run_boot_sequence)
        self.root.after(200, self._update_clock)
        self.root.after(260, self._update_signal)
        self.root.after(300, self._blink_prompt)
        self.root.after(340, self._update_ticker)

    def _build_ui(self) -> None:
        self._title_font = tkfont.Font(family=self.config.get("font", "DejaVu Sans Mono"), size=14, weight="bold")
        self._body_font = tkfont.Font(
            family=self.config.get("font", "DejaVu Sans Mono"),
            size=self._current_font_size,
        )

        top_bar = tk.Frame(self.root, bg=self.config["panel"])
        top_bar.pack(fill="x")

        title = tk.Label(
            top_bar,
            text=self.config["banner"],
            bg=self.config["panel"],
            fg=self.config["accent"],
            font=self._title_font,
            pady=8,
        )
        title.pack(side="left", padx=12)

        self.status = tk.Label(
            top_bar,
            text="BOOTING",
            bg=self.config["panel"],
            fg=self.config["accent2"],
            font=(self.config.get("font", "DejaVu Sans Mono"), 10, "bold"),
            pady=8,
        )
        self.status.pack(side="right", padx=(8, 12))

        self.clock = tk.Label(
            top_bar,
            text="00:00:00",
            bg=self.config["panel"],
            fg=self.config["accent"],
            font=(self.config.get("font", "DejaVu Sans Mono"), 10, "bold"),
            pady=8,
        )
        self.clock.pack(side="right", padx=(8, 0))

        self.signal = tk.Label(
            top_bar,
            text=self.signal_frames[0],
            bg=self.config["panel"],
            fg=self.config["accent2"],
            font=(self.config.get("font", "DejaVu Sans Mono"), 10, "bold"),
            pady=8,
        )
        self.signal.pack(side="right", padx=(0, 8))

        self.ticker = tk.Label(
            self.root,
            text="",
            bg=self.config["bg"],
            fg=self.config["accent2"],
            anchor="w",
            font=(self.config.get("font", "DejaVu Sans Mono"), 9),
            padx=12,
            pady=3,
        )
        self.ticker.pack(fill="x")

        output_frame = tk.Frame(self.root, bg=self.config["panel"])
        output_frame.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        self.output = tk.Text(
            output_frame,
            bg=self.config["bg"],
            fg=self.config["fg"],
            insertbackground=self.config["accent"],
            selectbackground=self.config["select"],
            relief="flat",
            wrap="none",
            font=self._body_font,
            padx=12,
            pady=10,
        )

        self.v_scroll = tk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.output.yview,
            bg=self.config["panel"],
            troughcolor=self.config["input_bg"],
            activebackground=self.config["button_active_bg"],
        )
        self.h_scroll = tk.Scrollbar(
            output_frame,
            orient="horizontal",
            command=self.output.xview,
            bg=self.config["panel"],
            troughcolor=self.config["input_bg"],
            activebackground=self.config["button_active_bg"],
        )
        self.output.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.output.pack(side="left", fill="both", expand=True)
        self.output.configure(state="disabled")

        prompt_frame = tk.Frame(self.root, bg=self.config["panel"])
        prompt_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.prompt_label = tk.Label(
            prompt_frame,
            text=self.config["prompt"],
            bg=self.config["panel"],
            fg=self.config["accent"],
            font=(self.config.get("font", "DejaVu Sans Mono"), 11, "bold"),
            padx=10,
            pady=8,
        )
        self.prompt_label.pack(side="left")

        self.command_entry = tk.Entry(
            prompt_frame,
            bg=self.config["input_bg"],
            fg=self.config["fg"],
            insertbackground=self.config["accent"],
            relief="flat",
            font=self._body_font,
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)
        self.command_entry.configure(state="disabled")

        send_button = tk.Button(
            prompt_frame,
            text="EXEC",
            bg=self.config["button_bg"],
            fg=self.config["button_fg"],
            activebackground=self.config["button_active_bg"],
            activeforeground=self.config["button_fg"],
            relief="flat",
            bd=0,
            padx=15,
            pady=8,
            font=(self.config.get("font", "DejaVu Sans Mono"), 10, "bold"),
            command=self._submit_command,
        )
        send_button.pack(side="right", padx=6)

        self.command_entry.bind("<Return>", lambda _event: self._submit_command())
        self.command_entry.bind("<Up>", self._history_up)
        self.command_entry.bind("<Down>", self._history_down)
        self.command_entry.bind("<Control-l>", self._clear_via_shortcut)
        self.command_entry.bind("<Control-c>", self._send_sigint)
        self.command_entry.bind("<Control-d>", self._send_eof)
        self.command_entry.bind("<Tab>", self._send_tab)

        # Copy selected text from output pane with Ctrl+Shift+C
        self.root.bind("<Control-Shift-c>", self._copy_output_selection)

        # Font scaling
        self.root.bind("<Control-equal>", self._font_size_up)
        self.root.bind("<Control-plus>", self._font_size_up)
        self.root.bind("<Control-minus>", self._font_size_down)
        self.root.bind("<Control-0>", self._font_size_reset)

    def _start_shell(self) -> None:
        self.master_fd, slave_fd = os.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        self.shell_process = subprocess.Popen(
            ["/bin/bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            env=env,
        )
        os.close(slave_fd)

        reader = threading.Thread(target=self._reader_loop, daemon=True)
        reader.start()

    def _write_intro(self) -> None:
        intro = (
            f"[{self.config['codename']}] shell online\n"
            "Running real /bin/bash in a persistent session.\n"
            "  Up/Down        : command history\n"
            "  Tab            : shell tab-completion\n"
            "  Ctrl+C         : interrupt running process\n"
            "  Ctrl+D         : send EOF / logout\n"
            "  Ctrl+L         : clear screen\n"
            "  Ctrl++ / Ctrl- : adjust font size  |  Ctrl+0 : reset\n"
            "  Ctrl+Shift+C   : copy selected output\n\n"
        )
        self._append_text(intro)

    def _animate_status_pulse(self) -> None:
        if not self.root.winfo_exists():
            return
        current_fg = self.status.cget("fg")
        next_fg = self.config["accent"] if current_fg == self.config["accent2"] else self.config["accent2"]
        self.status.configure(fg=next_fg)
        self.root.after(380, self._animate_status_pulse)

    def _update_clock(self) -> None:
        if not self.root.winfo_exists():
            return
        self.clock.configure(text=time.strftime("%H:%M:%S"))
        self.root.after(500, self._update_clock)

    def _update_signal(self) -> None:
        if not self.root.winfo_exists():
            return
        self.signal_index = (self.signal_index + 1) % len(self.signal_frames)
        self.signal.configure(text=self.signal_frames[self.signal_index])
        self.root.after(260, self._update_signal)

    def _blink_prompt(self) -> None:
        if not self.root.winfo_exists():
            return
        self.prompt_visible = not self.prompt_visible
        self.prompt_label.configure(fg=self.config["accent"] if self.prompt_visible else self.config["accent2"])
        self.root.after(420, self._blink_prompt)

    def _update_ticker(self) -> None:
        if not self.root.winfo_exists():
            return
        noise = "".join(random.choice("0123456789ABCDEF") for _ in range(28))
        elapsed = int(time.monotonic() - self._session_start)
        uptime_str = f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}"
        template = self._TICKER_TEMPLATES[self._ticker_index % len(self._TICKER_TEMPLATES)]
        self._ticker_index += 1
        self.ticker.configure(text=template.format(noise=noise, uptime=uptime_str))
        self.root.after(280, self._update_ticker)

    def _run_boot_sequence(self) -> None:
        if self.boot_index < len(self.boot_lines):
            line = self.boot_lines[self.boot_index]
            self._append_text(f"[boot] {line}\n")
            self.boot_index += 1
            self.root.after(150, self._run_boot_sequence)
            return

        if not self.boot_complete:
            self.boot_complete = True
            self.command_entry.configure(state="normal")
            self.command_entry.focus_set()
            self.status.configure(text="ONLINE")
            self._write_intro()

    def _reader_loop(self) -> None:
        if self.master_fd is None:
            return
        while True:
            try:
                data = os.read(self.master_fd, 4096)
            except OSError:
                break
            if not data:
                break
            self.output_queue.put(data.decode(errors="replace"))
        self.output_queue.put("\n[shell disconnected]\n")

    def _flush_output(self) -> None:
        while not self.output_queue.empty():
            chunk = self.output_queue.get_nowait()
            self._append_text(chunk)
        self.root.after(20, self._flush_output)

    def _append_text(self, text: str) -> None:
        clean_text = self.ANSI_ESCAPE_RE.sub("", text)
        self.output.configure(state="normal")
        self.output.insert("end", clean_text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear_output_screen(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _clear_via_shortcut(self, _event: tk.Event) -> str:
        self._clear_output_screen()
        return "break"

    def _send_sigint(self, _event: tk.Event) -> str:
        """Send Ctrl+C (SIGINT) byte to the shell PTY."""
        if self.master_fd is not None and self.boot_complete:
            os.write(self.master_fd, b"\x03")
        return "break"

    def _send_eof(self, _event: tk.Event) -> str:
        """Send Ctrl+D (EOF) byte to the shell PTY."""
        if self.master_fd is not None and self.boot_complete:
            os.write(self.master_fd, b"\x04")
        return "break"

    def _send_tab(self, _event: tk.Event) -> str:
        """Forward Tab to the PTY for bash tab-completion.

        Any text currently in the entry is flushed to bash first so readline
        can expand it, then the entry is cleared.  Completions (or the
        expanded command) appear in the output pane.
        """
        if self.master_fd is None or not self.boot_complete:
            return "break"
        partial = self.command_entry.get()
        if partial:
            os.write(self.master_fd, partial.encode())
            self.command_entry.delete(0, "end")
        os.write(self.master_fd, b"\t")
        return "break"

    def _copy_output_selection(self, _event: tk.Event) -> str:
        """Copy the currently selected text in the output pane to the clipboard."""
        try:
            selected = self.output.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass
        return "break"

    def _font_size_up(self, _event: tk.Event) -> str:
        self._set_font_size(self._current_font_size + 1)
        return "break"

    def _font_size_down(self, _event: tk.Event) -> str:
        self._set_font_size(max(6, self._current_font_size - 1))
        return "break"

    def _font_size_reset(self, _event: tk.Event) -> str:
        self._set_font_size(self._base_font_size)
        return "break"

    def _set_font_size(self, size: int) -> None:
        self._current_font_size = size
        self._body_font.configure(size=size)

    def _submit_command(self) -> None:
        if self.master_fd is None:
            return
        if not self.boot_complete:
            return
        command = self.command_entry.get()
        if command.strip().lower() in {"clear", "cls"}:
            self._clear_output_screen()
            self.command_entry.delete(0, "end")
            return
        if command.strip():
            self.command_history.append(command)
            self.history_index = len(self.command_history)
        os.write(self.master_fd, (command + "\n").encode())
        self.command_entry.delete(0, "end")

    def _history_up(self, _event: tk.Event) -> str:
        if not self.command_history:
            return "break"
        self.history_index = max(0, self.history_index - 1)
        self.command_entry.delete(0, "end")
        self.command_entry.insert(0, self.command_history[self.history_index])
        return "break"

    def _history_down(self, _event: tk.Event) -> str:
        if not self.command_history:
            return "break"
        self.history_index = min(len(self.command_history), self.history_index + 1)
        self.command_entry.delete(0, "end")
        if self.history_index < len(self.command_history):
            self.command_entry.insert(0, self.command_history[self.history_index])
        return "break"

    def on_close(self) -> None:
        if self.shell_process and self.shell_process.poll() is None:
            try:
                os.killpg(self.shell_process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
