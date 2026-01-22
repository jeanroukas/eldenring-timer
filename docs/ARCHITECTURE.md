# Project Architecture

This document describes the internal architecture of the Elden Ring Nightreign Timer (Phase 2 - UI Modernization).

## Overview

The application is an **Event-Driven OCR Overlay** utilizing a **Service-Oriented Architecture**. It captures the game screen, detects specific text triggers ("JOUR 1", "JOUR 2", "JOUR 3", "VICTORY"), and automatically manages a game timer.

## Core Services

The application is built around distinct services managed by a Dependency Injection container.

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
  - Notifies observers (StateService) when text is detected.

### 4. `IOverlayService` (in `src/services/overlay_service.py`)

- **Responsibility**: Manages the UI View (**PyQt6**).
- **Logic**:
  - Owns and renders the `ModernOverlay` window.
  - Handles UI thread scheduling via Qt Signals.

### 5. `IStateService` (in `src/services/state_service.py`)

- **Responsibility**: The "Brain" of the application.
- **Logic**:
  - **Game Loop**: Monitors `nightreign.exe` to wake/hibernate the app.
  - **State Machine**: Tracks phases (Day 1 -> Storm -> Boss...).
  - **Consensus Algorithm**: Buffers OCR signals to prevent false positives.

## UI Components (in `src/ui/`)

- **`ModernOverlay`**: A frameless, transparent Qt window that stays on top. Uses custom painting for high-quality text outlines.
- **`SettingsWindow`**: A tabbed configuration interface with live persistence via `ConfigService`.

## File Structure

```
.
├── main.py                     # Application Entry Point (QApplication)
├── config.json                 # User Configuration
├── requirements.txt            # Dependencies (including PyQt6)
├── src/                        # Source Code
│   ├── service_container.py    # DI Container
│   ├── vision_engine.py        # Core OCR logic
│   ├── services/               # Service Layer
│   │   ├── config_service.py
│   │   ├── overlay_service.py  # Qt implementation
│   │   ├── state_service.py
│   │   └── vision_service.py
│   └── ui/                     # UI Layer (PyQt6)
│       ├── qt_overlay.py       # Transparent Window
│       └── settings_window.py  # Configuration UI
├── tests/                      # Tests
└── tools/                      # Dev Tools
```

## Data Flow

1. **Capture**: `VisionEngine` captures a frame.
2. **Detect**: `VisionService` notifies `StateService` of detected text.
3. **Decide**: `StateService` processes triggers and updates the internal state.
4. **Update**: `StateService` calls `OverlayService.update_timer()`.
5. **Render**: `OverlayService` emits a signal to update the `ModernOverlay` widget.
