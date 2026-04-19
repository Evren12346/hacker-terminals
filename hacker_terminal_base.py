#!/usr/bin/env python3
"""Shared hacker-themed terminal GUI using a persistent bash session."""

from __future__ import annotations

import os
import queue
import random
import re
import signal
import struct
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

        # Session management
        self.session_file = os.path.expanduser(f"~/.{config.get('codename', 'terminal').lower()}_session")
        self._load_session()

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

        self.command_entry.bind("<Control-l>", self._clear_via_shortcut)
        self.command_entry.bind("<Control-c>", self._send_sigint)
        self.command_entry.bind("<Control-d>", self._send_eof)
        self.command_entry.bind("<Tab>", self._send_tab)
        self.command_entry.bind("<Control-a>", self._select_all_input)
        self.command_entry.bind("<Control-u>", self._clear_line_to_start)
        self.command_entry.bind("<Control-k>", self._clear_line_to_end)
        self.command_entry.bind("<Control-w>", self._delete_word_backward)
        self.command_entry.bind("<Control-y>", self._paste_from_clipboard)

        # Copy selected text from output pane with Ctrl+Shift+C
        self.root.bind("<Control-Shift-c>", self._copy_output_selection)
        self.root.bind("<Control-Shift-C>", self._copy_output_selection)
        
        # Paste into input with Ctrl+V and middle-click
        self.root.bind("<Control-v>", self._paste_to_input)
        self.root.bind("<Control-V>", self._paste_to_input)
        self.command_entry.bind("<Button-2>", self._middle_click_paste)
        
        # Search functionality
        self.root.bind("<Control-f>", self._open_search)
        self.root.bind("<Control-F>", self._open_search)
        
        # Select all in output
        self.output.bind("<Control-a>", self._select_all_output)
        self.output.bind("<Control-A>", self._select_all_output)
        
        # Right-click context menu
        self.output.bind("<Button-3>", self._show_context_menu)
        self.command_entry.bind("<Button-3>", self._show_input_context_menu)
        
        # Mouse wheel scrolling
        self.output.bind("<MouseWheel>", self._mouse_wheel)
        self.output.bind("<Button-4>", self._mouse_wheel)  # Linux scroll up
        self.output.bind("<Button-5>", self._mouse_wheel)  # Linux scroll down
        
        # Handle window resizing
        self.root.bind("<Configure>", self._handle_resize)
        
        # Font scaling
        self.root.bind("<Control-equal>", self._font_size_up)
        self.root.bind("<Control-plus>", self._font_size_up)
        self.root.bind("<Control-minus>", self._font_size_down)
        self.root.bind("<Control-0>", self._font_size_reset)
        
        # Additional keyboard shortcuts
        self.root.bind("<Control-r>", self._reverse_search)
        self.root.bind("<Control-R>", self._reverse_search)
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._escape_handler)
        
        # Track shell busy state
        self.shell_busy = False

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
            "  Ctrl+A         : select all in input\n"
            "  Ctrl+U         : clear to line start\n"
            "  Ctrl+K         : clear to line end\n"
            "  Ctrl+W         : delete word backward\n"
            "  Ctrl+Y         : paste from clipboard\n"
            "  Ctrl+V         : paste to input\n"
            "  Ctrl+F         : search output\n"
            "  Ctrl++ / Ctrl- : adjust font size  |  Ctrl+0 : reset\n"
            "  Ctrl+Shift+C   : copy selected output\n"
            "  Right-click     : context menu\n"
            "  Middle-click    : paste\n\n"
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
        # Try to restart shell if it disconnected unexpectedly
        self.root.after(1000, self._attempt_shell_restart)

    def _attempt_shell_restart(self) -> None:
        """Attempt to restart the shell if it disconnected."""
        if self.shell_process and self.shell_process.poll() is None:
            return  # Shell is still running
            
        self._append_text("\n[attempting to restart shell...]\n")
        try:
            self._start_shell()
            self._append_text("[shell restarted successfully]\n")
        except Exception as e:
            self._append_text(f"[failed to restart shell: {e}]\n")
            self.status.configure(text="ERROR")

    def _visual_bell(self) -> None:
        """Flash the status bar as a visual bell."""
        original_bg = self.status.cget("bg")
        self.status.configure(bg=self.config["accent"])
        self.root.after(100, lambda: self.status.configure(bg=original_bg))

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
            self._save_session()  # Save session after each command
            self.shell_busy = True
            self.status.configure(text="BUSY")
        os.write(self.master_fd, (command + "\n").encode())
        self.command_entry.delete(0, "end")

    def _flush_output(self) -> None:
        while not self.output_queue.empty():
            chunk = self.output_queue.get_nowait()
            self._append_text(chunk)
            
            # Check if command completed (look for prompt)
            if self.prompt_visible and self.shell_busy:
                self.shell_busy = False
                self.status.configure(text="ONLINE")
                
        self.root.after(20, self._flush_output)

    def _update_terminal_size(self) -> None:
        """Update the PTY terminal size based on window dimensions."""
        if self.master_fd is None or self.shell_process is None:
            return
            
        try:
            import fcntl
            import termios
            
            # Get current window dimensions
            output_width = self.output.winfo_width()
            output_height = self.output.winfo_height()
            
            # Estimate character dimensions (rough approximation)
            char_width = self._body_font.measure("M")
            char_height = self._body_font.metrics("linespace")
            
            if char_width > 0 and char_height > 0:
                cols = max(80, output_width // char_width)
                rows = max(24, output_height // char_height)
                
                # Set terminal size
                size = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size)
                
                # Send SIGWINCH to shell to notify of size change
                try:
                    self.shell_process.send_signal(signal.SIGWINCH)
                except ProcessLookupError:
                    pass
        except (ImportError, OSError):
            pass  # Gracefully handle systems that don't support this

    def _append_text(self, text: str) -> None:
        """Append text to output with improved ANSI handling and URL detection."""
        # Handle ANSI escape sequences for colors and formatting
        self._process_ansi_text(text)
        
        # Detect and make URLs clickable
        self._detect_and_highlight_urls()

    def _process_ansi_text(self, text: str) -> None:
        """Process text with ANSI escape sequences for colors and formatting."""
        # For now, we'll strip ANSI codes but could implement full color support
        # This is a simplified version - full ANSI parsing would be more complex
        clean_text = self.ANSI_ESCAPE_RE.sub("", text)
        
        self.output.configure(state="normal")
        self.output.insert("end", clean_text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _detect_and_highlight_urls(self) -> None:
        """Detect URLs in the output and make them clickable."""
        content = self.output.get("1.0", "end-1c")
        
        # Simple URL regex pattern
        url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w)*)?)?'
        
        # Remove existing URL tags
        self.output.tag_remove("url", "1.0", "end")
        
        for match in re.finditer(url_pattern, content):
            start_idx = self._get_text_index(match.start())
            end_idx = self._get_text_index(match.end())
            
            self.output.tag_add("url", start_idx, end_idx)
            self.output.tag_config("url", foreground=self.config["accent"], underline=True)
            self.output.tag_bind("url", "<Button-1>", 
                               lambda e, url=match.group(): self._open_url(url))
            self.output.tag_bind("url", "<Enter>", 
                               lambda e: self.output.config(cursor="hand2"))
            self.output.tag_bind("url", "<Leave>", 
                               lambda e: self.output.config(cursor=""))

    def _get_text_index(self, char_pos: int) -> str:
        """Convert character position to text widget index."""
        content = self.output.get("1.0", "end-1c")
        line = content[:char_pos].count('\n') + 1
        line_start = content.rfind('\n', 0, char_pos)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        char = char_pos - line_start
        return f"{line}.{char}"

    def _open_url(self, url: str) -> None:
        """Open URL in default browser."""
        import webbrowser
        webbrowser.open(url)

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

    def _select_all_input(self, _event: tk.Event) -> str:
        """Select all text in the input field."""
        self.command_entry.select_range(0, "end")
        return "break"

    def _clear_line_to_start(self, _event: tk.Event) -> str:
        """Clear from cursor to start of line (Ctrl+U)."""
        self.command_entry.delete(0, "insert")
        return "break"

    def _clear_line_to_end(self, _event: tk.Event) -> str:
        """Clear from cursor to end of line (Ctrl+K)."""
        self.command_entry.delete("insert", "end")
        return "break"

    def _delete_word_backward(self, _event: tk.Event) -> str:
        """Delete word backward (Ctrl+W)."""
        current = self.command_entry.index("insert")
        text = self.command_entry.get()
        # Find the start of the current word
        word_start = current
        while word_start > 0 and text[word_start - 1].isspace():
            word_start -= 1
        while word_start > 0 and not text[word_start - 1].isspace():
            word_start -= 1
        self.command_entry.delete(word_start, current)
        return "break"

    def _paste_from_clipboard(self, _event: tk.Event) -> str:
        """Paste from clipboard (Ctrl+Y)."""
        try:
            clipboard = self.root.clipboard_get()
            self.command_entry.insert("insert", clipboard)
        except tk.TclError:
            pass
        return "break"

    def _paste_to_input(self, _event: tk.Event) -> str:
        """Paste clipboard content into input field."""
        try:
            clipboard = self.root.clipboard_get()
            self.command_entry.insert("insert", clipboard)
            self.command_entry.focus_set()
        except tk.TclError:
            pass
        return "break"

    def _middle_click_paste(self, _event: tk.Event) -> str:
        """Handle middle-click paste."""
        return self._paste_to_input(_event)

    def _open_search(self, _event: tk.Event) -> str:
        """Open search dialog for output text."""
        self._create_search_dialog()
        return "break"

    def _create_search_dialog(self) -> None:
        """Create a search dialog for finding text in output."""
        if hasattr(self, 'search_dialog') and self.search_dialog.winfo_exists():
            self.search_dialog.lift()
            self.search_entry.focus_set()
            return
            
        self.search_dialog = tk.Toplevel(self.root)
        self.search_dialog.title("Search Output")
        self.search_dialog.geometry("400x120")
        self.search_dialog.resizable(False, False)
        self.search_dialog.configure(bg=self.config["panel"])
        
        # Search entry
        search_frame = tk.Frame(self.search_dialog, bg=self.config["panel"])
        search_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(search_frame, text="Search:", bg=self.config["panel"], 
                fg=self.config["fg"]).pack(side="left")
        
        self.search_entry = tk.Entry(search_frame, bg=self.config["input_bg"], 
                                   fg=self.config["fg"], width=30)
        self.search_entry.pack(side="left", padx=(5, 0))
        self.search_entry.bind("<Return>", self._perform_search)
        
        # Buttons
        button_frame = tk.Frame(self.search_dialog, bg=self.config["panel"])
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        tk.Button(button_frame, text="Find Next", command=self._perform_search,
                 bg=self.config["button_bg"], fg=self.config["button_fg"],
                 activebackground=self.config["button_active_bg"]).pack(side="left", padx=(0, 5))
        
        tk.Button(button_frame, text="Close", command=self.search_dialog.destroy,
                 bg=self.config["button_bg"], fg=self.config["button_fg"],
                 activebackground=self.config["button_active_bg"]).pack(side="left")
        
        self.search_entry.focus_set()

    def _perform_search(self, _event: tk.Event | None = None) -> None:
        """Perform search in output text."""
        search_term = self.search_entry.get().strip()
        if not search_term:
            return
            
        # Get current output content
        content = self.output.get("1.0", "end-1c")
        
        # Find current insertion point
        current_pos = self.output.index("insert")
        
        # Search from current position onward
        start_index = content.find(search_term, int(float(current_pos.split('.')[0])) - 1)
        if start_index == -1:
            # Wrap around to beginning
            start_index = content.find(search_term)
            
        if start_index != -1:
            # Convert to text widget indices
            line = content[:start_index].count('\n') + 1
            char = start_index - content.rfind('\n', 0, start_index)
            start_idx = f"{line}.{char}"
            end_idx = f"{line}.{char + len(search_term)}"
            
            # Select and scroll to the found text
            self.output.tag_remove("search", "1.0", "end")
            self.output.tag_add("search", start_idx, end_idx)
            self.output.tag_config("search", background=self.config["select"])
            self.output.mark_set("insert", end_idx)
            self.output.see(start_idx)
        else:
            # Clear previous search highlights
            self.output.tag_remove("search", "1.0", "end")

    def _select_all_output(self, _event: tk.Event) -> str:
        """Select all text in output pane."""
        self.output.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _show_context_menu(self, event: tk.Event) -> None:
        """Show context menu for output pane."""
        menu = tk.Menu(self.root, tearoff=0, bg=self.config["panel"], fg=self.config["fg"])
        menu.add_command(label="Copy", command=self._copy_output_selection_menu)
        menu.add_command(label="Select All", command=lambda: self._select_all_output(event))
        menu.add_separator()
        menu.add_command(label="Clear Screen", command=self._clear_output_screen)
        menu.add_command(label="Search...", command=self._create_search_dialog)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_input_context_menu(self, event: tk.Event) -> None:
        """Show context menu for input field."""
        menu = tk.Menu(self.root, tearoff=0, bg=self.config["panel"], fg=self.config["fg"])
        menu.add_command(label="Paste", command=lambda: self._paste_to_input(event))
        menu.add_command(label="Select All", command=lambda: self._select_all_input(event))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_output_selection_menu(self) -> None:
        """Copy selected text from output pane (menu version)."""
        try:
            selected = self.output.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass

    def _mouse_wheel(self, event: tk.Event) -> None:
        """Handle mouse wheel scrolling."""
        if event.delta > 0:
            self.output.yview_scroll(-1, "units")
        else:
            self.output.yview_scroll(1, "units")

    def _handle_resize(self, event: tk.Event) -> None:
        """Handle window resize events."""
        if event.widget == self.root:
            # Update terminal size if PTY supports it
            self._update_terminal_size()

    def _font_size_up(self, _event: tk.Event) -> str:
        self._set_font_size(self._current_font_size + 1)
        return "break"

    def _font_size_down(self, _event: tk.Event) -> str:
        self._set_font_size(max(6, self._current_font_size - 1))
        return "break"

    def _font_size_reset(self, _event: tk.Event) -> str:
        self._set_font_size(self._base_font_size)
        return "break"

    def _reverse_search(self, _event: tk.Event) -> str:
        """Open reverse search (Ctrl+R) - simplified version."""
        self._create_search_dialog()
        return "break"

    def _toggle_fullscreen(self, _event: tk.Event) -> str:
        """Toggle fullscreen mode."""
        current_state = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not current_state)
        return "break"

    def _escape_handler(self, _event: tk.Event) -> str:
        """Handle Escape key - clear search or close dialogs."""
        if hasattr(self, 'search_dialog') and self.search_dialog.winfo_exists():
            self.search_dialog.destroy()
            return "break"
        return "break"

    def _set_font_size(self, size: int) -> None:
        self._current_font_size = size
        self._body_font.configure(size=size)
        self._save_session()  # Save font size change

    def _load_session(self) -> None:
        """Load command history and settings from session file."""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    import json
                    session_data = json.load(f)
                    self.command_history = session_data.get('history', [])
                    self.history_index = len(self.command_history)
                    self._current_font_size = session_data.get('font_size', self._base_font_size)
                    self._set_font_size(self._current_font_size)
        except (OSError, json.JSONDecodeError, KeyError):
            pass  # Use defaults if session file is corrupted

    def _save_session(self) -> None:
        """Save command history and settings to session file."""
        try:
            session_data = {
                'history': self.command_history[-1000:],  # Keep last 1000 commands
                'font_size': self._current_font_size,
                'timestamp': time.time()
            }
            with open(self.session_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(session_data, f, indent=2)
        except OSError:
            pass  # Silently fail if we can't save session

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
            self._save_session()  # Save session after each command
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
        self._save_session()  # Save session on exit
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
