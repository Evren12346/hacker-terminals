#!/usr/bin/env python3
"""Kali Linux-flavored hacker aesthetic terminal."""

from hacker_terminal_base import HackerTerminal


KALI_CONFIG = {
    "title": "Kali Hacker Terminal",
    "banner": "KALI // RED CELL // ACCESS CORE",
    "codename": "KALI-RTI",
    "prompt": "root@kali:~#",
    "geometry": "1100x720",
    "font": "DejaVu Sans Mono",
    "output_font_size": "12",
    "bg": "#000300",
    "panel": "#041004",
    "fg": "#caffca",
    "accent": "#31ff4f",
    "accent2": "#9cff9c",
    "select": "#0c4a0f",
    "input_bg": "#020702",
    "button_bg": "#092809",
    "button_active_bg": "#186318",
    "button_fg": "#e4ffe4",
    "boot_lines": [
        "[ OK ] Mounting encrypted filesystem...",
        "[ OK ] Loading kernel security modules...",
        "[ OK ] Establishing PTY transport...",
        "[ OK ] Initializing exploit framework...",
        "[ OK ] Enabling stealth mode...",
        "[ OK ] Arming prompt subsystem...",
        "[ OK ] Red cell is online. Stay quiet.",
    ],
}


if __name__ == "__main__":
    HackerTerminal(KALI_CONFIG).run()