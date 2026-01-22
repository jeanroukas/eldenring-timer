# Elden Ring Timer - Project Tracking

## 🎯 Current Objectives

- [x] **Core OCR**: "Day" Detection (Journal I, II, III).
- [ ] **Core OCR**: "Victory" Detection (BOSS DEFEATED / RÉSULTAT).
- [ ] **UI/Overlay**: Timer display and history.
- [ ] **Data Persistence**: Saving run splitting/segments.

## 🟢 Completed Milestones

### 1. Day Detection Optimization (Jan 2026)

- **Problem**: "Day 2" was consistently misread as `JOURIL` or `JOURTI`.
- **Solution**:
  - Implemented `Dynamic Threshold` formula: `230 + (Brightness * 0.1)`.
  - Added `Adaptive` and `Inverted` fallback passes.
  - Added `CORRECTION_MAP` for common OCR typos.
- **Result**: ~40% strict accuracy on raw frames (enough for reliable detection over 1 second).

## 📝 Roadmap / Next Steps

### Phase 2: Victory Detection

- The current victory detection uses fuzzy matching on "RESULTAT".
- **Action**: We need to collect "Victory" samples just like we did for "Day" to ensure it triggers perfectly (vital for splitting).

### Phase 3: Application Logic

- **State Machine**: Ensure state transitions (Menu -> Loading -> Game -> Victory -> Menu) are robust.
- **Overlay**: Ensure it draws on top of the game (Borderles/Windowed).

### Phase 4: Polish

- **Performance**: Ensure OCR doesn't eat CPU (currently efficiently early-exiting).
- **Packaging**: Create .exe.
