import matplotlib.pyplot as plt
import numpy as np

# Apply style BEFORE creating the figure
plt.style.use('dark_background')

def get_ideal_runes_at_time(t):
    # Constants from StateService (Phase 3 Fix)
    NR_DAY_DURATION = 840      # 14 minutes
    NR_TOTAL_TIME = 1680       # 28 minutes
    NR_FARMING_GOAL = 337578   # Target - Boss Drops (437k - 100k)
    NR_BOSS_DROPS = 50000      # 50k per boss
    NR_SNOWBALL_D1 = 1.35
    NR_SNOWBALL_D2 = 1.15
    NR_IDEAL_TARGET = 437578   # Lvl 14
    
    # Piecewise Logic
    if t < NR_DAY_DURATION:
        # Day 1: 0 -> 14m
        ratio = t / NR_TOTAL_TIME
        val = NR_FARMING_GOAL * (ratio ** NR_SNOWBALL_D1)
        return val
    elif t < NR_TOTAL_TIME:
        # Day 2: 14m -> 28m
        # Calculate Day 1 end point (Farming only)
        val_d1_end = NR_FARMING_GOAL * ((NR_DAY_DURATION / NR_TOTAL_TIME) ** NR_SNOWBALL_D1)
        start_d2 = val_d1_end + NR_BOSS_DROPS
        
        # Growth needed in Day 2 to reach Target (437k)
        rem_farming = NR_IDEAL_TARGET - start_d2
        
        # Progress in Day 2
        t_d2 = t - NR_DAY_DURATION
        ratio_d2 = t_d2 / NR_DAY_DURATION
        val = start_d2 + rem_farming * (ratio_d2 ** NR_SNOWBALL_D2)
        return val
    else:
        # Post Day 2: Flat + Boss 2 Drop
        return NR_IDEAL_TARGET + NR_BOSS_DROPS

# Generate Data
times = np.linspace(0, 2400, 2400) # Up to 40 mins for comparison
runes = [get_ideal_runes_at_time(t) for t in times]

# Plot
plt.figure(figsize=(12, 6))
plt.plot(times / 60, runes, label='Courbe Idéale (Phase 4)', color='gold', linewidth=2)

# Markers (40% opacity, no labels in legend)
# 7.5m (End Shrink 1.1), 14.0m (End Shrink 1.2), 21.5m (End Shrink 2.1), 28.0m (End Shrink 2.2)
plt.axvline(x=7.5, color='white', linestyle='-', alpha=0.4)
plt.axvline(x=14.0, color='white', linestyle='-', alpha=0.4)
plt.axvline(x=21.5, color='white', linestyle='-', alpha=0.4)
plt.axvline(x=28.0, color='white', linestyle='-', alpha=0.4)

plt.axhline(y=437578, color='green', linestyle=':', alpha=0.5, label='Objectif Lvl 14')
plt.axhline(y=437578 + 50000, color='gold', linestyle=':', alpha=0.5, label='Final (+Boss 2)')

plt.title("Visualisation de la Courbe Idéale with Markers (40% Opacity)")
plt.xlabel("Temps (minutes)")
plt.ylabel("Runes")
plt.grid(True, alpha=0.2)
plt.legend()
# plt.style.use('dark_background') # Moved to top

# Save
# Save with explicit facecolor to avoid transparency issues
output_path = "ideal_curve_preview.png"
plt.savefig(output_path, facecolor='black')
print(f"Visualisation sauvegardée dans {output_path}")

# Display raw numbers at key points
print(f"t=0m: {get_ideal_runes_at_time(0):,.0f}")
print(f"t=14m (Before Boss 1): {get_ideal_runes_at_time(839):,.0f}")
print(f"t=14m (After Boss 1): {get_ideal_runes_at_time(841):,.0f}")
print(f"t=28m (Before Boss 2): {get_ideal_runes_at_time(1679):,.0f}")
print(f"t=28m (After Boss 2): {get_ideal_runes_at_time(1681):,.0f}")
