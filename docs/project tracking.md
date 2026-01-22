# Project Tracking: Elden Ring Nightreign Timer

> [!IMPORTANT]
> **CRITICAL**: It is extremely important to keep a trace of all user requests and project changes in this file for future interactions. Update this log with every significant change.

## 📌 Project Overview

A Python-based overlay for Elden Ring Nightreign that uses OCR to detect game cycles ("Day 1", "Day 2") and displays a synchronized countdown timer for specific storm phases.

## 🧠 Implemented Logic

The timer logic is a State Machine derived from community tools (lud-berthe and Kiluan7).

### Global Cycle Structure

Total "Day" duration is 14 minutes (840s), divided into 4 phases:

1. **Storm**: 4 minutes 30 seconds (270s)
2. **Shrinking**: 3 minutes (180s)
3. **Storm 2**: 3 minutes 30 seconds (210s)
4. **Shrinking 2**: 3 minutes (180s)

### Triggers & Transitions

- **"Day 1" (OCR)** → Starts Day 1 Cycle (Phases 1-4).
- **"Day 2" (OCR)** → Starts Day 2 Cycle (Phases 6-9).
- **Boss Phases** (Day 1 End, Day 2 End) → Manual advance (or wait for next trigger).
- **Cycle Reset** → After Day 2 Final Boss, overlay resets to "Waiting for Day 1...".

## 👁️ OCR & Vision Engine

Located in `src/vision_engine.py`.

- **Engine**: Tesseract OCR (`--psm 7` single line).
- **Preprocessing Strategy (Optimized "Stars Aligned" config)**:
  - **Auto-Resize**: Input image scaled to **300px height** (crucial for serif clarity).
  - **Gamma Correction**: `gamma=0.8` (HDR detail recovery).
  - **Otsu Thresholding**: Replaced adaptive thresholding to eliminate "hollow letters" (donuts).
  - **Morphological Closing**: 2x2 kernel to bridge gaps and solidify character strokes.
  - **Inversion**: Handled within Otsu/Preprocessing logic.
  - **Debug**: Saves `debug_raw`, `debug_gray`, and `debug_proc` to `debug_images/`.
- **Cleaning Logic**:
  - **Raw Output**: No fuzzy mapping logic (e.g. `ae -> Day 1`) is applied per user request. The system trusts the raw, cleaned (upper/strip) output.

## 👤 User Preferences & Constraints

- **Strict Detection**: Do not use fuzzy mappings. Only trust clear reads.
- **Nomenclature**: Use specific phase names ("Storm", "Shrinking") in the overlay.
- **Reset Behavior**: The timer must automatically reset to a waiting state after the full run (post-Day 2).
- **Region Selection**: User prefers selecting a region, but OCR must handle "very big" text.

## 🔗 References & Resources

- **lud-berthe/nightreign-auto-timer**: [GitHub Link](https://github.com/lud-berthe/nightreign-auto-timer) - Logic Source: Day/Night cycle concepts.
- **Kiluan7/nightreign-storm-timer**: [GitHub Link](https://github.com/Kiluan7/nightreign-storm-timer) - Logic Source: Specific phase durations.

## 📝 Recent Actions Log

- **2026-01-22**:
  - **OCR Fine-tuning (HDR)**: Implemented Grid Search. Found that **Gamma 0.5 + Threshold 245 + Height 80** is the optimal configuration for HDR "burnt" images.
  - **Validation**: User confirmed the fix works in-game. "JOUR I" / "JOUR II" are correctly detected.
  - **Cleanup**: Disabled default debug logging and image capture (set `debug_mode` to `false` in `config.json`).
  - **Data Collection**: Created `capture_samples.py` for burst capture and `optimize_ocr.py` for parameter tuning.
  - **Logic Revert**: Removed all hardcoded fuzzy logic mappings from `vision_engine.py` to produce raw OCR output `clean.strip().upper()`.
  - **UI Overhaul**:
    - **Typography**: Switched to White text with Black outline (Canvas implementation) for better readability.
    - **Layout**: Moved to Top-Right (`-50+20`) and Right-Aligned text (`anchor="e"`) per user preference.
    - **Size**: Increased overlay window to `600x120` (previously 450x120) as text was still truncated.
    - **Opacity**: Further reduced background opacity to `0.50` (was 0.85 then 0.65).
  - **Features**:
    - **Test Mode**: Added loop mechanism to cycle through all phases every 2 seconds for visual verification.
    - **Controls**: Added `Ctrl+Q` and `q` shortcut to quit the application.
  - **Logic Update**: Implemented "Smart Reset" for `trigger_day_1` and `trigger_day_2`.
    - **Previous Behavior**: Blocked reset if already in the same Day (to avoid flickering).
    - **New Behavior**: Allows reset if the current phase has been running for > 15 seconds. This handles "Game Over / Restart" scenarios automatically while preventing the timer from resetting constantly during the initial 5-10s banner display.
  - OCR Hardening: Added image resizing and aggressive thresholding (215).
  - Refined Triggers: Linked `main.py` OCR results to specific `trigger_day_1` / `trigger_day_2` methods.
  - **Trigger Logic**:
    - **Buffering**: Implemented a 2-second stability check. Triggers must persist (allowing for gaps < 2s) before firing.
    - **Glitch Filter**: Added a 0.5s minimum duration requirement for triggers.
    - **Robust Matching**: enhanced detection for "JOURI", "JOUR I", "DAY I" by stripping spaces and normalizing text.
  - **Cleanup**: Removed "Test/Demo Mode" from `overlay.py` entirely.
  - **Optimization**: Increased OCR sampling rate from 1Hz to 5Hz (0.2s interval) to capture fleeting "Day 2" triggers and pass the duration filter.
  - **Tuning**: Created `tune_preview.py`. Final selected values: **Gamma 0.05** (High Contrast) and **Threshold 254** (Strict).
  - **Features**:
    - **Blinking Warning (⚠️)**: Added a "⚠" prefix that blinks 30 seconds before any "Shrinking" phase to warn the user.
    - **Inline Recording Indicator**: Moved the recording indicator from a canvas circle to a "🔴 " prefix on the text itself.
    - **Debug Image Toggle**: Added a checkbox to `main.py` ("Save Debug Images") to control image saving independently of console logging.
  - **Optimization**:
    - **Dynamic OCR Sampling**: Implemented variable scan rates. System idles at 0.12s but accelerates to 0.02s upon detecting a potential trigger to capture more frames for validation.
    - **Resolution**: Doubled the OCR processed image height target to **160px** for improved accuracy.
    - **Smoothing & Robustness**: Implemented a "Rolling Buffer" with consensus logic:
      - **Buffer**: 2.5s window.
      - **Dominance Rule**: "Day 2" overrides "Day 1" if detected at least twice (resolves "JOUR IT" noise).
      - **Consensus**: Requires consensus and minimum span (> 0.5s) to fire.
  - **Background Service (In Progress)**:
    - **Goal**: Auto-start with Windows, hibernate when game is not running, wake on `eldenring.exe`.
    - **Strategy**:
      - Use `tasklist` to monitor process presence (5s polling).
      - Pause `VisionEngine` and Hide `Overlay` when hibernating.
      - Add `--config` arg to show GUI for settings.
  - **Adaptive OCR & Self-Learning**:
    - **French Only**: Strictly "JOUR". Remove all "DAY" references.
    - **Hotkeys (AZERTY)**:
      - `&` (1): Force "JOUR I".
      - `é` (2): Force "JOUR II".
      - `"` (3): Force "JOUR III".
      - `(` (5): False Alarm / Cancel.
    - **Fast Mode**: Coherent triggers only (no single letters). Triggers must be part of learning/known patterns.
    - **Audio Feedback**:
      - Beep on Fast Mode entry.
      - Beep at **30s** remaining.
      - Beep at **10s** remaining.
      - Beep at **3s, 2s, 1s** remaining.
  - **OCR Overhaul (Multi-Pass & Geometry)**:
    - **3-Pass Strategy**: Implemented sequential preprocessing to handle all lighting conditions (Pass 1: Otsu, Pass 2: Fixed 200/Gamma 1.2 for HDR, Pass 3: Adaptive).
    - **Geometry Validation**: Added `text_width` analysis using Tesseract's `image_to_data`. Differentiates between short (Day 1/2) and long (Day 3) banners based on the visual shape of the text.
    - **Fuzzy Matching**: Integrated `fuzzywuzzy` for better handle on OCR misreads, with strict length penalties and exact match boosts.
    - **Day 3 (Stopwatch)**: Consolidated all Day 3 phases into a single positive stopwatch phase and implemented "sticky" trigger logic to prevent accidental resets.
