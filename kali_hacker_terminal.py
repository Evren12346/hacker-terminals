#!/usr/bin/env python3
"""Kali Linux-flavored hacker aesthetic terminal."""

from hacker_terminal_base import HackerTerminal


KALI_CONFIG = {
    "title": "Kali Hacker Terminal",
    "banner": "KALI // RED TEAM INTERFACE",
    "codename": "KALI-RTI",
    "prompt": "root@kali:~#",
    "geometry": "1060x700",
    "font": "DejaVu Sans Mono",
    "bg": "#05070a",
    "panel": "#0d1118",
    "fg": "#8be9fd",
    "accent": "#ff5c8a",
    "accent2": "#66ffd9",
    "select": "#213a46",
    "input_bg": "#0a0e15",
    "button_bg": "#29162a",
    "button_active_bg": "#44203f",
    "button_fg": "#ffd5df",
}


if __name__ == "__main__":
    HackerTerminal(KALI_CONFIG).run()