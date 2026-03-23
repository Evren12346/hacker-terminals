#!/usr/bin/env python3
"""Kali Linux-flavored hacker aesthetic terminal."""

from hacker_terminal_base import HackerTerminal


KALI_CONFIG = {
    "title": "Kali Hacker Terminal",
    "banner": "KALI // OPERATOR CONSOLE",
    "codename": "KALI-RTI",
    "prompt": "root@kali:~#",
    "geometry": "1060x700",
    "font": "DejaVu Sans Mono",
    "output_font_size": "12",
    "bg": "#010501",
    "panel": "#050d05",
    "fg": "#c5ffc5",
    "accent": "#3aff55",
    "accent2": "#8dff9a",
    "select": "#0f4a16",
    "input_bg": "#040904",
    "button_bg": "#0a1c0a",
    "button_active_bg": "#174217",
    "button_fg": "#ddffdd",
}


if __name__ == "__main__":
    HackerTerminal(KALI_CONFIG).run()