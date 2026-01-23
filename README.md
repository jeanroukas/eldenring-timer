# Elden Ring Nightreign Timer

A transparent, event-driven overlay for Elden Ring Nightreign that automatically tracks game "Days" and "Storm" phases using OCR.

## Overview

This application monitors your gameplay in real-time, detecting specific triggers ("JOUR 1", "VICTORY", etc.) to initiate a synchronized countdown timer. It is designed to help players anticipate storm phases and boss fights.

## Features

- **Automatic Cycle Detection**: Uses OCR (Tesseract) to read "Day" banners.
- **Smart Timer**: Tracks "Storm", "Shrinking", and "Boss" phases.
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

- **`q` or `Ctrl+Q`**: Quit the application.
- **`&` (1)**: Force trigger "JOUR I".
- **`é` (2)**: Force trigger "JOUR II".
- **`"` (3)**: Force trigger "JOUR III".
- **`(` (5)**: Cancel/False Alarm.
- **System Tray**: Right-click the tray icon to access Settings or Quit.

## Configuration

Edit `config.json` or use the "Settings" option in the system tray menu to adjust:

- **Monitor Region**: Select the screen area where the "Day" text appears.
- **Volume**: Adjust audio feedback volume.
- **Debug Options**: Enable/disable debug images and logs.
