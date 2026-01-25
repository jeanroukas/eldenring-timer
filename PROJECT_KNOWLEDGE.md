# Elden Ring Timer - Project Knowledge Base

This document serves as the "Source of Truth" for the Elden Ring Timer project, consolidating all game-specific logic, technical implementations, and OCR strategies.

---

## 🎮 Game Logic & Run Rules

### Nightreign Roguelike Mode Constants

Target: Level 15 Max.

- **Total Runes Required**: **513,116** Runes (Lvl 1 -> 15).
- **Night 1 Boss Revenue**: ~11,000 Runes.
- **Night 2 Boss Revenue**: ~50,000 Runes.
- **Farming Goal**: Total - Bosses = ~**452,116 Runes** to be farmed during Day phases.
- **Snowball Factor**: 1.7 (Exponential progression).

### Run Phases & Transitions

The application tracks progress through defined game phases. Transitions are triggered by specific OCR patterns ("JOUR I", "JOUR II", etc.) or the "RÉSULTAT" victory banner.

- **Day 1 (Storm)**:
  - Triggers: "JOUR I", "JOUR 1", "JOURI".
  - Effect: **Reset Level to 1**. Reset timer. Start new Session Log (`Run_N_Storm...`). Reset RPS history (40s).
- **Day 2 (Storm)**:
  - Triggers: "JOUR II", "JOUR 2", "JOURII".
- **Day 3 (Preparation & Final Boss)**:
  - Triggers: "JOUR III", "JOUR 3", "JOURIII".
- **Boss Phases**:
  - **Boss 1 & 2**: RPS calculation and graph progress are **PAUSED** to keep farm statistics accurate.
- **Victory Condition**:
  - Trigger: Detection of "RÉSULTAT" (or fuzzy matches like "RESULT") via dedicated scan region.

---

## 📈 Analytics Engine: "Ideal Curve"

We utilize a mathematical model to assess real-time performance against an ideal exponential growth curve.

### Stepped "Snowball" Model

The model now better reflects game reality by separating **Farming Progress** (Continuous) from **Boss Rewards** (Discrete Steps).

#### Base Constants

- **Farming Goal**: 452,116 Runes.
- **Total Farming Time**: 40 Minutes (2400s).
- **Boss 1 Bonus**: 11,000 Runes (at 20 mins).
- **Boss 2 Bonus**: 50,000 Runes (at 40 mins).
- **Start Delay**: 15s (Falling/Loading).

#### Formula: $Ideal(t)$

1. **Effective Time**: $t_{eff} = \max(0, t - 15)$.
2. **Base Farming (Continuous)**:
    $$ \text{Runes}_{farm} = 452,116 \times \left( \frac{t_{eff}}{2400} \right)^{1.7} $$
3. **Boss Steps (Discrete)**:
    - If $t_{eff} > 1200$ (20m): Add 11,000.
    - If $t_{eff} > 2400$ (40m): Add 50,000.

**Total Ideal**: $\text{Runes}_{farm} + \text{Bonus}$

---

## 💰 Rune & Death Analytics

### Tracking Logic

- **Total Runes Accumulés**: `Runes Dépensées (Niveaux)` + `Runes Dépensées (Marchands)` + `Runes Actuelles`.
- **Merchant Spending**: Detected when `current_runes` decreases while Level remained stable.

### 🛡️ "Triple Lock" Death Logic

To prevent false positives (e.g., OCR misreading Level 3 as 2), a death is **ONLY** validated if ALL three conditions are met simultaneously:

1. 📉 **Level Drop**: The Level decreases (e.g., 3 -> 2).
2. 💰 **Strict 0 Runes**: The Rune count reading must be **EXACTLY 0**.
    - If Runes > 0, the level drop is assumed to be an OCR glitch and is IGNORED.
3. ⚫ **Recent Black Screen**: A "Black Screen" event (Fade-out/Fade-in) must have ended within the last **12 seconds**.
    - This confirms the game actually reset the player.

### ♻️ "All or Nothing" Recovery Logic

- **Recovery Condition**: A rune gain is classified as a "Recovery" ONLY if it matches the pending bloodstain amount **EXACTLY** (with a tiny tolerance of ±5 runes for OCR jitter).
- **Strict Logic**:
  - Match -> ✅ **RECOVERED**. (`lost_runes_pending` becomes 0).
  - No Match -> 🚜 **FARMING**. (Treated as standard gain, `lost_runes_pending` persists).
- **Double Death**: If a new death occurs while `lost_runes_pending > 0`, those pending runes are moved to `permanent_loss` but remain in the "Total Accumulated" graph to reflect total lifetime wealth.

---

## 🖥️ UI Architecture: "Unified Dashboard"

The UI has been consolidated into a single "Unified Overlay" (`qt_overlay.py`) using a 3-column dashboard layout (640x420).

### Layout Specs

- **Left Column**: Timer, Phase, Level -> Potential, Missing Runes.
- **Center Column**: Analytics (RPS, Next Level Prediction, Grade S/A/B).
- **Right Column**: Stats (Merch, Deaths, Recov, OCR).
- **Bottom Graph**: Full run history with Event Markers (💀, ♻️, ⚔️) and dashed benchmarks.

---

## 👁️ OCR & Vision Strategy

### Multi-Monitor Coordinates

- **Capture Engine**: PIL `ImageGrab` with `all_screens=True` to support negative coordinate offsets.
- **High Performance**: Uses `libtesseract-5.dll` (TessAPI) directly (20ms latency).

### Global Black Screen Detection

- **Mechanism**: Monitors brightness globally to validate deaths.
- **Threshold**: Brightness < 3.

### Robustness & Consensus

- **Level Consensus**: 2 consecutive identical readings required.
- **Rune "Burst" Validation**: 5 high-speed scans on change, requiring 3/5 majority.
- **Flicker Filtering**: Transitions of ±1 rune are smoothed or ignored.

---

## 🐛 Known Bugs & Fixes (Session Learnings)

### 1. Rune Spike / Double Counting (Level Up)

**Issue**: When leveling up, the "Merchant Spending" (detected by rune drop) and the "Level Cost" (detected by Level Up) were both added to the Total Runes graph, causing a massive spike.
**Fix**: Retroactive Spending Correction in `Level Up` logic.

- When `level > old_level` is confirmed:
- Check `recent_spending_history` (last 60 seconds).
- Identify and SUM any spending events.
- **REVERT** them from `spent_at_merchants` (assume they paid for the level).
- Log: "Reverted X spending due to Level Up".

### 2. Ideal Curve Delay

**Logic**: The Ideal Curve (Snowball) now has a **15-second offset**.

- Reason: The first 15s of a run are falling/loading, yielding 0 runes.
- Calculation: `Ideal(t) = Goal * ((t - 15) / (Total - 15))^Snowball`
- UI: The dashed line on the graph starts at t=15s.

### 3. Audio Nuances

- **Startup Silence**: Day 1 Phase announcements are suppressed on initial startup to avoid spam.
- **No False Victory**: The "Victoire" announcement is suppressed when manually resetting to Day 1 via hotkey or auto-reset.

### 4. UI Adjustments

- **Recording Dot**: Removed red pulsing dot from Timer area (UI cleanup).
- **Grade**: Now S-F based on Delta from Ideal Curve (S = +10% ahead).
