# EDNA - Elite Dangerous Navigation Assistant

**EDNA** is a lightweight, single-file navigation companion for [Elite Dangerous](https://www.elitedangerous.com/), designed to help commanders plot and follow long-range routes with ease. It features joystick support, chord-based input detection, and both clipboard and keystroke output modes.

---

## Features

- **Joystick Support**: Auto-detects all connected joysticks and gamepads
- **Chord Detection**: Bind single buttons or combinations (e.g., two buttons simultaneously)
- **Dual Input Modes**:
  - **Clipboard**: Copies system names to clipboard
  - **Keystroke**: Types system names directly into Elite Dangerous
- **Route Management**: Load route CSV files and track progress
- **Manual Navigation**: Previous/Next buttons and Reset Route functionality
- **Progress Persistence**: Automatically saves and resumes your position
- **Elite Dangerous Theme**: Authentic orange/amber/green dark UI
- **Single-Instance Lock**: Prevents accidental multiple launches

---

## Installation

### Option 1: Pre-built Release (Recommended)

1. Download `EDNA.zip` from the [Releases](https://github.com/ficklef0x/EDNA/releases) page
2. Extract to any folder
3. Run `EDNA.exe`

### Option 2: Run from Source

1. Clone this repository:
   ```bash
   git clone https://github.com/ficklef0x/EDNA.git
   cd EDNA/EDNA-Main
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

---

## Usage

### Setting Up Routes

1. Place your route CSV files in the `Routes/` folder
2. Launch EDNA
3. Go to the **LOAD** tab and select your route
4. Route CSVs should have headers including: `System Name`, `Distance To Arrival`, `Distance Remaining`, `Neutron Star`, `Jumps`

### Binding Controls

1. Go to the **SETTINGS** tab
2. Click **DETECT** next to the action you want to bind
3. Press your joystick button(s) or keyboard key(s)
4. Release to confirm the binding

### Controls

| Action | Description |
|--------|-------------|
| **Next Jump** | Advance to the next system in the route |
| **Previous Jump** | Go back to the previous system |
| **Enter Jump** | Copy/type the current system name |
| **Reset Route** | Return to the beginning of the route |

### Input Modes

- **Clipboard Mode**: Copies system names to your clipboard (useful for third-party tools)
- **Keystroke Mode**: Types system names directly into Elite Dangerous's galaxy map search

**Note**: In Clipboard mode, the Enter Jump binding is disabled to prevent conflicts.

---

## File Structure

```
EDNA/
├── EDNA.exe              # Main executable (release)
├── EDNA_Icon.ico         # Application icon
├── EDNA_Icon.png         # Window icon
├── Routes/               # Place route CSV files here
│   └── *.csv
├── config.json           # User settings (auto-generated)
└── app.log               # Debug log (auto-generated)
```

---

## Building from Source

To create a standalone executable:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "EDNA" --icon="EDNA_Icon.ico" --add-data "EDNA_Icon.png;." main.py
```

The executable will be created in the `dist/` folder.

---

## Credits & Dependencies

EDNA is built with the following open-source libraries:

- **[pygame](https://www.pygame.org/)** - Joystick and event handling
- **[pyautogui](https://pyautogui.readthedocs.io/)** - Keystroke simulation
- **[pyperclip](https://github.com/asweigart/pyperclip)** - Clipboard operations
- **[tkinter](https://docs.python.org/3/library/tkinter.html)** - GUI framework (Python standard library)
- **[pyinstaller](https://pyinstaller.org/)** - Executable bundler (build tool)

---

## License

This project is open source. See the repository for license details.

---

*Fly safe, Commander. o7*
