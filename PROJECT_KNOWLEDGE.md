# Elden Ring Timer - Project Knowledge Base

This document serves as the "Source of Truth" for the Elden Ring Timer project, consolidating all game-specific logic, technical implementations, and OCR strategies.

---

## 🎮 Game Logic & Run Rules

### Nightreign Roguelike Mode Constants

Target: Level 15 Max.

- **Total Runes Required**: **512,936** Runes (Lvl 1 -> 15).
- **Ideal Target**: Reach **Level 14** at the start of Boss 2 (approx 28 min).
- **Post-Target**: +50k runes after Boss 2, then flat (minimal farm).
- **Night 1 Boss Revenue**: ~50,000 Runes.
- **Night 2 Boss Revenue**: ~50,000 Runes.
- **Snowball Factor**: **1.35** (Day 1) -> **1.15** (Day 2). *To be moved to config.json*.

### Run Phases & Transitions

The application tracks progress through defined game phases. Transitions happen automatically or via detection:

#### Automatic Timer-Based Transitions

- **All timed phases** (Storm, Shrinking): Automatically advance to next phase when timer reaches 00:00.
- **Shrink End Markers**: Graph logs vertical barriers at the end of each "Shrinking" phase:
  - **End Shrink 1.1** (Day 1 - 7m30s)
  - **End Shrink 1.2** (Day 1 - 14m00s)
  - **End Shrink 2.1** (Day 2 - 21m30s)
  - **End Shrink 2.2** (Day 2 - 28m00s)
- Example: Day 2 - Shrinking 2 (3:00) → Boss 2 (automatic)

#### OCR-Based Transitions

- **Day 1 (Storm)**:
  - Triggers: "JOUR I", "JOUR 1", "JOURI"
  - Effect: **Reset Level to 1**. Reset timer to "00:00" / "Game Init". Start new Session Log
- **Day 2 (Storm)**:
  - Triggers: "JOUR II", "JOUR 2", "JOURII"
  - **Prerequisite**: Must be in **Boss 1 Phase** (Strict or Manual Override)

#### Black Screen Fade Detection

- **Boss 2 → Day 3 Preparation**:
  - Trigger: Black screen fade (0.3s - 3.0s duration)
  - **NOT** OCR-based (no "JOUR III" detection needed)
- **Day 3 Prep → Final Boss**:
  - Trigger: Black screen fade (0.3s - 3.0s duration)
  - Requires 10s delay after entering Day 3 Prep

#### Boss Phases

- **Boss 1 & 2**: RPS calculation and graph progress are **PAUSED**

#### Victory Condition

- Trigger: Detection of "RÉSULTAT"

---

## 📈 Analytics Engine: "Ideal Curve"

We utilize a mathematical model to assess real-time performance against an ideal exponential growth curve.

### Stepped "Snowball" Model

#### Base Constants

- **Farming Goal**: 512,936 Runes (Total).
- **Snowball Factors**:
  - Day 1: **1.35**
  - Day 2: **1.15**

#### Formula: $Ideal(t)$

1. **Effective Time**: $t_{eff} = \max(0, t - 15)$.
2. **Base Farming (Continuous)**:
    - Splits calculation based on Day 1 End time.
    - Uses 1.35 power for first segment, 1.15 for second.
3. **Boss Steps (Discrete)**:
    - Adds 50,000 at Day 1 End.
    - Adds 50,000 at Day 2 End.

---

## 💰 Rune & Death Analytics

### Tracking Logic

- **Green Curve (Real)**: Corrected total. Monotonic (Ratchet). No dips allowed except Death/Spend.
- **Orange Curve (Sensor)**: Raw OCR data. Shows glitches/dips for debugging.
- **Merchant Spending**: Detected when `current_runes` decreases while Level remained stable.

### 🛡️ "Stat-Based" Death Logic (Revised Jan 2026)

To deal with variable localizations and OCR reliability:

**Death Condition**:

1. 📉 **Level Drop**: The Level decreases EXACTLY by 1 (e.g., 9 -> 8).
    - Drops > 1 are rejected as OCR glitches.
2. 💰 **Runes -> Zero**: The Rune count drops to **< 50** (or low value).
3. **Black Screen**: **OPTIONAL**. Used for confidence but not a blocker (some deaths are instant/cutscenes).

### ♻️ "All or Nothing" Recovery Logic

- **Recovery Condition**: A rune gain is classified as a "Recovery" ONLY if it matches the pending bloodstain amount **EXACTLY**.
- **Double Death**: Pending runes are **LOST** (Deleted from total acquired & potential).
- **Reset Guard**: Manual Shortcuts FORCE state changes.
- **Loading vs Death**:
  - **Loading**: Same level, Same runes after black screen.
  - **Death**: Level - 1, Runes = 0 after black screen.

---

## 🖥️ UI Architecture: "Unified Dashboard"

The UI has been consolidated into a single "Unified Overlay" (`qt_overlay.py`) using a 3-column dashboard layout (640x420).

### Layout Specs

- **Main focus**: Timer (Chrono), Grade (Rank), and Missing Runes.
- **Level-Up Indicator (NEW)**: A "Royale Blue" circle (approx 300px diameter) around the Level OCR region.
  - 1 Circle = 1 level possible.
  - 2 Circles = 2 levels possible, etc.
- **Bottom Graph**: Dual Plot (Green=Real, Orange=Sensor).

---

## 👁️ OCR & Vision Strategy

### Multi-Monitor Coordinates

- **Capture Engine**: PIL `ImageGrab` with `all_screens=True`.

### Global Black Screen Detection

- **Mechanism**: Monitors brightness globally to validate deaths.
- **Threshold**: Brightness < 3.

### Conditional Vision (Menu Scan)

- **Rule**: Main Menu Screen ("Game Init") is checked **only if** the Rune Icon (gameplay HUD) is **NOT visible**.
- **Insight**: The Rune Icon is always visible in gameplay but hidden in menus/inventory. The Menu Icon is only in the main title screen.

### Robustness & Consensus

- **Level Consensus**: 2 consecutive identical readings required.
- **Rune "Burst" Validation**: 5 high-speed scans on change, requiring 3/5 majority.
- **Flicker Filtering**: Transitions of ±1 rune are smoothed or ignored.

### Boss HP Detection (PROPOSED)

- **Mechanism**: Use image analysis (template matching or color histograms) to monitor the Boss HP bar area.
- **Goals**:
  - Confirm Victory/Defeat based on bar depletion vs. player death.
  - Estimate Time-to-Kill (TTK) based on depletion rate.
  - Handle multi-bars (e.g., Godrick, Malenia phases).

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
- **Deep Graph Repair**: Repairs the last **60 seconds** of history (previously 10s) effectively erasing long-standing "Ghost" dips caused by glitches.

### 5. Graph Stability (The "Ratchet")

**Issue**: Random OCR noise (e.g., `7774` -> `7174`) caused temporary dips in the Total Runes graph.
**Fix**:

- **Monotonicity Rule**: The "Green Curve" (Total Runes) is **LOCKED** and cannot drop.
- **Exceptions**: Valid Death or Merchant Spend events imply a drop; these are handled explicitly.
- **Suspicious Drop Filter**: Drops involving a single-digit change are held as "Uncertain" for 15s+.

### 6. Fuzzy Logic Strategy (`difflib`)

**Issue**: Day banners often have typos (e.g., "JOOR" instead of "JOUR") due to font rendering.
**Fix**:

- **Algorithm**: python `difflib.SequenceMatcher`.
- **Threshold**: Similarity > **0.7** (70%).
- **Noise Filter**: Text length must be < 20 chars to reject long sentences.
- **Context**: If Phase is "Boss 1", we accept "JOUR" (or similar) as "Day 2" immediately.

### 7. Conditional Vision & Burst Logic

To optimize performance and accuracy:

- **Rule**: Main Menu Screen is checked **only if** the Rune Icon (gameplay HUD) is NOT visible.
- **Burst Verification**: If the menu screen is detected tentatively (1Hz), we trigger a **5-frame rapid burst** (approx 200ms duration).
- **Consensus**: We require **4 out of 5** frames to match the template before triggering a "Run Reset". This prevents false positives from UI fading or loading screens.
- **UI Feedback**: Upon confirmation, the Timer Overlay displays **"🏠 Menu"** instead of "00:00" to provide clear visual confirmation that the auto-reset system is active. This state persists until "Day 1" starts.

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
- **Hotkeys**:
  - **F4**: Full Reset (Clear Run Data & Sensors)
  - **F5**: Reset / Start Day 1.
  - **F6**: Force Day 2.
  - **F7**: Force Day 3.
  - **F8**: Boss Skip / Correction.
  - **F9**: Open OCR Tuner (Pauses Logic).
  - **F10**: Exit Application.
