# Developer Guide

This document contains detailed technical information about the Elden Ring Nightreign Timer, including its architecture, game logic, and evolution plan.

## 🏗️ Architecture

The application is an **Event-Driven OCR Overlay** utilizing a **Service-Oriented Architecture** (SOA).

### Services

Managed by a Dependency Injection container (`ServiceContainer`).

1. **`IConfigService`**: Manages persistence of `config.json`.
2. **`IVisionService`**: Wrapper for `VisionEngine`. Manages background capture and OCR strategy.
3. **`IOverlayService`**: Manages the PyQt6 View (`ModernOverlay`).
4. **`IStateService`**: The "Brain". Implements the State Machine and consensus algorithm for triggers.
5. **`NightreignLogic`**: (New) Central static class encapsulating pure game invariants (Death, Graph Stability, Min Rune counts).
6. **`ITrayService`**: Manages the system tray icon and background persistence.

### Data Flow

`VisionEngine (Capture)` -> `VisionService (Detect)` -> `StateService (Decide)` -> `OverlayService (Update UI)`

### File Structure

- `main.py`: Entry point.
- `src/`: Core source code (services, engines, ui).
- `tools/`: Diagnostic and development scripts.
- `tests/`: Unit and integration tests.

---

## 🧠 Game Logic & State Machine

### Cycles

Total "Day" duration is 14 minutes, divided into 4 phases:

1. **Storm**: 4m 30s
2. **Shrinking**: 3m 00s
3. **Storm 2**: 3m 30s
4. **Shrinking 2**: 3m 00s

### Triggers

- **"Day 1"**: Starts Day 1 Cycle.
- **"Day 2"**: Starts Day 2 Cycle.
- **"Victory" / Boss**: Manual advance or specific triggers.

### OCR & Vision Engine

- **Engine**: Tesseract OCR (`--psm 7`).
- **Strategy**:
  - **Preprocessing**: Auto-resize (160px height), Gamma (0.5), Otsu Thresholding.
  - **Logic**:
    - **Fuzzy Logic**: Uses `difflib` for Day detection (Smart Typo acceptance, >70% similarity).
    - **Context Awareness**: Boss Phases heavily bias acceptance of next-day triggers.
  - **Consensus**: "Rolling Buffer" (2.5s window) checks for stable reads before firing triggers.

---

## 🔮 Roadmap & Gap Analysis

Based on a project audit (Jan 2026), the following areas have been identified for improvement to reach "Production Grade" status.

### 1. DevOps & CI/CD (🛑 Missing)

- **Status**: No automated testing or build pipeline.
- **Action**: Create `.github/workflows` to run tests on push.

### 2. Packaging & Distribution (🛑 Missing)

- **Status**: Users must install Python manually.
- **Action**: Create build scripts (PyInstaller/Nuitka) to generate standalone `EldenRingTimer.exe`.

### 3. Test Suite Maturity (⚠️ Archived)

- **Status**: Tests exist but are currently in `archive/tests/`.
- **Action**: Restore `tests/` to root, adopt `pytest`, and enforce coverage for critical components like `VisionEngine`.

### 4. Code Architecture (🚧 In Progress)

- **Status**: Phase 1 Refactoring complete, but `vision_engine.py` remains monolithic.
- **Action**: Split `VisionEngine` into `Capture`, `Processing`, and `OCR` sub-modules.

### 5. User Experience (⚠️ Partial)

- **Status**: Functional UI (PyQt6) exists, but lacks onboarding.
- **Action**: Implement a "Setup Wizard" for first-time region selection and an Auto-Updater.

### 6. Intelligence & Data (Phase 3 🚧)

- **Status**: Data collection tools exist (`archive/tuning_results`), but no automated training pipeline.
- **Action**: Formalize dataset labeling for future custom OCR models.

### Completed Milestones

- **Phase 1**: Architecture & DI Container (✅ Done)
- **Phase 2**: UI Modernization to PyQt6 (✅ Done)

---

## 🛠️ Tools & Scripts

Located in the `tools/` directory.

- `check_libs.py`: Verify dependencies.
- `check_region.py`: Visual tool to check monitor region.
- `diagnose_capture.py`: Diagnose screen capture issues.
- `optimize_ocr.py`: Tuning script for OCR parameters.
