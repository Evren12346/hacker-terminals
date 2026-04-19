# Hacker Terminals (Ubuntu + Kali)

Two themed Python terminal GUIs that run a real persistent bash shell with full terminal emulator functionality:
- Ubuntu Hacker Terminal
- Kali Hacker Terminal

This folder is the canonical home for the terminal scripts and desktop launchers.
Older duplicate copies from the repository root are archived under `../archive/root_duplicates`.

## Features

### Core Functionality
- **Real Bash Shell**: Persistent `/bin/bash -i` session with full PTY support
- **Command History**: Up/Down arrows with persistent storage across sessions
- **Tab Completion**: Native bash tab-completion support
- **Session Persistence**: Command history and settings saved automatically

### Advanced Keyboard Shortcuts
- `Ctrl+C`: Interrupt running process (SIGINT)
- `Ctrl+D`: Send EOF / logout
- `Ctrl+L`: Clear screen
- `Ctrl+A`: Select all in input field
- `Ctrl+U`: Clear from cursor to line start
- `Ctrl+K`: Clear from cursor to line end
- `Ctrl+W`: Delete word backward
- `Ctrl+Y`: Paste from clipboard
- `Ctrl+V`: Paste to input field
- `Ctrl+F`: Search output text
- `Ctrl+R`: Reverse search (opens search dialog)
- `Ctrl+Shift+C`: Copy selected output text
- `Ctrl++` / `Ctrl+-`: Adjust font size
- `Ctrl+0`: Reset font size
- `F11`: Toggle fullscreen
- `Escape`: Close search dialog

### Mouse & Interaction
- **Right-click Context Menu**: Copy, Select All, Clear Screen, Search
- **Middle-click Paste**: Paste clipboard content
- **Mouse Wheel Scrolling**: Smooth scrolling in output pane
- **URL Detection**: Clickable URLs that open in default browser
- **Visual Bell**: Status bar flashes for notifications

### Terminal Features
- **Dynamic Resizing**: Terminal size adjusts to window dimensions
- **ANSI Escape Sequence Handling**: Basic color and formatting support
- **Error Recovery**: Automatic shell restart on disconnection
- **Status Indicators**: Shows BUSY/ONLINE states
- **Search Dialog**: Find text within terminal output
- **Font Scaling**: Adjustable font sizes with persistence

### Theming
- **Ubuntu Theme**: Green-on-black with Ubuntu-inspired styling
- **Kali Theme**: Dark red/black with Kali Linux aesthetic
- Both themes include animated status indicators and hacker-style boot sequences

## Requirements
- Python 3
- Tkinter (usually preinstalled on Ubuntu/Kali)

## Run
```bash
python3 ubuntu_hacker_terminal.py
python3 kali_hacker_terminal.py
```

## Install Kali App Menu Launcher
From inside this repository on your Kali machine:

```bash
bash install_kali_launcher.sh
```

This creates:
- `~/.local/share/applications/KaliHackerTerminal.desktop`

## Notes
- Both variants share `hacker_terminal_base.py`.
- Desktop launcher files are included:
  - `UbuntuHackerTerminal.desktop`
  - `KaliHackerTerminal.desktop`
- The launcher files point at this folder, so the project is self-contained.
- Session data is stored in `~/.ubuntu_hacker_terminal_session` and `~/.kali_hacker_terminal_session`
