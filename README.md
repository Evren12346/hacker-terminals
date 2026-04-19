# Hacker Terminals (Ubuntu + Kali)

Two themed Python terminal GUIs that run a real persistent bash shell:
- Ubuntu Hacker Terminal
- Kali Hacker Terminal

This folder is the canonical home for the terminal scripts and desktop launchers.
Older duplicate copies from the repository root are archived under `../archive/root_duplicates`.

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
