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
  - **Prerequisite**: Must be in **Boss 1 Phase** (Index 4).
- **Day 3 (Preparation & Final Boss)**:
  - Triggers: "JOUR III", "JOUR 3", "JOURIII".
  - **Prerequisite**: Must be in **Boss 2 Phase** (Index 9).
  - *Boosted OCR*: Weights for "JOUR III" are heavily boosted to overcome Day 1/2 noise.
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

- **Total Runes Accumulés (UI/Graphe)**: `Runes Dépensées (Niveaux)` + `Runes Actuelles` + `lost_runes_pending`.
  - *Note*: Cette formule est dite "Puissance Effective". Elle n'inclut PAS les dépenses marchandes ni les pertes permanentes, afin d'afficher des "trous" de progression sur le graphique.
- **Total Wealth (Log Session)**: Somme brute incluant marchands et pertes.
- **Merchant Spending**: Detected when `current_runes` decreases while Level remained stable.

### 🛡️ "Stat-Based" Death Logic (Revised Jan 2026)

To deal with variable localizations and OCR reliability, we moved from text-based detection ("VOUS AVEZ PERI") to a **Strict Stat Interaction Model**:

**Death Condition**:

1. 📉 **Level Drop**: The Level decreases EXACTLY by 1 (e.g., 9 -> 8).
    - Drops > 1 are rejected as OCR errors.
2. 💰 **Runes -> Zero**: The Rune count drops to **< 50**.
    - We allow small non-zero values (e.g., 8, 42) to account for OCR noise on the dark screen background.
    - If Runes stay high (e.g., 1000+), the Level Drop is rejected as an OCR error.

*Note: Black Screen detection is still tracked but no longer mandatory for the trigger, to avoid missing deaths where the screen doesn't go fully black or timing is off.*

### ♻️ "All or Nothing" Recovery Logic

- **Recovery Condition**: A rune gain is classified as a "Recovery" ONLY if it matches the pending bloodstain amount **EXACTLY** (with a tiny tolerance of ±5 runes for OCR jitter).
- **Strict Logic**:
  - Match -> ✅ **RECOVERED**. (`lost_runes_pending` becomes 0).
  - No Match -> 🚜 **FARMING**. (Treated as standard gain, `lost_runes_pending` persists).
- **Double Death**: If a new death occurs while `lost_runes_pending > 0`, those pending runes are moved to `permanent_loss` but remain in the "Total Accumulated" graph to reflect total lifetime wealth.

---

- [x] **Phase 8: Graph Strategy (Effective Wealth)** <!-- id: 33 -->
  - [x] Implement "Effective Wealth" formula for Graph <!-- id: 34 -->
  - [x] Add `total_wealth` vs `effective_wealth` toggle logic <!-- id: 35 -->

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
