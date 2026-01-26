import matplotlib.pyplot as plt
import numpy as np

def get_ideal_runes_at_time(t_seconds, offset=30.0, farming_goal=400000, snowball=1.7):
    if t_seconds <= offset:
        return 0
    effective_t = t_seconds - offset
    
    # 1. Base Farming (Stepped Snowball)
    # Farming duration is 40 min = 2400s
    ratio = effective_t / 2400.0
    if ratio > 1.0: ratio = 1.0
    
    farming_val = farming_goal * (ratio ** snowball)
    
    # 2. Boss Steps (Guaranteed Drops)
    boss_bonus = 0
    if effective_t >= 1185: # Boss 1 around 20m 
        boss_bonus += 50000
    if effective_t >= 2385: # Boss 2 around 40m
        boss_bonus += 100000
        
    return farming_val + boss_bonus

# Level Cumulative Costs (from RuneData)
LEVEL_CUMULATIVE = {
    1: 0,
    2: 3698,
    3: 11620,
    4: 23968,
    5: 40766,
    6: 62584,
    7: 89453,
    8: 121590,
    9: 159214,
    10: 202549,
    11: 251820,
    12: 307259,
    13: 369099,
    14: 437578,
    15: 512936
}

t = np.linspace(0, 2500, 2500)
y = [get_ideal_runes_at_time(ti) for ti in t]

plt.figure(figsize=(12, 7))
plt.plot(t, y, label='Ideal Curve (Snowball 1.7)', color='gold', linewidth=2)

# Plot Level markers
for lvl, runes in LEVEL_CUMULATIVE.items():
    if lvl > 1:
        plt.axhline(y=runes, color='grey', linestyle='--', alpha=0.2)
        plt.text(2510, runes, f'Lvl {lvl}', verticalalignment='center', fontsize=8)

# Plot phase markers
plt.axvline(x=1200, color='red', linestyle=':', label='Boss 1 (20m)')
plt.axvline(x=2400, color='red', linestyle=':', label='Boss 2 (40m)')

plt.title("Elden Ring Timer - Curve Verification")
plt.xlabel("Time (seconds)")
plt.ylabel("Total Runes")
plt.legend()
plt.grid(True, which='both', linestyle='-', alpha=0.1)

# Save the plot
plt.savefig("curve_verification.png")
print("Plot saved as curve_verification.png")

# Print some key checkpoints
print(f"At 10m (600s): {get_ideal_runes_at_time(600):,.0f} runes")
print(f"At 20m (1200s): {get_ideal_runes_at_time(1200):,.0f} runes")
print(f"At 30m (1800s): {get_ideal_runes_at_time(1800):,.0f} runes")
print(f"At 40m (2400s): {get_ideal_runes_at_time(2400):,.0f} runes")
