# Elden Ring Nightreign Timer

A transparent, event-driven overlay for Elden Ring Nightreign that automatically tracks game "Days" and "Storm" phases using OCR.

## Overview

This application monitors your gameplay in real-time, detecting specific triggers ("JOUR 1", "VICTORY", etc.) to initiate a synchronized countdown timer. It is designed to help players anticipate storm phases and boss fights.

## Features

- **Automatic Cycle Detection**: Uses OCR (Tesseract) to read "Day" banners with fuzzy logic.
- **Smart Timer**: Tracks "Storm", "Shrinking", and "Boss" phases.
- **Auto-Reset**: Automatically detects "Main Menu" screen to reset the run (supports Rage Quit vs Victory logic).
- **Advanced Graph Analytics**: Tracks "Total Lifetime Wealth" with stability logic (Ratchet) to prevent OCR glitches.
- **Stat-Based Death Detection**: Strict validation of deaths (Level drop + Runes lost) to prevent false positives.
- **Visual Overlay**: Non-intrusive, always-on-top overlay with high-contrast text.
- **Audio Cues**: Beeps for critical phase changes and countdowns.
- **System Tray Integration**: Run in background, accessible via system tray.

## Installation

1. **Dependencies**: Ensure you have Python installed.

    ```bash
    pip install -r requirements.txt
    ```

2. **Tesseract OCR**: This project requires Tesseract OCR. Ensure it is installed and added to your system PATH, or configured in the code.

## Usage

### Starting the Application

- **Standard Start**: Run `start_background.bat`. This starts the application in the background (system tray).
- **Restart**: Run `restart.bat` to force-restart the application.

### Controls & Hotkeys

- **`Ctrl+F5`**: Reset / Start Day 1
- **`F6`**: Force Day 2
- **`F7`**: Force Day 3
- **`F8`**: Skip to next boss/phase
- **`F9`**: Toggle UI visibility
- **`F10`**: Undo last action
- **`F11`**: Quit the application
- **System Tray**: Right-click the tray icon to access Settings or Quit

### Phase Transitions

The timer automatically advances through phases:

- **Timer-based**: Phases with fixed durations (Storm, Shrinking) advance automatically when time expires
- **OCR-based**: Boss 1 → Day 2 transition uses "JOUR II" text detection
- **Black screen**: Boss 2 → Day 3 and Day 3 Prep → Final Boss use black screen fade detection (0.3-3.0s)

## Configuration

Edit `config.json` or use the "Settings" option in the system tray menu to adjust:

- **Monitor Region**: Select the screen area where the "Day" text appears.
- **Character Name Region**: Select the area to detect character selection (for auto-reset).
- **Volume**: Adjust audio feedback volume.
- **Debug Options**: Enable/disable debug images and logs.
