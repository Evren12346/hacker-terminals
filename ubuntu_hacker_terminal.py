#!/usr/bin/env python3
"""Ubuntu-flavored hacker aesthetic terminal."""

from hacker_terminal_base import HackerTerminal


UBUNTU_CONFIG = {
    "title": "Ubuntu Hacker Terminal",
    "banner": "UBUNTU // ACCESS NODE // OPERATOR",
    "codename": "UBN-XTERM",
    "prompt": "user@ubuntu:~$",
    "geometry": "1060x700",
    "font": "DejaVu Sans Mono",
    "output_font_size": "12",
    "bg": "#010401",
    "panel": "#051005",
    "fg": "#c8ffc8",
    "accent": "#39ff66",
    "accent2": "#8fffaa",
    "select": "#0f4f12",
    "input_bg": "#030803",
    "button_bg": "#0a2b0a",
    "button_active_bg": "#185618",
    "button_fg": "#e8ffe8",
}


if __name__ == "__main__":
    HackerTerminal(UBUNTU_CONFIG).run()