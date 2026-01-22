# Project Architecture

This document describes the internal architecture of the Elden Ring Nightreign Timer (Phase 1 Refactoring).

## Overview

The application is an **Event-Driven OCR Overlay** utilizing a **Service-Oriented Architecture**. It captures the game screen, detects specific text triggers ("JOUR 1", "JOUR 2", "JOUR 3", "VICTORY"), and automatically manages a game timer.

## Core Services

The application has been refactored from a monolithic class into distinct services managed by a Dependency Injection container.

### 1. `ServiceContainer` (in `src/service_container.py`)

A singleton container that manages the lifecycle and dependency resolution of all services.

### 2. `IConfigService` (in `src/services/config_service.py`)

- **Responsibility**: Loads and saves `config.json`.
- **Logic**: Provides typed access to configuration values and handles persistence.

### 3. `IVisionService` (in `src/services/vision_service.py`)

- **Responsibility**: Acts as a high-level wrapper around the `VisionEngine`.
- **Logic**:
  - Manages the background capture thread.
  - Implements the **2-Pass OCR Strategy** (Dynamic Threshold -> Adaptive Fallback).
  - Handles **Fast Mode** (20Hz scanning) when triggers are suspected.
  - Notifies observers (StateService) when text is detected.

### 4. `IOverlayService` (in `src/services/overlay_service.py`)

- **Responsibility**: Manages the UI View (Tkinter).
- **Logic**:
  - Renders the transparent overlay window.
  - Exposes methods like `update_timer(text)` and `show_recording(bool)`.
  - Handles UI thread scheduling.

### 5. `IStateService` (in `src/services/state_service.py`)

- **Responsibility**: The "Brain" of the application.
- **Logic**:
  - **Game Loop**: Monitors `nightreign.exe` to wake/hibernate the app.
  - **State Machine**: Tracks phases (Day 1 -> Storm -> Boss...).
  - **Consensus Algorithm**: Buffers OCR signals to prevent false positives.
  - **Logic**: Handles Boss 3 sequences (Black screen detection) and Victory checks.

## File Structure

```
.
├── main.py                     # Application Entry Point (Bootstrapper)
├── config.json                 # User Configuration
├── requirements.txt            # Dependencies
├── monitor.log                 # Service watchdog log
├── ocr_log.txt                 # Detailed OCR logs
├── ocr_patterns.json           # OCR fuzzy matching patterns
├── src/                        # Source Code
│   ├── service_container.py    # DI Container
│   ├── pattern_manager.py      # Fuzzy Match Logic
│   ├── region_selector.py      # UI Utility
│   ├── vision_engine.py        # Core Computer Vision Implementation
│   └── services/               # Service Layer
│       ├── base_service.py     # Interfaces (Abstract Base Classes)
│       ├── config_service.py   # Config Implementation
│       ├── overlay_service.py  # UI Implementation
│       ├── state_service.py    # Game Logic Implementation
│       └── vision_service.py   # Vision Wrapper
├── tests/                      # Tests
└── tools/                      # Dev Tools
```

## Data Flow

1. **Capture**: `VisionEngine` (via `VisionService`) captures a frame.
2. **Process**: OCR is performed. If text is found, observers are notified.
3. **Event**: `StateService` (observer) receives the raw text event.
4. **Decide**: `StateService` filters the event through its **Time-Window Buffer**.
5. **Update**: If a state change occurs, `StateService` calls `OverlayService.update_timer()`.
6. **Render**: `OverlayService` updates the Tkinter canvas.
