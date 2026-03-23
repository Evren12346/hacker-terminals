#!/usr/bin/env python3
"""Ubuntu-flavored hacker aesthetic terminal."""

from hacker_terminal_base import HackerTerminal


UBUNTU_CONFIG = {
    "title": "Ubuntu Hacker Terminal",
    "banner": "UBUNTU // CYBER OPS CONSOLE",
    "codename": "UBN-XTERM",
    "prompt": "user@ubuntu:~$",
    "geometry": "1060x700",
    "font": "DejaVu Sans Mono",
    "bg": "#07120a",
    "panel": "#0d1f12",
    "fg": "#9ef7a8",
    "accent": "#22e46f",
    "accent2": "#7cf5cb",
    "select": "#1a4f2a",
    "input_bg": "#0a1710",
    "button_bg": "#133a1f",
    "button_active_bg": "#1b5a2f",
    "button_fg": "#c8ffd4",
}


if __name__ == "__main__":
    HackerTerminal(UBUNTU_CONFIG).run()