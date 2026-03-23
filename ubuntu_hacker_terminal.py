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
    "output_font_size": "12",
    "bg": "#020702",
    "panel": "#071007",
    "fg": "#b9ffb9",
    "accent": "#29ff5d",
    "accent2": "#73ff8f",
    "select": "#104d10",
    "input_bg": "#050d05",
    "button_bg": "#0c220c",
    "button_active_bg": "#144014",
    "button_fg": "#d9ffd9",
}


if __name__ == "__main__":
    HackerTerminal(UBUNTU_CONFIG).run()