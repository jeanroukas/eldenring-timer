# Project Architecture

This document describes the internal architecture of the Elden Ring Nightreign Timer.

## Overview

The application is an **Event-Driven OCR Overlay** that captures the game screen, detects specific text triggers ("JOUR 1", "JOUR 2", "JOUR 3", "VICTORY"), and automatically manages a countdown timer displayed on top of the game.

## Core Components

### 1. `App` (in `main.py`)

The central controller that acts as the "glue" between components.

- **Responsibility**: Application lifecycle, UI setup, Service loop (Hibernation/Wake), Event Dispatching.
- **Key Logic**:
  - **Hibernation Loop**: Scans for `nightreign.exe` every 5 seconds. Pauses Vision/Overlay when game is closed.
  - **State Machine**: Maintains the application state (Waiting -> Day 1 -> Boss 1 -> Day 2...).
  - **Consensus Algorithm**: Buffers OCR results (`trigger_buffer`) and uses a weighted voting system to prevent false positives (e.g., requires multiple consistent detections).

### 2. `VisionEngine` (in `src/vision_engine.py`)

The "eyes" of the application. It runs on a separate thread.

- **Responsibility**: Screen Capture, Image Preprocessing, OCR, Pattern Matching.
- **Mechanism**:
  - **Capture**: Uses `BetterCam` (DXGI) for low-latency capture or `WindowsGraphicsCapture` for HDR support.
  - **Pipeline**: Capture -> Preprocess (Gamma/Threshold) -> Tesseract OCR -> Clean Text.
  - **Optimization**: Uses a **2-Pass Strategy** (Dynamic Threshold first, Adaptive fallback) to handle varying lighting conditions (Day/Night cycles in game).
  - **Fast Mode**: Increases scan frequency (20Hz) when potential triggers are detected to capture fleeting text.

### 3. `Overlay` (in `src/overlay.py`)

The transparent UI window.

- **Responsibility**: Rendering the timer and status text.
- **Key Logic**:
  - **Transparent Window**: Uses "Chroma Key" transparency (`#000001` color key).
  - **Timer Logic**: Manages countdowns for specific phases (Storm, Shrinking).
  - **Audio Feedback**: Beeps on critical timer events (10s remaining, etc.).

### 4. `PatternManager` (in `src/pattern_manager.py`)

(Implicitly used by App/Vision)

- **Responsibility**: Fuzzy matching of OCR results against known patterns.
- **Logic**: Handles common misreadings (e.g., "JOURIL" -> "JOUR II") via a correction map.

## File Structure

```
.
├── main.py                     # Application Entry Point
├── config.json                 # User Configuration (Region, Debug flags)
├── requirements.txt            # Python dependencies
├── monitor.log                 # Service watchdog log
├── ocr_log.txt                 # Detailed OCR logs
├── ocr_patterns.json           # Known OCR patterns database
├── processes.txt               # Process list dump (for debugging)
├── scripts/                    # Scripts for end-users
│   ├── add_victory_region.py   # Helper to configure victory zone
│   ├── open_config.bat         # Launch config UI
│   └── start_background.bat    # Launch background service
├── src/                        # Core Application Code
│   ├── config.py               # Config loader/saver
│   ├── overlay.py              # Tkinter transparent overlay
│   ├── pattern_manager.py      # Fuzzy matching logic
│   ├── region_selector.py      # UI for selecting screen region
│   └── vision_engine.py        # Main OCR loop & Capture logic
├── tools/                      # Development & Analysis Tools
│   ├── analyze_best_params.py  # Analyze OCR tuning results
│   ├── analyze_data.py         # General data analysis
│   ├── analyze_images.py       # Image statistics
│   ├── analyze_logs.py         # Log parser
│   ├── analyze_region.py       # Region setting debugger
│   ├── benchmark_pil.py        # Performance test
│   ├── capture_samples.py      # Burst capture tool for training data
│   ├── cleanup_raw_samples.py  # Disk space cleaner
│   ├── debug_keys.py           # Keyboard hook debugger
│   ├── debug_shlex.py          # Shell execution debugger
│   ├── debug_vision_live.py    # Live vision debugger
│   ├── diagnostic_capture.py   # Single shot diagnostic
│   ├── label_samples.py        # Manual sample labeler
│   ├── list_windows.py         # Window title lister
│   ├── optimize_ocr.py         # Grid search for OCR params
│   ├── optimize_stars.py       # Star rating optimizer (experimental)
│   ├── probe_monitors.py       # Monitor topology probe
│   ├── probe_virtual_screen.py # Virtual screen coordinates probe
│   ├── tune_ocr.py             # Quick OCR tuner
│   ├── tune_ocr_params.py      # Parameter tuner v2
│   └── verify_dynamic_ocr.py   # Verify dynamic thresholding logic
├── tests/                      # Unit & Regression Tests
│   ├── test_capture_resultat.py# Test for victory screen capture
│   ├── test_ocr_tuning.py      # Test OCR parameters
│   ├── test_ocr_variants.py    # Comparison of OCR preprocessing
│   ├── test_pattern_manager.py # Test pattern matching logic
│   ├── test_patterns.json      # Test data
│   ├── test_patterns_fr.json   # French test data
│   ├── test_pil.py             # PIL functionality test
│   ├── test_vision_fix.py      # Regression test for specific bug
│   ├── test_wgc.py             # Windows Graphics Capture test
│   ├── test_wgc_mon1.py        # WGC Monitor 1 specific test
│   ├── verify_final.py         # Verify final build
│   ├── verify_fix.py           # Verification script
│   ├── verify_fuzzy.py         # Fuzzy logic verification
│   ├── verify_multipass.py     # Multi-pass OCR verification
│   └── verify_winner.py        # Winner integration verification
└── docs/                       # Documentation
    └── ARCHITECTURE.md         # This file
```

## Data Flow

1. **Capture**: `VisionEngine` captures a frame from the defined `monitor_region`.
2. **Process**: Frame is processed (Greyscale -> Threshold) and sent to Tesseract.
3. **Detect**: Text is cleaned and normalized. If it matches a pattern (e.g., "JOUR"), it's sent to the `App` via callback.
4. **Decide**: `App` receives the trigger.
    - It activates **Fast Mode** to gather more samples.
    - It pushes the result to a **Time-Window Buffer (2.5s)**.
    - If the buffer reaches a consensus (e.g., 2+ "DAY 2" signals), it triggers the state change.
5. **Render**: `Overlay` updates the text/timer on the screen.
